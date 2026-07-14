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
        # det_db_thresh diturunkan ke 0.2 (default: 0.3) agar teks kecil/kontras rendah
        # di area logo dan footer poster tetap bisa terdeteksi.
        ocr_model = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            enable_mkldnn=False,
            det_db_thresh=0.2,
        )
    return ocr_model

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Memproses gambar dengan OpenCV agar mudah dibaca oleh OCR:
    1. Konversi transparan ke latar belakang putih solid.
    2. Upscale gambar 2x jika resolusinya kurang dari 2000px agar teks kecil
       di area logo, header, dan footer bisa terdeteksi dengan lebih baik.
    3. Output tetap dalam format BGR berwarna (tidak dikonversi ke grayscale),
       karena PaddleOCR dilatih dengan gambar berwarna dan memberikan akurasi
       lebih baik pada teks berwarna/kontras tinggi seperti putih di atas biru.
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
        # Background putih
        white_bg = np.ones_like(img[:, :, :3]) * 255

        # Pisahkan warna (BGR)
        color = img[:, :, :3]

        # Gabungkan warna asli dengan background putih sesuai alpha
        img_bgr = np.zeros_like(color)
        for c in range(3):
            img_bgr[:, :, c] = (alpha * color[:, :, c] + (1 - alpha) * white_bg[:, :, c])
        img = img_bgr.astype(np.uint8)

    # Pastikan format BGR 3 channel (bukan grayscale 1 channel) sebelum resize
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    # Upscale 2x hanya untuk gambar yang benar-benar kecil (< 800px).
    # Gambar poster normal sudah cukup besar sehingga tidak perlu di-upscale,
    # karena upscaling pada gambar besar justru memperlambat proses OCR tanpa
    # manfaat akurasi yang signifikan.
    h, w = img.shape[:2]
    if max(h, w) < 800:
        img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Kembalikan gambar BGR berwarna langsung ke PaddleOCR (tanpa konversi grayscale/binarisasi).
    # Model PP-OCRv6 dilatih pada data berwarna sehingga input berwarna lebih optimal.
    return img

def extract_text_from_image(image_path: str) -> str:
    """
    Mengekstrak seluruh teks yang ditemukan di dalam gambar menggunakan PaddleOCR,
    dengan preprocessing OpenCV.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File gambar tidak ditemukan di path: {image_path}")
        
    try:
        # Gunakan lock thread-safety untuk mencegah tabrakan memori di tingkat engine AI (C++)
        with ocr_lock:
            # Preprocessing gambar
            processed_img = preprocess_image(image_path)
            
            ocr = get_ocr_model()
            # Kirim hasil array OpenCV ke OCR, bukan path file-nya lagi
            result = ocr.ocr(processed_img)
            
            extracted_lines = []
            if result and len(result) > 0:
                res = result[0]
                if isinstance(res, dict):
                    # Format dictionary (PaddleOCR / PaddleX)
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
