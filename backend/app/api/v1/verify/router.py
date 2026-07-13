from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from app.services.osint.whois_handler import check_domain_age, check_email_security, scan_email_osint, scan_username_osint

router = APIRouter()

@router.get("/check-domain")
def verify_domain(domain: str = Query(..., description="Domain email yang akan diperiksa (misal: pertamina.com)")):
    age_info = check_domain_age(domain)
    security_info = check_email_security(domain)
    
    # Hitung logika risiko sederhana
    risk_score = 0
    reasons = []
    
    if age_info.get("is_new"):
        risk_score += 50
        reasons.append(f"Domain email sangat baru (dibuat pada {age_info.get('created_at')})")
        
    if not security_info["spf_active"]:
        risk_score += 25
        reasons.append("Domain tidak mengaktifkan proteksi SPF (Rentan spoofing/pemalsuan email)")
        
    if not security_info["dmarc_active"]:
        risk_score += 25
        reasons.append("Domain tidak mengaktifkan kebijakan DMARC")
        
    verdict = "AMAN"
    if risk_score >= 75:
        verdict = "BAHAYA"
    elif risk_score >= 40:
        verdict = "WASPADA"
        
    return {
        "domain": domain,
        "risk_score": risk_score,
        "verdict": verdict,
        "reasons": reasons,
        "details": {
            "age": age_info,
            "security": security_info
        }
    }

@router.get("/osint/scan-email")
async def verify_email_osint(
    email: str = Query(..., description="Email yang akan dilacak footprint-nya"),
    categories: Optional[List[str]] = Query(None, description="Kategori platform (misal: social, dev, jobs, shopping)")
):
    try:
        results = await scan_email_osint(email, categories)
        return {
            "email": email,
            "found_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/osint/scan-username")
async def verify_username_osint(
    username: str = Query(..., description="Username yang akan dilacak footprint-nya"),
    categories: Optional[List[str]] = Query(None, description="Kategori platform (misal: social, dev, finance, community)")
):
    try:
        results = await scan_username_osint(username, categories)
        return {
            "username": username,
            "found_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
