import threading
import psycopg2
import time
from config import DSN, EVENT_ID, NUM_USERS

SETUP_SQL = """
ALTER TABLE events ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0;
"""


def reset(conn):
    with conn.cursor() as cur:
        cur.execute(SETUP_SQL)
        cur.execute("UPDATE events SET version = 0 WHERE id = %s", (EVENT_ID,))
        cur.execute("DELETE FROM tickets WHERE event_id = %s", (EVENT_ID,))
    conn.commit()


def buy_ticket_optimistic(user_id: int, results: list, max_retries: int = 5):
    conn = psycopg2.connect(DSN)
    conn.autocommit = False

    for attempt in range(1, max_retries + 1):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT capacity, version FROM events WHERE id = %s",
                    (EVENT_ID,),
                )
                capacity, version = cur.fetchone()

                cur.execute(
                    "SELECT COUNT(*) FROM tickets WHERE event_id = %s",
                    (EVENT_ID,),
                )
                sold = cur.fetchone()[0]

                time.sleep(0.02)

                if sold >= capacity:
                    conn.rollback()
                    results.append(f"User {user_id:>3}: DENIED  ({sold}/{capacity})")
                    return

                cur.execute(
                    """
                    UPDATE events
                    SET version = version + 1
                    WHERE id = %s AND version = %s
                    """,
                    (EVENT_ID, version),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    time.sleep(0.01 * attempt)
                    continue

                cur.execute(
                    "INSERT INTO tickets (event_id, user_id) VALUES (%s, %s)",
                    (EVENT_ID, user_id),
                )
                conn.commit()
                results.append(
                    f"User {user_id:>3}: BOUGHT  (attempt {attempt}, version {version}->{version+1})"
                )
                return

        except Exception as e:
            conn.rollback()
            results.append(f"User {user_id:>3}: ERROR - {e}")
            return

    results.append(f"User {user_id:>3}: GAVE UP after {max_retries} retries")
    conn.close()


def main():
    conn = psycopg2.connect(DSN)
    reset(conn)
    conn.close()

    print(f"Event capacity: 5  |  Concurrent buyers: {NUM_USERS}\n")

    results = []
    threads = [
        threading.Thread(target=buy_ticket_optimistic, args=(i, results))
        for i in range(1, NUM_USERS + 1)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for r in sorted(results):
        print(r)

    conn = psycopg2.connect(DSN)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tickets WHERE event_id = %s", (EVENT_ID,))
        total = cur.fetchone()[0]
        cur.execute("SELECT capacity FROM events WHERE id = %s", (EVENT_ID,))
        capacity = cur.fetchone()[0]
    conn.close()

    print(f"\nResult: {total} tickets sold for a {capacity}-seat event")
    assert total <= capacity, "BUG: oversold!"
    print("No oversell - optimistic concurrency control works.")


if __name__ == "__main__":
    main()
