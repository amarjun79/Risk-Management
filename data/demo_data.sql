INSERT INTO customer_profiles (user_id, full_name, home_city, avg_transaction_amount, avg_monthly_spend, card_frozen) VALUES
    ('USR_2001', 'Marcus Vance', 'Minneapolis', 85.0, 2400.0, 0),
    ('USR_2002', 'Elena Rostova', 'Chicago', 65.0, 1750.0, 0),
    ('USR_2003', 'David Chen', 'Seattle', 110.0, 3200.0, 0),
    ('USR_2004', 'Amina Al-Mansoor', 'New York', 75.0, 2100.0, 0),
    ('USR_2005', 'Liam O''Connor', 'San Francisco', 95.0, 2800.0, 0);

-- User 1: Marcus Vance (Minneapolis) - 7 transactions (4 baseline successful + 1 routine successful + 2 failed)
INSERT INTO transactions (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status, risk_score, risk_level, policy_flagged) VALUES
    ('TXN_20101', 'USR_2001', 78.50, 'Target', 'Minneapolis', '2026-08-15T10:00:00+00:00', 1, '73.162.12.8', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20102', 'USR_2001', 45.00, 'Caribou Coffee', 'Minneapolis', '2026-08-16T12:30:00+00:00', 1, '73.162.12.8', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20103', 'USR_2001', 92.00, 'Whole Foods', 'Minneapolis', '2026-08-17T15:45:00+00:00', 1, '73.162.12.8', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20104', 'USR_2001', 64.50, 'Shell Gas', 'Minneapolis', '2026-08-18T09:15:00+00:00', 1, '73.162.12.8', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20105', 'USR_2001', 82.00, 'Trader Joe''s', 'Minneapolis', '2026-08-20T09:30:00+00:00', 1, '73.162.12.8', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20106', 'USR_2001', 1450.00, 'Amazon UK', 'London', '2026-08-20T10:00:00+00:00', 0, '185.220.101.5', 1, 'Failed', 100, 'High', 1),
    ('TXN_20107', 'USR_2001', 480.00, 'Best Buy Online', 'Minneapolis', '2026-08-21T11:00:00+00:00', 0, '198.51.100.22', 1, 'Failed', 57, 'Medium', 1);

-- User 2: Elena Rostova (Chicago) - 8 transactions (4 baseline successful + 1 routine successful + 3 failed)
INSERT INTO transactions (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status, risk_score, risk_level, policy_flagged) VALUES
    ('TXN_20201', 'USR_2002', 42.00, 'CTA Transit', 'Chicago', '2026-08-14T08:30:00+00:00', 1, '24.148.88.19', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20202', 'USR_2002', 85.00, 'Jewel-Osco', 'Chicago', '2026-08-15T14:00:00+00:00', 1, '24.148.88.19', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20203', 'USR_2002', 58.00, 'Walgreens', 'Chicago', '2026-08-16T11:15:00+00:00', 1, '24.148.88.19', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20204', 'USR_2002', 65.00, 'Corner Bakery', 'Chicago', '2026-08-17T18:20:00+00:00', 1, '24.148.88.19', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20205', 'USR_2002', 54.00, 'Chicago Diner', 'Chicago', '2026-08-19T13:00:00+00:00', 1, '24.148.88.19', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20206', 'USR_2002', 2200.00, 'Akihabara Tech', 'Tokyo', '2026-08-19T13:45:00+00:00', 0, '103.251.167.2', 1, 'Failed', 100, 'High', 1),
    ('TXN_20207', 'USR_2002', 320.00, 'Nordstrom Direct', 'Chicago', '2026-08-20T16:30:00+00:00', 0, '24.148.88.19', 0, 'Failed', 32, 'Medium', 1),
    ('TXN_20208', 'USR_2002', 75.00, 'Uber Rides', 'Chicago', '2026-08-21T09:00:00+00:00', 0, '24.148.88.19', 0, 'Failed', 12, 'Low', 1);

-- User 3: David Chen (Seattle) - 9 transactions (4 baseline successful + 2 routine successful + 3 failed)
INSERT INTO transactions (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status, risk_score, risk_level, policy_flagged) VALUES
    ('TXN_20301', 'USR_2003', 120.00, 'REI Seattle', 'Seattle', '2026-08-13T09:00:00+00:00', 1, '67.183.45.101', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20302', 'USR_2003', 95.00, 'Pike Place Fish', 'Seattle', '2026-08-14T12:00:00+00:00', 1, '67.183.45.101', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20303', 'USR_2003', 140.00, 'Safeway', 'Seattle', '2026-08-15T17:30:00+00:00', 1, '67.183.45.101', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20304', 'USR_2003', 85.00, 'Starbucks Reserve', 'Seattle', '2026-08-16T10:45:00+00:00', 1, '67.183.45.101', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20305', 'USR_2003', 112.00, 'Home Depot', 'Seattle', '2026-08-18T14:00:00+00:00', 1, '67.183.45.101', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20306', 'USR_2003', 3500.00, 'CryptoPay Global', 'Zurich', '2026-08-18T14:25:00+00:00', 0, '185.107.56.88', 1, 'Failed', 100, 'High', 1),
    ('TXN_20307', 'USR_2003', 720.00, 'Apple Store Online', 'Seattle', '2026-08-19T16:00:00+00:00', 0, '192.42.116.16', 1, 'Failed', 57, 'Medium', 1),
    ('TXN_20308', 'USR_2003', 480.00, 'Hotel Grand View', 'San Francisco', '2026-08-20T18:30:00+00:00', 0, '67.183.45.101', 0, 'Failed', 32, 'Medium', 1),
    ('TXN_20309', 'USR_2003', 98.00, 'Costco Wholesale', 'Seattle', '2026-08-21T08:30:00+00:00', 1, '67.183.45.101', 0, 'Successful', 0, 'Low', 0);

-- User 4: Amina Al-Mansoor (New York) - 6 transactions (4 baseline successful + 1 routine successful + 1 failed)
INSERT INTO transactions (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status, risk_score, risk_level, policy_flagged) VALUES
    ('TXN_20401', 'USR_2004', 55.00, 'MTA Subway', 'New York', '2026-08-15T08:00:00+00:00', 1, '72.229.28.185', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20402', 'USR_2004', 110.00, 'Fairway Market', 'New York', '2026-08-16T13:15:00+00:00', 1, '72.229.28.185', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20403', 'USR_2004', 45.00, 'Joe Coffee', 'New York', '2026-08-17T09:30:00+00:00', 1, '72.229.28.185', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20404', 'USR_2004', 70.00, 'Duane Reade', 'New York', '2026-08-18T16:00:00+00:00', 1, '72.229.28.185', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20405', 'USR_2004', 85.00, 'Shake Shack', 'New York', '2026-08-20T11:00:00+00:00', 1, '72.229.28.185', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20406', 'USR_2004', 1850.00, 'Printemps Boutique', 'Paris', '2026-08-20T11:35:00+00:00', 0, '185.220.100.252', 1, 'Failed', 100, 'High', 1);

-- User 5: Liam O'Connor (San Francisco) - 10 transactions (4 baseline successful + 2 routine successful + 4 failed)
INSERT INTO transactions (transaction_id, user_id, amount, merchant, location, timestamp, card_present, ip_address, ip_is_proxy, status, risk_score, risk_level, policy_flagged) VALUES
    ('TXN_20501', 'USR_2005', 85.00, 'Safeway', 'San Francisco', '2026-08-12T09:00:00+00:00', 1, '98.210.14.77', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20502', 'USR_2005', 120.00, 'Philz Coffee', 'San Francisco', '2026-08-13T11:30:00+00:00', 1, '98.210.14.77', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20503', 'USR_2005', 65.00, 'BART Transit', 'San Francisco', '2026-08-14T08:15:00+00:00', 1, '98.210.14.77', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20504', 'USR_2005', 110.00, 'Trader Joe''s', 'San Francisco', '2026-08-15T17:00:00+00:00', 1, '98.210.14.77', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20505', 'USR_2005', 88.00, 'CVS Pharmacy', 'San Francisco', '2026-08-17T14:00:00+00:00', 1, '98.210.14.77', 0, 'Successful', 0, 'Low', 0),
    ('TXN_20506', 'USR_2005', 4200.00, 'Global Wire Hub', 'Frankfurt', '2026-08-17T14:20:00+00:00', 0, '185.220.102.8', 1, 'Failed', 100, 'High', 1),
    ('TXN_20507', 'USR_2005', 950.00, 'Electronics World', 'San Francisco', '2026-08-18T16:45:00+00:00', 0, '194.26.29.112', 1, 'Failed', 57, 'Medium', 1),
    ('TXN_20508', 'USR_2005', 350.00, 'Urban Outfitters Online', 'San Francisco', '2026-08-19T12:00:00+00:00', 0, '98.210.14.77', 0, 'Failed', 32, 'Medium', 1),
    ('TXN_20509', 'USR_2005', 90.00, 'Software Subscription', 'San Francisco', '2026-08-20T10:15:00+00:00', 0, '98.210.14.77', 0, 'Failed', 12, 'Low', 1),
    ('TXN_20510', 'USR_2005', 105.00, 'Chevron Gas', 'San Francisco', '2026-08-21T07:45:00+00:00', 1, '98.210.14.77', 0, 'Successful', 0, 'Low', 0);
