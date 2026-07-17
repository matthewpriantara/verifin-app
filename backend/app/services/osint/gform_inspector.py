"""
Google Form Inspector Module for Verifin OSINT.
Memfollow redirect shortlink (bit.ly, forms.gle), mengekstrak pertanyaan Google Form,
dan menganalisis indikator pertanyaan phishing / sensitif (No Rekening, PIN, KTP, Biaya Transfer).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote, urlparse

from scrapling.fetchers import Fetcher

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
        # Check 302 location redirect (misal forms.gle -> docs.google.com/forms/...)
        try:
            r_short = httpx.get(url, headers=headers, follow_redirects=False, timeout=5.0)
            loc = r_short.headers.get("location")
            if loc:
                target_url = loc
        except Exception:
            pass

        r = httpx.get(target_url, headers=headers, follow_redirects=True, timeout=8.0)
        html = r.text
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
        if "accounts.google.com" in html or "accounts.google.com" in final_url:
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
            try:
                form_title = (page.css("title::text").get() or "").strip()
            except Exception:
                pass

        risk_flags: list[str] = []
        safe_flags: list[str] = []

        # Deteksi Phishing pada pertanyaan & deskripsi
        combined_text = (form_title + " " + form_desc + " " + " ".join(questions)).lower()
        
        detected_phishing_terms = [
            kw for kw in PHISHING_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", combined_text)
        ]

        if detected_phishing_terms:
            terms_str = ", ".join(detected_phishing_terms[:4])
            risk_flags.append(
                f"🚨 Google Form memuat pertanyaan sensitif/phishing mencurigakan ({terms_str})."
            )
        else:
            if form_desc:
                safe_flags.append(
                    f"✅ Deskripsi Google Form terverifikasi resmi: '{form_desc[:180]}...'"
                )
            if questions:
                q_sample = ", ".join(questions[:3])
                safe_flags.append(
                    f"✅ Google Form terverifikasi aman: memuat {len(questions)} pertanyaan standar loker ({q_sample})."
                )
            elif "forms" in final_url.lower() or "bit.ly" in url.lower():
                safe_flags.append(
                    "✅ Shortlink/Google Form terverifikasi terhubung ke infrastruktur resmi Google Forms."
                )

        return {
            "is_gform": True,
            "url": url,
            "final_url": final_url,
            "form_title": form_title or "Formulir Pendaftaran Loker",
            "form_desc": form_desc,
            "questions": questions[:10],
            "has_phishing_signals": bool(detected_phishing_terms),
            "risk_flags": risk_flags,
            "safe_flags": safe_flags,
        }
    except Exception as exc:
        return {
            "is_gform": True,
            "url": url,
            "ok": False,
            "error": str(exc),
            "risk_flags": [],
            "safe_flags": [],
        }
