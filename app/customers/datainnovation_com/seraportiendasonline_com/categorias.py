# ./run.sh datainnovation_com seraportiendasonline_com categorias

import csv
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "http://www.seraportiendasonline.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}


def _is_real_http_url(href: str) -> bool:
    if not href:
        return False
    href = href.strip().lower()
    if href.startswith("javascript:"):
        return False
    return href.startswith("http://") or href.startswith("https://") or href.startswith("/")


def extract_category_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    container = soup.select_one("div.categorySideHolder")
    cat_blocks = container.select("div.catitemHolder") if container else soup.select("div.catitemHolder")

    for block in cat_blocks:
        a = block.select_one("h2 a[href]")
        if not a:
            continue

        categoria = a.get_text(" ", strip=True)
        href = (a.get("href") or "").strip()
        if not categoria or not _is_real_http_url(href):
            continue

        url = urljoin(base_url, href)
        rows.append({"categoria": categoria, "url": url})

    # dedupe por url (por si acaso)
    seen = set()
    out = []
    for r in rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        out.append(r)

    return out


def run(out_dir: str, **kwargs):
    """
    Compatible con tu runner.
    Opcionales:
      - url: sobreescribir DEFAULT_URL
      - html_file: path a HTML guardado
    """
    url = kwargs.get("url") or DEFAULT_URL
    html_file = kwargs.get("html_file")

    if html_file:
        html = Path(html_file).read_text(encoding="utf-8", errors="ignore")
        base_url = url
    else:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text
        base_url = url

    cats = extract_category_links(html, base_url=base_url)

    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    out_path = out_dir_path / "categorias.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["categoria", "url"])
        w.writeheader()
        w.writerows(cats)

    print(f"✅ Guardadas {len(cats)} categorías en {out_path}")
