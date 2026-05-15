"""
Demo 2 — Fix: Pessimistic Locking (SELECT FOR UPDATE)

SELECT ... FOR UPDATE acquires a row-level lock on the event row.
Any other transaction trying to lock the same row will block until
the first one commits or rolls back. This serializes the check-and-insert.

Tradeoff: high contention → transactions queue up → lower throughput.
Best when conflicts are frequent and you need strong guarantees.
"""

import threading
import psycopg2
import time
from config import DSN, EVENT_ID, NUM_USERS


def reset(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tickets WHERE event_id = %s", (EVENT_ID,))
    conn.commit()


def buy_ticket_locked(user_id: int, results: list):
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # Lock the event row — blocks concurrent buyers until we commit
            cur.execute(
                "SELECT capacity FROM events WHERE id = %s FOR UPDATE",
                (EVENT_ID,),
            )
            capacity = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM tickets WHERE event_id = %s",
                (EVENT_ID,),
            )
            sold = cur.fetchone()[0]

            time.sleep(0.01)

            if sold < capacity:
                cur.execute(
                    "INSERT INTO tickets (event_id, user_id) VALUES (%s, %s)",
                    (EVENT_ID, user_id),
                )
                conn.commit()
                results.append(f"User {user_id:>3}: BOUGHT  ({sold + 1}/{capacity})")
            else:
                conn.rollback()
                results.append(f"User {user_id:>3}: DENIED  ({sold}/{capacity})")
    except Exception as e:
        conn.rollback()
        results.append(f"User {user_id:>3}: ERROR — {e}")
    finally:
        conn.close()


def main():
    conn = psycopg2.connect(DSN)
    reset(conn)
    conn.close()

    print(f"Event capacity: 5  |  Concurrent buyers: {NUM_USERS}\n")

    results = []
    threads = [
        threading.Thread(target=buy_ticket_locked, args=(i, results))
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
    print("No oversell — pessimistic locking works.")


if __name__ == "__main__":
    main()
