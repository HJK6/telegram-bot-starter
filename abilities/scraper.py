"""
Web Scraper ability — fetch a URL and extract readable text.

Uses requests + BeautifulSoup. For JS-heavy pages you'd swap in
Playwright or Selenium (see README for notes).
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15


def scrape_url(url: str, max_chars: int = 8000) -> str:
    """Fetch a URL and return cleaned text content."""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse blank lines
    lines = [line for line in text.splitlines() if line.strip()]
    result = "\n".join(lines)

    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n... (truncated)"
    return result


def summarize_page(url: str) -> dict:
    """Fetch a URL and return structured metadata + text preview."""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.title.string.strip() if soup.title else "(no title)"
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    # Grab first few paragraphs
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")[:5]]
    preview = "\n".join(paragraphs)[:2000]

    # Collect links
    links = []
    for a in soup.find_all("a", href=True)[:20]:
        href = a["href"]
        label = a.get_text(strip=True)[:80]
        if href.startswith("http"):
            links.append({"text": label, "url": href})

    return {
        "title": title,
        "description": meta_desc,
        "preview": preview,
        "links": links,
    }
