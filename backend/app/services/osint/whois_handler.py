"""WHOIS + DNS checker — umur domain dan rekaman keamanan email (SPF/DMARC/MX)."""
import logging
from datetime import datetime, timezone

import dns.resolver
import whois

logger = logging.getLogger(__name__)


def _wayback_first_seen(domain: str) -> datetime | None:
    """Fallback: tanya Wayback Machine CDX API kapan domain pertama kali di-crawl."""
    try:
        from curl_cffi import requests as cffi_req
        url = (
            f"https://web.archive.org/cdx/search/cdx"
            f"?url={domain}&output=json&limit=1&fl=timestamp&from=2000&filter=statuscode:200"
        )
        r = cffi_req.get(url, impersonate="chrome120", timeout=6)
        if r.status_code != 200:
            return None
        data = r.json()
        # data[0] = header row ["timestamp"], data[1] = first result
        if len(data) >= 2 and data[1]:
            ts = data[1][0]  # format: "20250317144540"
            return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.debug("Wayback CDX fallback gagal untuk %s: %s", domain, e)
    return None


def check_domain_age(domain: str) -> dict:
    """Cek umur domain dari WHOIS, fallback ke Wayback Machine CDX kalau WHOIS gagal."""
    logger.debug("Mengecek umur domain: %s", domain)
    creation_date = None
    source = "whois"

    try:
        w = whois.whois(domain)
        cd = w.creation_date
        if isinstance(cd, list):
            cd = cd[0]
        if cd:
            creation_date = cd
    except Exception as e:
        logger.debug("WHOIS lookup gagal untuk %s: %s", domain, e)

    if not creation_date:
        creation_date = _wayback_first_seen(domain)
        source = "wayback_cdx"

    if not creation_date:
        return {"age_days": -1, "age_years": None, "is_new": None, "created_at": "Unknown", "source": source}

    # Normalize ke UTC
    now = datetime.now(timezone.utc)
    if getattr(creation_date, "tzinfo", None) is None:
        creation_date = creation_date.replace(tzinfo=timezone.utc)
    else:
        creation_date = creation_date.astimezone(timezone.utc)

    age_days = (now - creation_date).days
    return {
        "age_days": age_days,
        "age_years": round(age_days / 365, 2) if age_days >= 0 else None,
        "is_new": age_days < 90,
        "created_at": creation_date.strftime("%Y-%m-%d"),
        "source": source,
    }


def check_email_security(domain: str) -> dict:
    """Cek rekaman SPF, DMARC, dan MX pada DNS domain."""
    logger.debug("Memeriksa keamanan email untuk domain: %s", domain)
    results = {"spf_active": False, "dmarc_active": False, "mx_active": False, "mx_provider": None}
    try:
        for rdata in dns.resolver.resolve(domain, "TXT"):
            if "v=spf1" in str(rdata):
                results["spf_active"] = True
    except Exception:
        pass

    try:
        for rdata in dns.resolver.resolve(f"_dmarc.{domain}", "TXT"):
            if "v=DMARC1" in str(rdata):
                results["dmarc_active"] = True
    except Exception:
        pass

    try:
        mx_records = list(dns.resolver.resolve(domain, "MX"))
        if mx_records:
            results["mx_active"] = True
            results["mx_provider"] = str(mx_records[0].exchange).rstrip(".")
    except Exception:
        pass

    return results


