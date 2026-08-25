INSERT INTO customer_profiles (user_id, full_name, home_city, avg_transaction_amount, avg_monthly_spend) VALUES
    ('USR_1001', 'Jordan Williams', 'Minneapolis', 86, 1850),
    ('USR_1002', 'Taylor Reed', 'Chicago', 62, 1320);

INSERT INTO transactions (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status) VALUES
    ('TXN_99812', 'USR_1001', 780, 'Amazon', 'London', '2026-08-20T10:00:00+00:00', 0, '185.220.101.4', 1, 'Declined'),
    ('TXN_99811', 'USR_1001', 74, 'Target', 'Minneapolis', '2026-08-20T09:30:00+00:00', 1, '73.162.12.8', 0, 'Approved'),
    ('TXN_99810', 'USR_1001', 52, 'Coffee Corner', 'Minneapolis', '2026-08-19T10:00:00+00:00', 1, '73.162.12.8', 0, 'Approved'),
    ('TXN_99809', 'USR_1001', 89, 'Groceries', 'Minneapolis', '2026-08-18T10:00:00+00:00', 1, '73.162.12.8', 0, 'Approved'),
    ('TXN_78221', 'USR_1002', 45, 'Transit', 'Chicago', '2026-08-20T07:00:00+00:00', 1, '192.168.1.12', 0, 'Approved');
