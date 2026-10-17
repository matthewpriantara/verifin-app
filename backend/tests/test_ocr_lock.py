import threading

from app.services import ocr


def test_ocr_lock_is_reentrant_so_cold_model_load_does_not_deadlock(monkeypatch):
    # Simulasikan model belum dimuat: get_ocr_model() dipanggil saat lock sudah dipegang.
    monkeypatch.setattr(ocr, "ocr_model", None)
    monkeypatch.setattr(ocr, "PaddleOCR", lambda **kw: "model-palsu")
    done = threading.Event()

    def run():
        with ocr.ocr_lock:
            assert ocr.get_ocr_model() == "model-palsu"
        done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    assert done.wait(timeout=5), "get_ocr_model() macet saat lock sudah dipegang"
