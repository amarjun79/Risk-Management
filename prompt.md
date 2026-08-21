# AI Transaction Decline Investigation Chatbot

## Role

You are a senior AI Solutions Architect and Full-Stack .NET Developer.

Build an **AI-powered Transaction Decline Investigation Chatbot** for the **U.S. Bank AI Hackathon 2026**. The chatbot helps customers understand **why their credit card transaction was declined** through a natural language conversation.

The solution must combine:
- Structured transaction history (SQL/mock database)
- RAG over a Risk Policy PDF
- LLM reasoning and summarization
- A simple conversational web UI

## Business Problem

Customers should be able to ask questions such as:

- Why was my transaction declined?
- Check transaction TXN_99812.
- My payment at Amazon failed.

The chatbot extracts the transaction ID from natural language, retrieves transaction history and customer profile using function calling, searches the policy PDF using RAG, and generates an explainable response grounded in evidence.

## Functional Requirements

### Chat UI
Create a minimal banking-themed interface containing:
- Chat history
- User input
- Send button
- Scrollable conversation
- Conversation cards for investigation results

### Transaction ID Extraction

Extract transaction IDs from natural language using regex with LLM fallback.

Examples:

| User Input | Extracted |
|---|---|
| Check TXN_99812 | TXN_99812 |
| Why did txn99812 fail? | TXN_99812 |
| My transaction is txn-99812 | TXN_99812 |

### Structured Data (Function Calling)

Use services instead of allowing the LLM to access SQL directly.

Tables:

#### Transactions
- TransactionId
- UserId
- Amount
- Merchant
- Location
- Timestamp
- CardPresent
- IpAddress
- IpIsProxy
- Status

#### Customer Profile
- UserId
- FullName
- HomeCity
- AvgTransactionAmount
- AvgMonthlySpend

Required functions:

- GetTransactionById()
- GetCustomerProfile()
- GetPreviousTransactions()
- CalculateRiskSignals()

### Risk Detection

Implement deterministic business rules for:
- Impossible travel
- Proxy IP detection
- Card-not-present anomaly
- Unusual transaction amount
- Rapid geographical movement
- Unusual spending pattern

These signals become inputs to the LLM.

## RAG Requirements

Project structure:

```text
/docs
   Risk_Policy.pdf
```

On application startup:

1. Read the PDF
2. Split into semantic chunks
3. Generate embeddings
4. Store vectors in ChromaDB
5. Persist the vector database locally

For every investigation:

- Perform similarity search
- Retrieve the top 3 relevant policy chunks
- Pass only retrieved policy text to the LLM

Never allow the model to answer policy questions without retrieval.

## AI Workflow

1. User submits a natural language query.
2. Extract the transaction ID.
3. Fetch transaction details.
4. Fetch customer profile.
5. Retrieve previous transactions.
6. Calculate fraud risk signals.
7. Query ChromaDB using RAG.
8. Retrieve matching policy sections.
9. Send structured evidence to the LLM.
10. Return a concise customer-friendly explanation.

## LLM Context

Provide the model with:

- Original user query
- Current transaction
- Previous transactions
- Customer profile
- Calculated risk signals
- Retrieved policy chunks

The LLM should:
- Explain the likely decline reason
- Summarize evidence
- Cite policy sections
- Recommend next steps

Do not fabricate policies or unsupported facts.

## Response Template

Example:

**Transaction:** TXN_99812

**Risk:** HIGH (88/100)

### Why it was declined

- London transaction occurred 30 minutes after Minneapolis.
- Transaction originated from a verified Tor exit node.
- Amount was significantly above the customer's average.

### Policy

- Section 4.2 — Impossible Travel Velocity
- Section 5.3 — Anonymizing Proxies

### Recommendation

This transaction was likely declined by automated fraud prevention. Ask the customer to verify identity or contact the bank to authorize future transactions.

## Technical Stack

- ASP.NET Core 8 MVC
- C#
- SQL Server (mock data supported)
- ChromaDB
- RAG with embeddings
- Dependency Injection
- Repository Pattern
- Clean layered architecture

The solution should prioritize explainability, evidence grounding, and a conversational customer experience.
