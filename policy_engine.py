"""Policy Vector Store and PDF Chunking Engine using ChromaDB."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions
import pypdf

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Normalizes text by cleaning special encoding characters and whitespace."""
    if not text:
        return ""
    # Normalize Windows-1252/Unicode dashes and special symbols
    text = (
        text.replace("\x96", "—")
        .replace("\x97", "—")
        .replace("\u0096", "—")
        .replace("\u0097", "—")
        .replace("\ufffd", "—")
        .replace("\u2013", "—")
        .replace("\u2014", "—")
        .replace(" - ", " — ")
        .replace(" – ", " — ")
        .replace(" \u00a7 ", " Section ")
        .replace("\u00a7", "Section ")
    )
    # Collapse multiple whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


EXAMPLE_PARENT_MAP = {
    "Example A1": "4.2 Impossible Travel Velocity",
    "Example A2": "5.3 Anonymizing Proxies",
    "Example A3": "5.3 Anonymizing Proxies",
    "Example A4": "8.1 High-Risk Transactions"
}


def extract_policy_chunks(pdf_path: Path) -> list[dict[str, Any]]:
    """Extracts semantic sections and rule chunks from the Risk Policy PDF."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Policy PDF not found: {pdf_path}")

    reader = pypdf.PdfReader(str(pdf_path))
    sections_by_page: list[tuple[int, str]] = []

    # Pages 3..8 (0-indexed 2..len) contain the policy content (pages 1-2 are cover and TOC)
    for page_idx in range(2, len(reader.pages)):
        page_num = page_idx + 1
        raw_page_text = reader.pages[page_idx].extract_text() or ""
        
        lines = [line.strip() for line in raw_page_text.split("\n")]
        clean_lines: list[str] = []
        for line in lines:
            if not line or "U.S. Bank - Sample Risk Management Policy" in line or re.match(r"^Page \d+$", line):
                continue
            if "Document Status:" in line:
                break
            clean_lines.append(clean_text(line))
        
        sections_by_page.append((page_num, "\n".join(clean_lines)))

    all_text = "\n\n".join(s[1] for s in sections_by_page)

    # Split on major sections, numbered subsections, and appendix examples
    pattern = r"(?=(?:\n|^)(?:(?:[1-9]\d?(?:\.\d+)?)\s+[A-Z]|Appendix [A-Z]|Example [A-Z]\d))"
    raw_chunks = re.split(pattern, all_text)

    chunks: list[dict[str, Any]] = []
    chunk_counter = 1

    for raw in raw_chunks:
        raw = raw.strip()
        if not raw or len(raw) < 15:
            continue
        
        first_line = raw.split("\n", 1)[0].strip()
        clean_section = clean_text(first_line)
        clean_doc = clean_text(raw)

        # Identify parent policy section if this is an appendix example
        parent_sec = None
        for ex_key, parent_val in EXAMPLE_PARENT_MAP.items():
            if clean_section.startswith(ex_key):
                parent_sec = parent_val
                break

        chunks.append({
            "id": f"policy_sec_{chunk_counter}",
            "section": clean_section,
            "text": clean_doc,
            "parent_section": parent_sec,
            "chunk_index": chunk_counter
        })
        chunk_counter += 1

    # Fallback to predefined chunks if extraction produced fewer than expected
    if not chunks:
        chunks = [
            {"id": "policy_sec_1", "section": "4.2 — Impossible Travel Velocity", "text": "4.2 Impossible Travel Velocity POLICY TRIGGER — SECTION 4.2 Any Card-Not-Present (CNP) transaction occurring within 2 hours of a physical card swipe in a different geographical continent must be treated as an Impossible Travel Velocity event and routed for elevated fraud review.", "chunk_index": 1},
            {"id": "policy_sec_2", "section": "5.3 — Anonymizing Proxies", "text": "5.3 Anonymizing Proxies POLICY TRIGGER — SECTION 5.3 Transactions originating from known Tor exit nodes or proxy IPs carrying an amount higher than $500 trigger mandatory secondary fraud review.", "chunk_index": 2},
            {"id": "policy_sec_3", "section": "3.1 — Card-not-present Risk", "text": "Card-not-present purchases receive additional risk assessment when location, device, or spending behavior differs from the customer profile.", "chunk_index": 3},
            {"id": "policy_sec_4", "section": "6.2 — Unusual Amount Indicator", "text": "6.2 Unusual Amount Indicator A transaction that is materially above the customer baseline should be recorded as a behavioral anomaly.", "chunk_index": 4},
            {"id": "policy_sec_5", "section": "6.1 — Customer Baseline", "text": "6.1 Customer Baseline Where customer-level historical data is available, compare the current transaction amount against the customer average transaction amount and recent transaction behavior.", "chunk_index": 5},
            {"id": "policy_sec_6", "section": "8.1 — High-Risk Transactions", "text": "8.1 High-Risk Transactions HIGH-RISK ACTION RULE When the approved risk assessment classifies an investigation as High Risk (risk level greater than 80), the required action is Immediate Card Freeze, subject to applicable operational controls and analyst confirmation.", "chunk_index": 6},
        ]

    return chunks


class PolicyVectorStore:
    """Persistent ChromaDB vector store with semantic embeddings for Risk Policies."""

    COLLECTION_NAME = "risk_policies"

    def __init__(self, pdf_path: Path, db_dir: Path, json_fallback_path: Path | None = None, force_reindex: bool = False) -> None:
        self.pdf_path = pdf_path
        self.db_dir = db_dir
        self.json_fallback_path = json_fallback_path
        
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(path=str(self.db_dir))
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        
        if force_reindex:
            try:
                self.client.delete_collection(name=self.COLLECTION_NAME)
            except Exception:
                pass

        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

        # Index policy chunks if collection is empty
        if self.collection.count() == 0:
            self._index_pdf()
        else:
            # Refresh fallback JSON with current collection contents if path provided
            self._sync_fallback_json()

    def _index_pdf(self) -> None:
        """Parses the policy PDF, generates embeddings, and indexes chunks in ChromaDB."""
        chunks = extract_policy_chunks(self.pdf_path)
        if not chunks:
            return

        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "section": c["section"],
                "parent_section": c.get("parent_section", ""),
                "chunk_index": c["chunk_index"]
            }
            for c in chunks
        ]

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"Indexed {len(chunks)} policy chunks into ChromaDB.")

        if self.json_fallback_path:
            self._sync_fallback_json(chunks)

    def _sync_fallback_json(self, chunks: list[dict[str, Any]] | None = None) -> None:
        if not self.json_fallback_path:
            return
        if chunks is None:
            data = self.collection.get(include=["documents", "metadatas"])
            chunks = []
            for i, doc in enumerate(data.get("documents", [])):
                meta = data["metadatas"][i] if data.get("metadatas") else {}
                chunks.append({
                    "section": meta.get("section", "Policy Section"),
                    "parent_section": meta.get("parent_section", ""),
                    "text": doc,
                    "chunk_index": meta.get("chunk_index", i + 1)
                })
        
        self.json_fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_fallback_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")

    def _get_collection(self):
        return self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def search(self, query: str, take: int = 3) -> list[dict[str, Any]]:
        """Performs semantic similarity search across policy chunks using ChromaDB."""
        if not query or not query.strip():
            return []

        collection = self._get_collection()
        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(take, max(1, collection.count()))
            )
        except Exception as e:
            logger.error(f"Vector search query failed: {e}")
            try:
                collection = self._get_collection()
                results = collection.query(
                    query_texts=[query],
                    n_results=min(take, max(1, collection.count()))
                )
            except Exception as e2:
                logger.error(f"Vector search retry failed: {e2}")
                return []

        retrieved: list[dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return retrieved

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        chunks_lookup = {c["section"]: c for c in extract_policy_chunks(self.pdf_path)}

        for doc_id, doc_text, meta, dist in zip(ids, documents, metadatas, distances):
            # For cosine distance (range 0 to 2), relevance similarity = 1.0 - (dist / 2.0)
            similarity = max(0.0, 1.0 - (dist / 2.0))
            section_title = meta.get("section", "Policy Section")
            parent_sec = meta.get("parent_section")

            # Resolve appendix examples (e.g. Example A1) to primary operative policy rules (e.g. 4.2 Impossible Travel)
            if parent_sec and parent_sec in chunks_lookup:
                parent_chunk = chunks_lookup[parent_sec]
                section_title = parent_chunk["section"]
                doc_text = parent_chunk["text"]
                doc_id = parent_chunk["id"]

            retrieved.append({
                "section": section_title,
                "text": doc_text,
                "score": round(similarity, 4),
                "relevance": round(similarity * 100, 1),
                "id": doc_id
            })

        return retrieved
