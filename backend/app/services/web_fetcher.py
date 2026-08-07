"""Web/social fetcher — Scrapling + Instagram/Threads scraper untuk URL OSINT."""
from __future__ import annotations

import asyncio
import logging
import re
import tempfile

import httpx
from bs4 import BeautifulSoup
from app.services.url_guard import validate_public_http_url

logger = logging.getLogger(__name__)

# Noise pattern footer Instagram/Threads — break saat ketemu baris ini
_IG_NOISE_PATTERNS = [
    r"Jangan pernah lewatkan postingan",
    r"Daftar Instagram untuk tetap tahu",
    r"Pengunggahan Kontak & Nonpengguna Meta",
    r"Order Via Wa Only",
    r"Jasa Ketik CV",
    r"upgrade CV",
    r"Lihat Postingan Lainnya",
    r"INFO LOWONGAN KERJA SOLO",
    r"Dibutuhkan staf Kantor",
    r"Lihat apa yang sedang dibicarakan",
    r"bergabunglah dengan percakapan",
    r"Laporkan masalah",
]

def _sync_scrapling_fetch(url: str) -> tuple[str, list[str]]:
    """Scrape teks + image URLs dari URL (IG embed, oEmbed, proxy, Scrapling, HTTPX fallback)."""
    validate_public_http_url(url)

    combined_caption_text = ""
    image_urls = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # Penanganan Khusus Instagram (post / reel / tv)
    ig_match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url, re.I)
    if ig_match:
        shortcode = ig_match.group(1)
        # 1. Coba Halaman Embed Instagram (Sangat efektif mengekstrak poster & caption publik tanpa login)
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        try:
            res = httpx.get(embed_url, headers=headers, follow_redirects=True, timeout=12.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                caption_el = soup.find("div", class_="Caption") or soup.find("div", class_="CaptionComments")
                if caption_el:
                    combined_caption_text = caption_el.get_text(separator="\n", strip=True)

                img_els = soup.find_all("img", class_="EmbeddedMediaImage") or soup.find_all("img")
                for img in img_els:
                    src = img.get("src")
                    if src and ("scontent" in src or "cdninstagram.com" in src):
                        image_urls.append(src)

                # Ekstrak URL scontent CDN dari script/raw text HTML embed
                found_scontent = re.findall(r'https://scontent[^"\'\s\\]+', res.text)
                for s_url in found_scontent:
                    clean = s_url.replace("\\u0026", "&").replace("\\/", "/")
                    image_urls.append(clean)
        except Exception as exc:
            logger.warning("[Instagram Embed] %s", exc)

        # 2. Jika belum dapat gambar, coba oEmbed API
        if not image_urls:
            try:
                oembed_url = f"https://www.instagram.com/api/v1/oembed/?url={url}"
                o_res = httpx.get(oembed_url, headers=headers, follow_redirects=True, timeout=8.0)
                if o_res.status_code == 200:
                    data = o_res.json()
                    if data.get("title") and not combined_caption_text:
                        combined_caption_text = data.get("title")
                    if data.get("thumbnail_url"):
                        image_urls.append(data.get("thumbnail_url"))
            except Exception as exc:
                logger.warning("[Instagram oEmbed] %s", exc)

        # 3. Jika gambar belum dapat, coba proxy fixer (vxinstagram / ddinstagram)
        if not image_urls:
            for domain in ["vxinstagram.com", "ddinstagram.com"]:
                try:
                    fix_url = f"https://{domain}/p/{shortcode}/"
                    f_res = httpx.get(fix_url, headers={"User-Agent": "facebookexternalhit/1.1"}, follow_redirects=True, timeout=8.0)
                    if f_res.status_code == 200:
                        f_soup = BeautifulSoup(f_res.text, "html.parser")
                        og_i = f_soup.find("meta", property="og:image") or f_soup.find("meta", attrs={"name": "twitter:image"})
                        if og_i and og_i.get("content"):
                            image_urls.append(og_i["content"])
                        og_d = f_soup.find("meta", property="og:description") or f_soup.find("meta", attrs={"name": "description"})
                        if og_d and og_d.get("content") and not combined_caption_text:
                            combined_caption_text = og_d["content"]
                        if image_urls:
                            break
                except Exception:
                    pass

    # Generic Scrapling/HTTPX fetcher (untuk website non-IG atau fallback)
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, headers=headers)
        text_parts = []
        if combined_caption_text:
            text_parts.append(combined_caption_text)

        og_title = page.css("meta[property='og:title']::attr(content)").get() or page.css("title::text").get()
        if og_title and og_title.strip() and og_title.strip() not in text_parts:
            text_parts.append(og_title.strip())

        company_meta = (
            page.css("span[data-automation='advertiser-name']::text").get()
            or page.css("span[data-automation*='company']::text").get()
            or page.css("a[data-automation*='company']::text").get()
        )
        if company_meta and company_meta.strip():
            text_parts.append(f"Perusahaan/Pengiklan: {company_meta.strip()}")

        og_desc = (
            page.css("meta[property='og:description']::attr(content)").get() 
            or page.css("meta[name='description']::attr(content)").get()
        )
        if og_desc and og_desc.strip() and og_desc.strip() not in text_parts:
            text_parts.append(og_desc.strip())

        body_texts = [
            t.strip()
            for t in page.css(
                "p::text, h1::text, h2::text, h3::text, li::text, article::text, "
                "div[data-automation*='job']::text, div[class*='description']::text, "
                "div[class*='job']::text, span[dir='auto']::text, span[data-automation*='advertiser']::text"
            ).getall()
            if len(t.strip()) > 15
        ]
        if body_texts:
            seen_b = set()
            unique_body = []
            for b in body_texts:
                if b not in seen_b and not any(x in b.lower() for x in ["cookie", "privacy policy", "terms of service", "log in", "sign up"]):
                    seen_b.add(b)
                    unique_body.append(b)
            text_parts.append(" ".join(unique_body[:30])[:3000])

        combined_caption_text = "\n".join(text_parts).strip()

        # Filter footer noise Instagram/Threads
        lines_clean = []
        for line in (combined_caption_text or "").splitlines():
            if any(re.search(pat, line, re.I) for pat in _IG_NOISE_PATTERNS):
                break
            lines_clean.append(line)
        combined_caption_text = "\n".join(lines_clean).strip()

        og_img = (
            page.css("meta[property='og:image']::attr(content)").get()
            or page.css("meta[name='twitter:image']::attr(content)").get()
        )
        if og_img and og_img.strip():
            image_urls.append(og_img.strip())

    except Exception as exc:
        logger.warning("[Scrapling Fetch] %s", exc)

    if not combined_caption_text:
        try:
            res = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                text_parts = []
                og_title = soup.find("meta", property="og:title") or soup.find("title")
                if og_title:
                    text_parts.append(og_title.get("content") or og_title.get_text())
                og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                if og_desc and og_desc.get("content"):
                    text_parts.append(og_desc["content"].strip())
                combined_caption_text = "\n".join(text_parts).strip()
                if not image_urls:
                    og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                    if og_img and og_img.get("content"):
                        image_urls.append(og_img["content"].strip())
        except Exception as exc:
            logger.warning("[HTTPX Scrape Fallback] %s", exc)

    # Deduplicate preserving order
    seen_urls = set()
    dedup_images = []
    for img_u in image_urls:
        if img_u and img_u not in seen_urls:
            seen_urls.add(img_u)
            dedup_images.append(img_u)

    return combined_caption_text, dedup_images[:3]

async def _fetch_url_content_and_image(url: str) -> tuple[str, list[str]]:
    """
    Scrape teks (caption/description) & daftar image URL poster (termasuk carousel slides) dari URL.
    Returns: (extracted_text, temp_image_paths_list)
    """
    validate_public_http_url(url)
    loop = asyncio.get_running_loop()
    combined_caption_text, image_urls = await loop.run_in_executor(None, _sync_scrapling_fetch, url)

    tmp_img_paths = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        for img_url in image_urls:
            try:
                validate_public_http_url(img_url)
                img_res = await client.get(img_url)
                if img_res.status_code == 200 and len(img_res.content) > 1000:
                    ext = ".png" if ".png" in img_url.lower() else ".webp" if ".webp" in img_url.lower() else ".jpg"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(img_res.content)
                        tmp_img_paths.append(tmp.name)
            except Exception as exc:
                logger.warning("[URL Fetch] gagal unduh gambar %s: %s", img_url, exc)

    return combined_caption_text, tmp_img_paths
