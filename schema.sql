-- schema.sql : five tables (section 2.1). Run inside database momo.
-- Foreign keys are added AFTER loading (post_load.sql) so the 20M-row
-- \copy is not slowed by per-row FK checks. Final schema is identical.
SET timezone = 'Africa/Kigali';

DROP TABLE IF EXISTS transfers, account_devices, accounts, devices, customers CASCADE;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    region      TEXT NOT NULL
);

CREATE TABLE devices (
    device_id   INTEGER PRIMARY KEY,
    access_type TEXT NOT NULL
);

CREATE TABLE accounts (
    account_id  INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    role        TEXT NOT NULL
);

CREATE TABLE account_devices (
    account_id   INTEGER  NOT NULL,
    device_id    INTEGER  NOT NULL,
    first_day    SMALLINT NOT NULL,
    last_day     SMALLINT NOT NULL,
    observations INTEGER  NOT NULL,
    PRIMARY KEY (account_id, device_id),
    CONSTRAINT ck_observations_pos CHECK (observations > 0),
    CONSTRAINT ck_day_range CHECK (0 <= first_day AND first_day <= last_day AND last_day <= 29)
);

CREATE TABLE transfers (
    transfer_id BIGINT  PRIMARY KEY,
    sender_id   INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    occurred_at BIGINT  NOT NULL,   -- Unix seconds
    amount_rwf  INTEGER NOT NULL,   -- integer RWF
    CONSTRAINT ck_amount_pos CHECK (amount_rwf > 0)
);
