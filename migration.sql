-- ============================================================
-- MIGRATION SQL — Sistem Absensi Face Recognition
-- Kompatibel dengan mysql-connector-python (tanpa DELIMITER)
-- batas_terlambat dihitung di Python (database.py)
-- ============================================================

-- 1. admin
CREATE TABLE IF NOT EXISTS admin (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. kelas
CREATE TABLE IF NOT EXISTS kelas (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nama_kelas  VARCHAR(100) NOT NULL,
    angkatan    VARCHAR(10)  NOT NULL,
    dibuat_oleh INT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dibuat_oleh) REFERENCES admin(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 3. matakuliah
CREATE TABLE IF NOT EXISTS matakuliah (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    nama_mk  VARCHAR(100) NOT NULL,
    kode_mk  VARCHAR(20)  UNIQUE NOT NULL,
    kelas_id INT NOT NULL,
    sks      INT DEFAULT 2,
    FOREIGN KEY (kelas_id) REFERENCES kelas(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. jadwal
CREATE TABLE IF NOT EXISTS jadwal (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    matakuliah_id   INT NOT NULL,
    hari            ENUM('Senin','Selasa','Rabu','Kamis','Jumat','Sabtu') NOT NULL,
    jam_mulai       TIME NOT NULL,
    jam_selesai     TIME NOT NULL,
    batas_terlambat TIME NOT NULL,
    FOREIGN KEY (matakuliah_id) REFERENCES matakuliah(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. users (mahasiswa)
CREATE TABLE IF NOT EXISTS users (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nama       VARCHAR(100) NOT NULL,
    nim        VARCHAR(20)  UNIQUE NOT NULL,
    kelas_id   INT NOT NULL,
    foto_path  VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kelas_id) REFERENCES kelas(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 6. absensi
CREATE TABLE IF NOT EXISTS absensi (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT  NOT NULL,
    jadwal_id     INT  NOT NULL,
    tanggal       DATE NOT NULL,
    waktu_absen   TIME,
    status        ENUM('hadir','terlambat','izin','alpha') NOT NULL,
    snapshot_path VARCHAR(255),
    dibuat_manual BOOLEAN  DEFAULT FALSE,
    timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)   REFERENCES users(id)  ON DELETE CASCADE,
    FOREIGN KEY (jadwal_id) REFERENCES jadwal(id)  ON DELETE CASCADE,
    UNIQUE KEY uq_absensi (user_id, jadwal_id, tanggal)
) ENGINE=InnoDB;

-- 7. spoofing_log
CREATE TABLE IF NOT EXISTS spoofing_log (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP,
    snapshot_path    VARCHAR(255),
    confidence_score FLOAT
) ENGINE=InnoDB;
