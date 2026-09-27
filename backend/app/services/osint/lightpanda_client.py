from __future__ import annotations

import logging
import re
import subprocess
import json
import time
from typing import Any
from urllib.parse import quote_plus, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.services.url_guard import validate_public_http_url
from app.config import LIGHTPANDA_CONTAINER, LIGHTPANDA_CDP_URL

logger = logging.getLogger(__name__)

_LIGHTPANDA_CONTAINER = LIGHTPANDA_CONTAINER
_LIGHTPANDA_CDP_URL = LIGHTPANDA_CDP_URL
_LIGHTPANDA_TIMEOUT = 30  # detik

_DDG_HTML_URL = "https://html.duckduckgo.com/html/?q={query}"
_GOOGLE_HTML_URL = "https://www.google.com/search?q={query}&hl=id"
_BING_HTML_URL = "https://www.bing.com/search?q={query}&setlang=id"


def _lightpanda_fetch_via_docker(url: str, *, dump: str = "markdown", wait_ms: int = 3000) -> str:
    cmd = [
        "docker", "exec", _LIGHTPANDA_CONTAINER,
        "lightpanda", "fetch",
        "--dump", dump,
        "--wait-ms", str(wait_ms),
        "--log-level", "error",
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_LIGHTPANDA_TIMEOUT,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:300]
            logger.warning("[Lightpanda] fetch gagal untuk %s: %s", url, stderr)
            return ""
        return result.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        logger.warning("[Lightpanda] timeout untuk %s", url)
        return ""
    except Exception as exc:
        logger.warning("[Lightpanda] error untuk %s: %s", url, exc)
        return ""


def lightpanda_fetch(
    url: str,
    *,
    output: str = "markdown",
    wait_ms: int = 3000,
) -> dict[str, Any]:
    try:
        url = validate_public_http_url(url)
    except ValueError as exc:
        return {"ok": False, "url": url, "content": "", "title": "", "error": str(exc)}

    content = _lightpanda_fetch_via_docker(url, dump=output, wait_ms=wait_ms)

    if not content:
        try:
            with httpx.Client(timeout=15, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }) as client:
                resp = client.get(url)
                content = resp.text if output == "html" else _html_to_markdown(resp.text)
        except Exception as exc:
            return {"ok": False, "url": url, "content": "", "title": "", "error": str(exc)}

    title = ""
    if output == "html":
        soup = BeautifulSoup(content, "html.parser")
        if soup.title:
            title = soup.title.get_text(strip=True)
    else:
        for line in content.split("\n")[:5]:
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break

    return {
        "ok": bool(content),
        "url": url,
        "content": content,
        "title": title,
        "error": None if content else "Empty response",
    }


def lightpanda_search(
    query: str,
    *,
    max_results: int = 8,
    engine: str = "duckduckgo",
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "ok": False, "query": q, "engine": engine, "results": [],
            "raw_result_count": 0, "error": "Query kosong.",
        }

    if engine == "google":
        search_url = _GOOGLE_HTML_URL.format(query=quote_plus(q))
    elif engine == "bing":
        search_url = _BING_HTML_URL.format(query=quote_plus(q))
    else:
        search_url = _DDG_HTML_URL.format(query=quote_plus(q))

    fetch_result = lightpanda_fetch(search_url, output="html", wait_ms=2000)
    if not fetch_result["ok"]:
        return {
            "ok": False, "query": q, "engine": engine, "results": [],
            "raw_result_count": 0, "error": fetch_result.get("error", "Fetch gagal"),
        }

    html = fetch_result["content"]
    results = _parse_search_results(html, engine=engine)

    return {
        "ok": bool(results),
        "query": q,
        "engine": f"lightpanda-{engine}",
        "results": results[:max_results],
        "raw_result_count": len(results),
        "error": None if results else "Tidak ada hasil parse.",
    }


def _parse_search_results(html: str, *, engine: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    soup = BeautifulSoup(html, "html.parser")

    if engine == "google":
        for div in soup.select("div.g, div.tF2Cxc"):
            link = div.select_one("a[href]")
            title_el = div.select_one("h3")
            if link and title_el:
                href = link.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[-1].split("&")[0]
                elif href.startswith("/"):
                    continue
                if not href.startswith("http"):
                    continue
                title = title_el.get_text(strip=True)
                snippet_el = div.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe, div.IsZ7c")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                results.append({"title": title, "url": href, "snippet": snippet})
    elif engine == "bing":
        for li in soup.select("li.b_algo"):
            link = li.select_one("h2 a")
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)
            snippet_el = li.select_one("p.b_lineclamp2, p.b_lineclamp1, div.b_caption > p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            cite = li.select_one("cite")
            if cite:
                cite_text = cite.get_text(strip=True)
                cite_text = re.sub(r"\s*[›»]\s*", "/", cite_text)
                cite_text = re.sub(r"\s+", "", cite_text)
                if not cite_text.startswith("http"):
                    cite_text = "https://" + cite_text
                href = cite_text
            if href and href.startswith("http") and "bing.com/ck/a" not in href:
                results.append({"title": title, "url": href, "snippet": snippet})
            elif href and "bing.com/ck/a" in href:
                import base64 as b64
                from urllib.parse import urlsplit, parse_qs
                qs = parse_qs(urlsplit(href).query)
                u_param = qs.get("u", [""])[0]
                if u_param.startswith("a1"):
                    try:
                        decoded = b64.urlsafe_b64decode(u_param[2:] + "==").decode("utf-8", errors="ignore")
                        if decoded.startswith("http"):
                            results.append({"title": title, "url": decoded, "snippet": snippet})
                    except Exception:
                        pass
    else:
        for res in soup.select("div.result, div.web-result, div.results_links"):
            link = res.select_one("a.result__a, a.result-link")
            if not link:
                continue
            href = link.get("href", "")
            if "uddg=" in href:
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(href).query)
                href = qs.get("uddg", [href])[0]
            if not href.startswith("http"):
                continue
            title = link.get_text(strip=True)
            snippet_el = res.select_one("a.result__snippet, div.result__snippet, td.result__snippet")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            results.append({"title": title, "url": href, "snippet": snippet})

    if not results:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "duckduckgo.com" not in href and "google.com" not in href:
                title = a.get_text(strip=True)
                if title and len(title) > 5:
                    results.append({"title": title, "url": href, "snippet": ""})

    return results


def _html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    lines: list[str] = []
    for el in soup.find_all(["h1", "h2", "h3", "p", "li", "div"]):
        text = el.get_text(strip=True)
        if text:
            if el.name in ("h1", "h2", "h3"):
                level = int(el.name[1])
                lines.append(f"{'#' * level} {text}")
            else:
                lines.append(text)
    return "\n\n".join(lines)


def is_lightpanda_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={_LIGHTPANDA_CONTAINER}", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5,
        )
        return _LIGHTPANDA_CONTAINER in result.stdout.strip()
    except Exception:
        return False
