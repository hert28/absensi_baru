import mysql.connector
import os
from config import DB_CONFIG

def check():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("Tabel di database:")
        for t in tables:
            print(f"- {t[0]}")
            cursor.execute(f"DESCRIBE {t[0]}")
            cols = cursor.fetchall()
            for c in cols:
                print(f"    {c[0]} ({c[1]})")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check()
