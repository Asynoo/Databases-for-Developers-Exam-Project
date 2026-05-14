CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    capacity    INT         NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets (
    id           SERIAL PRIMARY KEY,
    event_id     INT         NOT NULL REFERENCES events(id),
    user_id      INT         NOT NULL,
    purchased_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO events (name, capacity) VALUES ('Rock Concert', 5);
