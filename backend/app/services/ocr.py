import os
import cv2
import logging
from paddleocr import PaddleOCR
import numpy as np
import threading

# Matikan logging debug dari PaddleOCR
logging.getLogger("ppocr").setLevel(logging.ERROR)

ocr_model = None
ocr_lock = threading.Lock()

def get_ocr_model():
    global ocr_model
    if ocr_model is None:
        # det_db_thresh (0.15), det_db_box_thresh (0.3), unclip_ratio (2.0)
        # dioptimalkan agar teks kecil/kontras rendah di dalam logo, stempel,
        # dan icon (seperti email & kata 'BADAN') tetap terdeteksi dan tidak terbuang.
        ocr_model = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            enable_mkldnn=False,
            det_db_thresh=0.15,
            det_db_box_thresh=0.3,
            det_db_unclip_ratio=2.0,
        )
    return ocr_model

def enhance_contrast(img_bgr: np.ndarray) -> np.ndarray:
    """
    Meningkatkan kontras lokal menggunakan CLAHE pada saluran L (Lab color space),
    sehingga teks samar di dalam stempel bulat, logo, atau latar belakang gelap
    menjadi jauh lebih jelas bagi PaddleOCR tanpa merusak informasi warna.
    """
    try:
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    except Exception:
        return img_bgr

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Memproses gambar dengan OpenCV agar mudah dibaca oleh OCR:
    1. Konversi transparan ke latar belakang putih solid.
    2. Upscale gambar 2x jika resolusinya kurang dari 2000px agar teks kecil
       di area logo, header, dan footer bisa terdeteksi dengan lebih baik.
    3. Peningkatan kontras adaptif (CLAHE) untuk menajamkan teks samar di stempel/logo.
    """
    # Gunakan IMREAD_UNCHANGED untuk membaca Alpha Channel (transparansi)
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"OpenCV gagal membaca gambar di {image_path}")

    # Batasi resolusi maksimum (maks 4000x4000 piksel) untuk mencegah crash memori (OOM)
    h, w = img.shape[:2]
    if h > 4000 or w > 4000:
        raise ValueError(f"Resolusi gambar terlalu besar ({w}x{h}px). Maksimal resolusi adalah 4000x4000px.")

    # Jika gambar punya transparansi (4 channels: BGRA), ubah ke BGR dengan background putih
    if len(img.shape) == 3 and img.shape[-1] == 4:
        alpha = img[:, :, 3] / 255.0
        white_bg = np.ones_like(img[:, :, :3]) * 255
        color = img[:, :, :3]

        img_bgr = np.zeros_like(color)
        for c in range(3):
            img_bgr[:, :, c] = (alpha * color[:, :, c] + (1 - alpha) * white_bg[:, :, c])
        img = img_bgr.astype(np.uint8)

    # Pastikan format BGR 3 channel
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    # Upscale 2x hanya untuk gambar yang resolusinya sangat kecil (< 600px).
    # Gambar poster normal (800x1000px) tidak perlu di-upscale agar proses OCR 4x lebih cepat.
    h, w = img.shape[:2]
    if max(h, w) < 600:
        img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Terapkan peningkatan kontras CLAHE
    img = enhance_contrast(img)

    # Tambahkan margin/padding putih 30px di sekeliling gambar agar teks
    # di pinggir paling atas (seperti logo/header 'BADAN') atau paling bawah
    # tidak terpotong oleh kotak deteksi (bounding box) OCR.
    img = cv2.copyMakeBorder(img, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255])

    return img

def extract_text_from_image(image_path: str) -> str:
    """
    Mengekstrak seluruh teks yang ditemukan di dalam gambar menggunakan PaddleOCR
    dengan preprocessing OpenCV (CLAHE & padding).
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File gambar tidak ditemukan di path: {image_path}")

    try:
        with ocr_lock:
            processed_img = preprocess_image(image_path)
            ocr = get_ocr_model()
            result = ocr.ocr(processed_img)

            extracted_lines = []
            if result and len(result) > 0:
                res = result[0]
                if isinstance(res, dict):
                    # Format dictionary (PaddleX)
                    texts = res.get("rec_texts", [])
                    for text in texts:
                        if len(text.strip()) > 1:
                            extracted_lines.append(text)
                elif isinstance(res, list):
                    # Format standard list-of-lists
                    for line in res:
                        if line and len(line) > 1:
                            text = line[1][0]
                            if len(text.strip()) > 1:
                                extracted_lines.append(text)

            return "\n".join(extracted_lines)
    except Exception as e:
        print(f"[OCR Error] Gagal mengekstrak gambar: {str(e)}")
        raise e

