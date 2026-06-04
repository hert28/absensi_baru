# face/recognition.py — Engine face_recognition (deep learning 128-dim embeddings)
# Menggantikan LBPH yang tidak akurat untuk mencegah false positive
# Library face_recognition menggunakan dlib ResNet untuk encoding wajah

import cv2
import os
import pickle
import numpy as np
import face_recognition as fr

# Path ke file encodings yang disimpan oleh trainer
ENCODINGS_PATH = 'models/encodings.pkl'

# Toleransi face distance (Euclidean distance pada 128-dim embedding)
# Semakin rendah = semakin ketat. Default dlib: 0.6
# 0.5 = ketat, cocok untuk mencegah false positive pada absensi
FACE_DISTANCE_TOLERANCE = 0.5

# Data encoding yang dimuat dari file
_known_encodings = None
_known_ids = None


def _load_encodings():
    """Muat face encodings dari file pickle. Dipanggil otomatis saat predict."""
    global _known_encodings, _known_ids
    if not os.path.exists(ENCODINGS_PATH):
        print('[RECOGNITION] File encodings belum ada. Jalankan training terlebih dahulu.')
        return False

    with open(ENCODINGS_PATH, 'rb') as f:
        data = pickle.load(f)

    _known_encodings = data['encodings']
    _known_ids = data['ids']
    print(f'[RECOGNITION] {len(_known_encodings)} encoding dari '
          f'{len(set(_known_ids))} user berhasil dimuat.')
    return True


def reload_model():
    """Muat ulang encodings setelah re-training.
    Dipanggil setelah background training selesai.
    """
    global _known_encodings, _known_ids
    _known_encodings = None
    _known_ids = None
    return _load_encodings()


def detect_faces(frame):
    """Deteksi semua wajah dalam frame menggunakan HOG detector (face_recognition).

    Args:
        frame: numpy array BGR dari OpenCV (atau grayscale)

    Returns:
        List of (x, y, w, h) untuk setiap wajah terdeteksi
    """
    # Konversi ke RGB (face_recognition membutuhkan RGB)
    if len(frame.shape) == 2:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    else:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Deteksi wajah menggunakan HOG — cepat dan akurat
    locations = fr.face_locations(frame_rgb, model='hog')

    # Konversi format (top, right, bottom, left) → (x, y, w, h) agar kompatibel
    faces = []
    for (top, right, bottom, left) in locations:
        faces.append((left, top, right - left, bottom - top))
    return faces


def predict(frame):
    """Kenali SEMUA wajah dalam frame menggunakan deep learning embeddings (multi-face).

    Alur:
    1. Resize frame ke 1/2 untuk deteksi cepat
    2. Deteksi semua lokasi wajah (HOG)
    3. Hitung 128-dim encoding untuk setiap wajah
    4. Bandingkan encoding dengan database (Euclidean distance)
    5. Jika distance < FACE_DISTANCE_TOLERANCE → dikenali

    Args:
        frame: numpy array BGR dari OpenCV

    Returns:
        List of dict: [{'user_id': int, 'confidence': float, 'bbox': (x,y,w,h), 'dikenali': bool}]
        confidence = face_distance (0.0-1.0+), rendah = lebih mirip.
    """
    global _known_encodings, _known_ids

    # Muat encodings jika belum
    if _known_encodings is None:
        if not _load_encodings():
            return []

    # Konversi BGR → RGB
    if len(frame.shape) == 2:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    else:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Resize ke 1/2 ukuran untuk mempercepat deteksi (4x lebih cepat)
    small = cv2.resize(frame_rgb, (0, 0), fx=0.5, fy=0.5)

    # Deteksi wajah pada frame kecil
    face_locations = fr.face_locations(small, model='hog')
    if not face_locations:
        return []

    # Hitung encoding 128-dim untuk setiap wajah
    face_encodings = fr.face_encodings(small, face_locations)

    hasil = []
    for i, encoding in enumerate(face_encodings):
        top, right, bottom, left = face_locations[i]
        # Skalakan kembali ke ukuran asli (karena resize 0.5x)
        top *= 2; right *= 2; bottom *= 2; left *= 2

        # Hitung Euclidean distance terhadap SEMUA encoding terdaftar
        distances = fr.face_distance(_known_encodings, encoding)

        if len(distances) == 0:
            continue

        # Ambil yang paling mirip (distance terkecil)
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])
        best_id = _known_ids[best_idx]

        # KEPUTUSAN: hanya dikenali jika distance < toleransi ketat
        dikenali = best_distance < FACE_DISTANCE_TOLERANCE

        print(f'[RECOGNITION] user_id={best_id}, distance={best_distance:.3f}, '
              f'tolerance={FACE_DISTANCE_TOLERANCE}, dikenali={dikenali}')

        hasil.append({
            'user_id': best_id,
            'confidence': round(best_distance, 4),
            'bbox': (left, top, right - left, bottom - top),
            'dikenali': dikenali
        })

    return hasil


def predict_single(frame):
    """Kenali satu wajah utama (confidence terbaik) dalam frame.

    Returns:
        dict {'user_id': int, 'confidence': float, 'bbox': tuple, 'dikenali': bool}
        atau None jika tidak ada wajah.
    """
    results = predict(frame)
    if not results:
        return None

    # Ambil yang distance terkecil (paling mirip)
    best = min(results, key=lambda r: r['confidence'])
    return best


def draw_prediction(frame, predictions):
    """Gambar kotak dan label prediksi di atas frame.

    Args:
        frame: numpy array BGR
        predictions: list dari predict()

    Returns:
        frame yang sudah ditandai
    """
    annotated = frame.copy()

    for pred in predictions:
        x, y, w, h = pred['bbox']
        dist = pred['confidence']
        uid = pred['user_id']
        dikenali = pred['dikenali']

        # Warna: hijau jika dikenali, merah jika tidak
        color = (0, 255, 0) if dikenali else (0, 0, 255)
        label = f"ID:{uid} ({dist:.2f})" if dikenali else f"Unknown ({dist:.2f})"

        # Gambar kotak wajah
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

        # Label di atas kotak
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (x, y - label_size[1] - 10),
                      (x + label_size[0], y), color, -1)
        cv2.putText(annotated, label, (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return annotated
