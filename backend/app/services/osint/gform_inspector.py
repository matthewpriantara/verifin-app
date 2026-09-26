"""
Google Form Inspector Module for Verifin OSINT.
Memfollow redirect shortlink (bit.ly, forms.gle), mengekstrak pertanyaan Google Form,
dan menganalisis indikator pertanyaan phishing / sensitif (No Rekening, PIN, KTP, Biaya Transfer).
"""


import json
import re
from typing import Any
from urllib.parse import unquote, urlparse

from scrapling.fetchers import Fetcher
from app.services.status_contract import COMPLETED, LOGIN_REQUIRED, PARSE_FAILED, UNAVAILABLE

# Kata kunci berisiko tinggi pada pertanyaan Google Form (Phishing / Keuangan / E-KTP)
PHISHING_KEYWORDS = {
    "rekening",
    "nomor rekening",
    "no rek",
    "no. rek",
    "cvv",
    "pin",
    "otp",
    "biaya",
    "bayar",
    "transfer",
    "deposit",
    "seragam",
    "biaya admin",
    "biaya tes",
    "travel",
    "tiket",
    "foto ktp",
    "scan ktp",
    "foto kk",
    "foto atm",
    "password",
    "kata sandi",
}

# Kata kunci normal formulir lamaran kerja
NORMAL_JOB_KEYWORDS = {
    "nama",
    "pendidikan",
    "alamat",
    "no hp",
    "whatsapp",
    "telepon",
    "pengalaman",
    "cv",
    "portofolio",
    "email",
    "posisi",
    "gaji",
}


def is_gform_url(url: str) -> bool:
    """Mengecek apakah URL merupakan Google Form atau shortlink loker umum."""
    u = (url or "").lower()
    return any(
        k in u
        for k in (
            "forms.gle",
            "docs.google.com/forms",
            "bit.ly",
            "tinyurl.com",
            "s.id",
            "linktr.ee",
        )
    )


import httpx


def inspect_gform(url: str) -> dict[str, Any]:
    """
    Mengunjungi URL Google Form / Shortlink, mem-parse judul, deskripsi & pertanyaan,
    lalu mendeteksi indikator risiko phishing / keuangan.
    """
    if not url:
        return {"is_gform": False, "risk_flags": [], "safe_flags": []}

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        target_url = url
        final_url = target_url

        def _resolve(u: str) -> tuple[str, int, str]:
            """Ikuti redirect; bila forms.gle menampilkan halaman interstitial
            Firebase Dynamic Links (proxy.link.app), ulangi dengan ?_imcp=1."""
            try:
                r0 = httpx.get(u, headers=headers, follow_redirects=False, timeout=5.0)
                loc = r0.headers.get("location")
                if loc:
                    return loc, r0.status_code, r0.text
                # Interstitial: status 200 tapi host proxy.link.app tanpa konten form
                if "proxy.link.app" in r0.text and "forms.gle" in u:
                    sep = "&" if "?" in u else "?"
                    u2 = f"{u}{sep}_imcp=1"
                    r1 = httpx.get(u2, headers=headers, follow_redirects=False, timeout=5.0)
                    loc1 = r1.headers.get("location")
                    if loc1:
                        return loc1, r1.status_code, r1.text
                    return u2, r1.status_code, r1.text
                return u, r0.status_code, r0.text
            except Exception:
                return u, 0, ""

        resolved, _, _ = _resolve(url)
        if resolved != url:
            target_url = resolved

        r = httpx.get(target_url, headers=headers, follow_redirects=True, timeout=8.0)
        final_url = str(r.url)
        html = r.text
        http_status = r.status_code
        # Check if bitly page html contains forms.gle
        match_gle = re.search(r"forms\.gle/[a-zA-Z0-9_-]+", html)
        if match_gle:
            gle_url = "https://" + match_gle.group(0)
            try:
                r_gle = httpx.get(gle_url, follow_redirects=False, timeout=5.0)
                loc_g = r_gle.headers.get("location")
                if loc_g:
                    final_url = loc_g
            except Exception:
                pass

        # Jika shortlink mengarahkan ke Google Form via URL login
        landed_on_login = "accounts.google.com" in final_url.lower()
        if "accounts.google.com" in html or landed_on_login:
            match_continue = re.search(
                r"continue=([^&\"']+)", html + " " + final_url, re.I
            )
            if match_continue:
                target_form_url = unquote(match_continue.group(1))
                if "forms" in target_form_url:
                    final_url = target_form_url

        # Parse FB_PUBLIC_LOAD_DATA_ dari Google Form
        form_title = ""
        form_desc = ""
        questions: list[str] = []

        matches = re.findall(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(.*?);</script>", html, re.DOTALL)
        if matches:
            try:
                data = json.loads(matches[0])
                if len(data) > 1 and data[1]:
                    form_desc = str(data[1][0] or "")[:500]
                    form_title = str(
                        data[1][8] if (len(data[1]) > 8 and data[1][8]) else data[1][0] or ""
                    )[:150]
                    items = data[1][1] or []
                    for item in items:
                        if item and len(item) > 1 and item[1]:
                            q_text = str(item[1]).strip()
                            if q_text and q_text not in questions:
                                questions.append(q_text)
            except Exception:
                pass

        # Jika parsing JS state gagal, coba ekstraksi teks kasar
        if not form_title:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            form_title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""

        risk_flags: list[str] = []
        safe_flags: list[str] = []
        final_url_lower = final_url.lower()
        invalid_dynamic_link = "invalid dynamic link" in form_title.lower()

        # Form yang mewajibkan login Google: server me-redirect ke
        # accounts.google.com (halaman "Google Formulir: Login") ATAU mengembalikan
        # HTTP 401. Isi form tidak dapat dibaca tanpa kredensial — laporkan jujur,
        # jangan salah-klaim PARSE_FAILED.
        login_required = landed_on_login or http_status == 401

        valid_form_target = (
            (
                "docs.google.com/forms" in final_url_lower
                or "forms.google.com" in final_url_lower
                or login_required  # final_url login tapi target asli adalah form
            )
            and not invalid_dynamic_link
        )

        content_verification_status = (
            "COMPLETED"
            if valid_form_target and (form_desc or questions) and not login_required
            else (LOGIN_REQUIRED if login_required else "UNVERIFIED")
        )

        # Form title/redirect alone is not enough to assess phishing content.
        combined_text = (form_desc + " " + " ".join(questions)).lower()
        detected_phishing_terms = (
            [
                kw for kw in PHISHING_KEYWORDS
                if re.search(rf"\b{re.escape(kw)}\b", combined_text)
            ]
            if content_verification_status == "COMPLETED"
            else []
        )

        if detected_phishing_terms:
            terms_str = ", ".join(detected_phishing_terms[:4])
            risk_flags.append(
                f"🚨 Google Form memuat pertanyaan sensitif/phishing mencurigakan ({terms_str})."
            )
        else:
            if form_desc:
                safe_flags.append(
                    f"ℹ️ Deskripsi form berhasil dibaca dari Google Forms: '{form_desc[:180]}...'"
                )
            if questions:
                q_sample = ", ".join(questions[:3])
                safe_flags.append(
                    f"✅ Tidak ditemukan kata kunci phishing pada {len(questions)} pertanyaan yang berhasil dibaca ({q_sample})."
                )
            elif valid_form_target:
                safe_flags.append("ℹ️ URL terhubung ke infrastruktur resmi Google Forms; ini bukan verifikasi perusahaan atau lowongan.")

        verification_note = None
        if valid_form_target and content_verification_status == LOGIN_REQUIRED:
            verification_note = (
                "Formulir mewajibkan login akun Google (data identitas responden direkam); "
                "isi pertanyaan tidak dapat diverifikasi tanpa kredensial. Pelamar disarankan "
                "berhati-hati membagikan dokumen sensitif (KTP/KK/ijazah) sebelum keabsahan "
                "perusahaan terkonfirmasi."
            )
            safe_flags.append(
                "ℹ️ Formulir mewajibkan login akun Google — isi pertanyaan tidak dapat "
                "dibaca sistem tanpa kredensial."
            )
        elif valid_form_target and content_verification_status == "UNVERIFIED":
            verification_note = (
                "URL mengarah ke Google Forms, tetapi pertanyaan/deskripsi belum berhasil "
                "dibaca; sinyal phishing belum dapat dinilai."
            )

        return {
            "is_gform": True,
            "probe_status": COMPLETED,
            "parse_status": (
                COMPLETED
                if content_verification_status == "COMPLETED"
                else (LOGIN_REQUIRED if login_required else PARSE_FAILED)
            ),
            "content_verification_status": content_verification_status,
            "login_required": login_required,
            "verification_note": verification_note,
            "url": url,
            "final_url": final_url,
            "form_title": (
                "Google Form (login diperlukan)" if login_required
                else (form_title or "Formulir Pendaftaran Loker")
            ),
            "form_desc": form_desc,
            "questions": questions[:10],
            "has_phishing_signals": (
                bool(detected_phishing_terms)
                if content_verification_status == "COMPLETED"
                else None
            ),
            "risk_flags": risk_flags,
            "safe_flags": safe_flags,
        }
    except Exception as exc:
        return {
            "is_gform": True,
            "probe_status": UNAVAILABLE,
            "parse_status": PARSE_FAILED,
            "url": url,
            "ok": False,
            "error": str(exc),
            "risk_flags": [],
            "safe_flags": [],
        }
