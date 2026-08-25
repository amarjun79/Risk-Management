CREATE TABLE customer_profiles (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    home_city TEXT NOT NULL,
    avg_transaction_amount REAL NOT NULL,
    avg_monthly_spend REAL NOT NULL,
    card_frozen INTEGER NOT NULL DEFAULT 0 CHECK (card_frozen IN (0, 1))
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES customer_profiles(user_id),
    amount REAL NOT NULL,
    merchant TEXT NOT NULL,
    location TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    card_present INTEGER NOT NULL CHECK (card_present IN (0, 1)),
    ip_address TEXT NOT NULL,
    ip_is_proxy INTEGER NOT NULL CHECK (ip_is_proxy IN (0, 1)),
    status TEXT NOT NULL,
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'Low',
    policy_flagged INTEGER NOT NULL DEFAULT 0 CHECK (policy_flagged IN (0, 1)),
    escalated INTEGER NOT NULL DEFAULT 0 CHECK (escalated IN (0, 1))
);

CREATE INDEX idx_transactions_user_timestamp ON transactions(user_id, timestamp DESC);
