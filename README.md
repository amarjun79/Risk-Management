# RiskLens — AI Transaction Decline Investigation Chatbot

RiskLens is an intelligent, evidence-grounded banking chatbot designed to investigate, explain, and take action on declined card transactions. It combines deterministic fraud scoring, pure semantic vector retrieval via ChromaDB, dynamic customer baseline calculation, and LLM-assisted investigation summaries within a single-screen responsive interface.

---

## Key Features

- **Pure ChromaDB Semantic Retrieval**:
  - Automatically parses and indexes the risk policy PDF (`docs/Risk_Policy.pdf`) into dense vector embeddings (`all-MiniLM-L6-v2`) in `App_Data/chroma_db`.
  - Operates purely on dense vector similarity, resolving specific test scenarios to authoritative policy sections (e.g. *Section 4.2 Impossible Travel Velocity*, *Section 5.3 Anonymizing Proxies*, *Section 6.2 Unusual Amount Indicator*).
  - Handles general policy questions when no specific transaction ID is provided.

- **Dynamic Customer Baseline & Fraud Engine**:
  - Computes fraud signals across geographic impossible travel velocity, anonymizing Tor/proxy IPs, Card-Not-Present (CNP) channels, spend spike ratios against baseline average amounts, and 24-hour spend spikes.
  - Automatically classifies risk scores into three distinct bands:
    - 🔴 **High Risk** (`Score 80–100`)
    - 🟡 **Moderate Risk** (`Score 40–79`)
    - 🟢 **Low Risk** (`Score 0–39`)
  - **4-Transaction Baseline History**: The first 4 transactions for each customer are legitimate successful baselines used exclusively for calculating usual spending patterns, average transaction amounts, and velocity; they are automatically avoided from the failed risk lists.

- **Interactive Single-Screen Bento UI**:
  - **Compact KPI Strip**: 4-column metric bar displaying Amount & Baseline, Location & Channel, IP & Proxy, and Status & Timestamp.
  - **2-Column Signals Grid**: Displays point score badges, evidence snippets, and clear explanations with full text wrapping.
  - **Expandable Related Policy Rules**: Stacked full-width policy cards showing ChromaDB match percentages (`81% match`) with click-to-expand rule details.
  - **Interactive Action Buttons**: Clicking **"Freeze card"** or **"Escalate review"** automatically posts a chat query bubble and returns the confirmation as a new response bubble.
  - **Clean Transaction Assessment**: Clean transactions with no risk triggers suppress policy sections for a focused summary.

- **Interactive Category Selector**:
  - General queries (e.g., `list transactions`, `transactions`, `failed transactions`) return interactive category buttons (High Risk, Moderate Risk, Low Risk) that trigger filtered lists upon clicking.

- **LLM Evidence-Bound Explanation Service**:
  - Integrates with GenAI Lab / OpenAI API (`genailab-maas-sonnet-4.6`) to generate customer-friendly investigation summaries strictly grounded in verified transaction evidence and retrieved policy sections.

---

## Quickstart

### 1. Installation

Ensure Python 3.10+ is installed, then install project dependencies:

```powershell
pip install -r requirements.txt
```

### 2. Configure LLM (Optional)

Set environment variables in your terminal to enable AI-generated investigation explanations:

```powershell
$env:TCS_GENAILAB_API_KEY = "sk-hi12MawxfIhRmb5kiRELUQ"
$env:LLM_BASE_URL = "https://genailab.tcs.in"
$env:LLM_MODEL = "genailab-maas-sonnet-4.6"
```

*(If no LLM key is configured, the deterministic risk engine and ChromaDB vector search remain fully functional.)*

### 3. Run the Application

```powershell
python app.py
```

Open your browser and navigate to **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

---

## Example Queries to Try

| Goal | Query | Description |
| :--- | :--- | :--- |
| **High Risk Investigation** | `Why was TXN_20106 declined?` | Investigates Marcus Vance's London transaction ($1,450, Tor proxy, 30 min travel velocity). Returns 5 risk signals and Section 4.2 & 5.3 rules. |
| **Moderate Risk Investigation** | `Why was TXN_20307 declined?` | Investigates David Chen's Apple Store purchase ($720, proxy over $500). |
| **Low Risk Investigation** | `Why was TXN_20208 declined?` | Investigates Elena Rostova's Uber purchase ($75, CNP). |
| **Clean Baseline Transaction** | `Check TXN_20101` | Analyzes Marcus Vance's legitimate $78.50 Target swipe. Displays clean assessment without triggered policies. |
| **Risk Category Selector** | `list transactions` | Returns interactive selection buttons for High, Moderate, and Low risk failed transactions. |
| **High Risk List** | `List all high risk transactions` | Lists all failed transactions in the High Risk category (sorted by descending risk score). |
| **Moderate Risk List** | `List all moderate risk transactions` | Lists all failed transactions in the Moderate Risk category. |
| **Policy Search** | `What is the policy for impossible travel velocity?` | Performs semantic search against ChromaDB and summarizes Section 4.2 requirements and conditions. |
| **Card Action** | `Freeze card TXN_20106` | Freezes the card for user Marcus Vance and returns a confirmation chat bubble. |

---

## Project Structure

```
RiskPay/
├── App_Data/                          # Persistent storage (auto-initialized)
│   ├── chroma_db/                     # ChromaDB persistent vector database
│   ├── policy-vectors.json            # Synchronized JSON fallback cache
│   └── transaction_analytics.db       # SQLite transactional database
├── data/
│   ├── schema.sql                     # Database schema (customer_profiles & transactions)
│   └── demo_data.sql                  # 5 sample users and 40 transactions
├── docs/
│   └── Risk_Policy.pdf                # Authoritative U.S. Bank sample policy manual
├── static/
│   ├── site.css                       # Primary banking theme & single-screen layout
│   ├── risk-list.css                  # Category buttons & transaction list styling
│   ├── analyst-actions.css            # Action buttons styling (freeze/escalate)
│   ├── policy-links.css               # Expandable accordion rules styling
│   └── llm.css                        # AI explanation container styling
├── templates/
│   ├── index.html                     # Conversational chatbot interface
│   └── admin.html                     # Analytical ledger viewer
├── app.py                             # Flask server, repository, risk rules & routing
├── policy_engine.py                   # PDF extraction & ChromaDB vector store
├── requirements.txt                   # Project Python dependencies
└── README.md                          # Project documentation
```

---

## API Endpoints

- `POST /api/investigate`: Chat endpoint processing natural language questions, transaction investigations, category filters, and policy queries.
- `GET /api/transactions`: Returns customer profiles and grouped transaction histories.
- `POST /api/transactions`: Assesses and registers a new transaction against configured policy rules.
- `POST /api/transactions/<id>/freeze-card`: Freezes the card associated with a medium or high-risk transaction.
- `POST /api/transactions/<id>/escalate`: Routes a low-risk transaction for manual fraud analyst escalation.
