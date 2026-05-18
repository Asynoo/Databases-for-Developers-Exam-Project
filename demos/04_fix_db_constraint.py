"""
Demo 4 - Fix: Database Constraint + Atomic Counter

The events_safe table holds a denormalized tickets_sold counter and a CHECK
constraint (tickets_sold <= capacity). The purchase is a single UPDATE that
increments the counter; the constraint is evaluated atomically by PostgreSQL.

This pushes the invariant into the schema itself, making it impossible to
violate regardless of application logic or direct SQL access. An idempotency
key (UUID UNIQUE) on the tickets table additionally prevents duplicate inserts
from retries or double-clicks.
"""

import threading
import psycopg2
from config import DSN, NUM_USERS

EVENT_ID = 1


def reset(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tickets_safe WHERE event_id = %s", (EVENT_ID,))
        cur.execute("UPDATE events_safe SET tickets_sold = 0 WHERE id = %s", (EVENT_ID,))
    conn.commit()


def buy_ticket_constrained(user_id: int, results: list):
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    idempotency_key = str(__import__("uuid").uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events_safe
                SET tickets_sold = tickets_sold + 1
                WHERE id = %s AND tickets_sold < capacity
                RETURNING tickets_sold, capacity
                """,
                (EVENT_ID,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                results.append(f"User {user_id:>3}: DENIED  (sold out)")
                return

            sold, capacity = row
            cur.execute(
                """
                INSERT INTO tickets_safe (event_id, user_id, idempotency_key)
                VALUES (%s, %s, %s)
                """,
                (EVENT_ID, user_id, idempotency_key),
            )
            conn.commit()
            results.append(f"User {user_id:>3}: BOUGHT  ({sold}/{capacity})")

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        results.append(f"User {user_id:>3}: DUPLICATE (idempotency key already used)")
    except psycopg2.errors.CheckViolation:
        conn.rollback()
        results.append(f"User {user_id:>3}: DENIED  (constraint violation)")
    except Exception as e:
        conn.rollback()
        results.append(f"User {user_id:>3}: ERROR - {e}")
    finally:
        conn.close()


def main():
    conn = psycopg2.connect(DSN)
    reset(conn)
    conn.close()

    print(f"Event capacity: 5  |  Concurrent buyers: {NUM_USERS}\n")

    results = []
    threads = [
        threading.Thread(target=buy_ticket_constrained, args=(i, results))
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
        cur.execute(
            "SELECT tickets_sold, capacity FROM events_safe WHERE id = %s",
            (EVENT_ID,),
        )
        sold, capacity = cur.fetchone()
    conn.close()

    print(f"\nResult: {sold} tickets sold for a {capacity}-seat event")
    assert sold <= capacity, "BUG: oversold!"
    print("No oversell - DB constraint approach works.")


if __name__ == "__main__":
    main()
