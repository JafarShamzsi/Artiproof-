"""
Google Scholar scraper — scrapes profile and publication data.
No official API — uses httpx + BeautifulSoup. CAPTCHA-prone, use as secondary source.
"""

import logging
import re
import asyncio
import random
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from app.services.scrapers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
BASE_URL = "https://scholar.google.com"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class ScraperBlockedError(Exception):
    """Google Scholar blocked us with CAPTCHA or rate limit."""
    pass


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }


def _check_blocked(resp: httpx.Response):
    if resp.status_code == 429 or "CAPTCHA" in resp.text or "/sorry/" in str(resp.url):
        raise ScraperBlockedError("Google Scholar rate limit / CAPTCHA")


def _parse_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


async def search_researcher(name: str, institution: str = None) -> list[dict]:
    """Search Google Scholar for researcher profiles."""
    query = name
    if institution:
        query += f" {institution}"

    await rate_limiter.acquire("google_scholar")

    async with httpx.AsyncClient(headers=_headers(), follow_redirects=True, timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/citations", params={"view_op": "search_authors", "mauthors": query})
        _check_blocked(resp)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for div in soup.select("div.gsc_1usr"):
        name_link = div.select_one("h3.gs_ai_name a")
        if not name_link:
            continue
        href = name_link.get("href", "")
        sid = re.search(r"user=([^&]+)", href)

        aff_el = div.select_one("div.gs_ai_aff")
        cby_el = div.select_one("div.gs_ai_cby")

        results.append({
            "scholar_id": sid.group(1) if sid else None,
            "name": name_link.get_text(strip=True),
            "affiliation": aff_el.get_text(strip=True) if aff_el else None,
            "interests": [a.get_text(strip=True) for a in div.select("a.gs_ai_one_int")],
            "cited_by": _parse_int(cby_el.get_text()) if cby_el else 0,
        })

    return results


async def scrape_profile(scholar_id: str) -> dict:
    """Scrape a researcher's full profile page."""
    await rate_limiter.acquire("google_scholar")

    async with httpx.AsyncClient(headers=_headers(), follow_redirects=True, timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/citations", params={"user": scholar_id, "hl": "en"})
        _check_blocked(resp)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    name_el = soup.select_one("#gsc_prf_in")
    aff_el = soup.select_one(".gsc_prf_il")

    profile = {
        "scholar_id": scholar_id,
        "name": name_el.get_text(strip=True) if name_el else None,
        "affiliation": aff_el.get_text(strip=True) if aff_el else None,
        "interests": [a.get_text(strip=True) for a in soup.select("#gsc_prf_int a")],
        "total_citations": None,
        "h_index": None,
        "i10_index": None,
    }

    stats = soup.select("#gsc_rsb_st tbody tr")
    if len(stats) >= 3:
        tds = [row.select("td") for row in stats]
        if len(tds[0]) > 1:
            profile["total_citations"] = _parse_int(tds[0][1].get_text())
        if len(tds[1]) > 1:
            profile["h_index"] = _parse_int(tds[1][1].get_text())
        if len(tds[2]) > 1:
            profile["i10_index"] = _parse_int(tds[2][1].get_text())

    return profile


async def scrape_publications(scholar_id: str, max_papers: int = 200) -> list[dict]:
    """Scrape all publications from a GS profile, paginated."""
    all_pubs = []
    cstart = 0
    pagesize = 100

    while cstart < max_papers:
        await rate_limiter.acquire("google_scholar")
        await asyncio.sleep(random.uniform(2, 5))  # extra delay to avoid detection

        async with httpx.AsyncClient(headers=_headers(), follow_redirects=True, timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/citations",
                params={"user": scholar_id, "hl": "en", "cstart": cstart, "pagesize": pagesize, "sortby": "pubdate"},
            )
            _check_blocked(resp)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("tr.gsc_a_tr")
        if not rows:
            break

        for row in rows:
            title_el = row.select_one("a.gsc_a_at")
            grays = row.select("div.gs_gray")
            cite_el = row.select_one("a.gsc_a_ac")
            year_el = row.select_one("span.gsc_a_h")

            cluster_id = None
            if cite_el and cite_el.get("href"):
                cid = re.search(r"cites=(\d+)", cite_el.get("href", ""))
                cluster_id = cid.group(1) if cid else None

            all_pubs.append({
                "title": title_el.get_text(strip=True) if title_el else None,
                "authors_string": grays[0].get_text(strip=True) if len(grays) > 0 else None,
                "venue": grays[1].get_text(strip=True) if len(grays) > 1 else None,
                "citation_count": _parse_int(cite_el.get_text()) if cite_el else 0,
                "year": _parse_int(year_el.get_text()) if year_el else None,
                "cluster_id": cluster_id,
            })

        if len(rows) < pagesize:
            break
        cstart += pagesize

    return all_pubs
