# face/recognition.py — Engine LBPH: predict wajah, load model
# Digunakan oleh dashboard saat kamera aktif untuk mengenali mahasiswa

import cv2
import os
import numpy as np
from config import MODEL_PATH, CONFIDENCE_THRESHOLD

# Override threshold ke 80.0 (Keseimbangan antara toleransi kacamata dan pencegahan wajah salah dikenali)
CONFIDENCE_THRESHOLD = 80.0


# Haar Cascade untuk deteksi wajah
_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
_face_cascade = cv2.CascadeClassifier(_cascade_path)

# LBPH Recognizer — dimuat saat pertama kali dibutuhkan
_recognizer = None


def _load_recognizer():
    """Muat model LBPH dari file. Dipanggil otomatis saat predict."""
    global _recognizer
    if not os.path.exists(MODEL_PATH):
        print('[RECOGNITION] Model belum ada. Jalankan training terlebih dahulu.')
        return False
    _recognizer = cv2.face.LBPHFaceRecognizer_create()
    _recognizer.read(MODEL_PATH)
    print(f'[RECOGNITION] Model berhasil dimuat dari {MODEL_PATH}')
    return True


def reload_model():
    """Muat ulang model setelah re-training.
    Dipanggil setelah background training selesai agar predict pakai model terbaru.
    """
    global _recognizer
    _recognizer = None
    return _load_recognizer()


def detect_faces(frame):
    """Deteksi semua wajah dalam frame.
    
    Menggunakan parameter optimal agar bisa mendeteksi wajah dekat maupun jauh,
    serta wajah berkerumun (multi-face).
    
    Args:
        frame: numpy array BGR dari OpenCV (atau grayscale)
    
    Returns:
        List of (x, y, w, h) untuk setiap wajah terdeteksi
    """
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # Gunakan CLAHE agar deteksi wajah tahan terhadap pencahayaan tidak merata (misal: bayangan/terang sebelah)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray)

    faces = _face_cascade.detectMultiScale(
        gray_clahe,
        scaleFactor=1.1,     # Kembali ke 1.1 agar stabil
        minNeighbors=5,      # Ditingkatkan ke 5 untuk menghindari false detection pada background/benda mati
        minSize=(40, 40)     # Ukuran minimal 40x40 agar tidak mendeteksi noise
    )
    return faces


def predict(frame):
    """Kenali SEMUA wajah dalam frame menggunakan model LBPH (multi-face).
    
    Preprocessing yang sama dengan trainer:
    - Crop wajah → resize 200x200 → histogram equalization (CLAHE)
    Ini memastikan data saat predict konsisten dengan data saat training.
    
    Args:
        frame: numpy array BGR dari OpenCV
    
    Returns:
        List of dict: [{'user_id': int, 'confidence': float, 'bbox': (x,y,w,h)}]
        confidence rendah = lebih mirip. Threshold < CONFIDENCE_THRESHOLD = dikenali.
        Return list kosong jika tidak ada wajah atau model belum dimuat.
    """
    global _recognizer

    # Muat model jika belum
    if _recognizer is None:
        if not _load_recognizer():
            return []

    # Konversi ke grayscale
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame.copy()

    # Deteksi wajah menggunakan CLAHE
    faces = detect_faces(gray)
    if len(faces) == 0:
        return []

    # Gunakan CLAHE untuk preprocessing crop wajah agar sama persis dengan dataset training
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)

    hasil = []
    for (x, y, w, h) in faces:
        # Crop dan resize wajah sesuai ukuran training (200x200)
        face_roi = gray_eq[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (200, 200))

        # Predict dengan LBPH
        user_id, confidence = _recognizer.predict(face_roi)

        dikenali = confidence < CONFIDENCE_THRESHOLD
        print(f'[RECOGNITION] user_id={user_id}, confidence={confidence:.1f}, '
              f'threshold={CONFIDENCE_THRESHOLD}, dikenali={dikenali}')

        hasil.append({
            'user_id': user_id,
            'confidence': round(confidence, 2),
            'bbox': (int(x), int(y), int(w), int(h)),
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

    # Ambil yang confidence terkecil (paling mirip)
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
        conf = pred['confidence']
        uid = pred['user_id']
        dikenali = pred['dikenali']

        # Warna: hijau jika dikenali, merah jika tidak
        color = (0, 255, 0) if dikenali else (0, 0, 255)
        label = f"ID:{uid} ({conf:.0f})" if dikenali else f"Unknown ({conf:.0f})"

        # Gambar kotak wajah
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

        # Label di atas kotak
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (x, y - label_size[1] - 10), 
                      (x + label_size[0], y), color, -1)
        cv2.putText(annotated, label, (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return annotated
