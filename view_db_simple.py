import sqlite3
from pathlib import Path

db_path = Path("data/fitness_coach.db")

def view_database():
    """
    View the contents of the SQLite database in the console for debugging purposes.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 100)
    print("DATABASE CONTENTS")
    print("=" * 100)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]

    for table in tables:
        print(f"\n[TABLE: {table}]")
        print("-" * 100)

        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]

        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()

        if not rows:
            print("  (empty)")
        else:
            print("  " + " | ".join(columns))
            print("  " + "-" * 100)

            for row in rows:
                print("  " + " | ".join(str(val)[:50] if val else "NULL" for val in row))

        print()

    conn.close()

    print("\n" + "=" * 100)
    print(f"Total tables: {len(tables)}")
    print("=" * 100)

if __name__ == "__main__":
    view_database()
