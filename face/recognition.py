# face/recognition.py — Engine OpenCV DNN (YuNet + SFace) untuk face recognition
# Menggunakan deep learning 128-dim embeddings TANPA dlib/face_recognition
# Semua sudah built-in di opencv-contrib-python 4.8

import cv2
import os
import pickle
import numpy as np
import urllib.request

MODELS_DIR = 'models'
YUNET_PATH = os.path.join(MODELS_DIR, 'yunet.onnx')
SFACE_PATH = os.path.join(MODELS_DIR, 'sface.onnx')
ENCODINGS_PATH = os.path.join(MODELS_DIR, 'encodings.pkl')

YUNET_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
SFACE_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx'

# Cosine similarity threshold: semakin tinggi = semakin ketat
# Default OpenCV: 0.363 | Untuk absensi: 0.4 (ketat, anti false positive)
COSINE_THRESHOLD = 0.4

_detector = None
_recognizer = None
_known_encodings = None
_known_ids = None


def _download_if_needed(url, path):
    """Download model ONNX jika belum ada di disk."""
    if os.path.exists(path):
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f'[RECOGNITION] Downloading {os.path.basename(path)}...')
    try:
        urllib.request.urlretrieve(url, path)
        print(f'[RECOGNITION] Download selesai: {path}')
        return True
    except Exception as e:
        print(f'[RECOGNITION] Gagal download: {e}')
        return False


def _ensure_models():
    """Pastikan model YuNet dan SFace sudah tersedia."""
    global _detector, _recognizer
    if _detector is None:
        if not _download_if_needed(YUNET_URL, YUNET_PATH):
            return False
        _detector = cv2.FaceDetectorYN.create(YUNET_PATH, '', (320, 320), 0.5, 0.3, 20)
    if _recognizer is None:
        if not _download_if_needed(SFACE_URL, SFACE_PATH):
            return False
        _recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, '')
    return True


def _load_encodings():
    """Muat face encodings dari file pickle."""
    global _known_encodings, _known_ids
    if not os.path.exists(ENCODINGS_PATH):
        print('[RECOGNITION] File encodings belum ada. Jalankan training.')
        return False
    with open(ENCODINGS_PATH, 'rb') as f:
        data = pickle.load(f)
    _known_encodings = data['encodings']
    _known_ids = data['ids']
    print(f'[RECOGNITION] {len(_known_encodings)} encoding dari {len(set(_known_ids))} user dimuat.')
    return True


def reload_model():
    """Muat ulang encodings setelah re-training."""
    global _known_encodings, _known_ids
    _known_encodings = None
    _known_ids = None
    return _load_encodings()


def detect_faces(frame):
    """Deteksi semua wajah dalam frame menggunakan YuNet DNN.
    Returns: list of (x, y, w, h)
    """
    if not _ensure_models():
        return []
    h, w = frame.shape[:2]
    _detector.setInputSize((w, h))
    _, faces = _detector.detect(frame)
    if faces is None:
        return []
    return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]


def predict(frame):
    """Kenali SEMUA wajah dalam frame (multi-face) menggunakan SFace embeddings.
    Returns: list of dict [{'user_id', 'confidence', 'bbox', 'dikenali'}]
    """
    global _known_encodings, _known_ids

    if not _ensure_models():
        return []
    if _known_encodings is None:
        if not _load_encodings():
            return []

    # Resize frame untuk kecepatan (max 640px)
    h, w = frame.shape[:2]
    scale = 1.0
    if max(h, w) > 640:
        scale = 640.0 / max(h, w)
        small = cv2.resize(frame, (int(w * scale), int(h * scale)))
    else:
        small = frame

    sh, sw = small.shape[:2]
    _detector.setInputSize((sw, sh))
    _, faces = _detector.detect(small)
    if faces is None:
        return []

    hasil = []
    for face in faces:
        # Skalakan kembali ke ukuran asli
        face_orig = face.copy()
        if scale != 1.0:
            face_orig[:14] /= scale

        # Align dan crop wajah (SFace alignment built-in)
        try:
            aligned = _recognizer.alignCrop(frame, face_orig)
        except Exception:
            continue

        # Hitung 128-dim embedding
        embedding = _recognizer.feature(aligned)

        # Bandingkan dengan semua encoding terdaftar (cosine similarity)
        best_score = -1.0
        best_id = -1
        for i, known_enc in enumerate(_known_encodings):
            score = _recognizer.match(embedding, known_enc, cv2.FaceRecognizerSF_FR_COSINE)
            if score > best_score:
                best_score = score
                best_id = _known_ids[i]

        dikenali = best_score >= COSINE_THRESHOLD
        x, y, bw, bh = int(face_orig[0]), int(face_orig[1]), int(face_orig[2]), int(face_orig[3])

        print(f'[RECOGNITION] user_id={best_id}, cosine={best_score:.3f}, '
              f'threshold={COSINE_THRESHOLD}, dikenali={dikenali}')

        hasil.append({
            'user_id': best_id,
            'confidence': round(best_score, 4),
            'bbox': (x, y, bw, bh),
            'dikenali': dikenali
        })

    return hasil


def predict_single(frame):
    """Kenali satu wajah utama dalam frame."""
    results = predict(frame)
    if not results:
        return None
    return max(results, key=lambda r: r['confidence'])


def draw_prediction(frame, predictions):
    """Gambar kotak dan label prediksi di atas frame."""
    annotated = frame.copy()
    for pred in predictions:
        x, y, w, h = pred['bbox']
        dikenali = pred['dikenali']
        color = (0, 255, 0) if dikenali else (0, 0, 255)
        label = f"ID:{pred['user_id']} ({pred['confidence']:.2f})" if dikenali else f"Unknown ({pred['confidence']:.2f})"
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (x, y - label_size[1] - 10), (x + label_size[0], y), color, -1)
        cv2.putText(annotated, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return annotated
