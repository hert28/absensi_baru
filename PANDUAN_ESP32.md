# PANDUAN INTEGRASI ESP32 — Sistem Absensi Face Recognition (LCD 16×2 I2C)
> Panduan ini menjelaskan cara menghubungkan ESP32 + LCD 16×2 I2C ke sistem absensi yang sudah live di Railway (HTTPS).

---

## DAFTAR KOMPONEN YANG DIBUTUHKAN

| Komponen          | Jumlah | Keterangan                             |
|-------------------|--------|----------------------------------------|
| ESP32 Dev Board   | 1      | Versi 30-pin atau 38-pin               |
| LCD 16×2 I2C      | 1      | Modul dengan adapter I2C (PCF8574)     |
| Kabel jumper      | 4      | Female-to-Male untuk koneksi I2C       |
| Kabel USB         | 1      | Untuk upload kode dari laptop ke ESP32 |

---

## LANGKAH 1 — LIBRARY YANG WAJIB DIINSTALL (ARDUINO IDE)

Buka **Library Manager** (`Ctrl+Shift+I` atau `Sketch → Include Library → Manage Libraries...`) lalu install:

1. **LiquidCrystal I2C** (oleh Frank de Brabander) — untuk LCD 16×2 via I2C
2. **ArduinoJson** (oleh Benoit Blanchon) — disarankan versi **6.x** (stabil)
3. **HTTPClient** — sudah built-in di ESP32 Arduino Core, tidak perlu install manual
4. **WiFiClientSecure** — sudah built-in di ESP32 Arduino Core

---

## LANGKAH 2 — SKEMA WIRING LCD 16×2 I2C ke ESP32

```
LCD 16×2 I2C     ESP32
──────────────────────────
VCC          →   VIN  (5V)   ← VIN bukan 3.3V! LCD butuh 5V
GND          →   GND
SDA          →   GPIO 21
SCL          →   GPIO 22
```

> ⚠️ **Penting:** Gunakan pin **VIN** (5V), bukan 3.3V. LCD 16×2 tidak akan menyala dengan tegangan 3.3V.

### Diagram Wiring

```
                    ┌─────────────────────┐
                    │       ESP32          │
                    │                     │
    LCD SDA ────────┤ GPIO 21             │
    LCD SCL ────────┤ GPIO 22             │
    LCD VCC ────────┤ VIN (5V)       USB  │──── ke Laptop
    LCD GND ────────┤ GND                 │
                    └─────────────────────┘
```

---

## LANGKAH 3 — CARI ALAMAT I2C LCD (BIASANYA 0x27 atau 0x3F)

LCD 16×2 dengan adapter PCF8574 umumnya menggunakan alamat **`0x27`**. Jika LCD tidak menyala setelah upload, jalankan **I2C Scanner** berikut:

```cpp
#include <Wire.h>

void setup() {
  Wire.begin(21, 22);   // SDA=21, SCL=22
  Serial.begin(115200);
  Serial.println("\nScanning I2C...");

  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("Perangkat ditemukan di alamat: 0x");
      Serial.println(addr, HEX);
    }
  }
  Serial.println("Scan selesai.");
}

void loop() {}
```

**Cara menjalankan:**
1. Upload sketch scanner ke ESP32.
2. Buka **Serial Monitor** (Tools → Serial Monitor), baud rate **115200**.
3. Catat alamat yang muncul. Jika **`0x3F`** (bukan `0x27`), ubah baris di kode utama:
   ```cpp
   LiquidCrystal_I2C lcd(0x3F, 16, 2);  // ganti 0x27 → 0x3F
   ```

---

## LANGKAH 4 — PENJELASAN API ENDPOINT BACKEND

ESP32 akan mem-polling endpoint berikut secara berkala:

```
GET https://absensi-6ti3.up.railway.app/api/absensi/terakhir
```

**Contoh Response (ada absensi):**
```json
{
  "status": "ok",
  "data": {
    "nama": "David Soselisa",
    "status_label": "Tepat Waktu"
  },
  "pesan": null
}
```

**Contoh Response (belum ada absensi hari ini):**
```json
{
  "status": "ok",
  "data": null,
  "pesan": "Belum ada absensi hari ini."
}
```

---

## LANGKAH 5 — KODE ARDUINO IDE LENGKAP (esp32_lcd.ino)

```cpp
/**
 * esp32_lcd.ino — Tampilkan absensi terakhir di LCD 16x2 via I2C
 * 
 * Hardware : ESP32 + LCD 16x2 (PCF8574 I2C)
 * Library  : LiquidCrystal_I2C, ArduinoJson 6.x, WiFiClientSecure, HTTPClient
 * Backend  : Flask di Railway (HTTPS) — diakses dengan setInsecure() bypass SSL
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <LiquidCrystal_I2C.h>

// ── Konfigurasi WiFi ─────────────────────────────────────────
const char* WIFI_SSID     = "NAMA_WIFI_KAMU";       // ← Ganti
const char* WIFI_PASSWORD = "PASSWORD_WIFI_KAMU";   // ← Ganti

// ── URL API Backend (Railway) ─────────────────────────────────
const char* API_URL = "https://absensi-6ti3.up.railway.app/api/absensi/terakhir";

// ── Konfigurasi LCD 16x2 I2C ─────────────────────────────────
// Argumen: (alamat_i2c, kolom, baris)
// Alamat default PCF8574: 0x27 — jika tidak menyala, coba 0x3F
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ── Interval polling ke server (milliseconds) ─────────────────
const unsigned long POLLING_INTERVAL = 5000;  // 5 detik

// ── Variabel state ───────────────────────────────────────────
unsigned long lastPollTime  = 0;
String        lastNama      = "";
String        lastStatus    = "";


// ── Fungsi: potong string agar muat di LCD 16 kolom ──────────
// PANDUAN ADAPTIF — jika nama/status dari DB berubah jadi sangat panjang:
// Fungsi ini memotong otomatis di karakter ke-16. Cukup panggil truncate(str, 16).
String truncate(String str, int maxLen) {
  if (str.length() > maxLen) {
    return str.substring(0, maxLen);
  }
  return str;
}

// ── Fungsi: tampilkan pesan 2 baris di LCD ───────────────────
void tampilLCD(String baris1, String baris2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(truncate(baris1, 16));
  lcd.setCursor(0, 1);
  lcd.print(truncate(baris2, 16));
}


// ────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // Inisialisasi LCD
  lcd.init();
  lcd.backlight();

  // Status awal: sedang menghubungkan WiFi
  tampilLCD("Connecting WiFi", "Please wait...");
  Serial.println("[ESP32] Menghubungkan ke WiFi...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  // WiFi berhasil terhubung
  Serial.println();
  Serial.println("[ESP32] WiFi Terhubung!");
  Serial.print("[ESP32] IP: ");
  Serial.println(WiFi.localIP());

  tampilLCD("WiFi Connected!", WiFi.localIP().toString());
  delay(2000);  // Tampilkan IP selama 2 detik

  // Tampilan standby awal
  tampilLCD("Silakan Absen..", "Scan wajah Anda");
}


// ────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // Polling ke server setiap POLLING_INTERVAL ms
  if (now - lastPollTime >= POLLING_INTERVAL) {
    lastPollTime = now;
    pollServer();
  }
}


// ── Fungsi utama: ambil data dari API backend ─────────────────
void pollServer() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ESP32] WiFi terputus, reconnecting...");
    tampilLCD("WiFi terputus!", "Reconnecting...");
    WiFi.reconnect();
    return;
  }

  // Gunakan WiFiClientSecure dengan setInsecure() untuk bypass SSL Railway
  WiFiClientSecure client;
  client.setInsecure();  // Bypass verifikasi sertifikat HTTPS

  HTTPClient http;
  http.begin(client, API_URL);
  http.setTimeout(8000);  // Timeout 8 detik

  int httpCode = http.GET();
  Serial.printf("[HTTP] Response code: %d\n", httpCode);

  if (httpCode == 200) {
    String payload = http.getString();
    Serial.println("[HTTP] Payload: " + payload);
    parseAndDisplay(payload);
  } else {
    Serial.printf("[HTTP] Gagal, error: %s\n", http.errorToString(httpCode).c_str());
    tampilLCD("Server error!", "Code:" + String(httpCode));
  }

  http.end();
}


// ── Parse JSON dan tampilkan ke LCD ──────────────────────────
void parseAndDisplay(String json) {
  // ArduinoJson 6.x — alokasi dokumen JSON
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, json);

  if (err) {
    Serial.print("[JSON] Parse error: ");
    Serial.println(err.c_str());
    tampilLCD("JSON Error!", err.c_str());
    return;
  }

  // Cek field "data" dari response backend
  if (doc["data"].isNull()) {
    // Belum ada absensi hari ini
    tampilLCD("Silakan Absen..", "Scan wajah Anda");
    lastNama   = "";
    lastStatus = "";
    return;
  }

  // Ambil nama dan status dari JSON
  // PANDUAN ADAPTIF — jika nama key JSON berubah di backend:
  //   Ganti "nama" dan "status_label" di bawah sesuai key baru dari /api/absensi/terakhir
  String nama   = String(doc["data"]["nama"]        | "Unknown");
  String status = String(doc["data"]["status_label"] | "?");

  // Hindari refresh LCD jika data tidak berubah (mengurangi flicker)
  if (nama == lastNama && status == lastStatus) return;
  lastNama   = nama;
  lastStatus = status;

  // Tampilkan di LCD:
  // Baris 1 (0): Nama mahasiswa  (dipotong maks 16 karakter)
  // Baris 2 (1): Status kehadiran (dipotong maks 16 karakter)
  tampilLCD(nama, status);

  Serial.printf("[LCD] Nama: %s | Status: %s\n", nama.c_str(), status.c_str());
}
```

---

## LANGKAH 6 — CARA UPLOAD KE ESP32

1. Buka **Arduino IDE**, buat file baru, paste kode di atas.
2. Isi `WIFI_SSID` dan `WIFI_PASSWORD` sesuai jaringan WiFi Anda.
3. Pilih board: **Tools → Board → ESP32 Arduino → ESP32 Dev Module**
4. Pilih port COM yang terdeteksi: **Tools → Port → COMx**
5. Klik tombol **Upload** (→).
   > *Tips: Jika muncul `Connecting....`, tekan dan tahan tombol **BOOT** pada board ESP32 hingga proses upload dimulai.*

---

## LANGKAH 7 — TAMPILAN LCD YANG DIHARAPKAN

| Kondisi | Baris 1 | Baris 2 |
|---------|---------|---------|
| Saat startup, mencari WiFi | `Connecting WiFi` | `Please wait...` |
| WiFi berhasil terhubung | `WiFi Connected!` | `192.168.x.x` |
| Ada absensi, status hadir | `David Soselisa` | `Tepat Waktu` |
| Ada absensi, terlambat | `David Soselisa` | `Terlambat` |
| Belum ada absensi | `Silakan Absen..` | `Scan wajah Anda` |
| Server error | `Server error!` | `Code:500` |
| WiFi terputus | `WiFi terputus!` | `Reconnecting...` |

---

## BAGIAN: PANDUAN ADAPTIF (ANTISIPASI PERUBAHAN)

### Jika Nama Kolom `status` di Database Berubah

Edit di **`database.py`** fungsi `get_absensi_terakhir_hari_ini()`:

```python
# Baris yang harus diubah jika nama kolom berubah (misal jadi 'kehadiran'):
cursor.execute("""
    SELECT u.nama, a.kehadiran   ← ganti 'a.status' → 'a.kehadiran'
    FROM absensi a
    JOIN users u ON a.user_id = u.id
    WHERE a.tanggal = CURDATE()
    ORDER BY a.timestamp DESC
    LIMIT 1
""")
row = cursor.fetchone()
# ...
'status_label': STATUS_LABEL.get(row['kehadiran'], ...)  ← ganti 'status' → 'kehadiran'
```

### Jika Nama/Status Sangat Panjang (Melebihi 16 Karakter LCD)

Di kode Arduino, fungsi `truncate()` **sudah otomatis memotong** string di karakter ke-16:

```cpp
// Contoh: "Muhammad Firmansyah Ramadhan" (28 char) → "Muhammad Firmans" (16 char)
String truncate(String str, int maxLen) {
  if (str.length() > maxLen) {
    return str.substring(0, maxLen);   // ← Ubah maxLen jika pindah ke LCD 20x4
  }
  return str;
}
```

Jika suatu saat pindah ke **LCD 20×4**, cukup ubah satu baris:
```cpp
tampilLCD(truncate(nama, 20), truncate(status, 20));
```

---

## TROUBLESHOOTING

| Masalah | Kemungkinan Penyebab | Solusi |
|---------|---------------------|--------|
| LCD tidak menyala sama sekali | VCC terhubung ke 3.3V, bukan 5V | Pindahkan VCC ke pin **VIN** (5V) di ESP32 |
| LCD menyala tapi tidak ada teks | Alamat I2C salah | Jalankan I2C Scanner, ubah `0x27` → `0x3F` (atau sebaliknya) |
| Layar tampil kotak-kotak hitam | Kontras LCD terlalu rendah | Putar **potensiometer biru** di belakang modul I2C perlahan hingga teks muncul |
| ESP32 gagal terhubung ke WiFi | SSID/Password salah, atau WiFi 5GHz | Pastikan WiFi **2.4GHz** dan konfigurasi SSID/Password benar |
| HTTP response code -1 | Timeout, Railway sedang cold start | Naikkan `http.setTimeout(8000)` menjadi `15000` ms |
| JSON Parse error | Backend mengembalikan HTML (error page) | Cek URL `API_URL` sudah benar, buka di browser untuk verifikasi |
| Teks terpotong di LCD | Nama mahasiswa > 16 karakter | Fungsi `truncate()` sudah menangani ini secara otomatis |
