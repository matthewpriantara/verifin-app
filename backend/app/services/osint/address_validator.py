"""
Address Validator untuk Verifin OSINT Engine.
Memverifikasi alamat fisik dari lowongan kerja menggunakan dua API gratis:
1. Nominatim (OpenStreetMap) — Geocoding: Apakah alamat ini nyata dan ada di Indonesia?
2. Overpass API (OpenStreetMap) — Places Search: Apakah nama perusahaan terdaftar di sekitar alamat tersebut?
"""

import re
from difflib import SequenceMatcher

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# Konfigurasi
# ─────────────────────────────────────────────────────────────────────────────

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 15.0

# Header wajib diisi untuk menggunakan Nominatim sesuai kebijakan penggunaan
NOMINATIM_HEADERS = {
    "User-Agent": "Verifin-OSINT-App/1.0 (gemastik-competition; contact@verifin.app)"
}

# Radius pencarian bisnis di sekitar alamat (dalam meter)
SEARCH_RADIUS_METERS = 200


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _similarity_score(a: str, b: str) -> float:
    """Menghitung kemiripan dua string (0.0 = berbeda total, 1.0 = identik)."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _normalize_company_name(name: str) -> str:
    """Menghapus prefix hukum (PT, CV, dll.) untuk perbandingan nama bisnis."""
    prefixes = r"^(pt\.?|cv\.?|ud\.?|tb\.?|firma|yayasan|koperasi)\s+"
    return re.sub(prefixes, "", name, flags=re.IGNORECASE).strip()


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



async def geocode_address(address: str) -> dict:
    """
    Mengkonversi alamat teks menjadi koordinat lat/lon menggunakan Nominatim.
    Mencoba beberapa variasi query (fallback) jika query utama tidak ditemukan.

    Returns:
        dict berisi: found (bool), lat, lon, display_name, country, confidence_score
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=NOMINATIM_HEADERS) as client:
            for query in _build_fallback_queries(address):
                result = await _geocode_single(query, client)
                if result:
                    address_details = result.get("address", {})
                    country = address_details.get("country", "")
                    importance = float(result.get("importance", 0))
                    return {
                        "found": True,
                        "lat": float(result["lat"]),
                        "lon": float(result["lon"]),
                        "display_name": result.get("display_name", ""),
                        "country": country,
                        "confidence_score": round(importance, 3),
                        "matched_query": query,
                        "google_maps_url": f"https://maps.google.com/?q={float(result['lat'])},{float(result['lon'])}",
                        "osm_url": f"https://www.openstreetmap.org/?mlat={float(result['lat'])}&mlon={float(result['lon'])}&zoom=17",
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
# Step 2: Cari Nama Bisnis di Sekitar Koordinat via Overpass API
# ─────────────────────────────────────────────────────────────────────────────

async def search_business_near_location(lat: float, lon: float, company_name: str) -> dict:
    """
    Mencari apakah nama perusahaan terdaftar sebagai bisnis di OpenStreetMap
    dalam radius SEARCH_RADIUS_METERS dari koordinat yang diberikan.
    Menggunakan dua strategi:
    1. Radius search: Cari semua bisnis dalam radius, lalu cocokkan nama.
    2. Name search: Cari langsung berdasarkan nama di seluruh kota sekitar.

    Returns:
        dict berisi: found (bool), matched_name, similarity, nearby_businesses (list)
    """
    normalized_target = _normalize_company_name(company_name)

    # ── Strategi 1: Cari semua bisnis dalam radius koordinat ──
    query_radius = f"""
    [out:json][timeout:15];
    (
      node["name"](around:{SEARCH_RADIUS_METERS},{lat},{lon});
      way["name"](around:{SEARCH_RADIUS_METERS},{lat},{lon});
      node["shop"](around:{SEARCH_RADIUS_METERS},{lat},{lon});
      node["amenity"](around:{SEARCH_RADIUS_METERS},{lat},{lon});
      node["office"](around:{SEARCH_RADIUS_METERS},{lat},{lon});
    );
    out body;
    """

    # ── Strategi 2: Cari langsung berdasarkan nama (radius lebih luas 3km) ──
    # Ini menangkap kasus bisnis yang terdaftar tapi koordinatnya sedikit berbeda
    name_keyword = normalized_target[:30]   # Batasi panjang keyword
    query_name = f"""
    [out:json][timeout:15];
    (
      node["name"~"{name_keyword}",i](around:3000,{lat},{lon});
      way["name"~"{name_keyword}",i](around:3000,{lat},{lon});
    );
    out body;
    """

    all_results = []

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # Jalankan strategi 1
            r1 = await client.post(OVERPASS_URL, data={"data": query_radius})
            r1.raise_for_status()
            for el in r1.json().get("elements", []):
                name = el.get("tags", {}).get("name", "").strip()
                if name:
                    all_results.append({"name": name, "strategy": "radius"})

            # Jalankan strategi 2
            r2 = await client.post(OVERPASS_URL, data={"data": query_name})
            r2.raise_for_status()
            for el in r2.json().get("elements", []):
                name = el.get("tags", {}).get("name", "").strip()
                if name:
                    all_results.append({"name": name, "strategy": "name_search"})

    except httpx.TimeoutException:
        return {"found": False, "error": "Timeout saat menghubungi Overpass API.", "nearby_businesses": []}
    except Exception as e:
        return {"found": False, "error": str(e), "nearby_businesses": []}

    if not all_results:
        return {
            "found": False,
            "matched_name": None,
            "similarity": 0.0,
            "nearby_businesses": [],
            "note": "Tidak ada bisnis terdaftar di OpenStreetMap sekitar lokasi ini."
        }

    # Cari nama yang paling mirip dengan nama perusahaan dari loker
    best_match = None
    best_score = 0.0
    best_strategy = None

    for item in all_results:
        normalized_name = _normalize_company_name(item["name"])
        score = _similarity_score(normalized_target, normalized_name)
        if score > best_score:
            best_score = score
            best_match = item["name"]
            best_strategy = item["strategy"]

    # Kumpulkan nama unik dari radius search untuk referensi
    nearby_sample = list({
        item["name"] for item in all_results
        if item["strategy"] == "radius"
    })[:10]

    return {
        "found": best_score >= 0.55,    # Threshold kemiripan 55%
        "matched_name": best_match,
        "similarity": round(best_score, 3),
        "matched_via": best_strategy,
        "nearby_businesses": nearby_sample
    }


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
        "business_found": None,
        "business_details": None,
        "risk_signals": [],
        "safe_signals": [],
        "neutral_notes": []  # Catatan tambahan yang bukan risiko keamanan
    }

    # Step 1: Geocode alamat
    geo = await geocode_address(address)
    result["address_details"] = geo

    if not geo.get("found"):
        result["address_found"] = False
        result["risk_signals"].append(
            f"Alamat '{address}' tidak ditemukan di peta OpenStreetMap Indonesia."
        )
        return result

    result["address_found"] = True
    result["safe_signals"].append(
        f"Alamat terverifikasi ada di peta: {geo.get('display_name', '')[:100]}"
    )

    # Step 2: Overpass bisnis lookup — dinonaktifkan, public instance 406/504
    # address_found dari Nominatim sudah cukup untuk SHAP; business_details
    # tidak affect verdict/risk_score. Web search location match lebih reliable
    # untuk konfirmasi keberadaan fisik UMKM Indonesia.
    if company_name:
        result["business_found"] = False
        result["business_details"] = {
            "found": False,
            "skipped": "overpass_disabled",
            "nearby_businesses": [],
        }
    else:
        result["business_found"] = None

    # Step 3: Web search fallback — kalau Overpass miss atau Nominatim miss
    if company_name and result["business_found"] is not True:
        web = _verify_address_via_web(address, company_name)
        result["web_verification"] = web
        if web.get("found"):
            result["business_found"] = True
            result["safe_signals"].append(
                f"Perusahaan '{company_name}' ditemukan di web dengan referensi alamat "
                f"(skor kemiripan: {web['match_score']})."
            )

    if result.get("address_details"):
        # Similarity nyata dari hasil Overpass — None kalau bisnis tidak ditemukan
        result["address_details"]["business_name_similarity"] = (
            round((result.get("business_details") or {}).get("similarity", 0.0), 2)
            if result["business_found"]
            else None
        )
        # Confidence score langsung dari Nominatim tanpa inflate
        result["address_details"]["coordinate_confidence"] = (
            result["address_details"].get("confidence_score")
            if result["address_found"]
            else None
        )

    return result
