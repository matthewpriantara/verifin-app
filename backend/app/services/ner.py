import re
from transformers import pipeline
import warnings

# Mengabaikan warning pydantic dan urllib3 agar output terminal bersih
warnings.filterwarnings("ignore")

# Inisialisasi pipeline NER secara malas (lazy loading)
ner_pipeline = None

def get_ner_pipeline():
    global ner_pipeline
    if ner_pipeline is None:
        # Menggunakan model NER bahasa Indonesia yang lebih stabil dan resmi
        # Model ini mengenali entitas: B-ORG/I-ORG (Organisasi), B-LOC/I-LOC (Lokasi), B-PER/I-PER (Nama Orang)
        model_name = "cahya/bert-base-indonesian-NER"
        print(f"[*] Memuat model IndoBERT NER ({model_name})...")
        ner_pipeline = pipeline("ner", model=model_name, aggregation_strategy="simple")
    return ner_pipeline

def extract_entities_from_text(text: str) -> dict:
    """
    Ekstraksi entitas kunci (Perusahaan/PT, No HP, Alamat, Email/URL) dari teks.
    """
    # 1. Regex parsing untuk data terstruktur yang berpola pasti
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    url_pattern = r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|id|co\.id|net|org|xyz|info))'
    phone_pattern = r'(?:\+62|62|0)[2-9]\d{7,11}'
    salary_pattern = r'(?:Rp\.?|IDR)\s?\d{1,3}(?:\.\d{3})*(?:\s?-\s?(?:Rp\.?|IDR)?\s?\d{1,3}(?:\.\d{3})*)?'
    
    emails = list(set(re.findall(email_pattern, text)))
    urls = list(set(re.findall(url_pattern, text)))
    # Bersihkan URL yang terdeteksi sebagai email
    urls = [url for url in urls if url not in emails and "gmail.com" not in url and "yahoo.com" not in url]
    
    phones = list(set(re.findall(phone_pattern, text)))
    # Standarisasi format nomor telepon ke format E.164 (+62)
    standardized_phones = []
    for ph in phones:
        clean_ph = re.sub(r'\D', '', ph)
        if clean_ph.startswith('0'):
            clean_ph = '62' + clean_ph[1:]
        elif clean_ph.startswith('8'):
            clean_ph = '62' + clean_ph
        standardized_phones.append("+" + clean_ph)
    standardized_phones = list(set(standardized_phones))
    
    salaries = list(set(re.findall(salary_pattern, text, re.IGNORECASE)))
    
    # 2. IndoBERT NER parsing
    companies = []
    locations = []
    
    try:
        nlp = get_ner_pipeline()
        ner_results = nlp(text)
        
        for entity in ner_results:
            word = entity['word'].strip()
            # Bersihkan token subword (seperti ##word)
            word = word.replace('##', '')
            entity_group = entity['entity_group']
            
            if len(word) > 2:
                # Hindari memasukkan URL yang salah dideteksi sebagai ORG
                if "www" in word or ".com" in word or "http" in word:
                    continue
                    
                if entity_group == "ORG":
                    companies.append(word.title()) # Format kapital di awal kata
                elif entity_group == "LOC":
                    locations.append(word.title())
    except Exception as e:
        print(f"[NER Error] Gagal melakukan NER inference: {str(e)}")
    
    # Fallback PT via keyword regex
    pt_pattern = r'(?:PT\s+|CV\s+|PT\.\s*)([A-Z][a-zA-Z0-9\s]+)'
    pt_matches = re.findall(pt_pattern, text)
    for match in pt_matches:
        match_clean = match.strip()
        words = match_clean.split()
        if words:
            # Ambil maksimal 3 kata, buang kata-kata tidak perlu seperti 'membuka'
            clean_words = []
            for w in words[:4]:
                if w.lower() in ['membuka', 'mencari', 'lowongan', 'membutuhkan']:
                    break
                clean_words.append(w.title())
            if clean_words:
                companies.append(" ".join(clean_words))
            
    # Hapus duplikasi dengan case-insensitive
    unique_companies = list({c.lower(): c for c in companies}.values())
    unique_locations = list({c.lower(): c for c in locations}.values())
    
    return {
        "companies": unique_companies,
        "contacts": standardized_phones,
        "emails": emails,
        "urls": urls,
        "addresses": unique_locations,
        "salaries": salaries
    }
