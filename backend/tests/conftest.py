import os
import sys
import pytest

# Ensure backend root is on sys.path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


@pytest.fixture
def sample_legit_text() -> str:
    return """The Biker Shop
membuka lowongan
Marketing Officer - Sales Counter - Mekanik Motor
The Biker Shop saat ini membuka lowongan kerja untuk posisi sebagai :

Marketing Officer
Sales Counter
Mekanik Motor
Ringkasan
Pendidikan: SMA / SMK
Pengalaman: 0 - 2 Tahun
Gender: Pria/Wanita
Besaran Gaji: Kompetitif
Lokasi Kerja: The Biker Shop Jogja, Jl. Parangtritis No.38, Mantrijeron, Kec. Mantrijeron, Kota Jogja, DIY - 55143
Kirim Lamaran
Formulir: https://forms.gle/N6mfqUbVnC2JF68y6
Email: hrdthebikershop@gmail.com
No. Telepon: +6285738325536"""


@pytest.fixture
def sample_scam_text() -> str:
    return """URGENT HIRING! Kerja dari rumah gaji 8-15 juta per bulan. Tidak perlu pengalaman.
Daftar sekarang bayar biaya administrasi Rp150.000 transfer ke rekening BCA 1234567890 an. ADMIN LOKER.
WA langsung ke 082134567890. Kerja di luar negeri Malaysia Singapore gaji dollar. Berangkat minggu ini!
Daftar via: bit.ly/daftarloker2026"""


@pytest.fixture
def sample_entities() -> dict:
    return {
        "companies": ["The Biker Shop"],
        "emails": ["hrdthebikershop@gmail.com"],
        "phones": ["+6285738325536"],
        "urls": ["https://forms.gle/N6mfqUbVnC2JF68y6"],
        "addresses": ["Jl. Parangtritis No.38, Mantrijeron, Kec. Mantrijeron, Kota Jogja, DIY - 55143"],
        "salaries": ["Kompetitif"],
        "job_titles": ["Marketing Officer", "Sales Counter", "Mekanik Motor"],
    }


@pytest.fixture
def sample_osint_results() -> dict:
    return {
        "phones": [
            {
                "phone": "+6285738325536",
                "reported_fraud": False,
                "reports_count": 0,
                "provider": "Kaspersky Who Calls / Kredibel",
                "status": "VALID",
            }
        ],
        "domain": {
            "domain": "forms.gle",
            "age_years": 10.5,
            "is_new": False,
            "status": "VALID",
        },
        "web": {
            "query": "The Biker Shop Jogja",
            "risk_flags": [],
            "safe_flags": ["Brand terdaftar resmi"],
            "status": "FOUND",
        },
        "address_validations": [
            {
                "query": "Jl. Parangtritis No.38, Mantrijeron, Kota Jogja",
                "found": True,
                "lat": -7.818,
                "lon": 110.366,
                "status": "FOUND",
            }
        ],
        "fraud_network": {
            "entity_in_fraud_network": False,
            "total_case_count": 1,
            "fraud_case_count": 0,
        },
    }


@pytest.fixture
def sample_historical_cases() -> list[dict]:
    return [
        {
            "id": "case-001",
            "verdict": "BAHAYA",
            "risk_score": 92,
            "phones": ["081234567890", "+6282199887766"],
            "emails": ["recruitment.fakecorp@gmail.com"],
            "companies": ["PT SCAM INDONESIA", "GLOBAL LOGISTICS JAYA"],
            "urls": ["https://bit.ly/scam-apply", "http://fakejob-portal.site"],
            "created_at": "2026-08-01T10:00:00Z",
        },
        {
            "id": "case-002",
            "verdict": "AMAN",
            "risk_score": 15,
            "phones": ["+6285738325536"],
            "emails": ["hrdthebikershop@gmail.com"],
            "companies": ["The Biker Shop"],
            "urls": ["https://thebikershop.co.id"],
            "created_at": "2026-08-05T14:30:00Z",
        },
        {
            "id": "case-003",
            "verdict": "BAHAYA",
            "risk_score": 88,
            "phones": ["+6282199887766"],  # Sybil reuse of phone from case-001
            "emails": ["admin.tppo@yahoo.com"],
            "companies": ["PT SUMBER CUAN SEJAHTERA"],
            "urls": ["https://forms.gle/phishing-form"],
            "created_at": "2026-08-10T09:15:00Z",
        },
    ]
