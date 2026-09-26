"""
Lightpanda Browser Client — headless browser dengan JavaScript rendering penuh.

Menggantikan SearXNG + Scrapling untuk:
1. Fetch & render halaman web (SPA, Ajax, infinite scroll)
2. Search via Google/DuckDuckGo HTML page (di-render oleh Lightpanda)
3. Extract konten Instagram, Facebook, Threads (heavy JS)

Komunikasi via Docker exec ke container Lightpanda CDP server.
"""
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

# Container name untuk Lightpanda (dari config / env)
_LIGHTPANDA_CONTAINER = LIGHTPANDA_CONTAINER
_LIGHTPANDA_CDP_URL = LIGHTPANDA_CDP_URL
_LIGHTPANDA_TIMEOUT = 30  # detik

# Search engine HTML endpoints (di-render oleh Lightpanda)
_DDG_HTML_URL = "https://html.duckduckgo.com/html/?q={query}"
_GOOGLE_HTML_URL = "https://www.google.com/search?q={query}&hl=id"
_BING_HTML_URL = "https://www.bing.com/search?q={query}&setlang=id"


def _lightpanda_fetch_via_docker(url: str, *, dump: str = "markdown", wait_ms: int = 3000) -> str:
    """
    Jalankan `lightpanda fetch` di dalam Docker container.
    Mengembalikan output (markdown/html) sebagai string.
    """
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


def _lightpanda_fetch_via_http(url: str, *, wait_ms: int = 3000) -> str:
    """
    Fallback: fetch via CDP (Chrome DevTools Protocol) WebSocket endpoint.
    Lightpanda CDP server berjalan di port 9222.

    Alur CDP:
    1. GET /json — ambil list target browser
    2. Connect ke webSocketDebuggerUrl via WebSocket
    3. Target.createTarget(url) — buka halaman baru
    4. Target.attachToTarget — attach ke target
    5. Runtime.evaluate — ambil document.documentElement.outerHTML
    """
    import asyncio

    cdp_host = _LIGHTPANDA_CDP_URL.split(":")[1].strip("/")
    cdp_port = _LIGHTPANDA_CDP_URL.rsplit(":", 1)[-1]

    try:
        with httpx.Client(timeout=_LIGHTPANDA_TIMEOUT) as client:
            # 1. Ambil list target browser yang aktif
            resp = client.get(f"http://{cdp_host}:{cdp_port}/json")
            if resp.status_code != 200:
                return ""
            targets = resp.json()
            # Cari target browser (bukan page)
            browser_ws_url = None
            for t in targets:
                if t.get("type") == "browser":
                    browser_ws_url = t.get("webSocketDebuggerUrl")
                    break
            if not browser_ws_url and targets:
                browser_ws_url = targets[0].get("webSocketDebuggerUrl")
            if not browser_ws_url:
                return ""

        # 2. Connect ke WebSocket dan jalankan CDP commands
        return _cdp_fetch_via_websocket(browser_ws_url, url, wait_ms)
    except Exception as exc:
        logger.warning("[Lightpanda HTTP] gagal: %s", exc)
        return ""


def _cdp_fetch_via_websocket(ws_url: str, target_url: str, wait_ms: int) -> str:
    """Fetch URL via CDP WebSocket — buka tab, tunggu render, ambil HTML."""
    import asyncio
    import json as _json

    try:
        import websockets
    except ImportError:
        logger.warning("[Lightpanda CDP] websockets tidak terinstall, skip CDP fetch")
        return ""

    async def _fetch():
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            msg_id = 1

            async def send_cmd(method: str, params: dict | None = None) -> dict:
                nonlocal msg_id
                cmd = {"id": msg_id, "method": method}
                if params:
                    cmd["params"] = params
                await ws.send(_json.dumps(cmd))
                # Tunggu response dengan matching id
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=_LIGHTPANDA_TIMEOUT)
                    data = _json.loads(raw)
                    if data.get("id") == msg_id:
                        msg_id += 1
                        return data
                    # Event tanpa id — skip (tapi bisa berguna untuk debugging)

            # Buat target baru
            result = await send_cmd("Target.createTarget", {"url": target_url})
            target_id = result.get("result", {}).get("targetId", "")
            if not target_id:
                return ""

            # Attach ke target
            result = await send_cmd("Target.attachToTarget", {
                "targetId": target_id, "flatten": True,
            })
            session_id = result.get("result", {}).get("sessionId", "")
            if not session_id:
                return ""

            # Tunggu render
            await asyncio.sleep(wait_ms / 1000)

            # Ambil HTML via Runtime.evaluate
            cmd = {
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.documentElement.outerHTML",
                    "returnByValue": True,
                },
                "sessionId": session_id,
            }
            msg_id += 1
            await ws.send(_json.dumps(cmd))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=_LIGHTPANDA_TIMEOUT)
                data = _json.loads(raw)
                if data.get("id") == msg_id - 1:
                    value = data.get("result", {}).get("result", {}).get("value", "")
                    return value

    return asyncio.run(_fetch())


def lightpanda_fetch(
    url: str,
    *,
    output: str = "markdown",
    wait_ms: int = 3000,
) -> dict[str, Any]:
    """
    Fetch URL dengan Lightpanda — render JavaScript penuh.

    Returns:
        {
            "ok": bool,
            "url": str,
            "content": str,  # markdown atau html
            "title": str,
            "error": str | None,
        }
    """
    try:
        url = validate_public_http_url(url)
    except ValueError as exc:
        return {"ok": False, "url": url, "content": "", "title": "", "error": str(exc)}

    content = _lightpanda_fetch_via_docker(url, dump=output, wait_ms=wait_ms)

    if not content:
        # Fallback ke httpx biasa (tanpa JS render)
        try:
            with httpx.Client(timeout=15, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }) as client:
                resp = client.get(url)
                content = resp.text if output == "html" else _html_to_markdown(resp.text)
        except Exception as exc:
            return {"ok": False, "url": url, "content": "", "title": "", "error": str(exc)}

    # Extract title dari content
    title = ""
    if output == "html":
        soup = BeautifulSoup(content, "html.parser")
        if soup.title:
            title = soup.title.get_text(strip=True)
    else:
        # Markdown: title biasanya di baris pertama dengan #
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
    """
    Search via Lightpanda — render halaman HTML search engine, parse hasilnya.

    Engine: "duckduckgo" (default) atau "google".

    Returns:
        {
            "ok": bool,
            "query": str,
            "engine": str,
            "results": [{"title", "url", "snippet"}],
            "raw_result_count": int,
            "error": str | None,
        }
    """
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

    # Fetch search page via Lightpanda (render JS)
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
    """Parse hasil pencarian dari HTML DuckDuckGo atau Google."""
    results: list[dict[str, str]] = []
    soup = BeautifulSoup(html, "html.parser")

    if engine == "google":
        # Google: div.g > div > a, h3 untuk title
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
        # Bing: li.b_algo > h2 > a, p untuk snippet, cite untuk URL asli
        for li in soup.select("li.b_algo"):
            link = li.select_one("h2 a")
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)
            # Snippet dari p.b_lineclamp2 atau div.b_caption
            snippet_el = li.select_one("p.b_lineclamp2, p.b_lineclamp1, div.b_caption > p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            # URL asli dari <cite> — Bing bold match keywords dengan <strong>
            cite = li.select_one("cite")
            if cite:
                cite_text = cite.get_text(strip=True)
                # Bing menampilkan breadcrumb dengan separator "›" (mis.
                # "instagram.com › thebikershop.id"). Konversi ke path URL valid.
                cite_text = re.sub(r"\s*[›»]\s*", "/", cite_text)
                cite_text = re.sub(r"\s+", "", cite_text)
                # Bersihkan prefix seperti "https://" yang terpisah
                if not cite_text.startswith("http"):
                    cite_text = "https://" + cite_text
                href = cite_text
            if href and href.startswith("http") and "bing.com/ck/a" not in href:
                results.append({"title": title, "url": href, "snippet": snippet})
            elif href and "bing.com/ck/a" in href:
                # Fallback: decode base64 URL dari parameter u=
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
        # DuckDuckGo HTML: div.result > a.result__a, snippet di a.result__snippet
        for res in soup.select("div.result, div.web-result, div.results_links"):
            link = res.select_one("a.result__a, a.result-link")
            if not link:
                continue
            href = link.get("href", "")
            # DDG wrap URL di /l/?uddg=
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

    # Fallback: parse semua anchor dengan href http
    if not results:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "duckduckgo.com" not in href and "google.com" not in href:
                title = a.get_text(strip=True)
                if title and len(title) > 5:
                    results.append({"title": title, "url": href, "snippet": ""})

    return results


def _html_to_markdown(html: str) -> str:
    """Konversi HTML ke markdown sederhana."""
    soup = BeautifulSoup(html, "html.parser")
    # Hapus script, style
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


def lightpanda_fetch_instagram(url: str) -> dict[str, Any]:
    """
    Fetch profil/post Instagram via Lightpanda.
    Instagram heavy JS — butuh render penuh.

    Returns:
        {
            "ok": bool,
            "url": str,
            "username": str,
            "content": str,
            "title": str,
            "error": str | None,
        }
    """
    # Pastikan URL valid
    try:
        url = validate_public_http_url(url)
    except ValueError as exc:
        return {"ok": False, "url": url, "username": "", "content": "", "title": "", "error": str(exc)}

    # Extract username dari URL
    username = ""
    parsed = urlparse(url)
    if "instagram.com" in parsed.netloc:
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts and parts[0] not in ("p", "reel", "reels", "stories", "explore", "accounts"):
            username = parts[0]

    # Fetch dengan wait lebih lama untuk Instagram
    result = lightpanda_fetch(url, output="html", wait_ms=5000)
    if not result["ok"]:
        return {**result, "username": username}

    content = result["content"]
    soup = BeautifulSoup(content, "html.parser")

    # Extract bio/name dari meta tags
    title = ""
    desc = ""
    for meta in soup.find_all("meta"):
        prop = meta.get("property", meta.get("name", ""))
        if prop == "og:title":
            title = meta.get("content", "")
        elif prop == "og:description":
            desc = meta.get("content", "")

    if title:
        result["title"] = title

    # Gabungkan teks visible
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    body_text = soup.get_text(separator=" ", strip=True)
    # Bersihkan noise IG
    body_text = re.sub(r"\s+", " ", body_text).strip()

    result["content"] = f"{title}\n\n{desc}\n\n{body_text}".strip()
    result["username"] = username

    return result


def lightpanda_fetch_facebook(url: str) -> dict[str, Any]:
    """Fetch profil/halaman Facebook via Lightpanda."""
    try:
        url = validate_public_http_url(url)
    except ValueError as exc:
        return {"ok": False, "url": url, "content": "", "title": "", "error": str(exc)}

    result = lightpanda_fetch(url, output="html", wait_ms=5000)
    if not result["ok"]:
        return result

    soup = BeautifulSoup(result["content"], "html.parser")
    for meta in soup.find_all("meta"):
        prop = meta.get("property", meta.get("name", ""))
        if prop == "og:title":
            result["title"] = meta.get("content", "")
        elif prop == "og:description":
            result["content"] = meta.get("content", "")

    if not result["content"]:
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        result["content"] = soup.get_text(separator=" ", strip=True)[:2000]

    return result


def is_lightpanda_available() -> bool:
    """Cek apakah container Lightpanda running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={_LIGHTPANDA_CONTAINER}", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5,
        )
        return _LIGHTPANDA_CONTAINER in result.stdout.strip()
    except Exception:
        return False
