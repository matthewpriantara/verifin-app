"""
Search Intelligence Layer — entity resolution + result re-ranking untuk SearXNG.

Modul ini TIDAK menduplikasi query_builder.py (yang sudah handle query building).
Fokusnya pada hal yang belum ada di pipeline:

1. resolve_entity   — normalisasi nama perusahaan (strip PT/CV, ambil alias/brand)
2. rerank_results   — skor ulang hasil SearXNG berdasarkan relevansi entitas + lokasi
3. classify_result  — kategorikan hasil (official / marketplace / social / scam_report / ...)
4. aggregate_signals— gabungkan sinyal dari semua hasil jadi verdict evidence
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Konstanta ─────────────────────────────────────────────────────────────────

_LEGAL_PREFIX_RE = re.compile(r"\b(pt|cv|ud|pd|tbk|firma|yayasan|koperasi)\b\.?", re.I)
_PAREN_ALIAS_RE = re.compile(r"\(([^()]{2,80})\)")

_SCAM_TOKENS = {
    "penipuan", "penipu", "scam", "fraud", "palsu", "modus", "korban",
    "lapor", "hati-hati", "waspada", "blacklist",
}
_ADVICE_TOKENS = {
    "cara", "tips", "ciri", "mengenali", "menghindari", "waspadai",
    "contoh", "panduan", "edukasi",
}
_OFFICIAL_TOKENS = {
    "official", "resmi", "career", "karir", "recruitment", "rekrutmen",
    "tentang", "about", "kontak", "contact",
}
_LOCATION_STOPWORDS = {
    "jalan", "jl", "jln", "no", "nomor", "rt", "rw", "kec", "kecamatan",
    "kab", "kabupaten", "kota", "desa", "kelurahan", "indonesia",
}

_DOMAIN_CATEGORY: list[tuple[tuple[str, ...], str]] = [
    (("instagram.com", "facebook.com", "tiktok.com", "threads.net", "x.com", "twitter.com"), "social"),
    (("tokopedia.com", "shopee.co.id", "bukalapak.com", "lazada.co.id"), "marketplace"),
    (("jobstreet.co.id", "glints.com", "kalibrr.com", "linkedin.com", "karir.com"), "job_portal"),
    (("gofood", "grabfood", "shopeefood"), "food_delivery"),
    (("maps.google", "google.com/maps"), "maps"),
    (("kompas.com", "detik.com", "tribunnews.com", "liputan6.com"), "news"),
    (("wikipedia.org",), "wiki"),
    (("kaskus.co.id", "reddit.com", "quora.com"), "forum"),
]


# ── 1. Entity Resolution ──────────────────────────────────────────────────────

def resolve_entity(raw_company: str) -> dict[str, Any]:
    """
    Normalisasi nama perusahaan mentah menjadi bentuk-bentuk pencarian.

    Returns:
        {
            "canonical": str,          # nama bersih tanpa prefix legal
            "brand": str | None,       # alias dari tanda kurung, misal "Bangor"
            "legal_form": str | None,  # "PT" / "CV" / None
            "tokens": list[str],       # token identitas untuk matching
            "search_names": list[str], # urutan kandidat nama untuk query
        }
    """
    raw = re.sub(r"\s+", " ", (raw_company or "")).strip()
    if not raw:
        return {"canonical": "", "brand": None, "legal_form": None, "tokens": [], "search_names": []}

    # Legal form
    legal_match = _LEGAL_PREFIX_RE.search(raw)
    legal_form = legal_match.group(1).upper().rstrip(".") if legal_match else None

    # Brand alias dari tanda kurung
    aliases = _PAREN_ALIAS_RE.findall(raw)
    brand = aliases[0].strip() if aliases else None

    # Canonical: hapus prefix legal + tanda kurung
    canonical = _LEGAL_PREFIX_RE.sub("", raw)
    canonical = _PAREN_ALIAS_RE.sub("", canonical)
    canonical = re.sub(r"[^\w\s]", " ", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip()

    # Tokens identitas (untuk matching hasil)
    tokens = [
        w.lower() for w in re.split(r"[^\w]+", canonical)
        if len(w) >= 3
    ]
    if brand:
        tokens.extend(w.lower() for w in re.split(r"[^\w]+", brand) if len(w) >= 3)
    tokens = sorted(set(tokens), key=len, reverse=True)

    # Urutan kandidat nama untuk search
    search_names: list[str] = []
    if brand and brand.lower() != canonical.lower():
        search_names.append(brand)
    if canonical:
        search_names.append(canonical)
    if raw not in search_names:
        search_names.append(raw)

    return {
        "canonical": canonical,
        "brand": brand,
        "legal_form": legal_form,
        "tokens": tokens,
        "search_names": search_names,
    }


def extract_location_tokens(address: str) -> list[str]:
    """Ekstrak token lokasi signifikan dari alamat (kota, kecamatan, nama jalan)."""
    if not address:
        return []
    words = re.split(r"[^\w]+", address.lower())
    return [
        w for w in words
        if len(w) >= 4 and w not in _LOCATION_STOPWORDS and not w.isdigit()
    ]


# ── 2. Result Classification ──────────────────────────────────────────────────

def classify_result(url: str, title: str = "", snippet: str = "") -> str:
    """
    Kategorikan satu hasil pencarian.

    Kategori: official | social | marketplace | job_portal | food_delivery
              maps | news | wiki | forum | scam_report | advice_article | web
    """
    url_lower = url.lower()
    text = f"{title} {snippet}".lower()

    # Domain-based dulu
    for domains, category in _DOMAIN_CATEGORY:
        if any(d in url_lower for d in domains):
            return category

    # Content-based
    if any(t in text for t in _SCAM_TOKENS):
        return "advice_article" if any(t in text for t in _ADVICE_TOKENS) else "scam_report"
    if any(t in text for t in _OFFICIAL_TOKENS):
        return "official"

    return "web"


# ── 3. Re-Ranking ─────────────────────────────────────────────────────────────

_CATEGORY_WEIGHTS: dict[str, float] = {
    "official":      1.5,
    "maps":          1.4,
    "marketplace":   1.3,
    "food_delivery": 1.3,
    "social":        1.2,
    "job_portal":    1.1,
    "news":          1.0,
    "wiki":          0.9,
    "forum":         0.8,
    "web":           0.7,
    "scam_report":   0.6,
    "advice_article": 0.3,
}


# Token yang terlalu umum/lemah untuk membuktikan identitas sendirian.
# Kata-kata ini sering muncul di konteks tak terkait (lagu, video, dsb).
_WEAK_ENTITY_TOKENS = {
    "the", "shop", "store", "toko", "biker", "motor", "mobil", "jual",
    "online", "official", "indonesia", "group", "jaya", "abadi", "sentosa",
}


def _entity_match_score(
    tokens: list[str],
    url: str,
    title: str,
    snippet: str,
    *,
    canonical: str = "",
    brand: str = "",
) -> float:
    """Skor 0–1 berdasarkan seberapa kuat hasil mencerminkan entitas.

    Strategi (paling kuat menang):
      1. Phrase penuh (canonical/brand, compact) ada di hasil → 1.0
      2. Semua token identitas kuat cocok → proporsional
      3. Hanya token lemah/umum yang cocok → dikembalikan rendah (<=0.34)
         supaya tidak sendirian mengangkat hasil tak relevan.
    """
    if not tokens:
        return 0.5

    hay = re.sub(r"[^a-z0-9]+", " ", f"{url} {title} {snippet}".lower())
    hay_compact = hay.replace(" ", "")
    hay_words = set(hay.split())

    # 1) Phrase match penuh (paling kuat) — "thebikershop" di "thebikershop.id"
    for phrase in (canonical, brand):
        p = re.sub(r"[^a-z0-9]+", "", (phrase or "").lower())
        if len(p) >= 5 and p in hay_compact:
            return 1.0

    # 2) Token-level matching — pisahkan token kuat vs lemah
    strong = [t for t in tokens if t not in _WEAK_ENTITY_TOKENS]
    weak = [t for t in tokens if t in _WEAK_ENTITY_TOKENS]

    strong_hits = sum(1 for t in strong if t in hay_words or t in hay_compact)
    weak_hits = sum(1 for t in weak if t in hay_words)

    # Bila ada token kuat, skor didominasi oleh token kuat.
    if strong:
        base = strong_hits / len(strong)
        # Bonus kecil bila token lemah juga ikut cocok (menambah keyakinan)
        bonus = 0.1 * (weak_hits / len(weak)) if weak else 0.0
        return min(1.0, base + bonus)

    # 3) Hanya token lemah — batasi skor maksimal supaya 1 kata umum
    #    ("biker" di "biker song") tidak lolos sebagai bukti identitas.
    if weak_hits >= 2:
        return 0.34
    if weak_hits == 1:
        return 0.2
    return 0.0


def _location_match_score(loc_tokens: list[str], title: str, snippet: str) -> float:
    """Skor 0–1 berdasarkan token lokasi yang cocok."""
    if not loc_tokens:
        return 0.0
    text = f"{title} {snippet}".lower()
    hits = sum(1 for t in loc_tokens if t in text)
    return hits / len(loc_tokens)


def rerank_results(
    results: list[dict[str, Any]],
    entity: dict[str, Any],
    location_tokens: list[str] | None = None,
    *,
    max_results: int = 10,
    drop_irrelevant: bool = True,
) -> list[dict[str, Any]]:
    """
    Re-rank hasil SearXNG berdasarkan:
      - skor SearXNG asli (dari engine)
      - entity match score
      - location match score
      - kategori berat

    Guardian: bila ``drop_irrelevant=True`` (default), hasil yang sama sekali
    tidak menyebut entitas (entity_score == 0) DAN tidak menyebut lokasi
    (location_score == 0) dibuang. Ini menyaring hasil SERP acak yang kebetulan
    lolos (misal lagu/video yang tak terkait dengan bisnis).

    Returns list yang sudah diurutkan, dengan field tambahan:
      "_final_score", "_category", "_entity_score", "_location_score"
    """
    if not results:
        return []

    loc_tokens = location_tokens or []
    ent_tokens: list[str] = entity.get("tokens") or []
    _canonical = entity.get("canonical") or ""
    _brand = entity.get("brand") or ""
    scored: list[dict[str, Any]] = []

    for r in results:
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = r.get("snippet", "")

        category = classify_result(url, title, snippet)
        ent_score = _entity_match_score(
            ent_tokens, url, title, snippet,
            canonical=_canonical, brand=_brand,
        )
        loc_score = _location_match_score(loc_tokens, title, snippet)
        sx_score = float(r.get("score") or 0)
        cat_weight = _CATEGORY_WEIGHTS.get(category, 0.7)

        # Skor gabungan: entity (40%) + searxng (30%) + category (20%) + location (10%)
        final = (ent_score * 0.40) + (min(sx_score, 1.0) * 0.30) + (cat_weight * 0.20) + (loc_score * 0.10)

        scored.append({
            **r,
            "_category": category,
            "_entity_score": round(ent_score, 3),
            "_location_score": round(loc_score, 3),
            "_final_score": round(final, 4),
        })

    scored.sort(key=lambda x: x["_final_score"], reverse=True)

    # ── Guardian: buang hasil yang sama sekali tidak relevan ──────────────
    # Hanya aktif bila kita PUNYA token entitas untuk dicocokkan. Bila entity
    # kosong (resolve gagal), jangan filter — biarkan semua hasil lewat.
    if drop_irrelevant and ent_tokens:
        # Ambang relevansi: entity_score >= 0.5 berarti ada bukti identitas kuat
        # (phrase match penuh = 1.0, atau mayoritas token kuat cocok). Skor
        # rendah (0.2/0.34 dari token lemah tunggal seperti "biker song") TIDAK
        # cukup. location_score >= 0.5 jadi jalur alternatif bukti relevansi.
        relevant = [
            s for s in scored
            if s["_entity_score"] >= 0.5 or s["_location_score"] >= 0.5
        ]
        # Bila SEMUA hasil tidak relevan, kembalikan list kosong agar caller
        # bisa escalate ke query berikutnya (jangan kembalikan sampah).
        if not relevant:
            logger.info(
                "[Rerank] Semua %d hasil tidak relevan dengan entitas (tokens=%s) — dibuang.",
                len(scored), ent_tokens,
            )
            return []
        dropped = len(scored) - len(relevant)
        if dropped:
            logger.info("[Rerank] %d hasil tidak relevan dibuang, %d tersisa.", dropped, len(relevant))
        return relevant[:max_results]

    return scored[:max_results]


# ── 4. Signal Aggregation ─────────────────────────────────────────────────────

def aggregate_signals(reranked_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Gabungkan sinyal dari hasil yang sudah di-rerank menjadi verdict evidence.

    Returns:
        {
            "digital_footprint": "strong" | "moderate" | "weak" | "none",
            "official_presence": bool,
            "marketplace_presence": bool,
            "social_presence": bool,
            "maps_presence": bool,
            "scam_mentions": int,
            "advice_only_scam": bool,   # scam mention tapi hanya artikel edukasi
            "top_categories": list[str],
            "risk_flags": list[str],
            "safe_flags": list[str],
        }
    """
    if not reranked_results:
        return {
            "digital_footprint": "none",
            "official_presence": False,
            "marketplace_presence": False,
            "social_presence": False,
            "maps_presence": False,
            "scam_mentions": 0,
            "advice_only_scam": False,
            "top_categories": [],
            "risk_flags": ["Tidak ditemukan jejak digital untuk entitas ini."],
            "safe_flags": [],
        }

    categories = [r.get("_category", "web") for r in reranked_results]
    cat_counts: dict[str, int] = {}
    for c in categories:
        cat_counts[c] = cat_counts.get(c, 0) + 1

    scam_mentions = cat_counts.get("scam_report", 0)
    advice_mentions = cat_counts.get("advice_article", 0)
    advice_only_scam = scam_mentions == 0 and advice_mentions > 0

    official = cat_counts.get("official", 0) > 0
    marketplace = cat_counts.get("marketplace", 0) > 0
    social = cat_counts.get("social", 0) > 0
    maps = cat_counts.get("maps", 0) > 0

    presence_count = sum([official, marketplace, social, maps])
    total = len(reranked_results)
    if presence_count >= 3 or total >= 6:
        footprint = "strong"
    elif presence_count >= 2 or total >= 4:
        footprint = "moderate"
    elif total >= 1:
        footprint = "weak"
    else:
        footprint = "none"

    risk_flags: list[str] = []
    safe_flags: list[str] = []

    if scam_mentions > 0:
        risk_flags.append(f"Ditemukan {scam_mentions} hasil yang menyebut indikasi penipuan/scam.")
    if advice_only_scam:
        risk_flags.append("Tidak ada laporan scam spesifik; hanya artikel edukasi umum.")
    if footprint == "none":
        risk_flags.append("Entitas tidak memiliki jejak digital yang terverifikasi.")
    elif footprint == "weak":
        risk_flags.append("Jejak digital sangat minim — sulit diverifikasi.")

    if official:
        safe_flags.append("Ditemukan indikasi website/halaman resmi perusahaan.")
    if marketplace:
        safe_flags.append("Ditemukan keberadaan di marketplace publik.")
    if maps:
        safe_flags.append("Ditemukan di Google Maps / direktori lokasi.")
    if social:
        safe_flags.append("Ditemukan keberadaan di platform media sosial.")

    return {
        "digital_footprint": footprint,
        "official_presence": official,
        "marketplace_presence": marketplace,
        "social_presence": social,
        "maps_presence": maps,
        "scam_mentions": scam_mentions,
        "advice_only_scam": advice_only_scam,
        "top_categories": sorted(cat_counts, key=cat_counts.get, reverse=True)[:5],  # type: ignore[arg-type]
        "risk_flags": risk_flags,
        "safe_flags": safe_flags,
    }


# ── 5. Orchestrator ───────────────────────────────────────────────────────────

def intelligent_search(
    raw_company: str,
    raw_address: str = "",
    *,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Pipeline penuh: resolve entity → search SearXNG → rerank → aggregate.

    Dipakai oleh web_evidence.py sebagai pengganti search_web_evidence()
    bila ingin hasil yang lebih akurat dan terstruktur.
    """
    from app.services.osint.searxng_client import searxng_search, is_searxng_available

    entity = resolve_entity(raw_company)
    loc_tokens = extract_location_tokens(raw_address)

    if not entity["search_names"]:
        return {
            "ok": False, "entity": entity, "results": [],
            "signals": aggregate_signals([]), "error": "Nama perusahaan kosong.",
        }

    if not is_searxng_available():
        return {
            "ok": False, "entity": entity, "results": [],
            "signals": aggregate_signals([]),
            "error": "SearXNG tidak tersedia.",
        }

    # ── Query planning: SATU query paling spesifik saja ────────────────────
    # Untuk menghindari rate-limit/captcha engine publik, kita hanya menembak
    # SATU query terbaik (brand + lokasi bila ada, else brand). Hasilnya lalu
    # dipakai bersama oleh semua konsumen (web evidence, social, platform).
    # Versi lama mencoba beberapa query berurutan — itu memicu limit.
    primary_name = entity["brand"] or entity["canonical"] or entity["search_names"][0]
    if loc_tokens:
        used_query = f"{primary_name} {' '.join(loc_tokens[:3])}"
    else:
        used_query = primary_name

    res = searxng_search(used_query, max_results=max_results * 2)
    reranked: list[dict[str, Any]] = []
    if res.get("ok") and res.get("results"):
        reranked = rerank_results(res["results"], entity, loc_tokens, max_results=max_results)
        if not reranked:
            logger.info("[IntelligentSearch] Query '%s' menghasilkan %d hasil tapi 0 relevan.", used_query, len(res["results"]))

    signals = aggregate_signals(reranked)

    return {
        "ok": bool(reranked),
        "query_used": used_query,
        "entity": entity,
        "location_tokens": loc_tokens,
        "results": reranked,
        "signals": signals,
        "engine": "searxng",
        "error": None if reranked else "Tidak ada hasil relevan.",
    }
