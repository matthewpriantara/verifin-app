import whois
import dns.resolver
from datetime import datetime, timezone


def check_domain_age(domain: str):
    """Mengecek umur domain web dalam hitungan hari."""
    print(f"[*] Mengecek umur domain: {domain}...")
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date

        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if not creation_date:
            return {
                "age_days": -1,
                "age_years": None,
                "is_new": True,
                "created_at": "Unknown",
            }

        # Samakan timezone-aware vs naive
        if getattr(creation_date, "tzinfo", None) is not None:
            now = datetime.now(timezone.utc)
            if creation_date.tzinfo is None:
                creation_date = creation_date.replace(tzinfo=timezone.utc)
            else:
                creation_date = creation_date.astimezone(timezone.utc)
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
        return {
            "error": str(e),
            "is_new": True,
            "age_days": -1,
            "age_years": None,
            "created_at": "Unknown",
        }

def check_email_security(domain: str):
    """Memeriksa record SPF dan DMARC pada DNS domain."""
    print(f"[*] Memeriksa keamanan email untuk domain: {domain}...")
    results = {"spf_active": False, "dmarc_active": False}
    try:
        # Cek Record SPF
        spf_records = dns.resolver.resolve(domain, 'TXT')
        for rdata in spf_records:
            if "v=spf1" in str(rdata):
                results["spf_active"] = True
                
        # Cek Record DMARC
        dmarc_records = dns.resolver.resolve(f"_dmarc.{domain}", 'TXT')
        for rdata in dmarc_records:
            if "v=DMARC1" in str(rdata):
                results["dmarc_active"] = True
    except Exception:
        # Jika record DNS tidak ditemukan, return False
        pass
    return results

async def scan_email_osint(email: str, categories: list = None):
    """Scan email footprint (opsional — butuh paket user-scanner)."""
    try:
        from user_scanner.core import engine
    except ImportError:
        return []

    if not categories:
        categories = ["social", "dev", "jobs", "shopping"]

    results = []
    for cat in categories:
        try:
            cat_results = await engine.check_category(cat, email, is_email=True)
            results.extend(cat_results)
        except Exception as e:
            print(f"Error scanning email category {cat}: {e}")

    return [r.to_dict() for r in results if r.is_found()]


async def scan_username_osint(username: str, categories: list = None):
    """Scan username footprint (opsional — butuh paket user-scanner)."""
    try:
        from user_scanner.core import engine
    except ImportError:
        return []

    if not categories:
        categories = ["social", "dev", "finance", "community"]

    results = []
    for cat in categories:
        try:
            cat_results = await engine.check_category(cat, username, is_email=False)
            results.extend(cat_results)
        except Exception as e:
            print(f"Error scanning username category {cat}: {e}")

    return [r.to_dict() for r in results if r.is_found()]
