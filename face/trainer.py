# face/trainer.py — Training: hitung 128-dim face encodings dari dataset
# Menggunakan library face_recognition (dlib ResNet) — menggantikan LBPH
# Dijalankan di background thread, tidak boleh blokir Flask

import os
import pickle
import cv2
import numpy as np
import face_recognition as fr
from config import DATASET_PATH

# Path output encodings (pickle)
ENCODINGS_PATH = 'models/encodings.pkl'


def train_model():
    """Hitung face encodings dari semua foto di folder dataset/.

    Struktur folder:
        dataset/{user_id}/0.jpg, 1.jpg, ... 49.jpg

    Foto sudah di-crop ke area wajah saat pengambilan (api_foto_upload).
    Trainer mendeteksi ulang wajah di dalam crop untuk alignment yang presisi,
    lalu menghitung 128-dim encoding menggunakan dlib ResNet.

    Output:
        models/encodings.pkl — berisi dict {'encodings': [...], 'ids': [...]}
    """
    known_encodings = []
    known_ids = []

    # Baca semua foto dari setiap subfolder user
    for user_folder in os.listdir(DATASET_PATH):
        user_path = os.path.join(DATASET_PATH, user_folder)
        if not os.path.isdir(user_path):
            continue

        try:
            user_id = int(user_folder)
        except ValueError:
            continue

        count = 0
        for filename in os.listdir(user_path):
            if not filename.lower().endswith('.jpg'):
                continue

            filepath = os.path.join(user_path, filename)

            # Baca gambar dalam format RGB (face_recognition butuh RGB)
            img = fr.load_image_file(filepath)
            if img is None:
                print(f'[TRAINER] Gagal baca file: {filepath}')
                continue

            # Deteksi wajah di dalam crop — untuk alignment yang presisi
            face_locations = fr.face_locations(img, model='hog')

            if len(face_locations) == 0:
                # Fallback: jika HOG gagal mendeteksi wajah di dalam crop,
                # anggap seluruh gambar adalah wajah (karena sudah di-crop saat registrasi)
                h, w = img.shape[:2]
                face_locations = [(0, w, h, 0)]  # (top, right, bottom, left)

            # Hitung encoding untuk wajah pertama (terbesar)
            encodings = fr.face_encodings(img, face_locations)
            if len(encodings) > 0:
                known_encodings.append(encodings[0])
                known_ids.append(user_id)
                count += 1

        if count > 0:
            print(f'[TRAINER] User {user_id}: {count} encoding berhasil dihitung.')

    if len(known_encodings) == 0:
        print('[TRAINER] Tidak ada data wajah untuk training.')
        return False

    # Simpan encodings ke file pickle
    os.makedirs(os.path.dirname(ENCODINGS_PATH), exist_ok=True)
    data = {
        'encodings': known_encodings,
        'ids': known_ids
    }
    with open(ENCODINGS_PATH, 'wb') as f:
        pickle.dump(data, f)

    print(f'[TRAINER] Training selesai! {len(known_encodings)} encoding dari '
          f'{len(set(known_ids))} user.')

    # Muat ulang encodings di engine recognition agar langsung aktif
    try:
        from face.recognition import reload_model
        reload_model()
        print('[TRAINER] Encodings berhasil dimuat ulang di recognition engine.')
    except Exception as e:
        print(f'[TRAINER] Gagal reload encodings: {e}')

    return True
