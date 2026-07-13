import whois
import dns.resolver
from datetime import datetime

def check_domain_age(domain: str):
    """Mengecek umur domain web dalam hitungan hari."""
    print(f"[*] Mengecek umur domain: {domain}...")
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        
        # WHOIS terkadang mengembalikan list datetime jika ada beberapa server
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
            
        if not creation_date:
            return {"age_days": -1, "is_new": True, "created_at": "Unknown"}
            
        age_days = (datetime.now() - creation_date).days
        return {
            "age_days": age_days,
            "is_new": age_days < 90, # Bendera merah jika umur domain < 3 bulan
            "created_at": creation_date.strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": str(e), "is_new": True, "age_days": -1}

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
    """Scan email across specified categories or all categories using user-scanner."""
    from user_scanner.core import engine
    if not categories:
        # Check common categories to avoid scanning all 120+ platforms which might be slow
        categories = ["social", "dev", "jobs", "shopping"]
    
    results = []
    for cat in categories:
        try:
            cat_results = await engine.check_category(cat, email, is_email=True)
            results.extend(cat_results)
        except Exception as e:
            print(f"Error scanning email category {cat}: {e}")
            
    # Return list of dicts for found/registered accounts
    return [r.to_dict() for r in results if r.is_found()]

async def scan_username_osint(username: str, categories: list = None):
    """Scan username across specified categories or all categories using user-scanner."""
    from user_scanner.core import engine
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

if __name__ == "__main__":
    import asyncio
    # Test case 1: Domain Resmi UGM (Pasti Aman)
    domain_aman = "ugm.ac.id"
    # Test case 2: Domain simulasi penipuan (Ubah dengan domain mencurigakan yang Anda temukan)
    domain_mencurigakan = "recruitment-pertamina-tbk.com"
    
    print("=== PENGUJIAN 1: DOMAIN RESMI UGM ===")
    print(check_domain_age(domain_aman))
    print(check_email_security(domain_aman))
    print("-" * 50)
    
    print("=== PENGUJIAN 2: DOMAIN RECRUITMENT PALSU ===")
    print(check_domain_age(domain_mencurigakan))
    print(check_email_security(domain_mencurigakan))
    print("-" * 50)

    print("=== PENGUJIAN 3: OSINT SCAN EMAIL ===")
    email_test = "test@gmail.com"
    results_email = asyncio.run(scan_email_osint(email_test, ["dev"]))
    print(f"Hasil scan email '{email_test}' pada kategori 'dev':")
    for r in results_email:
        print(f"- {r.get('site_name')}: {r.get('status')} ({r.get('url')})")
    print("-" * 50)

    print("=== PENGUJIAN 4: OSINT SCAN USERNAME ===")
    username_test = "kaifcodec"
    results_username = asyncio.run(scan_username_osint(username_test, ["dev"]))
    print(f"Hasil scan username '{username_test}' pada kategori 'dev':")
    for r in results_username:
        print(f"- {r.get('site_name')}: {r.get('status')} ({r.get('url')})")
