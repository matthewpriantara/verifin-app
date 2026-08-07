"""Build generic search fallbacks from extracted job entities."""

import re

from app.services.constants import FREE_EMAIL_DOMAINS

_LEGAL_PREFIX = re.compile(r"^(?:pt|cv|ud|tbk|firma|yayasan)\.?\s+", re.I)
_ADDRESS_LABEL = re.compile(
    r"^(?:alamat|lokasi|penempatan|wilayah|area|office|basecamp)\s*[:.-]?\s*",
    re.I,
)
_GENERIC_LOCATION_WORDS = {
    "jalan", "jl", "jln", "nomor", "no", "rt", "rw", "kec", "kecamatan",
    "kab", "kabupaten", "kota", "desa", "kelurahan", "daerah", "istimewa",
    "indonesia", "prov", "provinsi",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip(" ,.;:-")


def _company_forms(company: str) -> tuple[str, str | None]:
    full = _clean_text(company)
    aliases = re.findall(r"\(([^()]{3,80})\)", full)
    without_legal = _clean_text(_LEGAL_PREFIX.sub("", full))
    without_legal = _clean_text(re.sub(r"[^\w\s]", " ", without_legal))
    brand = _clean_text(aliases[0]) if aliases else None
    if brand and brand.lower() == without_legal.lower():
        brand = None
    return without_legal, brand


def _location_phrase(address: str, brand: str | None = None) -> str | None:
    text = _ADDRESS_LABEL.sub("", _clean_text(address))
    parts = [p.strip() for p in text.split(",") if p.strip()]
    branch_hint = ""
    if ":" in text:
        branch_hint = _clean_text(text.split(":", 1)[0])
        if brand:
            brand_tokens = set(re.split(r"[^\w]+", brand.lower()))
            branch_hint = " ".join(
                word for word in re.split(r"\s+", branch_hint)
                if word.lower() not in brand_tokens
            )
    if len(parts) >= 2:
        words = [w for w in re.split(r"[^\w]+", " ".join(parts[-3:]).lower()) if w]
        useful = [w for w in words if len(w) >= 4 and w not in _GENERIC_LOCATION_WORDS and not w.isdigit()]
        location_words = ([word for word in branch_hint.lower().split() if len(word) >= 3] + useful)
        if location_words:
            return " ".join(dict.fromkeys(location_words[-5:]))
    if parts:
        useful = [
            word for word in re.split(r"[^\w]+", parts[0].lower())
            if len(word) >= 3 and word not in _GENERIC_LOCATION_WORDS
        ]
        if useful:
            return " ".join(useful[-3:])
    return None


def build_search_queries(entities: dict, *, include_email: bool = True) -> list[dict[str, str]]:
    """Return ordered, deduplicated fallback queries with their source kind."""
    companies = [str(c) for c in (entities.get("companies") or []) if str(c).strip()]
    addresses = [str(a) for a in (entities.get("addresses") or []) if str(a).strip()]
    locations = [str(a) for a in (entities.get("location_candidates") or []) if str(a).strip()]
    emails = [str(e).strip().lower() for e in (entities.get("emails") or []) if "@" in str(e)]

    queries: list[dict[str, str]] = []
    if companies:
        full = _clean_text(companies[0])
        without_legal, brand = _company_forms(full)
        queries.append({"kind": "company_exact", "query": f'"{full}"'})
        if without_legal and without_legal.lower() != full.lower():
            queries.append({"kind": "company_clean", "query": f'"{without_legal}"'})

        brands = [brand] if brand else []
        brands.extend(_clean_text(candidate) for candidate in companies[1:])
        location_source = addresses[0] if addresses else ", ".join(locations[:5])
        for candidate in brands:
            if not candidate or candidate.lower() == full.lower():
                continue
            queries.append({"kind": "brand", "query": f'"{candidate}"'})
            location = _location_phrase(location_source, candidate) if location_source else None
            if location:
                queries.append({"kind": "brand_location", "query": f'"{candidate}" "{location}"'})

    if include_email:
        for email in emails[:1]:
            domain = email.rsplit("@", 1)[-1]
            if domain not in FREE_EMAIL_DOMAINS:
                queries.append({"kind": "email", "query": f'"{email}"'})
            else:
                queries.append({"kind": "email", "query": f'"{email}"'})

    seen: set[str] = set()
    return [item for item in queries if not (item["query"].lower() in seen or seen.add(item["query"].lower()))]
