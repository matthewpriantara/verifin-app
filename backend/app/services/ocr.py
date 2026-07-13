import os
import cv2
import logging
from paddleocr import PaddleOCR
import numpy as np

# Matikan logging debug dari PaddleOCR
logging.getLogger("ppocr").setLevel(logging.ERROR)

ocr_model = None

def get_ocr_model():
    global ocr_model
    if ocr_model is None:
        # Gunakan mode deteksi yang lebih peka, biarkan use_angle_cls=True untuk tes
        # lang='en' atau 'id' (jika ada modelnya)
        ocr_model = PaddleOCR(use_angle_cls=True, lang='en')
    return ocr_model

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Memproses gambar dengan OpenCV agar mudah dibaca oleh OCR:
    1. Konversi transparan ke latar belakang putih solid.
    2. Konversi ke Grayscale agar fokus ke kontras tulisan.
    """
    # Gunakan IMREAD_UNCHANGED untuk membaca Alpha Channel (transparansi)
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"OpenCV gagal membaca gambar di {image_path}")

    # Jika gambar punya transparansi (4 channels: BGRA), ubah ke BGR dengan background putih
    if img.shape[-1] == 4:
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

    # Convert ke Grayscale (Hitam Putih)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Ubah kembali ke 3 channel (BGR) karena PaddleOCR/PaddleX membutuhkan format 3 channel
    gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    return gray_bgr

def extract_text_from_image(image_path: str) -> str:
    """
    Mengekstrak seluruh teks yang ditemukan di dalam gambar menggunakan PaddleOCR,
    dengan preprocessing OpenCV.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File gambar tidak ditemukan di path: {image_path}")
        
    try:
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
