FREE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "yahoo.com", "yahoo.co.id", "hotmail.com",
    "outlook.com", "live.com", "ymail.com", "icloud.com",
    "protonmail.com", "mail.com",
})

RISK_THRESHOLD_WASPADA = 40
RISK_THRESHOLD_BAHAYA = 75
DOMAIN_NEW_THRESHOLD_DAYS = 90

LEGAL_ENTITY_FORMS: frozenset[str] = frozenset({
    "pt", "cv", "ud", "pd", "perum", "persero", "tbk",
    "firma", "fa", "yayasan", "koperasi", "bumdes", "bumd", "bumn"
})

def score_to_verdict(score: int) -> str:
    if score < RISK_THRESHOLD_WASPADA:
        return "AMAN"
    if score < RISK_THRESHOLD_BAHAYA:
        return "WASPADA"
    return "BAHAYA"
