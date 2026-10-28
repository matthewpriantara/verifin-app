from __future__ import annotations

import logging
import re
from typing import Any

from app.services.ner import strip_negated_fee

logger = logging.getLogger(__name__)

# Keywords & Regex patterns for Indonesian Job Scams (Paper22, GASA 2024, UNODC 2023)
# Jarak antarkata dibatasi dalam satu kalimat; ".*?" lama bisa menyambung "biaya" di awal teks
# dengan "pelatihan" di paragraf lain.
_GAP = r"[^.\n!?;]{0,60}?"
_FEE_PATTERNS = [
    rf"\b(?:biaya|uang|dana|deposit|tarif|bayar|transfer)\s+{_GAP}(?:pendaftaran|administrasi|seleksi|tiket|akomodasi|travel|seragam|pelatihan|rekening|kembali|reimburse|proses)\b",
    rf"\b(?:mentransfer|transfer|bayar|setor)\s+{_GAP}(?:rekening|biro|travel|panitia|bendahara|biaya|dana|ovo|gopay|shopeepay)\b",
    rf"\b(?:tiket|akomodasi|transportasi)\s+{_GAP}(?:wajib|harus|ditransfer|dibayar|reimburse)\b",
    r"\b(?:uang\s*muka|uang\s*jaminan|deposit\s*awal|biaya\s*registrasi|biaya\s*formulir)\b",
]

_FOREIGN_WORK_PATTERNS = [
    r"\b(?:kamboja|cambodia|myanmar|laos|filipina|philippines|vietnam|thailand)\b",
    # Negara tujuan pekerja migran Indonesia yang paling sering dipakai modus penempatan ilegal.
    r"\b(?:jepang|japan|korea|taiwan|malaysia|hong\s*kong|singapura|singapore|brunei|arab\s+saudi|saudi|qatar|dubai|uni\s+emirat|turki|polandia|australia)\b",
    r"\b(?:luar\s*negeri|overseas|tki|pmi\s+ke)\b",
]

_WHATSAPP_APPLY_PATTERNS = [
    r"(?:daftar|hubungi|chat|kirim cv|kirim lamaran|kirim format)\s+(?:ke\s+)?(?:wa|whatsapp)\b",
    r"wa\.me/\d+",
    # "Kirim CV: 0896-...", "pesan WhatsApp", "WA: 0812..."
    r"(?:kirim|hubungi|daftar|chat)\s*(?:cv|lamaran|berkas)?[^\n\d]{0,25}(?:\+62|62|0)8\d",
    r"(?:pesan|via|lewat|melalui)\s+(?:wa|whatsapp)\b",
    r"\b(?:wa|whatsapp)\b\s*[:\-]?\s*(?:\+62|62|0)8\d",
    # "silakan WhatsApp admin", "konfirmasi kehadiran via WhatsApp", "daftar lewat link di bio"
    r"(?:silakan|silahkan|konfirmasi\s+\w+\s+(?:via|ke))\s+(?:wa|whatsapp)\b",
    r"\b(?:wa|whatsapp)\s+admin\b",
    # "link di bio", "link di. bio profil", "klik link dibio", "link bio", "link di profil"
    r"\blink\s+(?:yang\s+ada\s+)?(?:di\W*)?(?:bio|profil)\b",
]

# Nama BUMN/perusahaan terbuka. Nama ini mudah dicatut, jadi tidak boleh menjadi sinyal aman;
# rekrutmen resminya lewat portal karier, bukan WhatsApp admin atau tautan di bio.
_BRAND_CLAIM = re.compile(r"\b(?:bumn|persero|tbk)\b")

# Jalur lamaran resmi selain WhatsApp: email atau tautan formulir/portal.
_OFFICIAL_CHANNEL = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|https?://|forms\.gle|www\.", re.I)

# Lamaran diarahkan ke Telegram (masukan praktisi portal loker, 27 Okt 2026: "90% pasti penipuan").
# Kanal sah loker Indonesia: WhatsApp, email, formulir, atau walk-in.
# B4: "Tele"/"tg" adalah singkatan yang lazim di poster; handle tanpa titik dua juga dihitung.
_TELEGRAM_MENTION = re.compile(r"\btelegram\b|\btele\b|\btg\b|t\.me/|telegram\.me/", re.I)
_TELEGRAM_APPLY_PATTERNS = [
    r"(?:https?://)?(?:t|telegram|telegram\.dog)\.me/[\w+%-]+",
    r"\btelegram\s*[:@]\s*@?[a-z0-9_]{3,}",
    r"\btelegram\b[^.\n!?;]{0,12}@[a-z0-9_]{4,}",
    r"\b(?:tele|tg)\b\s*[:=@]\s*@?[a-z0-9_]{3,}",
    r"\b(?:via|lewat|melalui|hubungi|chat|kontak|dm|join|gabung|grup|group|channel|kanal|masuk)\b"
    r"[^.\n!?;]{0,25}\b(?:telegram|tele|tg)\b",
    r"\b(?:telegram|tele|tg)\b[^.\n!?;]{0,25}\b(?:daftar|lamar|melamar|apply|hubungi|chat|kirim|admin|hrd)\b",
    r"\b(?:info|detail|keterangan)\b[^.\n!?;]{0,20}\b(?:telegram|tele|tg)\b",
]
# Negasi hanya dihitung bila kata negasinya MENDAHULUI "telegram" di kalimat yang sama.
# "Daftar lewat Telegram @x, dijamin bukan penipuan" bukan peringatan, melainkan ajakan.
_TELEGRAM_NEGATION_BEFORE = re.compile(
    r"\b(?:tidak|bukan|tanpa|jangan|hindari|awas|waspada|hati-hati|penipuan|scam|modus|hoaks)\b"
    r"[^.\n!?;]{0,40}$",
    re.I,
)
_TELEGRAM_HANDLE_OR_LINK = re.compile(r"@[a-z0-9_]{3,}|t\.me/|telegram\.me/", re.I)


_WALK_IN = re.compile(
    r"\bwalk[\s-]?in\b|\b(?:wawancara|interview|tes|seleksi)\s+(?:langsung|tatap\s+muka|di\s+kantor)"
    r"|\bdatang\s+langsung\s+(?:ke|di)\b|\bantar\s+(?:langsung\s+)?lamaran\s+ke\b"
)


def _has_telegram_apply(text_lower: str) -> bool:
    segments = re.split(r"(?<=[.!?])\s+|\n+", text_lower)
    for segment in segments:
        mention = _TELEGRAM_MENTION.search(segment)
        if not mention:
            continue
        before = segment[: mention.start()]
        has_handle = bool(_TELEGRAM_HANDLE_OR_LINK.search(segment))
        # Peringatan ("tidak melalui Telegram", "waspada penipuan via Telegram") bukan ajakan.
        # Bila kalimat itu tetap memuat handle/tautan, negasi diabaikan: bisa jadi penipu menulis
        # "dijamin bukan penipuan" tepat setelah handle.
        if _TELEGRAM_NEGATION_BEFORE.search(before) and not has_handle:
            continue
        if any(re.search(pattern, segment) for pattern in _TELEGRAM_APPLY_PATTERNS):
            return True
    return False

# Badan usaha yang disebut namanya: "PT Maju Jaya", "CV. Sinar", "UD Makmur", "Koperasi ...".
# "CV" sebagai daftar riwayat hidup ("kirim CV", "CV terbaru", "CV dan KTP") tidak dihitung.
_NAMED_ENTITY = re.compile(
    r"\b(?:pt|ud|pd|koperasi|yayasan|perum|persero)\.?\s+[a-z0-9]{2,}"
    r"|(?<!kirim )(?<!kirimkan )(?<!lampirkan )(?<!sertakan )(?<!upload )(?<!unggah )(?<!berkas )"
    r"\bcv\.?\s+(?!(?:ke|dan|via|lewat|melalui|terbaru|lengkap|anda|kamu|lamaran|serta|beserta|&)\b)[a-z]{2,}"
    r"|\bnama\s+(?:perusahaan|usaha|toko|instansi)(?:\s*/\s*\w+)?\s*[:\-]\s*\S"
)

# Teks mengaku sebagai pemberi kerja berbadan usaha (pabrik, perusahaan, kantor, gudang).
_EMPLOYER_CLAIM = re.compile(r"\b(?:pabrik|perusahaan|kantor|gudang|factory|company|manufaktur)\b")

_FRAUD_KEYWORDS = [
    r"\b(?:biaya\s*pendaftaran|biaya\s*administrasi|uang\s*jaminan|deposit\s*awal|transfer\s*ke\s*rekening)\b",
    r"\b(?:biro\s*perjalanan|travel\s*agent|agen\s*perjalanan|tiket\s*pesawat|penggantian\s*biaya|reimburse\w*)\b",
    r"\b(?:gaji\s*fantastis|penghasilan\s*tak\s*terbatas|unlimited\s*income|tanpa\s*ijazah|tanpa\s*pengalaman)\b",
    r"\b(?:like\s*dan\s*subscribe|like\s*follow|paruh\s*waktu\s*online|tugas\s*harian|buka\s*tugas\s*vip)\b",
]

_SAFE_KEYWORDS = [
    r"\b(?:bpjs|thr|asuransi|pkwt|pkwtt|kontrak\s*kerja)\b",
    r"\b(?:portal\s*karir|karir\s*resmi|walk\s*in\s*interview|kualifikasi|syarat\s*pendidikan)\b",
    # "Gratis" saja tidak dihitung: poster palsu juga sering menulis "DAFTAR GRATIS!".
    r"\b(?:tidak\s*dipungut\s*biaya|tidak\s*ada\s*biaya\s*apapun)\b",
]

# Sinyal eksplisit lowongan kerja / rekrutmen (Audit 007 temuan 2)
_JOB_POSTING_SIGNALS = [
    r"\b(?:lowongan|loker|dibutuhkan|dicari|we\s*are\s*hiring|recruitment|rekrutmen|hiring|open\s*recruitment|open\s*position|posisi|job\s*vacancy|karir|career|kesempatan\s*berkarir)\b",
    r"\b(?:kualifikasi|persyaratan|syarat\s*kualifikasi|kriteria|requirement|requirements|qualification|qualifications)\b",
    r"\b(?:kirim\s*(?:cv|lamaran|resume|berkas)|send\s*(?:cv|resume)|apply\s*(?:here|via|now)|melamar|surat\s*lamaran|daftar\s*sekarang)\b",
    r"\b(?:gaji|salary|upah|benefit|fasilitas|uang\s*makan|uang\s*transport|tunjangan|bpjs|thr)\b",
    r"\b(?:deskripsi\s*pekerjaan|job\s*desc|tanggung\s*jawab|tugas|penempatan|lokasi\s*kerja|jam\s*kerja|shift)\b",
    r"\b(?:walk\s*in\s*interview|interview|seleksi\s*kerja|tahapan\s*seleksi)\b",
    r"\b(?:fresh\s*graduate|pengalaman\s*(?:kerja|min|minimal)|pendidikan\s*minimal|usia\s*maksimal|pria\s*/\s*wanita)\b",
    r"\b(?:staff|staf|admin|operator|supervisor|manager|kasir|barista|waiter|waitress|driver|supir|kurir|teknisi|programmer|designer|sales|marketing|security|satpam)\b",
]

# Sinyal artikel berita / pers
_NEWS_ARTICLE_SIGNALS = [
    r"\b(?:wartawan|jurnalis|diberitakan|dilaporkan|redaksi|pemred|narasumber)\b",
    r"\b(?:ujar|tutur|kata|jelas|pungkas|terang)\w*\s+(?:beliau|dia|kepala|menteri|direktur|pejabat|petugas|kapolres|humas)\b",
    r"\b(?:sebagaimana\s+dikutip|dilansir\s+dari|menurut\s+keterangan|dikutip\s+dari)\b",
    r"\b(?:detikcom|kompas\.com|tribunnews|tempo\.co|antara|cnn\s*indonesia|liputan6|kumparan)\b",
]

# Sinyal invoice / transaksi komersial bukan loker
_INVOICE_SIGNALS = [
    r"\b(?:invoice|faktur|kwitansi|tanda\s*terima|nota\s*penjualan|pembayaran\s*tagihan|rekening\s*koran|bukti\s*transfer|tagihan\s*sebesar|total\s*bayar)\b",
    r"\b(?:subtotal|diskon|jatuh\s*tempo|due\s*date|nomor\s*pesanan|order\s*id|status\s*pembayaran)\b",
]


def check_content_safety_and_type(text: str, companies: list[str] | None = None) -> dict[str, Any]:
    """Deteksi gerbang isi lowongan (Audit 007 temuan 2):
    Mendeteksi apakah teks merupakan lowongan kerja, artikel berita, invoice, atau teks non-loker acak.
    """
    text_lower = (text or "").lower()
    words = text_lower.split()
    word_count = len(words)

    job_hits = sum(1 for p in _JOB_POSTING_SIGNALS if re.search(p, text_lower))
    news_hits = sum(1 for p in _NEWS_ARTICLE_SIGNALS if re.search(p, text_lower))
    invoice_hits = sum(1 for p in _INVOICE_SIGNALS if re.search(p, text_lower))

    # Kasus teks sangat pendek (< 10 kata)
    if word_count < 10:
        if job_hits == 0:
            return {
                "is_job_posting": False,
                "confidence": "tinggi",
                "content_type": "non_job_text",
                "text_too_short": True,
                "job_signal_count": 0,
                "warning": "Teks terlalu pendek dan tidak memuat penanda posisi atau lowongan kerja.",
            }
        else:
            return {
                "is_job_posting": True,
                "confidence": "sedang",
                "content_type": "job_posting_minimal",
                "text_too_short": True,
                "job_signal_count": job_hits,
                "warning": "Informasi lowongan sangat sedikit untuk dianalisis secara akurat.",
            }

    # Berita / artikel umum
    if news_hits >= 2 and job_hits <= 1:
        return {
            "is_job_posting": False,
            "confidence": "tinggi",
            "content_type": "news_article",
            "text_too_short": False,
            "job_signal_count": job_hits,
            "warning": "Teks terdeteksi sebagai artikel berita atau publikasi pers, bukan lowongan kerja.",
        }

    # Invoice / faktur komersial
    if invoice_hits >= 2 and job_hits == 0:
        return {
            "is_job_posting": False,
            "confidence": "tinggi",
            "content_type": "invoice_receipt",
            "text_too_short": False,
            "job_signal_count": 0,
            "warning": "Teks terdeteksi sebagai faktur tagihan/invoice, bukan lowongan kerja.",
        }

    # Teks umum tanpa sinyal rekrutmen sama sekali
    if job_hits == 0 and not bool(re.search(r"\b(gaji\w*|salary|upah)\b", text_lower)):
        return {
            "is_job_posting": False,
            "confidence": "sedang",
            "content_type": "general_text",
            "text_too_short": False,
            "job_signal_count": 0,
            "warning": "Teks tidak menunjukkan karakteristik penawaran kerja atau proses rekrutmen.",
        }

    # Campuran loker + teks acak/berita
    has_mixed = news_hits >= 2 and job_hits >= 2

    return {
        "is_job_posting": True,
        "confidence": "tinggi",
        "content_type": "job_posting",
        "text_too_short": False,
        "job_signal_count": job_hits,
        "has_mixed_content": has_mixed,
        "warning": "Ada teks tambahan di luar lowongan kerja yang ikut terdeteksi." if has_mixed else None,
    }


def extract_behavioral_features(text: str, companies: list[str] | None = None) -> dict[str, Any]:
    """Sinyal perilaku dari teks lowongan.

    `companies` adalah nama perusahaan hasil NER; bila ada, lowongan dianggap menyebut badan usaha
    walaupun teksnya tidak memakai awalan PT/CV (mis. "HOTEL NEW SAPHIR").
    """
    text_lower = (text or "").lower()

    has_fee = any(re.search(p, strip_negated_fee(text_lower)) for p in _FEE_PATTERNS)
    has_foreign = any(re.search(p, text_lower) for p in _FOREIGN_WORK_PATTERNS)
    # Dihitung hanya bila WhatsApp satu-satunya jalur melamar; loker yang juga mencantumkan
    # email atau tautan resmi tidak dianggap "lamar via WA".
    has_wa = any(re.search(p, text_lower) for p in _WHATSAPP_APPLY_PATTERNS) and not _OFFICIAL_CHANNEL.search(text_lower)

    fraud_hits = sum(1 for p in _FRAUD_KEYWORDS if re.search(p, text_lower, re.I))
    safe_hits = sum(1 for p in _SAFE_KEYWORDS if re.search(p, text_lower, re.I))

    has_company = bool(companies) or bool(_NAMED_ENTITY.search(text_lower))
    has_address = bool(re.search(r"\b(?:jl|jln|jalan|gedung|gd|komplek|kompleks|ruko|kawasan)\b", text_lower))
    claims_employer = bool(_EMPLOYER_CLAIM.search(text_lower))
    has_salary = bool(re.search(r"\b(gaji\w*|salary|upah|honor)\b|rp\.?\s*\d", text_lower))

    return {
        "has_fee_request": bool(has_fee),
        "has_foreign_work": bool(has_foreign),
        "has_whatsapp_apply": bool(has_wa),
        "has_telegram_apply": _has_telegram_apply(text_lower),
        # Lamaran tatap muka di alamat fisik: modus pencatutan merek yang terlihat selalu daring.
        "has_walk_in": bool(_WALK_IN.search(text_lower)),
        "fraud_keyword_count": float(fraud_hits),
        "safe_keyword_count": float(safe_hits),
        "has_company": bool(has_company),
        "has_address": bool(has_address),
        "has_salary": bool(has_salary),
        "fee_no_company": bool(has_fee and not has_company),
        "salary_no_company": bool(has_salary and not has_company),
        # Mengaku pabrik/perusahaan tetapi tidak menyebut nama badan usaha yang bisa diperiksa.
        "anonymous_employer_claim": bool(claims_employer and not has_company),
        # Menyebut BUMN/Persero/Tbk tetapi pendaftaran hanya lewat WhatsApp atau tautan di bio.
        "brand_unofficial_channel": bool(_BRAND_CLAIM.search(text_lower) and has_wa),
        "word_count": float(len(text.split())),
        "char_count": float(len(text)),
    }


def classify_text(text: str, companies: list[str] | None = None) -> dict[str, Any]:
    behavioral = extract_behavioral_features(text, companies)
    content_meta = check_content_safety_and_type(text, companies)
    has_fee = behavioral.get("has_fee_request", False)
    has_foreign = behavioral.get("has_foreign_work", False)
    fraud_hits = behavioral.get("fraud_keyword_count", 0.0)
    safe_hits = behavioral.get("safe_keyword_count", 0.0)

    score = 15.0
    if has_fee:
        score += 45.0
    if has_foreign:
        score += 25.0
    score += min(30.0, fraud_hits * 10.0)
    score -= min(20.0, safe_hits * 5.0)
    score = max(0.0, min(100.0, score))

    if score >= 75.0 or has_fee:
        label = "BAHAYA"
    elif score >= 40.0 or has_foreign:
        label = "WASPADA"
    else:
        label = "AMAN"

    return {
        "enabled": True,
        "status": "RULE_BASED_HEURISTIC",
        "reason": "Taksonomi Pola Penipuan Kerja Indonesia (Paper22, GASA 2024, UNODC 2023)",
        "label": label,
        "nlp_score": score,
        "behavioral_features": behavioral,
        "content_validation": content_meta,
    }
