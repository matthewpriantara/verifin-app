"""WHOIS + DNS checker — umur domain dan rekaman keamanan email (SPF/DMARC/MX)."""
import logging
from datetime import datetime, timezone

import dns.resolver
import whois

logger = logging.getLogger(__name__)


def check_domain_age(domain: str) -> dict:
    """Cek umur domain dari data WHOIS."""
    logger.debug("Mengecek umur domain: %s", domain)
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date

        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if not creation_date:
            return {"age_days": -1, "age_years": None, "is_new": True, "created_at": "Unknown"}

        # Samakan timezone-aware vs naive
        if getattr(creation_date, "tzinfo", None) is not None:
            now = datetime.now(timezone.utc)
            creation_date = creation_date.replace(tzinfo=timezone.utc) if creation_date.tzinfo is None \
                else creation_date.astimezone(timezone.utc)
        else:
            now = datetime.now()

        age_days = (now - creation_date).days
        return {
            "age_days": age_days,
            "age_years": round(age_days / 365, 2) if age_days >= 0 else None,
            "is_new": age_days < 90,
            "created_at": creation_date.strftime("%Y-%m-%d"),
        }
    except Exception as e:
        logger.warning("WHOIS lookup gagal untuk %s: %s", domain, e)
        return {"error": str(e), "is_new": True, "age_days": -1, "age_years": None, "created_at": "Unknown"}


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


