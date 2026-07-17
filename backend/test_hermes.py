import asyncio
import sys
import json
from app.services.llm.hermes_reasoner import analyze_with_hermes, check_ollama_status

# Mock data untuk pengujian
MOCK_RAW_TEXT = """
LOWONGAN PEKERJAAN SEGERA!!!
PT INDO JAYA MAKMUR membuka lowongan untuk posisi Administrasi Kantor.
Gaji yang ditawarkan sangat menarik: Rp 8.500.000 - Rp 12.000.000 per bulan.
Persyaratan:
- Pria/Wanita, Usia maksimal 35 tahun
- Pendidikan minimal SMA/SMK
- Tanpa pengalaman dipersilakan melamar
Kirim CV dan lamaran Anda ke email kami: indojayamakmur.recruitment@gmail.com
Untuk informasi lebih lanjut hubungi Bpk. Andi di WhatsApp: 0812-9876-5432
Alamat kantor interview: Jl. Malioboro No. 123, Gedong Tengen, Kota Yogyakarta.
"""

MOCK_ENTITIES = {
    "companies": ["PT Indo Jaya Makmur"],
    "contacts": ["+6281298765432"],
    "emails": ["indojayamakmur.recruitment@gmail.com"],
    "urls": [],
    "addresses": ["Jl. Malioboro No. 123, Gedong Tengen, Kota Yogyakarta"],
    "salaries": ["Rp 8.500.000 - Rp 12.000.000"]
}

# Mock data OSINT yang mensimulasikan kegagalan SPF/DMARC (karena pakai Gmail gratisan)
# dan Alamat yang ditemukan di peta tapi nama bisnis tidak terdaftar di lokasi tersebut.
MOCK_OSINT = {
    "domain": {
        "age_years": None,
        "created_at": "Tidak diketahui",
        "is_new": False
    },
    "email_security": {
        "spf_active": False,
        "dmarc_active": False
    },
    "address_validations": [
        {
            "address_input": "Jl. Malioboro No. 123, Gedong Tengen, Kota Yogyakarta",
            "address_found": True,
            "address_details": {
                "display_name": "Jalan Malioboro, Sosromenduran, Gedong Tengen, Yogyakarta, Daerah Istimewa Yogyakarta, 55271, Indonesia"
            },
            "business_found": False,
            "business_details": {
                "nearby_businesses": ["Hotel Mutiara", "Malioboro Mall", "Batik Keris"]
            },
            "neutral_notes": [
                "Nama perusahaan 'PT Indo Jaya Makmur' tidak terdaftar di OpenStreetMap sekitar alamat ini."
            ]
        }
    ]
}

async def run_test():
    print("=" * 60)
    print("🤖 MEMULAI PENGUJIAN INTEGRASI LLM HERMES (OLLAMA)")
    print("=" * 60)
    
    # 1. Cek Status Ollama
    print("[1] Memeriksa koneksi ke Ollama...")
    status = check_ollama_status()
    
    if not status["ollama_running"]:
        print("\n❌ ERROR: Ollama tidak terdeteksi berjalan di http://localhost:11434")
        print("💡 Silakan jalankan Ollama terlebih dahulu di komputer Anda.")
        print("💡 Caranya:")
        print("   1. Buka aplikasi Ollama di Mac Anda.")
        print("   2. Atau jalankan di terminal: open -a Ollama (atau: ollama serve)")
        print("\nDetail Status:", status)
        sys.exit(1)
        
    print(f"✅ Ollama berjalan di http://localhost:11434")
    print(f"   Model yang tersedia di sistem Anda: {status['available_models']}")
    
    # Cek ketersediaan model target
    target_model = status["target_model"]
    if not status["hermes_available"]:
        print(f"\n⚠️ PERINGATAN: Model '{target_model}' belum di-pull di Ollama Anda!")
        print("💡 Jalankan perintah berikut di terminal Anda untuk mengunduh model:")
        print(f"   ollama pull {target_model}")
        print("\nAtau Anda bisa mengubah model target di file 'app/services/llm/hermes_reasoner.py'")
        print("pada variabel 'OLLAMA_MODEL' ke model yang sudah Anda miliki di atas.")
        sys.exit(1)
        
    print(f"✅ Model target '{target_model}' siap digunakan.")
    print("-" * 60)
    
    # 2. Jalankan Analisis Hermes
    print(f"[2] Mengirim data pengujian ke model '{target_model}'...")
    print("    Proses reasoning lokal sedang berjalan (ini dapat memakan waktu beberapa detik)...")
    
    try:
        result = await analyze_with_hermes(
            entities=MOCK_ENTITIES,
            osint_results=MOCK_OSINT,
            raw_text=MOCK_RAW_TEXT
        )
        
        print("\n--- HASIL ANALISIS HERMES LLM (JSON) ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("----------------------------------------")
        
        # Validasi sederhana
        if result.get("verdict") == "ERROR":
            print("\n❌ Uji coba gagal: AI mengembalikan error.")
        else:
            print(f"\n🎉 Uji coba sukses! Verdict: {result.get('verdict')} (Score: {result.get('risk_score')})")
            
    except Exception as e:
        print(f"\n❌ Terjadi error saat melakukan request ke Ollama: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_test())
