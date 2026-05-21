# run_migration.py — Jalankan migration.sql via mysql-connector-python
# Penggunaan: python run_migration.py

import mysql.connector
from config import DB_CONFIG

def run():
    # Koneksi langsung ke database dari config (otomatis pakai database Railway)
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    with open('migration.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    # Pisah per statement berdasarkan semicolon
    statements = [s.strip() for s in sql.split(';') if s.strip()]

    for i, stmt in enumerate(statements, 1):
        # Bersihkan komentar baris
        lines = [l for l in stmt.split('\n') if not l.strip().startswith('--')]
        clean = '\n'.join(lines).strip()
        if not clean:
            continue
        try:
            cursor.execute(clean)
            conn.commit()
            if 'CREATE TABLE' in clean.upper():
                # Ekstrak nama tabel
                upper = clean.upper()
                idx = upper.find('EXISTS') + 6 if 'EXISTS' in upper else upper.find('TABLE') + 5
                nama = clean[idx:].strip().split('(')[0].strip()
                print(f"  [OK] Tabel: {nama}")
            elif 'CREATE DATABASE' in clean.upper():
                print(f"  [OK] Database absensi_db siap")
            elif 'USE ' in clean.upper():
                print(f"  [OK] Menggunakan absensi_db")
        except mysql.connector.Error as e:
            print(f"  [!] Statement {i}: {e.msg}")

    cursor.close()
    conn.close()
    print("\n[DONE] Migration selesai!")

if __name__ == '__main__':
    print("=" * 45)
    print("  MIGRATION - Sistem Absensi Face Recognition")
    print("=" * 45)
    run()
