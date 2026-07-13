import asyncio
from app.services.ocr import extract_text_from_image
from app.services.ner import extract_entities_from_text

# --- 1. Testing OCR & NER Gabungan (Dari Gambar) ---
def test_image_pipeline(image_path: str):
    print(f"\n{'='*50}")
    print(f"🖼️ MENGUJI GAMBAR: {image_path}")
    print(f"{'='*50}")
    
    try:
        # Step 1: Ekstrak teks dari gambar pakai PaddleOCR
        print("[1] Menjalankan OCR...")
        extracted_text = extract_text_from_image(image_path)
        print("\n--- Hasil Teks Kasar (OCR) ---")
        print(extracted_text)
        print("------------------------------\n")
        
        # Step 2: Ekstrak entitas dari teks kasar pakai IndoBERT NER & Regex
        print("[2] Menjalankan NER & Regex Parsing...")
        entities = extract_entities_from_text(extracted_text)
        
        print("\n--- Hasil Ekstraksi Entitas Terstruktur ---")
        for key, value in entities.items():
            print(f"- {key.capitalize()}: {value}")
            
    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")

# --- 2. Testing NER Langsung (Dari Teks) ---
def test_text_pipeline():
    print(f"\n{'='*50}")
    print("📝 MENGUJI TEKS LANGSUNG")
    print(f"{'='*50}")
    
    # Contoh teks loker palsu yang sering beredar
    sample_text = """
    DIBUTUHKAN SEGERA!!!
    PT Pertamina Persero membuka lowongan pekerjaan untuk posisi Staff Administrasi.
    Gaji Rp 5.000.000 - Rp 8.000.000 per bulan.
    Syarat:
    - Pria/Wanita
    - Minimal SMA/SMK
    Kirim CV anda ke email: rekrutmen-pertamina@gmail.com atau daftar di link www.karir-pertamina-tbk.com
    Hubungi HRD Bpk. Budi di nomor WA: 081234567890
    Alamat Walk-in Interview: Jalan Jenderal Sudirman Kav 12, Jakarta Selatan.
    """
    
    print("\n--- Teks Input ---")
    print(sample_text)
    print("------------------\n")
    
    print("[1] Menjalankan NER & Regex Parsing...")
    entities = extract_entities_from_text(sample_text)
    
    print("\n--- Hasil Ekstraksi Entitas Terstruktur ---")
    for key, value in entities.items():
        print(f"- {key.capitalize()}: {value}")

if __name__ == "__main__":
    # Kita tes pakai .png sesuai nama file di error log kamu
    test_image_pipeline("loker_test.png")
