import re
from transformers import pipeline
import warnings
import threading

# Mengabaikan warning pydantic dan urllib3 agar output terminal bersih
warnings.filterwarnings("ignore")

# Inisialisasi pipeline NER secara malas (lazy loading)
ner_pipeline = None
ner_lock = threading.Lock()

def get_ner_pipeline():
    global ner_pipeline
    if ner_pipeline is None:
        # Menggunakan model NER bahasa Indonesia yang lebih stabil dan resmi
        # Model ini mengenali entitas: B-ORG/I-ORG (Organisasi), B-LOC/I-LOC (Lokasi), B-PER/I-PER (Nama Orang)
        model_name = "cahya/bert-base-indonesian-NER"
        print(f"[*] Memuat model IndoBERT NER ({model_name})...")
        ner_pipeline = pipeline("ner", model=model_name, aggregation_strategy="simple")
    return ner_pipeline

def normalize_phone_typos(text: str) -> str:
    """
    Menormalisasi typo umum OCR pada baris yang dicurigai sebagai nomor HP.
    Contoh: '0857-O431-3821' (O huruf besar) -> '0857-0431-3821'.
    """
    def repl(match):
        s = match.group(0)
        s = s.replace('O', '0').replace('o', '0')
        s = s.replace('I', '1').replace('l', '1').replace('|', '1')
        s = s.replace('S', '5').replace('s', '5')
        return s
    
    # Mencari pola yang diawali digit dan memiliki kombinasi 7-15 karakter angka
    # yang mungkin mengandung pemisah spasi/tanda hubung dan typo karakter huruf (O, o, I, l, |, S, s)
    return re.sub(r'\b\d(?:[\s\-]*[0-9OoIl|Ss]){6,14}\b', repl, text)

def extract_entities_from_text(text: str) -> dict:
    """
    Ekstraksi entitas kunci (Perusahaan/PT, No HP, Alamat, Email/URL) dari teks.
    """
    # Normalisasi typo OCR yang sering terjadi (misal: "JI." atau "JI" menjadi "Jl.")
    # dan "J|." menjadi "Jl."
    normalized_text = re.sub(r'\bJI\b\.?\s+', 'Jl. ', text)
    normalized_text = re.sub(r'\bJ\|\b\.?\s+', 'Jl. ', normalized_text)
    
    # Normalisasi typo OCR pada nomor telepon (O -> 0, I/l -> 1, dll.)
    normalized_text = normalize_phone_typos(normalized_text)

    # 1. Regex parsing untuk data terstruktur yang berpola pasti
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    url_pattern = r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|id|co\.id|net|org|xyz|info))'
    # Bug Fix #1: Regex nomor telepon kini mendukung pemisah spasi dan tanda hubung
    phone_pattern = r'(?:\+62|62|0)[2-9](?:[\s\-]?\d){7,11}'
    salary_pattern = r'(?:Rp\.?|IDR)\s?\d{1,3}(?:\.\d{3})*(?:\s?-\s?(?:Rp\.?|IDR)?\s?\d{1,3}(?:\.\d{3})*)?'
    
    # Regex untuk menangkap baris alamat lengkap di Indonesia dengan batasan kata (word boundary)
    address_pattern = r'\b(?:Jalan|Jl|Dusun|Kav|Gang|Gg)\b\.?\s+[A-Za-z0-9\s,\.\-/]+?(?=\s*(?:•|•|\n|$))'
    
    emails = list(set(re.findall(email_pattern, normalized_text)))
    urls = list(set(re.findall(url_pattern, normalized_text)))
    # Bug Fix #3: Ekstrak domain dari setiap email
    email_domains = {email.split('@')[1] for email in emails if '@' in email}
    urls = [url for url in urls if url not in emails and url not in email_domains]
    
    phones = list(set(re.findall(phone_pattern, normalized_text)))
    standardized_phones = []
    for ph in phones:
        clean_ph = re.sub(r'\D', '', ph)
        if clean_ph.startswith('0'):
            clean_ph = '62' + clean_ph[1:]
        elif clean_ph.startswith('8'):
            clean_ph = '62' + clean_ph
        standardized_phones.append("+" + clean_ph)
    standardized_phones = list(set(standardized_phones))
    
    salaries = list(set(re.findall(salary_pattern, normalized_text, re.IGNORECASE)))
    
    # Ekstraksi alamat menggunakan fallback regex
    extracted_addresses = list(set(re.findall(address_pattern, normalized_text, re.IGNORECASE)))
    # Bersihkan whitespace di ujung alamat
    extracted_addresses = [addr.strip() for addr in extracted_addresses]
    
    # 2. IndoBERT NER parsing (menggunakan chunking / sliding window untuk menghindari limit 512 token)
    companies = []
    locations = []
    
    # Potong teks menjadi chunk maksimum 300 kata dengan overlap 50 kata untuk BERT
    words_list = normalized_text.split()
    chunks = []
    if len(words_list) > 300:
        i = 0
        while i < len(words_list):
            chunks.append(" ".join(words_list[i:i+300]))
            i += 250
    else:
        chunks = [normalized_text]
    
    try:
        nlp = get_ner_pipeline()
        
        # Jalankan inferensi BERT pada setiap chunk secara aman dengan Lock (Thread-safety)
        with ner_lock:
            for chunk in chunks:
                ner_results = nlp(chunk)
                
                for entity in ner_results:
                    word = entity['word'].strip()
                    word = word.replace('##', '')
                    entity_group = entity['entity_group']
                    
                    if len(word) > 2:
                        # Hindari memasukkan URL/Email yang salah dideteksi sebagai ORG
                        if "www" in word or ".com" in word or "http" in word or "@" in word:
                            continue
                            
                        if entity_group == "ORG":
                            companies.append(word.title())
                        elif entity_group == "LOC":
                            locations.append(word.title())
    except Exception as e:
        print(f"[NER Error] Gagal melakukan NER inference: {str(e)}")
    
    # Fallback PT/CV via keyword regex
    # Perbaikan #1: Mendukung tanda titik setelah "CV" (CV. Maju Jaya) dengan (PT\.?|CV\.?)
    pt_pattern = r'\b(PT\.?|CV\.?)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})'
    pt_matches = re.findall(pt_pattern, normalized_text)
    for prefix, match in pt_matches:
        match_clean = match.strip()
        words = match_clean.split()
        if words:
            clean_words = []
            for w in words:
                if w.lower() in ['membuka', 'mencari', 'lowongan', 'membutuhkan']:
                    break
                clean_words.append(w.title())
            if clean_words:
                # Standarisasi awalan badan usaha (PT / CV)
                clean_prefix = "PT" if "pt" in prefix.lower() else "CV"
                companies.append(f"{clean_prefix} " + " ".join(clean_words))
                
    # Gabungkan lokasi dari BERT dengan lokasi dari fallback regex
    all_addresses = list(set(extracted_addresses + locations))
    
    # Standarisasi format penulisan prefix PT/CV (misal: "Cv. Maju" -> "CV Maju", "Pt." -> "PT")
    standardized_companies = []
    for c in companies:
        c_clean = c.strip()
        if c_clean.lower().startswith(('pt ', 'pt. ')):
            c_clean = "PT " + re.sub(r'^pt\b\.?\s*', '', c_clean, flags=re.IGNORECASE).strip()
        elif c_clean.lower().startswith(('cv ', 'cv. ')):
            c_clean = "CV " + re.sub(r'^cv\b\.?\s*', '', c_clean, flags=re.IGNORECASE).strip()
        standardized_companies.append(c_clean)
        
    # Hapus duplikasi dengan case-insensitive
    unique_companies = list({c.lower(): c for c in standardized_companies}.values())
    unique_addresses = list({a.lower(): a for a in all_addresses}.values())
    
    # Pembersihan Kunci (Cleanup Heuristics):
    # 1. Hapus entitas lokasi/alamat atau bagian dari alamat dari daftar nama perusahaan
    cleaned_companies = []
    for comp in unique_companies:
        # 1. Bersihkan kata berulang berturut-turut (misal: "Cakrawala Cakrawala" -> "Cakrawala")
        words = comp.split()
        deduped_words = []
        for w in words:
            if not deduped_words or deduped_words[-1].lower() != w.lower():
                deduped_words.append(w)
        comp_clean_words = " ".join(deduped_words)

        # 2. Saring kata-kata jabatan/informasi umum yang tidak relevan dari nama perusahaan
        comp_cleaned = re.sub(
            r'\b(?:tim|account|officer|hiring|lamar|yogyakarta|sleman|bantul|indonesia|jawa tengah|daerah istimewa)\b', 
            '', 
            comp_clean_words, 
            flags=re.IGNORECASE
        ).strip()

        # Jangan masukkan jika kosong setelah dibersihkan
        if not comp_cleaned:
            continue

        # Perbaikan #2: Jika nama usaha memiliki prefix resmi (PT/CV), jangan hapus meskipun
        # namanya sama dengan nama jalan lokasinya (contoh: PT Malioboro berlokasi di Jl. Malioboro).
        has_legal_prefix = comp.lower().startswith(('pt ', 'cv ', 'pt. ', 'cv. '))

        # Jangan masukkan jika merupakan bagian dari alamat (hanya untuk nama non-resmi/UMKM)
        is_part_of_address = False
        if not has_legal_prefix:
            for addr in unique_addresses:
                if comp_cleaned.lower() in addr.lower():
                    is_part_of_address = True
                    break
        
        # Saring kata-kata sampah / noise umum
        comp_lower = comp_cleaned.lower()
        if comp_lower in [
            'kerja', 'pekerjaan', 'tim kami', 'juli', 'januari', 'februari', 'maret', 
            'april', 'mei', 'juni', 'agustus', 'september', 'oktober', 'november', 'desember'
        ]:
            is_part_of_address = True
            
        # Saring jika ada ekstensi email/domain yang pecah
        # Normalisasi spasi sebelum pengecekan agar 'ail. com' terdeteksi
        comp_norm = comp_lower.replace(' ', '')
        if '.com' in comp_norm or 'gmail' in comp_norm or 'yahoo' in comp_norm or '@' in comp_norm:
            is_part_of_address = True
            
        if not is_part_of_address and len(comp_cleaned) > 2:
            # Pastikan teks dikembalikan dalam bentuk Title Case yang rapi
            cleaned_companies.append(comp_cleaned.title())
            
    # 2. Hapus nama perusahaan yang merupakan substring dari nama perusahaan lain yang lebih panjang
    # Contoh: 'Pt. Rumah' dan 'Cakrawala' diserap ke dalam 'Rumah Baik Cakrawala'
    final_companies = []
    for comp in cleaned_companies:
        # Hapus prefix 'pt' atau 'cv' dan spasi/tanda baca untuk perbandingan bersih
        comp_clean = re.sub(r'^(?:pt|cv)\b\.?\s*', '', comp.lower())
        comp_norm = re.sub(r'[^a-z0-9]', '', comp_clean)
        
        is_duplicate_substring = False
        for other_comp in cleaned_companies:
            if comp != other_comp:
                other_clean = re.sub(r'^(?:pt|cv)\b\.?\s*', '', other_comp.lower())
                other_norm = re.sub(r'[^a-z0-9]', '', other_clean)
                if comp_norm in other_norm and len(other_norm) > len(comp_norm):
                    is_duplicate_substring = True
                    break
        if not is_duplicate_substring:
            final_companies.append(comp)

    # 3. Hapus alamat yang terlalu pendek (misal hanya "Rt 03" atau "Bantul") jika sudah ada alamat yang lebih lengkap
    # Normalisasi spasi dan tanda baca saat perbandingan agar 'No. 26' dan 'No.26' cocok
    cleaned_addresses = []
    for addr in unique_addresses:
        addr_norm = re.sub(r'[^a-z0-9]', '', addr.lower())
        is_duplicate_substring = False
        for other_addr in unique_addresses:
            other_norm = re.sub(r'[^a-z0-9]', '', other_addr.lower())
            if addr != other_addr and addr_norm in other_norm and len(other_norm) > len(addr_norm):
                is_duplicate_substring = True
                break
        if not is_duplicate_substring:
            cleaned_addresses.append(addr)
            
    return {
        "companies": final_companies,
        "contacts": standardized_phones,
        "emails": emails,
        "urls": urls,
        "addresses": cleaned_addresses,
        "salaries": salaries
    }
