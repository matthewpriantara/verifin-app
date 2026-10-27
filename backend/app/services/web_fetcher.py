from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from urllib.parse import quote

from bs4 import BeautifulSoup
from app.services.url_guard import resolve_public_url, safe_get, safe_get_async, validate_public_http_url

logger = logging.getLogger(__name__)

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

_APPLY_LINK_HOSTS = re.compile(r"(?:^|\.)(?:s\.id|bit\.ly|forms\.gle|lynk\.id|linktr\.ee|tinyurl\.com)$|docs\.google\.com", re.I)
_APPLY_LINK_TEXT = re.compile(r"formulir|form|lamar|apply|daftar|register", re.I)


def _find_job_posting(node) -> dict | None:
    if isinstance(node, list):
        return next((p for p in (_find_job_posting(n) for n in node) if p), None)
    if not isinstance(node, dict):
        return None
    types = node.get("@type")
    if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
        return node
    return _find_job_posting(node.get("@graph")) if "@graph" in node else None


def _decode_cfemail(hexstr: str) -> str:
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except ValueError:
        return ""


def _job_posting_page_text(html: str, url: str) -> tuple[str, str | None]:
    """Halaman portal lowongan dengan schema.org JobPosting (LokerJogja, Jobstreet, Glints, KitaLulus).

    Hanya data lowongan itu sendiri dan tautan kontak di isi utama yang diambil. Sidebar
    "lowongan lain" sengaja tidak dibaca karena nama perusahaannya ikut terbaca sebagai
    pemberi kerja dan bagian "Kirim Lamaran" terpotong.
    """
    import json
    from urllib.parse import unquote, urlparse

    soup = BeautifulSoup(html, "html.parser")
    posting = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            posting = _find_job_posting(json.loads(script.string or script.get_text() or "", strict=False))
        except ValueError:
            continue
        if posting:
            break
    if not posting or not posting.get("title"):
        return "", None

    def clean(value) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    org = posting.get("hiringOrganization") or {}
    lines = [f"Posisi: {clean(posting.get('title'))}"]
    if isinstance(org, dict) and org.get("name"):
        lines.append(f"Perusahaan: {clean(org['name'])}")
    places = posting.get("jobLocation") or []
    for place in places if isinstance(places, list) else [places]:
        addr = (place or {}).get("address") if isinstance(place, dict) else None
        if isinstance(addr, dict):
            parts = [clean(addr.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")]
            parts = [p for p in parts if p and "tidak diketahui" not in p.lower()]
            if parts:
                lines.append(f"Lokasi: {', '.join(parts)}")
    salary = (posting.get("baseSalary") or {}).get("value") if isinstance(posting.get("baseSalary"), dict) else None
    if isinstance(salary, dict) and (salary.get("minValue") or salary.get("value")):
        lines.append(f"Gaji: {clean(salary.get('minValue') or salary.get('value'))}–{clean(salary.get('maxValue'))} {clean(salary.get('unitText'))}".strip("– "))
    if posting.get("employmentType"):
        lines.append(f"Tipe: {clean(posting['employmentType'])}")
    if posting.get("validThrough"):
        lines.append(f"Batas lamaran: {clean(posting['validThrough'])}")
    description = BeautifulSoup(str(posting.get("description") or ""), "html.parser").get_text("\n")
    description = "\n".join(l.strip() for l in description.splitlines() if l.strip())
    if description:
        lines.append(f"Deskripsi:\n{description}")

    own_host = (urlparse(url).hostname or "").removeprefix("www.")
    contacts: list[str] = []
    for a in soup.find_all("a", href=True):
        if a.find_parent(["footer", "header", "nav", "aside"]):
            continue
        href = a["href"].strip()
        low = href.lower()
        if "wa.me/" in low or "api.whatsapp.com" in low:
            num = re.search(r"(?:wa\.me/|phone=)(\+?\d{9,15})", href)
            if num:
                contacts.append(f"WhatsApp: +{num.group(1).lstrip('+')}")
        elif low.startswith("mailto:"):
            contacts.append(f"Email: {unquote(href[7:].split('?')[0])}")
        elif low.startswith("tel:"):
            contacts.append(f"Telepon: {href[4:]}")
        elif "/cdn-cgi/l/email-protection#" in low:
            email = _decode_cfemail(href.split("#", 1)[1])
            if "@" in email:
                contacts.append(f"Email: {email}")
        elif low.startswith("http"):
            host = (urlparse(href).hostname or "").removeprefix("www.")
            if host and host != own_host and (_APPLY_LINK_HOSTS.search(host) or _APPLY_LINK_TEXT.search(a.get_text(" ", strip=True))):
                contacts.append(f"Tautan lamaran: {href}")
    for el in soup.select("[data-cfemail]"):
        if not el.find_parent(["footer", "header", "nav", "aside"]):
            email = _decode_cfemail(el.get("data-cfemail", ""))
            if "@" in email:
                contacts.append(f"Email: {email}")
    contacts = list(dict.fromkeys(contacts))
    if contacts:
        lines.append("Cara melamar:\n" + "\n".join(contacts))

    og = soup.find("meta", property="og:image")
    return "\n".join(lines), (og.get("content").strip() if og and og.get("content") else None)


def _is_script_or_ad_junk(text: str) -> bool:
    if not text or not text.strip():
        return True
    low = text.lower()
    junk_patterns = (
        "adsbygoogle",
        "function timer",
        "clearinterval",
        "setinterval",
        "window.location",
        "document.getelementbyid",
        "document.queryselector",
        "targetnode",
        "mutationobserver",
        "you are being redirected",
        "intipxads",
        "var count =",
        "var counter =",
        '{"require":',
        "maybedisableanimations",
        "qpltagserverjs",
        "cometssrmergedcontentinjector",
        "window.adsbygoogle",
        "const targetnode",
        "clearinterval( counter )",
    )
    if any(p in low for p in junk_patterns):
        return True
    if re.search(r"function\s+\w+\s*\(|var\s+count\s*=|window\.location\.href\s*=|document\.getElementById\(|MutationObserver\(|\(adsbygoogle\s*=", text, re.I):
        return True
    # Cuplikan berisi selector CSS (mis. ".elementor-26052 .elementor-element > .x"), bukan teks halaman.
    if re.search(r"(?:\.[\w-]+\s*(?:>|,|\s)\s*){4,}|:not\(|var\(--|\{[^}]*:[^}]*;", text):
        return True
    return False


def _clean_text_lines(text: str) -> str:
    if not text:
        return ""
    clean_lines = []
    for line in text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        if _is_script_or_ad_junk(line_str):
            continue
        clean_lines.append(line_str)
    return "\n".join(clean_lines).strip()


def _sync_scrapling_fetch(url: str) -> tuple[str, list[str]]:
    validate_public_http_url(url)

    combined_caption_text = ""
    image_urls = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    if not combined_caption_text:
        ig_match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url, re.I)
        if ig_match:
            shortcode = ig_match.group(1)
            embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
            try:
                res = safe_get(embed_url, headers=headers, timeout=12.0)
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

                    found_scontent = re.findall(r'https://scontent[^"\'\s\\]+', res.text)
                    for s_url in found_scontent:
                        clean = s_url.replace("\\u0026", "&").replace("\\/", "/")
                        image_urls.append(clean)
            except Exception as exc:
                logger.warning("[Instagram Embed] %s", exc)

            if not image_urls:
                try:
                    oembed_url = f"https://www.instagram.com/api/v1/oembed/?url={quote(url, safe='')}"
                    o_res = safe_get(oembed_url, headers=headers, timeout=8.0)
                    if o_res.status_code == 200:
                        data = o_res.json()
                        if data.get("title") and not combined_caption_text:
                            combined_caption_text = data.get("title")
                        if data.get("thumbnail_url"):
                            image_urls.append(data.get("thumbnail_url"))
                except Exception as exc:
                    logger.warning("[Instagram oEmbed] %s", exc)

            if not image_urls:
                for domain in ["vxinstagram.com", "ddinstagram.com"]:
                    try:
                        fix_url = f"https://{domain}/p/{shortcode}/"
                        f_res = safe_get(fix_url, headers={"User-Agent": "facebookexternalhit/1.1"}, timeout=8.0)
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
                    except Exception as exc:
                        logger.warning("[IG Proxy %s] %s", domain, exc)

    if not combined_caption_text:
        try:
            res = safe_get(url, headers=headers, timeout=15.0)
            if res.status_code == 200 and "JobPosting" in res.text:
                posting_text, posting_img = _job_posting_page_text(res.text, url)
                if posting_text:
                    combined_caption_text = posting_text
                    if posting_img:
                        image_urls.append(posting_img)
        except Exception as exc:
            logger.warning("[JobPosting Fetch] %s", exc)

    if not combined_caption_text:
        try:
            from scrapling.fetchers import Fetcher
            page = Fetcher.get(resolve_public_url(url, headers=headers), headers=headers, follow_redirects=False, timeout=15)
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
            res = safe_get(url, headers=headers, timeout=15.0)
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

    seen_urls = set()
    dedup_images = []
    for img_u in image_urls:
        if img_u and img_u not in seen_urls:
            seen_urls.add(img_u)
            dedup_images.append(img_u)

    total_count = len(dedup_images)
    return combined_caption_text, dedup_images[:3], total_count

async def _fetch_url_content_and_image(url: str) -> tuple[str, list[str], dict[str, int]]:
    validate_public_http_url(url)
    loop = asyncio.get_running_loop()
    fetch_res = await loop.run_in_executor(None, _sync_scrapling_fetch, url)
    if len(fetch_res) == 3:
        combined_caption_text, image_urls, total_images = fetch_res
    else:
        combined_caption_text, image_urls = fetch_res
        total_images = len(image_urls)

    tmp_img_paths = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    for img_url in image_urls:
        try:
            img_res = await safe_get_async(img_url, headers=headers, timeout=15.0)
            if img_res.status_code == 200 and len(img_res.content) > 1000:
                ext = ".png" if ".png" in img_url.lower() else ".webp" if ".webp" in img_url.lower() else ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(img_res.content)
                    tmp_img_paths.append(tmp.name)
        except Exception as exc:
            logger.warning("[URL Fetch] gagal unduh gambar %s: %s", img_url, exc)

    carousel_meta = {
        "total_images": total_images,
        "processed_images": len(tmp_img_paths),
    }
    return combined_caption_text, tmp_img_paths, carousel_meta
