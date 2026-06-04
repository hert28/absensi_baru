# face/trainer.py — Training: hitung 128-dim SFace embeddings dari dataset
# Menggunakan OpenCV DNN (YuNet + SFace) — tanpa dlib
# Dijalankan di background thread, tidak boleh blokir Flask

import os
import pickle
import cv2
import numpy as np
from config import DATASET_PATH

# Import paths dan fungsi download dari recognition
from face.recognition import (
    YUNET_PATH, SFACE_PATH, YUNET_URL, SFACE_URL,
    ENCODINGS_PATH, _download_if_needed
)


def train_model():
    """Hitung SFace embeddings dari semua foto di folder dataset/.

    Struktur folder: dataset/{user_id}/0.jpg ... 49.jpg
    Output: models/encodings.pkl
    """
    # Download model jika belum ada
    if not _download_if_needed(YUNET_URL, YUNET_PATH):
        print('[TRAINER] Gagal download YuNet model.')
        return False
    if not _download_if_needed(SFACE_URL, SFACE_PATH):
        print('[TRAINER] Gagal download SFace model.')
        return False

    detector = cv2.FaceDetectorYN.create(YUNET_PATH, '', (320, 320), 0.5, 0.3, 20)
    recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, '')

    known_encodings = []
    known_ids = []

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
            img = cv2.imread(filepath)
            if img is None:
                continue

            h, w = img.shape[:2]
            detector.setInputSize((w, h))
            _, faces = detector.detect(img)

            if faces is not None and len(faces) > 0:
                # Gunakan wajah terdeteksi untuk alignment presisi
                aligned = recognizer.alignCrop(img, faces[0])
            else:
                # Fallback: resize langsung ke 112x112 (SFace input size)
                aligned = cv2.resize(img, (112, 112))

            embedding = recognizer.feature(aligned)
            known_encodings.append(embedding)
            known_ids.append(user_id)
            count += 1

        if count > 0:
            print(f'[TRAINER] User {user_id}: {count} encoding berhasil.')

    if len(known_encodings) == 0:
        print('[TRAINER] Tidak ada data wajah untuk training.')
        return False

    # Simpan encodings
    os.makedirs(os.path.dirname(ENCODINGS_PATH), exist_ok=True)
    with open(ENCODINGS_PATH, 'wb') as f:
        pickle.dump({'encodings': known_encodings, 'ids': known_ids}, f)

    print(f'[TRAINER] Training selesai! {len(known_encodings)} encoding dari {len(set(known_ids))} user.')

    # Muat ulang di recognition engine
    try:
        from face.recognition import reload_model
        reload_model()
        print('[TRAINER] Encodings berhasil dimuat ulang.')
    except Exception as e:
        print(f'[TRAINER] Gagal reload: {e}')

    return True
