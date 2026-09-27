import logging
from datetime import datetime, timezone

import dns.resolver
import whois
from app.services.constants import DOMAIN_NEW_THRESHOLD_DAYS
logger = logging.getLogger(__name__)


def _rdap_first_seen(domain: str) -> datetime | None:
    try:
        from curl_cffi import requests as cffi_req
        r = cffi_req.get(f"https://rdap.org/domain/{domain}", impersonate="chrome120", timeout=8)
    except ImportError:
        import requests as _stdlib_req
        r = _stdlib_req.get(f"https://rdap.org/domain/{domain}", timeout=8,
            headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        return None
    data = r.json()
    for event in data.get("events", []):
        if event.get("eventAction") == "registration":
            date_str = event.get("eventDate", "")
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return None


def _wayback_first_seen(domain: str) -> datetime | None:
    try:
        url = (
            f"https://web.archive.org/cdx/search/cdx"
            f"?url={domain}&output=json&limit=1&fl=timestamp&from=2000&filter=statuscode:200"
        )
        try:
            from curl_cffi import requests as cffi_req
            r = cffi_req.get(url, impersonate="chrome120", timeout=6)
        except ImportError:
            import requests as _stdlib_req
            r = _stdlib_req.get(url, timeout=6,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.1"})
        if r.status_code != 200:
            return None
        data = r.json()
        if len(data) >= 2 and data[1]:
            ts = data[1][0]
            return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.debug("Wayback CDX fallback gagal untuk %s: %s", domain, e)
    return None


def check_domain_age(domain: str) -> dict:
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
        creation_date = _rdap_first_seen(domain)
        if creation_date:
            source = "rdap"

    if not creation_date:
        creation_date = _wayback_first_seen(domain)
        source = "wayback_cdx"

    if not creation_date:
        return {"age_days": -1, "age_years": None, "is_new": None, "created_at": "Unknown", "source": source}

    now = datetime.now(timezone.utc)
    if getattr(creation_date, "tzinfo", None) is None:
        creation_date = creation_date.replace(tzinfo=timezone.utc)
    else:
        creation_date = creation_date.astimezone(timezone.utc)

    age_days = (now - creation_date).days
    return {
        "age_days": age_days,
        "age_years": round(age_days / 365, 2) if age_days >= 0 else None,
        "is_new": age_days < DOMAIN_NEW_THRESHOLD_DAYS,
        "created_at": creation_date.strftime("%Y-%m-%d"),
        "source": source,
    }


def check_email_security(domain: str) -> dict:
    logger.debug("Memeriksa keamanan email untuk domain: %s", domain)
    results = {"spf_active": False, "dmarc_active": False, "mx_active": False, "mx_provider": None}
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 4.0
    try:
        for rdata in resolver.resolve(domain, "TXT"):
            if "v=spf1" in str(rdata):
                results["spf_active"] = True
    except Exception:
        pass

    try:
        for rdata in resolver.resolve(f"_dmarc.{domain}", "TXT"):
            if "v=DMARC1" in str(rdata):
                results["dmarc_active"] = True
    except Exception:
        pass

    try:
        mx_records = list(resolver.resolve(domain, "MX"))
        if mx_records:
            results["mx_active"] = True
            results["mx_provider"] = str(mx_records[0].exchange).rstrip(".")
    except Exception:
        pass

    return results


