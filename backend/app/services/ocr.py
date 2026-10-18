import os
import cv2
import logging
from paddleocr import PaddleOCR
import numpy as np
import threading
import time

logging.getLogger("ppocr").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

ocr_model = None
# RLock: extract_text_from_image memegang lock ini lalu memanggil get_ocr_model(),
# yang juga mengambilnya saat model belum dimuat. Lock biasa akan deadlock di situ.
ocr_lock = threading.RLock()

def get_ocr_model():
    global ocr_model
    if ocr_model is None:
        with ocr_lock:
            if ocr_model is None:
                # Model rekognisi "en" (PP-OCRv4). Model "latin" v3 yang dipakai lang="id" sering
                # menghapus spasi pada judul berhuruf besar ("LOWONGANKERJA", "GLOBALSINERGI"),
                # sehingga nama perusahaan yang dicari di web jadi salah. Bahasa Indonesia tidak
                # memakai diakritik, jadi kamus "en" cukup.
                ocr_model = PaddleOCR(
                    use_angle_cls=False,
                    lang="en",
                    enable_mkldnn=False,
                    det_db_thresh=0.2,
                    det_db_box_thresh=0.4,
                    det_db_unclip_ratio=1.8,
                    rec_batch_num=6,
                )
    return ocr_model

def enhance_contrast(img_bgr: np.ndarray) -> np.ndarray:
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
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"OpenCV gagal membaca gambar di {image_path}")
    h, w = img.shape[:2]
    if h > 4000 or w > 4000:
        raise ValueError(f"Resolusi gambar terlalu besar ({w}x{h}px). Maksimal resolusi adalah 4000x4000px.")
    if len(img.shape) == 3 and img.shape[-1] == 4:
        alpha = img[:, :, 3] / 255.0
        white_bg = np.ones_like(img[:, :, :3]) * 255
        color = img[:, :, :3]

        img_bgr = np.zeros_like(color)
        for c in range(3):
            img_bgr[:, :, c] = (alpha * color[:, :, c] + (1 - alpha) * white_bg[:, :, c])
        img = img_bgr.astype(np.uint8)

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    h, w = img.shape[:2]
    if max(h, w) < 600:
        img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        h, w = img.shape[:2]
    max_side = 1000
    if max(h, w) > max_side:
        scale = max_side / float(max(h, w))
        img = cv2.resize(
            img,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )

    img = enhance_contrast(img)
    img = cv2.copyMakeBorder(
        img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )
    return img

def _box_bounds(box) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return min(xs), min(ys), max(xs), max(ys)


def order_text_by_layout(items: list[tuple[list, str]]) -> str:
    """Susun hasil OCR mengikuti tata letak poster, bukan urutan deteksi mentah.

    PaddleOCR mengurutkan kotak per baris dari atas ke bawah, sehingga teks dari kolom berbeda
    tercampur ("PT.INDOKARYA", "KERJA STABIL", "GLOBAL SINERGI"). Di sini kotak dikelompokkan
    menjadi blok: kotak yang bertumpuk secara vertikal dengan jarak kecil dan saling tumpang-tindih
    secara horizontal dianggap satu blok. Blok diurutkan per pita baris lalu dari kiri ke kanan;
    kotak dalam blok yang sejajar digabung dengan spasi. Antarblok dipisah baris kosong.
    """
    boxes = []
    for box, text in items:
        text = (text or "").strip()
        if len(text) <= 1:
            continue
        x0, y0, x1, y1 = _box_bounds(box)
        boxes.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "h": max(1.0, y1 - y0), "text": text})
    if not boxes:
        return ""

    parent = list(range(len(boxes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            h_overlap = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
            if h_overlap <= 0:
                continue
            gap = max(a["y0"], b["y0"]) - min(a["y1"], b["y1"])
            if gap < 0.8 * min(a["h"], b["h"]):
                parent[find(i)] = find(j)

    groups: dict[int, list[dict]] = {}
    for i, b in enumerate(boxes):
        groups.setdefault(find(i), []).append(b)

    blocks = []
    for members in groups.values():
        members.sort(key=lambda b: (b["y0"], b["x0"]))
        rows: list[list[dict]] = []
        for b in members:
            row = rows[-1] if rows else None
            if row:
                ref = row[0]
                v_overlap = min(ref["y1"], b["y1"]) - max(ref["y0"], b["y0"])
                if v_overlap > 0.5 * min(ref["h"], b["h"]):
                    row.append(b)
                    continue
            rows.append([b])
        lines = [" ".join(b["text"] for b in sorted(r, key=lambda b: b["x0"])) for r in rows]
        blocks.append({
            "x0": min(b["x0"] for b in members),
            "y0": min(b["y0"] for b in members),
            "h": members[0]["h"],
            "text": "\n".join(lines),
        })

    blocks.sort(key=lambda b: b["y0"])
    ordered: list[dict] = []
    band: list[dict] = []
    for blk in blocks:
        if band and blk["y0"] > band[0]["y0"] + band[0]["h"]:
            ordered.extend(sorted(band, key=lambda b: b["x0"]))
            band = []
        band.append(blk)
    ordered.extend(sorted(band, key=lambda b: b["x0"]))
    return "\n\n".join(b["text"] for b in ordered)


def extract_text_from_image(image_path: str, metrics: dict | None = None) -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File gambar tidak ditemukan di path: {image_path}")

    try:
        started = time.perf_counter()
        with ocr_lock:
            preprocess_started = time.perf_counter()
            processed_img = preprocess_image(image_path)
            preprocess_elapsed = time.perf_counter() - preprocess_started
            model_started = time.perf_counter()
            ocr = get_ocr_model()
            model_elapsed = time.perf_counter() - model_started
            inference_started = time.perf_counter()
            result = ocr.ocr(processed_img)
            inference_elapsed = time.perf_counter() - inference_started

            items: list[tuple[list, str]] = []
            if result and len(result) > 0 and result[0]:
                res = result[0]
                if isinstance(res, dict):
                    items = list(zip(res.get("rec_polys", []), res.get("rec_texts", [])))
                elif isinstance(res, list):
                    items = [(line[0], line[1][0]) for line in res if line and len(line) > 1]
            text = order_text_by_layout(items)
            line_count = sum(1 for l in text.splitlines() if l.strip())

            if metrics is not None:
                metrics.update({
                    "preprocess_sec": round(preprocess_elapsed, 3),
                    "model_init_sec": round(model_elapsed, 3),
                    "inference_sec": round(inference_elapsed, 3),
                    "total_sec": round(time.perf_counter() - started, 3),
                    "image_shape": list(processed_img.shape),
                    "line_count": line_count,
                })
            return text
    except Exception as e:
        logger.error("[OCR Error] Gagal mengekstrak gambar: %s", e)
        raise e
