"""
Web scraper — extracts article text, title, author, and citations from URLs.
"""

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.utils.public_http import UnsafeURL, fetch_public


async def scrape_url(url: str) -> dict:
    """
    Fetch a URL and extract article content.

    Returns dict with keys: title, body, author, date, citations, error
    """
    try:
        resp = await fetch_public(url)
        url = str(resp.url)  # Resolve references against the final redirect URL.
    except UnsafeURL as exc:
        return {"error": str(exc), "body": "", "title": None}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "body": "", "title": None}
    except httpx.RequestError as e:
        return {"error": str(e), "body": "", "title": None}

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    # Extract title
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # Extract author
    author = None
    for meta_name in ["author", "article:author"]:
        meta = soup.find("meta", attrs={"name": meta_name}) or soup.find("meta", property=meta_name)
        if meta and meta.get("content"):
            author = meta["content"].strip()
            break

    # Extract date
    date = None
    for prop in ["article:published_time", "datePublished", "date"]:
        meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if meta and meta.get("content"):
            date = meta["content"].strip()
            break

    # Extract body text — prefer <article>, fall back to <main>, then <body>
    article = soup.find("article") or soup.find("main") or soup.find("body")
    body = ""
    if article:
        paragraphs = article.find_all("p")
        body = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)

    if not body:
        body = soup.get_text(separator="\n", strip=True)
        # Collapse excessive whitespace
        body = re.sub(r"\n{3,}", "\n\n", body)

    # Extract citations / links
    citations = []
    if article:
        for a_tag in article.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            # Resolve relative URLs
            full_url = urljoin(url, href)
            parsed = urlparse(full_url)
            # Skip same-domain navigation links, anchors, mailto, javascript
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc == urlparse(url).netloc and not parsed.path.strip("/"):
                continue
            citations.append({"text": text[:200], "url": full_url})

    # Deduplicate by URL
    seen = set()
    unique_citations = []
    for c in citations:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique_citations.append(c)

    return {
        "title": title,
        "body": body[:50000],  # Cap at ~50K chars
        "author": author,
        "date": date,
        "citations": unique_citations[:50],  # Cap at 50 citations
        "error": None,
    }
