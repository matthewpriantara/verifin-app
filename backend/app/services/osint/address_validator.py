"""
Address Validator untuk Verifin OSINT Engine.
Memverifikasi alamat fisik dari lowongan kerja menggunakan dua API gratis:
1. Nominatim (OpenStreetMap) — Geocoding: Apakah alamat ini nyata dan ada di Indonesia?
2. Overpass API (OpenStreetMap) — Places Search: Apakah nama perusahaan terdaftar di sekitar alamat tersebut?
"""

import httpx
import re
from difflib import SequenceMatcher

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


def _build_fallback_queries(address: str) -> list:
    """
    Membangun daftar query fallback dari yang paling spesifik ke yang paling umum.
    Contoh: 'Jl. Letjen Suprapto No.26, Ngampilan, Kota Yogyakarta'
    → ['Letjen Suprapto, Ngampilan, Kota Yogyakarta, Indonesia',
       'Ngampilan, Kota Yogyakarta, Indonesia']
    """
    queries = [address]

    # Hapus nomor rumah (No.XX, No XX, RT/RW, dll.)
    stripped = re.sub(r'\bNo\.?\s*\d+\b', '', address, flags=re.IGNORECASE)
    stripped = re.sub(r'\bRT\s*\d+\s*(RW\s*\d+)?\b', '', stripped, flags=re.IGNORECASE)
    stripped = re.sub(r'\bRW\s*\d+\b', '', stripped, flags=re.IGNORECASE)
    # Hapus prefix "Jl." / "Jalan"
    stripped_no_prefix = re.sub(r'^(Jl\.?|Jalan)\s+', '', stripped.strip(), flags=re.IGNORECASE)
    queries.append(f"{stripped_no_prefix.strip(', ')}, Indonesia")

    # Ambil hanya nama kota/kabupaten dari akhir alamat (2 kata terakhir setelah koma terakhir)
    parts = [p.strip() for p in address.split(',') if p.strip()]
    if len(parts) >= 2:
        city_query = ', '.join(parts[-2:]) + ', Indonesia'
        queries.append(city_query)

    return queries


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
                        "matched_query": query
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

    # Step 2: Cari bisnis di sekitar koordinat (hanya jika ada nama perusahaan)
    lat, lon = geo["lat"], geo["lon"]

    if company_name:
        biz = await search_business_near_location(lat, lon, company_name)
        result["business_details"] = biz

        if biz.get("found"):
            result["business_found"] = True
            result["safe_signals"].append(
                f"Nama bisnis '{biz['matched_name']}' ditemukan di OpenStreetMap "
                f"dekat alamat tersebut (kemiripan: {biz['similarity']*100:.0f}%)."
            )
        else:
            result["business_found"] = False
            # Ini bukan risiko penipuan langsung (UMKM sering tidak terdaftar di OSM), masukkan ke catatan netral
            if biz.get("nearby_businesses"):
                result["neutral_notes"].append(
                    f"Nama perusahaan '{company_name}' tidak terdaftar di OpenStreetMap sekitar alamat ini. "
                    f"Bisnis terdekat yang tercatat di OSM: {', '.join(biz['nearby_businesses'][:3])}."
                )
            else:
                result["neutral_notes"].append(
                    f"Nama perusahaan '{company_name}' tidak terdaftar di OpenStreetMap sekitar alamat ini. "
                    f"Ini hal wajar untuk UMKM baru/kecil di Indonesia."
                )
    else:
        result["business_found"] = None  # Tidak bisa dicek karena tidak ada nama perusahaan

    return result
