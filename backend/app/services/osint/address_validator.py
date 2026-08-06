"""
Address Validator untuk Verifin OSINT Engine.
Memverifikasi alamat fisik dari lowongan kerja menggunakan dua API gratis + SERP Fallback:
1. Nominatim (OpenStreetMap) -- Geocoding: Apakah alamat ini nyata dan ada di Indonesia?
2. SERP Search Engine (DuckDuckGo/Yahoo) -- Auto-Correct Fallback untuk alamat typo.
3. Overpass API (OpenStreetMap) -- Places Search: Apakah nama perusahaan terdaftar di sekitar alamat tersebut?
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

NOMINATIM_HEADERS = {
    "User-Agent": "Verifin-OSINT-App/1.0 (gemastik-competition; contact@verifin.app)"
}

SEARCH_RADIUS_METERS = 200


def _similarity_score(a: str, b: str) -> float:
    """Menghitung kemiripan dua string (0.0 = berbeda total, 1.0 = identik)."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _normalize_company_name(name: str) -> str:
    """Menghapus prefix hukum (PT, CV, dll.) untuk perbandingan nama bisnis."""
    prefixes = r"^(pt\.?|cv\.?|ud\.?|tb\.?|firma|yayasan|koperasi)\s+"
    return re.sub(prefixes, "", name, flags=re.IGNORECASE).strip()


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


_OCR_ADDR_FIXES: list[tuple[str, str]] = [
    (r"\blstimewa\b", "Istimewa"),
    (r"\blndonesia\b", "Indonesia"),
    (r"\bJakarta\s+lndonesia\b", "Jakarta Indonesia"),
    (r"\bJI\.\s*", "Jl. "),
    (r"\bJI\s+(?=[A-Z])", "Jl. "),
    (r"\bNgg([a-z]+)", r"Ng\1"),
    (r"\bD?Jogyakarta\b", "Yogyakarta"),
    (r"\bD?Jogjakarta\b", "Yogyakarta"),
    (r"\bJogja(karta)?\b", "Yogyakarta"),
    (r"\bYogyakartaa?\b", "Yogyakarta"),
    (r"\bKaliyurang\b", "Kaliurang"),
    (r"\bSlemann\b", "Sleman"),
    (r"\bSuroboyo\b", "Surabaya"),
    (r"\bJaksel\b", "Jakarta Selatan"),
    (r"\bJakbar\b", "Jakarta Barat"),
    (r"\bJaktim\b", "Jakarta Timur"),
    (r"\bJakpus\b", "Jakarta Pusat"),
    (r"\bJakut\b", "Jakarta Utara"),
    (r"\b(Kec|Kab|Kel|Desa|Ds)\.([A-Z])", r"\1. \2"),
]


def _normalize_ocr_address(addr: str) -> str:
    """Koreksi OCR typo umum pada string alamat sebelum dikirim ke Nominatim."""
    a = addr
    a = re.sub(r'(Jl\.?|Jalan)\s+[a-z]\.', r'\1 ', a, flags=re.IGNORECASE)
    a = re.sub(r'([A-Za-z]+)\.([A-Za-z]+)', r'\1, \2', a)
    for pattern, replacement in _OCR_ADDR_FIXES:
        a = re.sub(pattern, replacement, a, flags=re.IGNORECASE)
    a = re.sub(r",([^\s])", r", \1", a)
    a = _normalize_street_number_to_roman(a)
    return a


_ARAB_TO_ROMAN = [
    (10, 'X'), (9, 'IX'), (8, 'VIII'), (7, 'VII'), (6, 'VI'),
    (5, 'V'), (4, 'IV'), (3, 'III'), (2, 'II'), (1, 'I'),
]


def _normalize_street_number_to_roman(addr: str) -> str:
    """Konversi angka Arab standalone setelah nama jalan ke Romawi.
    Contoh: 'Jl. Wijaya 2' -> 'Jl. Wijaya II'
    TIDAK mengubah: 'No. 122', 'RT 3', 'RW 2', 'Kav. 5'
    """
    def _replace(m):
        prefix = m.group(1)
        num = int(m.group(2))
        suffix = m.group(3)
        # Skip jika preceded by No/RT/RW/Kav (captured in prefix)
        if re.search(r'(?:No\.?|RT|RW|Kav\.?|Blok)\s*$', prefix, re.IGNORECASE):
            return m.group(0)
        for n, r in _ARAB_TO_ROMAN:
            if num == n:
                return prefix + r + suffix
        return m.group(0)
    return re.sub(r'([A-Za-z]\s+)(\d{1,2})(\s*[,\s]|$)', _replace, addr)


# Kata kunci yang menandai akhir dari string alamat (setelah ini bukan alamat lagi)
_ADDR_CUTOFF_PATTERN = re.compile(
    r"[,;\s]+(?:"
    r"OKER|LOKER|JOB|VACANCY|POSISI"
    r"|KIRIMKAN|KIRIM|Send|Apply|Atau|Walk(?:\s*-?\s*in)?|Dan\b|Via\b|Melalui|Ke\s+lokasi"
    r"|CV|Cover\s*Letter|Lamaran"
    r"|Commissary|Commissary\s+QC"
    r"|dari\s+industri|industri\s+bakery|pengolahan"
    r"|Paham|analisa|sensori|dasar|pengambilan"
    r"|sample|uji\s+lab|GMP|HACCP|FSSC|CCP"
    r"|Kualifikasi|Persyaratan|Syarat|Requirement"
    r"|lebih\s+diuta|diutamakan|istri\s+bakery"
    r"|inalisa|pengambilan\s+sample"
    r"|Subjek|Subject|Info|Informasi"
    r"|Hubungi|Gaji|Salary|Email\b|WA\b|WhatsApp"
    r")",
    flags=re.IGNORECASE,
)


def _clean_address_input(addr: str) -> str:
    a = (addr or "").strip()
    # Hapus prefix label alamat
    a = re.sub(
        r"^(?:Penempatan|Alamat|Lokasi|Office|Basecamp|Tempat|Wilayah|Area)\s*[:.\-]?\s*",
        "",
        a,
        flags=re.IGNORECASE,
    )
    # Potong di kata-kata non-alamat (persyaratan kerja, OCR garbage, dll)
    m = _ADDR_CUTOFF_PATTERN.search(a)
    if m:
        a = a[: m.start()]
    return a.strip(" .,;:-")


def _build_fallback_queries(address: str) -> list[str]:
    addr = _clean_address_input(address)
    addr_norm = _normalize_ocr_address(addr)
    queries = [addr]
    if addr_norm != addr:
        queries.append(addr_norm)
    queries += [f"{addr_norm}, Indonesia", f"{addr}, Indonesia"]

    stripped = re.sub(r"\bNo\.?\s*\d+\b", "", addr_norm, flags=re.IGNORECASE)
    stripped = re.sub(r"\bRT\s*\d+\s*(RW\s*\d+)?\b", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\bRW\s*\d+\b", "", stripped, flags=re.IGNORECASE)
    if stripped != addr:
        queries.append(f"{stripped.strip(' ,')}, Indonesia")

    stripped_no_prefix = re.sub(
        r"^(?:Jl\.?|Jalan|Jln\.?)\s+", "", stripped.strip(), flags=re.IGNORECASE
    )
    if stripped_no_prefix != stripped:
        queries.append(f"{stripped_no_prefix.strip(' ,')}, Indonesia")

    parts = [p.strip() for p in addr_norm.split(",") if p.strip()]
    if len(parts) >= 2:
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

        queries.append(f"{', '.join(clean_parts[1:])}, Indonesia")
        queries.append(f"{', '.join(clean_parts[-2:])}, Indonesia")

        old_parts = [p.strip() for p in addr_norm.split(",") if p.strip()]
        if old_parts != clean_parts:
            queries.append(f"{', '.join(old_parts[1:])}, Indonesia")
    else:
        stripped_head = re.sub(
            r"^(?:Jl\.?|Jalan|Jln\.?)\s+[A-Za-z0-9\.\'-]+\s*(?:No\.?\s*\d+)?\s*",
            "", addr_norm, flags=re.IGNORECASE,
        ).strip()
        if stripped_head and stripped_head != addr_norm:
            queries.append(f"{stripped_head}, Indonesia")

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


async def _serp_autocorrect_address(address: str) -> list[str]:
    clean_q = _clean_address_input(address)
    if not clean_q:
        return []

    search_query = f"{clean_q} alamat lokasi Indonesia"
    candidates: list[str] = []

    try:
        from urllib.parse import quote_plus
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"
            r = await client.get(url)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                snippets = [sn.text.strip() for sn in soup.select(".result__snippet")]
                titles = [a.text.strip() for a in soup.select("a.result__a")]
                combined = " ".join(titles + snippets)

                found_addrs = re.findall(
                    r"\b(?:Jl\.?|Jalan|Jln\.?)\s+[A-Za-z0-9\.\'\-\s]+(?:Kec\.?|Kab\.?|Kel\.?|Kota|Kabupaten|Kecamatan|DIY|Yogyakarta|Jakarta|Bandung|Surabaya|Semarang|Medan)\b[^\.\n]*",
                    combined,
                    flags=re.IGNORECASE,
                )
                for fa in found_addrs[:3]:
                    fa_clean = re.sub(r"\s+", " ", fa).strip(" ,.-")
                    if len(fa_clean) > 8 and fa_clean.lower() not in [c.lower() for c in candidates]:
                        candidates.append(fa_clean)
    except Exception:
        pass

    return candidates


async def _check_gmaps_serp_existence(company_name: str, address: str) -> dict:
    """
    Ketika Nominatim gagal menemukan alamat, cek di SERP apakah bisnis ini
    terdaftar di Google Maps, GoFood, GrabFood, atau TripAdvisor.
    Ini mitigasi gap data OSM vs Google Maps di Indonesia.
    """
    from urllib.parse import quote_plus
    from bs4 import BeautifulSoup

    if not address:
        return {"found_via_serp": False}

    # Bersihkan alamat dari garbage sebelum dijadikan query
    clean_addr = _clean_address_input(address)
    comp_clean = (company_name or "").strip()
    is_generic_company = not comp_clean or comp_clean.lower() in {"perusahaan", "unknown", "tidak diketahui"}

    if is_generic_company:
        query = f'{clean_addr} site:maps.google.com OR site:gofood.co.id OR site:grab.com OR site:tripadvisor.com'
    else:
        # Query: cari nama bisnis + alamat di platform maps/kuliner
        query = (
            f'"{comp_clean}" {clean_addr} '
            f'site:maps.google.com OR site:gofood.co.id OR site:grab.com OR '
            f'site:tripadvisor.com OR site:zomato.com OR site:qraved.com'
        )
    sources_found = []
    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as client:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            r = await client.get(url)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a.result__a")[:5]:
                    href = a.get("href", "")
                    title = a.text.strip().lower()
                    if is_generic_company:
                        for platform in ["maps.google", "gofood", "grab", "tripadvisor"]:
                            if platform in href.lower() or platform in title:
                                sources_found.append(platform)
                                break
                    else:
                        company_lower = comp_clean.lower()
                        # Pastikan hasil relevan dengan nama bisnis
                        if any(w in title for w in company_lower.split() if len(w) > 3):
                            for platform in ["maps.google", "gofood", "grab", "tripadvisor", "zomato", "qraved"]:
                                if platform in href.lower() or platform in title:
                                    sources_found.append(platform)
                                    break
    except Exception:
        pass

    if sources_found:
        return {
            "found_via_serp": True,
            "platforms": list(set(sources_found)),
            "note": f"Bisnis ditemukan di: {', '.join(set(sources_found))} — OSM mungkin belum terdata",
        }
    return {"found_via_serp": False}


async def _progressive_truncate_geocode(
    address: str,
    client: httpx.AsyncClient,
) -> tuple[str, dict | None]:
    """
    Layer 0 Address Cleaning — Progressive Nominatim Truncation.

    Prinsip: Biarkan OSM sendiri yang menentukan di mana batas valid alamat.
    Algoritma:
      1. Normalisasi OCR dulu (_normalize_ocr_address).
      2. Jika ≤3 segmen koma → skip truncation, langsung return (pakai fallback biasa).
      3. Coba dari terpanjang sampai terpendek (min 2 segmen), max 5 percobaan.
      4. Jeda 1.1 detik antar request agar tidak kena rate-limit Nominatim (policy: 1 req/s).
      5. Return (cleaned_address, nominatim_result) atau (normalized, None) jika semua gagal.

    NON-HARDCODE — tidak ada daftar kata. OSM sendiri yang validasi batas alamat.
    """
    import asyncio

    raw_clean = _clean_address_input(address)
    raw_norm = _normalize_ocr_address(raw_clean)
    parts = [p.strip() for p in raw_norm.split(",") if p.strip()]

    if not parts:
        return address, None

    # ── Guard 1: Alamat pendek/bersih (≤3 segmen) → skip truncation ───────────
    # Alamat normal punya 3–4 segmen (Jalan, Kecamatan, Kota, Provinsi).
    # Kalau sudah ≤3, tidak ada yang perlu dipotong → hemat quota Nominatim.
    if len(parts) <= 3:
        return raw_norm, None

    # ── Guard 2: Cap maksimal 5 upaya truncation ─────────────────────────────
    # Cegah looping panjang untuk alamat dengan banyak garbage koma.
    # Contoh: 8 segmen → coba dari 8, 7, 6, 5, 4 saja (5 percobaan maks).
    min_end = max(2, len(parts) - 5)

    best_cleaned: str | None = None
    best_result: dict | None = None
    first_attempt = True

    for end_idx in range(len(parts), min_end - 1, -1):
        # ── Guard 3: Rate-limit guard — jeda 1.1s kecuali percobaan pertama ──
        if not first_attempt:
            await asyncio.sleep(1.1)
        first_attempt = False

        candidate = ", ".join(parts[:end_idx])
        result = await _geocode_single(candidate + ", Indonesia", client)
        if result:
            best_cleaned = candidate
            best_result = result
            break  # Ambil versi terpanjang yang berhasil match — stop

    if best_cleaned:
        return best_cleaned, best_result
    # Semua gagal → kembalikan versi ternormalisasi (bukan input mentah)
    # agar Layer 1–2 tetap dapat input yang sudah bersih dari OCR typo
    return raw_norm or raw_clean or address, None



async def geocode_address(address: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=NOMINATIM_HEADERS) as client:

            # ── Layer 0: Progressive Truncation ─ OSM sendiri yang tentukan batas alamat ──
            cleaned_addr, trunc_result = await _progressive_truncate_geocode(address, client)
            if trunc_result:
                addr_details = trunc_result.get("address", {})
                importance = float(trunc_result.get("importance", 0))
                return {
                    "found": True,
                    "lat": float(trunc_result["lat"]),
                    "lon": float(trunc_result["lon"]),
                    "display_name": trunc_result.get("display_name", ""),
                    "country": addr_details.get("country", ""),
                    "confidence_score": round(importance, 3),
                    "matched_query": cleaned_addr,
                    "cleaned_address": cleaned_addr,
                    "is_autocorrected": cleaned_addr != address,
                    "google_maps_url": f"https://maps.google.com/?q={float(trunc_result['lat'])},{float(trunc_result['lon'])}",
                    "osm_url": f"https://www.openstreetmap.org/?mlat={float(trunc_result['lat'])}&mlon={float(trunc_result['lon'])}&zoom=17",
                }

            # ── Layer 1–2: Fallback hierarchy queries (pakai cleaned_addr hasil truncation) ──
            for query in _build_fallback_queries(cleaned_addr):
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
                        "cleaned_address": cleaned_addr,
                        "is_autocorrected": False,
                        "google_maps_url": f"https://maps.google.com/?q={float(result['lat'])},{float(result['lon'])}",
                        "osm_url": f"https://www.openstreetmap.org/?mlat={float(result['lat'])}&mlon={float(result['lon'])}&zoom=17",
                    }

            # ── Layer 3: SERP Auto-Correct Fallback ──
            serp_candidates = await _serp_autocorrect_address(cleaned_addr)
            for candidate_q in serp_candidates:
                result = await _geocode_single(candidate_q, client)
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
                        "confidence_score": round(importance * 0.9, 3),
                        "matched_query": candidate_q,
                        "cleaned_address": cleaned_addr,
                        "is_autocorrected": True,
                        "original_input": address,
                        "google_maps_url": f"https://maps.google.com/?q={float(result['lat'])},{float(result['lon'])}",
                        "osm_url": f"https://www.openstreetmap.org/?mlat={float(result['lat'])}&mlon={float(result['lon'])}&zoom=17",
                    }

        return {
            "found": False,
            "lat": None,
            "lon": None,
            "display_name": None,
            "country": None,
            "confidence_score": 0,
            "cleaned_address": cleaned_addr,
        }

    except httpx.TimeoutException:
        return {"found": False, "error": "Timeout saat menghubungi Nominatim.", "lat": None, "lon": None}
    except Exception as e:
        return {"found": False, "error": str(e), "lat": None, "lon": None}


async def validate_address_with_gmaps_fallback(company_name: str, address: str) -> dict:
    """Validasi alamat via OSM + fallback SERP ke Google Maps/GoFood jika OSM gagal."""
    result = await geocode_address(address)
    if not result.get("found"):
        serp = await _check_gmaps_serp_existence(company_name, address)
        result["gmaps_serp_fallback"] = serp
        if serp.get("found_via_serp"):
            result["found"] = True
            result["matched_source"] = "google_maps_serp"
            result["found_via_serp"] = True
            result["serp_note"] = serp.get("note", "")
    return result


async def search_business_near_location(lat: float, lon: float, company_name: str) -> dict:
    normalized_target = _normalize_company_name(company_name)

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

    name_keyword = normalized_target[:30]
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
            r1 = await client.post(OVERPASS_URL, data={"data": query_radius})
            r1.raise_for_status()
            for el in r1.json().get("elements", []):
                name = el.get("tags", {}).get("name", "").strip()
                if name:
                    all_results.append({"name": name, "strategy": "radius"})

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

    nearby_sample = list({
        item["name"] for item in all_results
        if item["strategy"] == "radius"
    })[:10]

    return {
        "found": best_score >= 0.55,
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
    result = {
        "address_input": address,
        "company_name_input": company_name,
        "address_found": False,
        "address_details": None,
        "business_found": None,
        "business_details": None,
        "risk_signals": [],
        "safe_signals": [],
        "neutral_notes": []
    }

    geo = await validate_address_with_gmaps_fallback(company_name, address)
    result["address_details"] = geo
    if geo.get("found_via_serp"):
        result["found_via_serp"] = True
        result["gmaps_serp_fallback"] = geo.get("gmaps_serp_fallback")

    if not geo.get("found"):
        result["address_found"] = False
        if geo.get("found_via_serp"):
            result["safe_signals"].append(
                f"Alamat/Perusahaan terverifikasi via Google Maps SERP Fallback: {geo.get('serp_note', '')}"
            )
        else:
            result["risk_signals"].append(
                f"Alamat '{address}' tidak ditemukan di peta OpenStreetMap Indonesia."
            )
        return result

    result["address_found"] = True
    if geo.get("is_autocorrected"):
        result["safe_signals"].append(
            f"Alamat terverifikasi di peta via SERP Auto-Correct ({geo.get('matched_query')}): {geo.get('display_name', '')[:100]}"
        )
    else:
        result["safe_signals"].append(
            f"Alamat terverifikasi ada di peta: {geo.get('display_name', '')[:100]}"
        )

    lat, lon = geo["lat"], geo["lon"]

    if company_name:
        biz = await search_business_near_location(lat, lon, company_name)
        result["business_details"] = biz

        if biz.get("found"):
            result["business_found"] = True
            result["safe_signals"].append(
                f"Nama bisnis '{biz['matched_name']}' ditemukan di OpenStreetMap dekat alamat tersebut (kemiripan: {biz['similarity']*100:.0f}%)."
            )
        else:
            result["business_found"] = False
            if biz.get("nearby_businesses"):
                result["neutral_notes"].append(
                    f"Nama perusahaan '{company_name}' tidak terdaftar di OpenStreetMap sekitar alamat ini. Bisnis terdekat yang tercatat di OSM: {', '.join(biz['nearby_businesses'][:3])}."
                )
            else:
                result["neutral_notes"].append(
                    f"Nama perusahaan '{company_name}' tidak terdaftar di OpenStreetMap sekitar alamat ini. Ini hal wajar untuk UMKM baru/kecil di Indonesia."
                )
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