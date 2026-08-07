"""
Address Validator untuk Verifin OSINT Engine.
Memverifikasi alamat fisik dari lowongan kerja menggunakan Nominatim (OpenStreetMap)
"""

import re
import httpx
from urllib.parse import quote_plus

# ─────────────────────────────────────────────────────────────────────────────
# Konfigurasi
# ─────────────────────────────────────────────────────────────────────────────

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_TIMEOUT = 15.0

# Header wajib diisi untuk menggunakan Nominatim sesuai kebijakan penggunaan
NOMINATIM_HEADERS = {
    "User-Agent": "Verifin-OSINT-App/1.0 (gemastik-competition; contact@verifin.app)"
}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Geocoding Alamat via Nominatim
# ─────────────────────────────────────────────────────────────────────────────

async def _geocode_single(address: str, client: httpx.AsyncClient) -> dict | None:
    """Jalankan satu query Nominatim, return None jika tidak ditemukan."""
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "id",
        "addressdetails": 1
    }
    response = await client.get(NOMINATIM_URL, params=params)
    response.raise_for_status()
    results = response.json()
    return results[0] if results else None


def _address_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^\w\s]", " ", (value or "").lower()).split()
        if len(token) >= 3 and token not in _ADDR_STOP_WORDS
    }


def _classify_geocode_match(address: str, result: dict) -> dict:
    address_details = result.get("address") or {}
    display_name = result.get("display_name") or ""
    result_text = " ".join(
        [display_name, *[str(value) for value in address_details.values() if value]]
    )
    input_tokens = _address_tokens(address)
    result_tokens = _address_tokens(result_text)
    matched_tokens = input_tokens & result_tokens
    house_numbers = set(re.findall(r"\b\d+[a-z]?\b", (address or "").lower()))
    result_house_numbers = set(re.findall(r"\b\d+[a-z]?\b", result_text.lower()))
    house_number_match = bool(house_numbers & result_house_numbers)
    street_name = str(address_details.get("road") or "").lower()
    street_match = bool(street_name) and any(
        token in street_name for token in input_tokens if len(token) >= 4
    )
    token_score = len(matched_tokens) / len(input_tokens) if input_tokens else 0.0

    if house_number_match and street_match:
        match_level = "exact"
    elif street_match and token_score >= 0.25:
        match_level = "street"
    else:
        match_level = "area"

    return {
        "match_level": match_level,
        "coordinates_exact": match_level == "exact",
        "house_number_match": house_number_match,
        "street_match": street_match,
        "token_score": round(token_score, 3),
        "matched_tokens": sorted(matched_tokens),
    }


# Peta koreksi OCR typo umum pada nama wilayah Indonesia
_OCR_ADDR_FIXES: list[tuple[str, str]] = [
    # 'l' terbaca sebagai huruf kapital 'I' (atau sebaliknya)
    (r"\blstimewa\b", "Istimewa"),
    (r"\blndonesia\b", "Indonesia"),
    (r"\bJakarta\s+lndonesia\b", "Jakarta Indonesia"),
    # JI. / JI (tanpa titik) -> Jl. (OCR salah baca 'l' sebagai 'I')
    (r"\bJI\.\s*", "Jl. "),
    (r"\bJI\s+(?=[A-Z])", "Jl. "),
    # Kec./Kab./Kel. tanpa spasi setelahnya (OCR nempel)
    (r"\b(Kec|Kab|Kel|Desa|Ds)\.([A-Z])", r"\1. \2"),
]


def _normalize_ocr_address(addr: str) -> str:
    """Koreksi OCR typo umum pada string alamat sebelum dikirim ke Nominatim."""
    a = addr
    for pattern, replacement in _OCR_ADDR_FIXES:
        a = re.sub(pattern, replacement, a)
    # Tambahkan spasi setelah koma jika langsung disambung huruf ("Sleman,Yogyakarta" → "Sleman, Yogyakarta")
    a = re.sub(r",([^\s])", r", \1", a)
    return a


def _clean_address_input(addr: str) -> str:
    a = (addr or "").strip()
    a = re.sub(
        r"^(?:Penempatan|Alamat|Lokasi|Office|Basecamp|Tempat|Wilayah|Area)\s*[:.\-]?\s*",
        "",
        a,
        flags=re.IGNORECASE,
    )
    a = re.split(
        r"\s+(?:Send|Apply|CV|Cover|Subjek|Subject|More|Info|Informasi|Hubungi|Gaji|Salary|Email|WA|WhatsApp)\b",
        a,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return a.strip(" .,;:-")


def _build_fallback_queries(address: str) -> list[str]:
    """
    Membangun daftar query fallback dari yang paling spesifik ke yang paling umum.
    Contoh: 'Penempatan:Jl. perumnas mundusaren, Caturtunggal, Depok, Sleman, Yogyakarta Send your'
    → ['Jl. perumnas mundusaren, Caturtunggal, Depok, Sleman, Yogyakarta',
       'Jl. perumnas, Caturtunggal, Depok, Sleman, Yogyakarta, Indonesia',
       'Caturtunggal, Depok, Sleman, Yogyakarta, Indonesia']
    """
    addr = _clean_address_input(address)
    addr_norm = _normalize_ocr_address(addr)  # versi setelah koreksi OCR typo
    queries = [addr]
    if addr_norm != addr:
        queries.append(addr_norm)
    queries += [f"{addr_norm}, Indonesia", f"{addr}, Indonesia"]

    # Hapus nomor rumah (No.XX, No XX, RT/RW, dll.)
    stripped = re.sub(r"\bNo\.?\s*\d+\b", "", addr, flags=re.IGNORECASE)
    stripped = re.sub(r"\bRT\s*\d+\s*(RW\s*\d+)?\b", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\bRW\s*\d+\b", "", stripped, flags=re.IGNORECASE)
    if stripped != addr:
        queries.append(f"{stripped.strip(' ,')}, Indonesia")

    # Hapus prefix "Jl." / "Jalan"
    stripped_no_prefix = re.sub(
        r"^(?:Jl\.?|Jalan|Jln\.?)\s+", "", stripped.strip(), flags=re.IGNORECASE
    )
    if stripped_no_prefix != stripped:
        queries.append(f"{stripped_no_prefix.strip(' ,')}, Indonesia")

    parts = [p.strip() for p in addr_norm.split(",") if p.strip()]
    if len(parts) >= 2:
        # Strip "Kec.", "Kab.", "Kel.", "Desa", "Daerah" prefix dari setiap part
        def _strip_admin_prefix(s: str) -> str:
            return re.sub(
                r"^(?:Kecamatan|Kabupaten|Kelurahan|Kec\.?\s*|Kab\.?\s*|Kel\.?\s*|Desa\s+|Ds\.?\s*|Kota\s+|Daerah\s+)\s*",
                "", s, flags=re.IGNORECASE,
            ).strip()


        clean_parts = [_strip_admin_prefix(p) for p in parts]

        street_part = clean_parts[0]
        words = street_part.split()
        if len(words) >= 3:
            short_street = " ".join(words[:2])
            rest_parts = ", ".join(clean_parts[1:])
            queries.append(f"{short_street}, {rest_parts}, Indonesia")

        # Versi tanpa part pertama (tanpa nama jalan)
        queries.append(f"{', '.join(clean_parts[1:])}, Indonesia")
        queries.append(f"{', '.join(clean_parts[-2:])}, Indonesia")

        # Versi asli (sebelum strip)
        old_parts = [p.strip() for p in addr_norm.split(",") if p.strip()]
        if old_parts != clean_parts:
            queries.append(f"{', '.join(old_parts[1:])}, Indonesia")
    else:
        # Untuk alamat tanpa koma (misal "Jl. Klaseman No.15 Ngabean Wetan Ngaglik Sleman"):
        # Strip street & house number
        stripped_head = re.sub(
            r"^(?:Jl\.?|Jalan|Jln\.?)\s+[A-Za-z0-9\.\'-]+\s*(?:No\.?\s*\d+)?\s*",
            "", addr_norm, flags=re.IGNORECASE,
        ).strip()
        if stripped_head and stripped_head != addr_norm:
            queries.append(f"{stripped_head}, Indonesia")

        # Ambil 2-3 kata terakhir sebagai hirarki wilayah (Kecamatan, Kabupaten)
        clean_words = [
            w for w in re.sub(r"\bNo\.?\s*\d+\b", "", addr_norm, flags=re.IGNORECASE).split()
            if len(w) >= 3 and not re.match(r"^(?:Jl\.?|Jalan|Jln\.?)$", w, re.IGNORECASE)
        ]
        if len(clean_words) >= 2:
            queries.append(f"{clean_words[-2]}, {clean_words[-1]}, Indonesia")
            if len(clean_words) >= 3:
                queries.append(f"{' '.join(clean_words[-3:-1])}, {clean_words[-1]}, Indonesia")


    out = []
    seen = set()
    for q in queries:
        q_clean = re.sub(r"\s+", " ", q).strip(" ,")
        if q_clean and q_clean.lower() not in seen:
            seen.add(q_clean.lower())
            out.append(q_clean)
    return out



async def geocode_address(address: str, company_name: str | None = None) -> dict:
    """
    Mengkonversi alamat teks menjadi koordinat lat/lon menggunakan Nominatim.
    Mencoba beberapa variasi query (fallback) jika query utama tidak ditemukan.

    Returns:
        dict berisi: found (bool), lat, lon, display_name, country, confidence_score
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=NOMINATIM_HEADERS) as client:
            queries = _build_fallback_queries(address)
            if company_name:
                clean_address = _clean_address_input(address)
                queries = [
                    f"{company_name}, {clean_address}, Indonesia",
                    f"{company_name}, {clean_address}",
                    *queries,
                ]

            best_result = None
            best_match = None
            best_query = None
            match_rank = {"area": 0, "street": 1, "exact": 2}
            for query in queries:
                result = await _geocode_single(query, client)
                if result:
                    match = _classify_geocode_match(address, result)
                    if best_match is None or match_rank[match["match_level"]] > match_rank[best_match["match_level"]]:
                        best_result = result
                        best_match = match
                        best_query = query
                    if match["match_level"] == "exact":
                        break

            if best_result and best_match:
                result = best_result
                address_details = result.get("address", {})
                country = address_details.get("country", "")
                importance = float(result.get("importance", 0))
                clean_address = _clean_address_input(address)
                maps_query = ", ".join(
                    value for value in (company_name, clean_address) if value
                )
                return {
                    "found": True,
                    "lat": float(result["lat"]),
                    "lon": float(result["lon"]),
                    "display_name": result.get("display_name", ""),
                    "country": country,
                    "confidence_score": round(importance, 3),
                    "matched_query": best_query,
                    "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(maps_query)}",
                    "osm_url": f"https://www.openstreetmap.org/?mlat={float(result['lat'])}&mlon={float(result['lon'])}&zoom=17",
                    **best_match,
                }

        return {
            "found": False,
            "lat": None,
            "lon": None,
            "display_name": None,
            "country": None,
            "confidence_score": 0
        }

    except httpx.TimeoutException:
        return {"found": False, "error": "Timeout saat menghubungi Nominatim.", "lat": None, "lon": None}
    except Exception as e:
        return {"found": False, "error": str(e), "lat": None, "lon": None}


# ─────────────────────────────────────────────────────────────────────────────
# Fungsi Utama: Validasi Lengkap Alamat + Keberadaan Bisnis
# ─────────────────────────────────────────────────────────────────────────────

# Stop words yang tidak bermakna untuk address matching
_ADDR_STOP_WORDS = {"jl", "no", "rt", "rw", "kec", "kab", "kel", "desa", "indonesia", "jalan", "gang", "gg"}


def _verify_address_via_web(address: str, company_name: str) -> dict:
    """Verifikasi keberadaan perusahaan via web search — fallback dari Overpass/OSM.

    Pakai search_web_evidence yang sudah ada. Cocokkan token alamat poster
    dengan snippet hasil pencarian.
    # ponytail: token overlap O(n) — upgrade ke TF-IDF/BM25 kalau precision perlu naik
    """
    from app.services.osint.web_evidence import search_web_evidence

    query = f'"{company_name}" alamat OR lokasi OR maps OR "Google Maps"'
    result = search_web_evidence(query, max_results=5)

    if not result.get("ok") or not result.get("results"):
        return {"found": False, "method": "web_search", "match_score": 0.0}

    addr_tokens = {
        w for w in re.sub(r"[^\w\s]", " ", address.lower()).split()
        if len(w) >= 3 and w not in _ADDR_STOP_WORDS
    }
    if not addr_tokens:
        return {"found": False, "method": "web_search", "match_score": 0.0}

    best_score = 0.0
    best_snippet = ""
    for r in result["results"]:
        snippet = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
        snippet_tokens = set(re.sub(r"[^\w\s]", " ", snippet).split())
        score = len(addr_tokens & snippet_tokens) / len(addr_tokens)
        if score > best_score:
            best_score = score
            best_snippet = snippet

    found = best_score >= 0.4
    return {
        "found": found,
        "method": "web_search",
        "match_score": round(best_score, 2),
        "matched_snippet": best_snippet[:200] if found else None,
    }


async def validate_address_and_business(address: str, company_name: str = None) -> dict:
    """
    Fungsi utama yang menggabungkan geocoding + pencarian bisnis menjadi
    satu hasil analisis OSINT yang lengkap.

    Args:
        address: Alamat fisik dari hasil NER.
        company_name: Nama perusahaan dari hasil NER (opsional).

    Returns:
        dict berisi semua hasil validasi alamat dan keberadaan bisnis.
    """
    result = {
        "address_input": address,
        "company_name_input": company_name,
        "address_found": False,
        "address_details": None,
        "risk_signals": [],
        "safe_signals": [],
        "neutral_notes": [],
    }

    # Step 1: Geocode alamat
    geo = await geocode_address(address, company_name)
    result["address_details"] = geo

    if not geo.get("found"):
        result["address_found"] = False
        result["risk_signals"].append(
            f"Alamat '{address}' tidak ditemukan di peta OpenStreetMap Indonesia."
        )
        return result

    result["address_found"] = True
    if geo.get("match_level") == "exact":
        result["safe_signals"].append(
            f"Alamat jalan dan nomor cocok dengan hasil peta: {geo.get('display_name', '')[:120]}"
        )
    elif geo.get("match_level") == "street":
        result["neutral_notes"].append(
            "Nama jalan ditemukan, tetapi nomor bangunan belum cocok dengan hasil peta."
        )
    else:
        result["neutral_notes"].append(
            "Peta hanya menemukan wilayah sekitar; titik ini bukan bukti alamat outlet yang exact."
        )

    # Step 2: Web search konfirmasi keberadaan bisnis
    if company_name:
        web = _verify_address_via_web(address, company_name)
        result["web_verification"] = web
        if web.get("found"):
            result["safe_signals"].append(
                f"Perusahaan '{company_name}' ditemukan di web dengan referensi alamat "
                f"(skor kemiripan: {web['match_score']})."
            )

    if result.get("address_details"):
        result["address_details"]["coordinate_confidence"] = (
            result["address_details"].get("confidence_score")
            if result["address_found"]
            else None
        )

    return result
