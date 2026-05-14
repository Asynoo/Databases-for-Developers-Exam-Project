CREATE TABLE IF NOT EXISTS events_safe (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    capacity     INT  NOT NULL,
    tickets_sold INT  NOT NULL DEFAULT 0,
    CONSTRAINT no_oversell CHECK (tickets_sold <= capacity)
);

CREATE TABLE IF NOT EXISTS tickets_safe (
    id              SERIAL PRIMARY KEY,
    event_id        INT         NOT NULL REFERENCES events_safe(id),
    user_id         INT         NOT NULL,
    idempotency_key UUID        NOT NULL UNIQUE,
    purchased_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO events_safe (name, capacity) VALUES ('Rock Concert', 5);
