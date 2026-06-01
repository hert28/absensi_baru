# face/trainer.py — Training LBPH dari dataset foto wajah
# Dijalankan di background thread, tidak boleh blokir Flask

import os
import cv2
import numpy as np
from config import DATASET_PATH, MODEL_PATH


def train_model():
    """Training model LBPH dari semua foto di folder dataset/.
    
    Struktur folder:
        dataset/{user_id}/0.jpg, 1.jpg, ... 49.jpg
    
    Output:
        models/trainer.yml
    """
    faces = []
    labels = []

    # Baca semua foto dari setiap subfolder user
    for user_folder in os.listdir(DATASET_PATH):
        user_path = os.path.join(DATASET_PATH, user_folder)
        if not os.path.isdir(user_path):
            continue

        try:
            user_id = int(user_folder)
        except ValueError:
            continue

        for filename in os.listdir(user_path):
            if not filename.endswith('.jpg'):
                continue

            filepath = os.path.join(user_path, filename)
            img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            # Resize ke ukuran standar untuk konsistensi
            img = cv2.resize(img, (200, 200))

            # Deteksi wajah dengan Haar Cascade
            # scaleFactor lebih kecil dan minNeighbors lebih rendah agar lebih sensitif
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            detected = cascade.detectMultiScale(
                img, scaleFactor=1.05, minNeighbors=2, minSize=(20, 20)
            )

            if len(detected) > 0:
                # Ambil wajah terbesar yang terdeteksi
                areas = [(w * h, i) for i, (x, y, w, h) in enumerate(detected)]
                _, best_idx = max(areas)
                (x, y, w, h) = detected[best_idx]
                face_roi = img[y:y+h, x:x+w]
                face_roi = cv2.resize(face_roi, (200, 200))
            else:
                # Fallback: foto sudah di-crop ke area wajah saat pengambilan,
                # gunakan seluruh gambar — jangan skip foto ini.
                face_roi = img  # sudah 200x200 dari resize di atas

            faces.append(face_roi)
            labels.append(user_id)

    if len(faces) == 0:
        print('[TRAINER] Tidak ada data wajah untuk training.')
        return False

    # Buat dan latih LBPH recognizer
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))

    # Simpan model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    recognizer.write(MODEL_PATH)

    print(f'[TRAINER] Training selesai! {len(faces)} foto dari {len(set(labels))} user.')

    # Muat ulang model di engine recognition agar langsung aktif
    try:
        from face.recognition import reload_model
        reload_model()
        print('[TRAINER] Model berhasil dimuat ulang di recognition engine.')
    except Exception as e:
        print(f'[TRAINER] Gagal reload model: {e}')

    return True
