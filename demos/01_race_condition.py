"""
Demo 1 — The Problem: Race Condition / Overselling

Two concurrent transactions both read the same available count,
both decide there is room, and both insert a ticket. The event
ends up with more tickets sold than its capacity.

Pattern (naive):
    1. SELECT count(*) FROM tickets WHERE event_id = ?   -- read
    2. if count < capacity: INSERT INTO tickets ...       -- write
    Steps 1 and 2 are NOT atomic: another transaction can slip in between.
"""

import threading
import psycopg2
import time
from config import DSN, EVENT_ID, NUM_USERS


def reset(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tickets WHERE event_id = %s", (EVENT_ID,))
    conn.commit()


def buy_ticket_naive(user_id: int, results: list):
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM tickets WHERE event_id = %s",
                (EVENT_ID,),
            )
            sold = cur.fetchone()[0]

            cur.execute("SELECT capacity FROM events WHERE id = %s", (EVENT_ID,))
            capacity = cur.fetchone()[0]

            # Artificial delay to widen the race window
            time.sleep(0.05)

            if sold < capacity:
                cur.execute(
                    "INSERT INTO tickets (event_id, user_id) VALUES (%s, %s)",
                    (EVENT_ID, user_id),
                )
                conn.commit()
                results.append(f"User {user_id:>3}: BOUGHT  (saw {sold}/{capacity} sold)")
            else:
                conn.rollback()
                results.append(f"User {user_id:>3}: DENIED  (saw {sold}/{capacity} sold)")
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
        threading.Thread(target=buy_ticket_naive, args=(i, results))
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
    if total > capacity:
        print("OVERSOLD — race condition confirmed!")
    else:
        print("No oversell this run (try again; timing-sensitive).")


if __name__ == "__main__":
    main()
