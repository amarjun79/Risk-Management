# RiskLens — Transaction Decline Investigation Chatbot

A Python/Flask demo for explaining declined card transactions. The conversational interface normalizes transaction IDs, obtains structured evidence through repository services, calculates deterministic fraud signals, retrieves the three most relevant local policy sections, and returns a customer-friendly investigation card.

## Run

```powershell
python app.py
```

Open `http://127.0.0.1:5000` and ask: `Why was txn99812 declined?`

Use the **Transactions** tab to view all transactions grouped by customer. The **Add transaction** form checks the record against the configured policy signals before storing it; transactions with a risk score of 35 or more are flagged immediately and include the supporting policy evidence.

## Demo architecture

- `app.py` exposes the UI, `/api/investigate` chat API, SQLite repository, risk rules, and workflow.
- `App_Data/transaction_analytics.db` is created automatically on the first run from `data/schema.sql` and `data/demo_data.sql`. Edit or replace it with your own SQLite data without changing application code.
- `templates/index.html` contains the conversational interface, while `static/site.css` provides the banking theme.
- On startup `app.py` validates `docs/Risk_Policy.pdf` and persists a lightweight local policy index in `App_Data/policy-vectors.json`.

SQLite is included with Python and stores analytical data locally; swap `TransactionRepository` for PostgreSQL later if needed. Production can replace `PolicySearch` with a PDF chunker/embedding client backed by ChromaDB.

## LLM configuration

The investigation response can use the supplied GenAI Lab model (`genailab-maas-sonnet-4.6`) at `https://genailab.tcs.in`. Set the key only in your terminal before running the server—never commit it or send it to the browser.

```powershell
$env:TCS_GENAILAB_API_KEY = "sk-hi12MawxfIhRmb5kiRELUQ"
$env:LLM_BASE_URL = "https://genailab.tcs.in"
$env:LLM_MODEL = "genailab-maas-sonnet-4.6"
pip install -r requirements.txt
python app.py
```

The backend passes the model only the user question, transaction and profile data, calculated risk signals, and the retrieved policy sections. If the key is not configured or the LLM is unavailable, the deterministic evidence-based investigation remains available. Any key that was previously committed to this README should be rotated before use.
