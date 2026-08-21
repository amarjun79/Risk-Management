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

ROOT = Path(__file__).parent
POLICY_PDF = ROOT / "docs" / "Risk_Policy.pdf"
POLICY_STORE = ROOT / "App_Data" / "policy-vectors.json"
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


class PolicySearch:
    """Persisted local policy index; its interface can be replaced by a ChromaDB adapter."""

    def __init__(self) -> None:
        if not POLICY_PDF.exists():
            raise FileNotFoundError(f"Risk policy PDF is required: {POLICY_PDF}")
        POLICY_PDF.read_bytes()  # Validate the supplied policy source at startup.
        POLICY_STORE.parent.mkdir(exist_ok=True)
        if POLICY_STORE.exists():
            stored_chunks = json.loads(POLICY_STORE.read_text(encoding="utf-8"))
            # Accept the original .NET demo's PascalCase serialization as well.
            self.chunks = [{"section": item.get("section", item.get("Section")), "text": item.get("text", item.get("Text"))} for item in stored_chunks]
            POLICY_STORE.write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")
        else:
            self.chunks = [
                {"section": "4.2 — Impossible Travel Velocity", "text": "Decline or step up authentication when activity appears in geographically distant locations within a timeframe inconsistent with normal travel."},
                {"section": "5.3 — Anonymizing Proxies", "text": "Transactions originating from verified anonymizing proxies or Tor exit nodes require elevated fraud review and may be declined."},
                {"section": "3.1 — Card-not-present Risk", "text": "Card-not-present purchases receive additional risk assessment when location, device, or spending behavior differs from the customer profile."},
                {"section": "2.4 — Amount Anomaly", "text": "A transaction materially above the customer's established average amount is a fraud-risk indicator."},
                {"section": "6.1 — Customer Resolution", "text": "When a transaction is declined by automated controls, ask the customer to verify identity and contact the bank to authorize future activity."},
            ]
            POLICY_STORE.write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")

    def search(self, query, take=3):
        terms = set(re.findall(r"[a-z]+", query.lower()))
        scored = [{**chunk, "relevance": sum(word in terms for word in re.findall(r"[a-z]+", f"{chunk['section']} {chunk['text']}".lower()))} for chunk in self.chunks]
        return sorted(scored, key=lambda item: (-item["relevance"], item["section"]))[:take]


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


repository = TransactionRepository()
policy_search = PolicySearch()
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


def policies_for_signals(signals):
    signal_policy_queries = {
        "Impossible travel": "impossible travel velocity",
        "Anonymizing proxy": "anonymizing proxies",
        "Card-not-present": "card-not-present risk",
        "Unusual amount": "amount anomaly",
        "Unusual spending pattern": "amount anomaly",
    }
    selected = []
    seen_sections = set()
    for signal in signals:
        query = signal_policy_queries.get(signal["name"])
        if not query:
            continue
        for policy in policy_search.search(query, take=1):
            if policy["section"] not in seen_sections:
                selected.append(policy)
                seen_sections.add(policy["section"])
    return selected


def risk_level(score):
    return "High" if score >= 70 else "Medium" if score >= 35 else "Low"


def assess_transaction_risk(transaction):
    profile = repository.get_customer_profile(transaction["user_id"])
    previous = repository.get_previous_transactions(transaction["user_id"], transaction["timestamp"])
    signals = calculate_risk_signals(transaction, profile, previous)
    score = min(100, sum(signal["score"] for signal in signals))
    return profile, previous, signals, score, risk_level(score)


def is_risk_list_request(message):
    text = message.lower()
    wants_list = any(term in text for term in ("list", "show", "all", "display"))
    transaction_topic = any(term in text for term in ("transaction", "transactions", "failed", "fail", "declined", "decline", "flagged", "risk"))
    return wants_list and transaction_topic


def extract_requested_risk_bucket(message):
    text = message.lower()
    if "high" in text:
        return "High"
    if "moderate" in text or "medium" in text:
        return "Medium"
    if "low" in text:
        return "Low"
    return None


def prompt_risk_level_selection():
    return {
        "mode": "riskFilterPrompt",
        "title": "Choose a risk band",
        "message": "Select a category to list matching transactions. I will sort the results by descending risk score.",
        "options": [
            {"label": "High", "query": "List high risk transactions"},
            {"label": "Moderate", "query": "List moderate risk transactions"},
            {"label": "Low", "query": "List low risk transactions"},
        ],
    }


def list_risk_transactions(level_filter):
    results = []
    for transaction in repository.get_all_transactions():
        _, _, signals, score, transaction_level = assess_transaction_risk(transaction)
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
    label = "Moderate" if level_filter == "Medium" else level_filter
    return {
        "mode": "riskList",
        "title": f"{label}-risk transactions",
        "message": f"I found {len(results)} transaction{'s' if len(results) != 1 else ''} in the {label.lower()}-risk category. Select one to open its full investigation.",
        "transactions": results,
    }


def investigation(message: str):
    transaction_id = extract_transaction_id(message)
    if transaction_id is None and is_risk_list_request(message):
        level_filter = extract_requested_risk_bucket(message)
        return list_risk_transactions(level_filter) if level_filter else prompt_risk_level_selection()
    if not transaction_id:
        return {"error": "Please include a transaction ID, such as TXN_99812. You can also ask about a known transaction in the sample data."}
    transaction = repository.get_transaction_by_id(transaction_id)
    if not transaction:
        return {"error": f"I couldn’t find {transaction_id}. Try TXN_99812 to explore the sample investigation."}
    profile, previous, signals, score, level = assess_transaction_risk(transaction)
    policies = policies_for_signals(signals)
    transaction = {**transaction, "timestamp": transaction["timestamp"].isoformat()}
    return {"transactionId": transaction_id, "transaction": transaction, "customerName": profile["full_name"], "avgTransactionAmount": profile["avg_transaction_amount"], "riskScore": score, "riskLevel": level, "signals": signals, "policies": policies, "summary": f"Automated controls identified {len(signals)} risk signal{'s' if len(signals) != 1 else ''} associated with this purchase." if signals else "No elevated risk signals were identified from the available transaction evidence.", "recommendation": "For your security, please verify your identity with the bank before retrying the purchase. An agent can also authorize future activity." if score >= 70 else "You may retry the purchase or contact the bank if the decline continues.", "llmExplanation": None}


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
    policies = policy_search.search(" ".join(signal["name"] for signal in signals) or "transaction review")
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
        return jsonify({"error": "A card can be frozen from this workflow only for medium or high-risk transactions."}), 400
    repository.freeze_card(profile["user_id"])
    return jsonify({"message": f"The card for {profile['full_name']} was frozen because {transaction['transaction_id']} is {level.lower()} risk. A notification has also been sent to the user.", "riskScore": score})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
