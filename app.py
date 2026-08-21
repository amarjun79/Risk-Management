"""RiskLens transaction decline chatbot — a self-contained Flask demo."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from openai import OpenAI

from policy_engine import PolicyVectorStore

ROOT = Path(__file__).parent
POLICY_PDF = ROOT / "docs" / "Risk_Policy.pdf"
POLICY_STORE = ROOT / "App_Data" / "policy-vectors.json"
POLICY_CHROMA_DIR = ROOT / "App_Data" / "chroma_db"
DATABASE_PATH = ROOT / "App_Data" / "transaction_analytics.db"
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://genailab.tcs.in")
LLM_MODEL = os.getenv("LLM_MODEL", "genailab-maas-sonnet-4.6")

app = Flask(__name__)


class TransactionRepository:
    """Repository backed by a local SQLite analytical database."""

    def __init__(self) -> None:
        DATABASE_PATH.parent.mkdir(exist_ok=True)
        with self._connect() as connection:
            if not DATABASE_PATH.exists() or not self._has_schema(connection):
                connection.executescript((ROOT / "data" / "schema.sql").read_text(encoding="utf-8"))
            self._migrate(connection)
            transaction_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            if transaction_count == 0:
                connection.executescript((ROOT / "data" / "demo_data.sql").read_text(encoding="utf-8"))

    @staticmethod
    def _connect():
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _has_schema(connection):
        return connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'transactions'").fetchone() is not None

    @staticmethod
    def _migrate(connection):
        columns = {row[1] for row in connection.execute("PRAGMA table_info(transactions)")}
        additions = {"risk_score": "INTEGER NOT NULL DEFAULT 0", "risk_level": "TEXT NOT NULL DEFAULT 'Low'", "policy_flagged": "INTEGER NOT NULL DEFAULT 0", "escalated": "INTEGER NOT NULL DEFAULT 0"}
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE transactions ADD COLUMN {name} {definition}")
        customer_columns = {row[1] for row in connection.execute("PRAGMA table_info(customer_profiles)")}
        if "card_frozen" not in customer_columns:
            connection.execute("ALTER TABLE customer_profiles ADD COLUMN card_frozen INTEGER NOT NULL DEFAULT 0")
        # Normalize legacy transaction IDs to the one canonical format: TXN_12345.
        connection.execute("""UPDATE transactions SET transaction_id = 'TXN_' || SUBSTR(transaction_id, 5)
            WHERE UPPER(transaction_id) LIKE 'TXN-%'""")

    @staticmethod
    def _to_transaction(row):
        if row is None:
            return None
        transaction = dict(row)
        transaction["timestamp"] = datetime.fromisoformat(transaction["timestamp"])
        transaction["card_present"] = bool(transaction["card_present"])
        transaction["ip_is_proxy"] = bool(transaction["ip_is_proxy"])
        return transaction

    def get_transaction_by_id(self, transaction_id):
        transaction_id = normalize_transaction_id(transaction_id)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
        return self._to_transaction(row)

    def get_customer_profile(self, user_id):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM customer_profiles WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_previous_transactions(self, user_id, before):
        with self._connect() as connection:
            rows = connection.execute("""SELECT * FROM transactions
                WHERE user_id = ? AND timestamp < ? ORDER BY timestamp DESC LIMIT 10""", (user_id, before.isoformat())).fetchall()
        return [self._to_transaction(row) for row in rows]

    def get_users_with_transactions(self):
        with self._connect() as connection:
            users = connection.execute("SELECT * FROM customer_profiles ORDER BY full_name").fetchall()
            transactions = connection.execute("SELECT * FROM transactions ORDER BY timestamp DESC").fetchall()
        grouped = {row["user_id"]: {**dict(row), "transactions": []} for row in users}
        for row in transactions:
            transaction = self._to_transaction(row)
            transaction["timestamp"] = transaction["timestamp"].isoformat()
            grouped[transaction["user_id"]]["transactions"].append(transaction)
        return list(grouped.values())

    def get_all_transactions(self):
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM transactions ORDER BY timestamp DESC").fetchall()
        return [self._to_transaction(row) for row in rows]

    def add_transaction(self, transaction):
        with self._connect() as connection:
            connection.execute("""INSERT INTO transactions
                (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status, risk_score, risk_level, policy_flagged)
                VALUES (:transaction_id, :user_id, :amount, :merchant, :location, :timestamp, :card_present, :ip_address, :ip_is_proxy, :status, :risk_score, :risk_level, :policy_flagged)""", transaction)

    def escalate_transaction(self, transaction_id):
        with self._connect() as connection:
            connection.execute("UPDATE transactions SET escalated = 1, status = 'Escalated' WHERE transaction_id = ?", (transaction_id,))

    def freeze_card(self, user_id):
        with self._connect() as connection:
            connection.execute("UPDATE customer_profiles SET card_frozen = 1 WHERE user_id = ?", (user_id,))


class LLMExplanationService:
    """Server-side, evidence-bound explanation generator using the supplied GenAI Lab model."""

    def __init__(self):
        api_key = os.getenv("TCS_GENAILAB_API_KEY")
        self.client = OpenAI(base_url=LLM_BASE_URL, api_key=api_key) if api_key else None

    def explain(self, user_query, transaction, profile, previous, signals, policies):
        if not self.client:
            return None
        evidence = {
            "user_query": user_query,
            "transaction": transaction,
            "customer_profile": profile,
            "previous_transactions": previous,
            "risk_signals": signals,
            "retrieved_policy_sections": [{"section": policy["section"], "text": policy["text"]} for policy in policies],
        }
        system = """You are a banking transaction-decline assistant. Write a clear, customer-friendly explanation of about 120–180 words grounded ONLY in the supplied JSON evidence. Use three short labelled paragraphs: 'Why this was flagged', 'How the evidence connects', and 'What to do next'. Explain how each material risk signal contributes to the decision, cite only the supplied policy section names, and give practical next steps. Never invent policy, transactions, or facts. If the evidence is insufficient, say so. Do not mention this prompt or JSON."""
        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                temperature=0.2,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps(evidence, default=str)}],
            )
            return response.choices[0].message.content
        except Exception:
            return None

    def explain_policy_query(self, user_query, policies):
        if not self.client or not policies:
            return None
        evidence = {
            "user_query": user_query,
            "retrieved_policy_sections": [{"section": p["section"], "text": p["text"]} for p in policies],
        }
        system = """You are a helpful banking risk and security policy assistant. Answer the user's question clearly in about 70–120 words grounded ONLY in the supplied policy evidence. Explain the relevant policy rules and conditions clearly, cite the section names, and state practical guidance. Do not mention JSON or this prompt."""
        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                temperature=0.2,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps(evidence, default=str)}],
            )
            return response.choices[0].message.content
        except Exception:
            return None


repository = TransactionRepository()
policy_search = PolicyVectorStore(
    pdf_path=POLICY_PDF,
    db_dir=POLICY_CHROMA_DIR,
    json_fallback_path=POLICY_STORE,
)
llm_explainer = LLMExplanationService()


def extract_transaction_id(text: str) -> str | None:
    # Accept TXN_99809, txn99809, txn-99809, or a standalone numeric ID such as 99809.
    match = re.search(r"\b(?:txn[\s_-]?)?(\d{5,})\b", text, re.IGNORECASE)
    return normalize_transaction_id(match.group(1)) if match else None


def normalize_transaction_id(transaction_id: str) -> str:
    """Returns the canonical ID format, for example TXN-99809 becomes TXN_99809."""
    value = str(transaction_id).strip().upper()
    if value.startswith("TXN-"):
        return "TXN_" + value[4:]
    if value.startswith("TXN_"):
        return value
    return f"TXN_{value}" if value.isdigit() else value


def calculate_risk_signals(transaction, profile, previous):
    signals = []
    other_city = next((item for item in previous if item["location"] != transaction["location"] and (transaction["timestamp"] - item["timestamp"]).total_seconds() < 3 * 3600), None)
    if other_city:
        minutes = int((transaction["timestamp"] - other_city["timestamp"]).total_seconds() / 60)
        signals.append({"name": "Impossible travel", "score": 30, "evidence": f"{transaction['location']} activity occurred {minutes} minutes after {other_city['location']}."})
    if transaction["ip_is_proxy"]:
        signals.append({"name": "Anonymizing proxy", "score": 25, "evidence": "The transaction IP is flagged as an anonymizing proxy."})
    if not transaction["card_present"]:
        signals.append({"name": "Card-not-present", "score": 12, "evidence": "The purchase was made without the physical card present."})
    if transaction["amount"] > profile["avg_transaction_amount"] * 3:
        signals.append({"name": "Unusual amount", "score": 20, "evidence": f"${transaction['amount']:,.0f} is over three times the typical ${profile['avg_transaction_amount']:,.0f} transaction."})
    recent_spend = sum(item["amount"] for item in previous if item["timestamp"] > transaction["timestamp"] - timedelta(days=1)) + transaction["amount"]
    if recent_spend > profile["avg_monthly_spend"] * 0.5:
        signals.append({"name": "Unusual spending pattern", "score": 15, "evidence": "Recent spend is materially higher than the normal profile."})
    return signals


def retrieve_policies_for_investigation(user_query: str, transaction: dict, signals: list[dict]) -> list[dict]:
    """Rely completely on ChromaDB vector store to semantically retrieve relevant policy chunks for triggered signals."""
    if not signals:
        return []

    retrieved_map = {}
    for signal in signals:
        query_text = f"{signal['name']}: {signal['evidence']}"
        for p in policy_search.search(query_text, take=1):
            if p["section"] not in retrieved_map or p.get("score", 0) > retrieved_map[p["section"]].get("score", 0):
                retrieved_map[p["section"]] = p

    # Sort retrieved policy chunks by ChromaDB similarity score
    sorted_policies = sorted(retrieved_map.values(), key=lambda x: x.get("score", 0), reverse=True)
    return sorted_policies


def risk_level(score):
    return "High" if score >= 70 else "Moderate" if score >= 35 else "Low"


def assess_transaction_risk(transaction):
    profile = repository.get_customer_profile(transaction["user_id"])
    previous = repository.get_previous_transactions(transaction["user_id"], transaction["timestamp"])
    
    # Calculate usual spending pattern dynamically from user profile and prior legitimate transactions
    if previous and profile:
        legit_txns = [t for t in previous if t.get("status") == "Successful"]
        if legit_txns:
            dynamic_avg = sum(t["amount"] for t in legit_txns) / len(legit_txns)
            profile = {**profile, "avg_transaction_amount": round(dynamic_avg, 2)}

    signals = calculate_risk_signals(transaction, profile, previous)
    score = min(100, sum(signal["score"] for signal in signals))
    return profile, previous, signals, score, risk_level(score)


def is_risk_list_request(message):
    text = message.lower().strip()
    intents = (
        "transaction", "transactions", "failed", "declined", "flagged",
        "list", "show", "view", "display", "category", "categories",
        "risk", "what failed", "what was declined"
    )
    return any(term in text for term in intents)


def extract_requested_risk_bucket(message):
    text = message.lower()
    if "high" in text:
        return "High"
    if "moderate" in text or "medium" in text:
        return "Moderate"
    if "low" in text:
        return "Low"
    return None


def prompt_risk_level_selection():
    return {
        "mode": "riskFilterPrompt",
        "title": "Select a Risk Category",
        "message": "Please select a risk category to view the matching failed transactions:",
        "options": [
            {"label": "High Risk (Score 80–100)", "query": "List high risk transactions", "badge": "high"},
            {"label": "Moderate Risk (Score 40–79)", "query": "List moderate risk transactions", "badge": "moderate"},
            {"label": "Low Risk (Score 0–39)", "query": "List low risk transactions", "badge": "low"},
        ],
    }


def list_risk_transactions(level_filter):
    results = []
    for transaction in repository.get_all_transactions():
        # Only display Failed transactions in the UI, avoiding the initial successful baseline history
        if transaction.get("status") != "Failed":
            continue
        profile, previous, signals, score, transaction_level = assess_transaction_risk(transaction)
        if transaction_level == level_filter:
            results.append(
                {
                    "transactionId": transaction["transaction_id"],
                    "merchant": transaction["merchant"],
                    "amount": transaction["amount"],
                    "location": transaction["location"],
                    "timestamp": transaction["timestamp"].isoformat(),
                    "riskScore": score,
                    "riskLevel": transaction_level,
                    "reason": signals[0]["evidence"] if signals else "Risk score meets the review threshold.",
                }
            )
    results.sort(key=lambda item: (-item["riskScore"], item["timestamp"]), reverse=False)
    label = "Moderate" if level_filter == "Moderate" else level_filter
    return {
        "mode": "riskList",
        "title": f"{label}-risk failed transactions",
        "message": f"I found {len(results)} failed transaction{'s' if len(results) != 1 else ''} in the {label.lower()}-risk category. Select one to open its full investigation.",
        "transactions": results,
    }


def investigation(message: str):
    message = str(message or "").strip()
    if not message:
        return {"error": "Please enter a question or a transaction ID to investigate."}

    transaction_id = extract_transaction_id(message)
    if transaction_id is None and is_risk_list_request(message):
        level_filter = extract_requested_risk_bucket(message)
        return list_risk_transactions(level_filter) if level_filter else prompt_risk_level_selection()

    if transaction_id:
        transaction = repository.get_transaction_by_id(transaction_id)
        if not transaction:
            suggested = policy_search.search(message, take=2)
            return {
                "error": f"I couldn’t find transaction {transaction_id} in the database. Please verify the ID or try sample TXN_20106.",
                "suggestedPolicies": suggested,
            }

        profile, previous, signals, score, level = assess_transaction_risk(transaction)

        # Handle direct action commands (e.g., "Freeze card TXN_20106", "Escalate TXN_20208")
        msg_lower = message.lower()
        if "freeze" in msg_lower:
            if level == "Low":
                return {"mode": "bubble", "message": "A card can be frozen only for moderate or high-risk transactions."}
            repository.freeze_card(profile["user_id"])
            return {"mode": "bubble", "message": f"The card for {profile['full_name']} was frozen because {transaction['transaction_id']} is {level.lower()} risk. A notification has also been sent to the user."}
        
        if "escalat" in msg_lower:
            if level != "Low":
                return {"mode": "bubble", "message": "Only low-risk transactions can be manually escalated. This transaction is already under elevated risk handling."}
            repository.escalate_transaction(transaction["transaction_id"])
            return {"mode": "bubble", "message": f"{transaction['transaction_id']} was escalated for manual analyst review."}
        
        # Pure semantic vector retrieval via ChromaDB
        policies = retrieve_policies_for_investigation(message, transaction, signals)
        
        llm_explanation = llm_explainer.explain(message, transaction, profile, previous, signals, policies)
        transaction_formatted = {**transaction, "timestamp": transaction["timestamp"].isoformat()}
        return {
            "transactionId": transaction_id,
            "transaction": transaction_formatted,
            "customerName": profile["full_name"],
            "avgTransactionAmount": profile["avg_transaction_amount"],
            "riskScore": score,
            "riskLevel": level,
            "signals": signals,
            "policies": policies,
            "summary": f"Automated controls identified {len(signals)} risk signal{'s' if len(signals) != 1 else ''} associated with this purchase." if signals else "No elevated risk signals were identified from the available transaction evidence.",
            "recommendation": "For your security, please verify your identity with the bank before retrying the purchase. An agent can also authorize future activity." if score >= 70 else "You may retry the purchase or contact the bank if the decline continues.",
            "llmExplanation": llm_explanation,
        }

    # For general queries without a transaction ID, perform direct semantic search on ChromaDB
    policies = policy_search.search(message, take=3)
    if not policies:
        return {"error": "Please enter a transaction ID (such as TXN_99812) or ask a question about bank risk policies."}

    llm_answer = llm_explainer.explain_policy_query(message, policies)
    summary_text = llm_answer if llm_answer else "Here are the most relevant policy rules retrieved from our Risk Management Policy via ChromaDB semantic vector search:"
    
    return {
        "mode": "policyQA",
        "title": "Risk Policy Search",
        "query": message,
        "summary": summary_text,
        "policies": policies,
        "llmExplanation": llm_answer,
        "recommendation": "To investigate a specific transaction, provide the Transaction ID (e.g. TXN_99812).",
    }


def assess_new_transaction(payload):
    required = ("transaction_id", "user_id", "amount", "merchant", "location", "timestamp", "ip_address")
    if any(not str(payload.get(field, "")).strip() for field in required):
        return None, {"error": "Complete all required transaction details."}
    transaction_id = normalize_transaction_id(payload["transaction_id"])
    if repository.get_transaction_by_id(transaction_id):
        return None, {"error": "That transaction ID already exists."}
    profile = repository.get_customer_profile(payload["user_id"])
    if not profile:
        return None, {"error": "Select a valid customer."}
    try:
        timestamp = datetime.fromisoformat(payload["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        transaction = {"transaction_id": transaction_id, "user_id": payload["user_id"], "amount": float(payload["amount"]), "merchant": str(payload["merchant"]).strip(), "location": str(payload["location"]).strip(), "timestamp": timestamp, "card_present": bool(payload.get("card_present")), "ip_address": str(payload["ip_address"]).strip(), "ip_is_proxy": bool(payload.get("ip_is_proxy")), "status": "Pending review"}
        if transaction["amount"] <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, {"error": "Enter a positive amount and a valid timestamp."}
    previous = repository.get_previous_transactions(transaction["user_id"], timestamp)
    signals = calculate_risk_signals(transaction, profile, previous)
    score = min(100, sum(signal["score"] for signal in signals))
    level = risk_level(score)
    flagged = score >= 35
    transaction.update({"timestamp": timestamp.isoformat(), "risk_score": score, "risk_level": level, "policy_flagged": int(flagged), "status": "Flagged" if flagged else "Approved"})
    policies = policy_search.search(" ".join(signal["name"] for signal in signals)) if signals else []
    return transaction, {"flagged": flagged, "riskScore": score, "riskLevel": level, "signals": signals, "policies": policies, "message": "Transaction was flagged for policy review before it was added." if flagged else "Transaction passed the configured policy checks and was added."}


@app.get("/")
def index():
    return render_template("index.html", admin=False)


@app.get("/admin")
def admin():
    """Direct-access transaction ledger; it is intentionally not linked from the public UI."""
    return render_template("admin.html")


@app.post("/api/investigate")
def investigate_api():
    payload = request.get_json(silent=True) or {}
    return jsonify(investigation(str(payload.get("message", ""))))


@app.get("/api/transactions")
def transactions_api():
    return jsonify(repository.get_users_with_transactions())


@app.post("/api/transactions")
def add_transaction_api():
    transaction, assessment = assess_new_transaction(request.get_json(silent=True) or {})
    if transaction is None:
        return jsonify(assessment), 400
    repository.add_transaction(transaction)
    return jsonify(assessment), 201


@app.post("/api/transactions/<transaction_id>/escalate")
def escalate_transaction_api(transaction_id):
    transaction = repository.get_transaction_by_id(transaction_id)
    if not transaction:
        return jsonify({"error": "Transaction not found."}), 404
    _, _, _, score, level = assess_transaction_risk(transaction)
    if level != "Low":
        return jsonify({"error": "Only low-risk transactions can be manually escalated. This transaction is already under elevated risk handling."}), 400
    repository.escalate_transaction(transaction["transaction_id"])
    return jsonify({"message": f"{transaction['transaction_id']} was escalated for manual analyst review.", "riskScore": score})


@app.post("/api/transactions/<transaction_id>/freeze-card")
def freeze_card_api(transaction_id):
    transaction = repository.get_transaction_by_id(transaction_id)
    if not transaction:
        return jsonify({"error": "Transaction not found."}), 404
    profile, _, _, score, level = assess_transaction_risk(transaction)
    if level == "Low":
        return jsonify({"error": "A card can be frozen from this workflow only for moderate or high-risk transactions."}), 400
    repository.freeze_card(profile["user_id"])
    return jsonify({"message": f"The card for {profile['full_name']} was frozen because {transaction['transaction_id']} is {level.lower()} risk. A notification has also been sent to the user.", "riskScore": score})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
