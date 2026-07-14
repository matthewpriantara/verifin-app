"""
Hermes Reasoning Engine untuk Verifin.
Menghubungkan sistem ke model LLM lokal (Ollama) untuk menganalisis
risiko penipuan lowongan kerja berdasarkan data OSINT & NER.
"""

import json
import re
import httpx
from app.services.llm.prompt_builder import build_verify_prompt, build_text_verify_prompt

# Konfigurasi Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "hermes3"  # Ganti sesuai nama model di Ollama (cek: ollama list)
OLLAMA_TIMEOUT = 300.0    # Timeout 5 menit untuk proses reasoning/cold-start loading


def _extract_json_from_response(text: str) -> dict:
    """
    Mengekstrak JSON dari respons teks LLM yang mungkin mengandung
    teks pengantar sebelum/sesudah JSON.
    """
    # Coba parse langsung terlebih dahulu
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Cari blok JSON menggunakan regex (antara kurung kurawal pertama dan terakhir)
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Jika tidak ditemukan JSON yang valid, kembalikan error terstruktur
    return {
        "verdict": "ERROR",
        "risk_score": 0,
        "summary": "AI tidak dapat menghasilkan analisis yang valid. Coba lagi.",
        "risk_factors": [],
        "safe_factors": [],
        "recommendations": ["Lakukan pengecekan manual pada lowongan kerja ini."]
    }


def _get_mock_osint_result() -> dict:
    """
    Data tiruan (mock) OSINT untuk modul yang belum diimplementasikan.
    Akan diganti dengan data asli setelah modul OSINT lain selesai dibuat.
    """
    return {
        "domain": {
            "age_years": None,
            "created_at": "Tidak diketahui",
            "is_new": False
        },
        "email_security": {
            "spf_active": False,
            "dmarc_active": False
        }
    }


async def analyze_with_hermes(entities: dict, osint_results: dict = None, raw_text: str = None) -> dict:
    """
    Mengirim data ke Hermes LLM via Ollama dan mengembalikan analisis risiko penipuan.
    
    Args:
        entities: Dict hasil ekstraksi NER (companies, contacts, emails, dll).
        osint_results: Dict hasil OSINT. Jika None, akan menggunakan mock data.
        raw_text: Teks kasar dari OCR (opsional, untuk konteks tambahan LLM).
        
    Returns:
        Dict berisi verdict, risk_score, summary, risk_factors, safe_factors, recommendations.
    """
    # Gunakan mock data jika OSINT belum dijalankan
    if osint_results is None:
        osint_results = _get_mock_osint_result()

    # Bangun prompt
    if raw_text:
        prompt = build_text_verify_prompt(raw_text, entities, osint_results)
    else:
        prompt = build_verify_prompt(entities, osint_results)

    # Kirim ke Ollama
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,    # Rendah agar output konsisten dan tidak ngawur
                        "top_p": 0.9,
                        "num_predict": 1024    # Batasi panjang jawaban
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            raw_llm_output = result.get("response", "")
            
            # Parsing JSON dari output LLM
            parsed = _extract_json_from_response(raw_llm_output)
            
            # Tambahkan metadata tambahan untuk transparansi
            parsed["model_used"] = OLLAMA_MODEL
            parsed["entities_analyzed"] = entities
            
            return parsed

    except httpx.ConnectError:
        # Ollama tidak berjalan di localhost
        return {
            "verdict": "ERROR",
            "risk_score": 0,
            "summary": f"Tidak dapat terhubung ke Ollama di {OLLAMA_BASE_URL}. Pastikan Ollama sudah berjalan dengan perintah: ollama serve",
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": ["Jalankan Ollama terlebih dahulu: ollama serve"],
            "model_used": OLLAMA_MODEL,
            "entities_analyzed": entities
        }
    except httpx.TimeoutException:
        return {
            "verdict": "ERROR",
            "risk_score": 0,
            "summary": f"Waktu tunggu habis saat menghubungi Ollama (timeout: {OLLAMA_TIMEOUT}s). Model terlalu lambat.",
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": ["Coba gunakan model yang lebih ringan di Ollama."],
            "model_used": OLLAMA_MODEL,
            "entities_analyzed": entities
        }
    except Exception as e:
        return {
            "verdict": "ERROR",
            "risk_score": 0,
            "summary": f"Terjadi kesalahan tak terduga saat menjalankan analisis AI: {str(e)}",
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": ["Lakukan pengecekan manual pada lowongan kerja ini."],
            "model_used": OLLAMA_MODEL,
            "entities_analyzed": entities
        }


def check_ollama_status() -> dict:
    """
    Mengecek apakah Ollama berjalan dan model Hermes tersedia.
    """
    try:
        import httpx as _httpx
        response = _httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]
        hermes_available = any(OLLAMA_MODEL in name for name in model_names)
        
        return {
            "ollama_running": True,
            "hermes_available": hermes_available,
            "available_models": model_names,
            "target_model": OLLAMA_MODEL
        }
    except Exception:
        return {
            "ollama_running": False,
            "hermes_available": False,
            "available_models": [],
            "target_model": OLLAMA_MODEL
        }
