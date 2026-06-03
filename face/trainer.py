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
    
    Foto sudah di-crop ke area wajah + margin saat pengambilan (api_foto_upload).
    Oleh karena itu, trainer TIDAK perlu re-deteksi wajah — langsung resize
    dan gunakan seluruh gambar sebagai face ROI.
    
    Preprocessing: histogram equalization untuk normalisasi pencahayaan
    agar model lebih tahan terhadap variasi kamera dan kondisi cahaya.
    
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

        foto_count = 0
        for filename in os.listdir(user_path):
            if not filename.lower().endswith('.jpg'):
                continue

            filepath = os.path.join(user_path, filename)
            img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f'[TRAINER] Gagal baca file: {filepath}')
                continue

            # Resize ke ukuran standar 200x200 untuk konsistensi
            img = cv2.resize(img, (200, 200))

            # Histogram equalization — normalisasi pencahayaan
            # Penting agar model tahan terhadap variasi kamera dan cahaya
            img = cv2.equalizeHist(img)

            faces.append(img)
            labels.append(user_id)
            foto_count += 1

        if foto_count > 0:
            print(f'[TRAINER] User {user_id}: {foto_count} foto dimuat.')

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
