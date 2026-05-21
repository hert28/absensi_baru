import os

# config.py — Konfigurasi Terpusat Sistem Absensi
# AMAN UNTUK GITHUB: Menggunakan Environment Variables untuk data sensitif

# === KONFIGURASI DATABASE ===
DB_CONFIG = {
    'host': os.environ.get('MYSQLHOST', os.environ.get('DB_HOST', 'localhost')),
    'port': int(os.environ.get('MYSQLPORT', os.environ.get('DB_PORT', 3306))),
    'user': os.environ.get('MYSQLUSER', os.environ.get('DB_USER', 'root')),
    'password': os.environ.get('MYSQLPASSWORD', os.environ.get('DB_PASSWORD', '')),
    'database': os.environ.get('MYSQLDATABASE', os.environ.get('DB_NAME', 'railway'))
}

# === KONFIGURASI SISTEM ===
DATASET_PATH            = 'dataset'
MODEL_PATH              = 'models/trainer.yml'
SNAPSHOT_PATH           = 'snapshots'
CONFIDENCE_THRESHOLD    = 55
FOTO_PER_USER           = 50
CAMERA_INDEX            = 0
TOLERANSI_MENIT         = 15

# === KONFIGURASI FLASK ===
FLASK_HOST       = '0.0.0.0'
FLASK_PORT       = 5000
FLASK_DEBUG      = True
FLASK_SECRET_KEY = 'ganti-dengan-secret-key-random-panjang-anda'

# === KONFIGURASI ESP32 ===
ESP32_ENABLED = False
ESP32_IP      = '192.168.1.9'
ESP32_PORT    = 80
ESP32_TIMEOUT = 3

# === KONFIGURASI ANTI-SPOOFING ===
# Threshold 0.0-1.0: semakin rendah semakin toleran (0.5 untuk webcam biasa)
ANTI_SPOOFING_THRESHOLD = 0.5
# Set False untuk menonaktifkan cek spoofing saat development/testing
ANTI_SPOOFING_ENABLED   = False