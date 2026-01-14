import csv
from pathlib import Path
import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://www.comunicare.es/mejores-agencias-publicidad-espana/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}

PREFIX = "Agencias de publicidad en "

def extract_city_links_from_content(html: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    # Buscamos h3 de Gutenberg (wp-block-heading) que contengan un <a>
    for h3 in soup.select("h3.wp-block-heading"):
        a = h3.find("a", href=True)
        if not a:
            continue

        text = a.get_text(" ", strip=True)
        if not text.startswith(PREFIX):
            continue

        ciudad = text[len(PREFIX):].strip()
        url = a["href"].strip()

        if ciudad and url:
            rows.append({
                "ciudad": ciudad,
                "url": url,
            })

    # dedupe por url
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
    Compatible con tu runner:
      module.run(out_dir=..., customer=..., base=..., entity=..., ...)
    Opcionales:
      - url: sobreescribir DEFAULT_URL
      - html_file: path a HTML guardado (si hay 403)
    """
    url = kwargs.get("url") or DEFAULT_URL
    html_file = kwargs.get("html_file")

    if html_file:
        html = Path(html_file).read_text(encoding="utf-8", errors="ignore")
    else:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text

    cities = extract_city_links_from_content(html)

    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    out_path = out_dir_path / "ciudades.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ciudad", "url"])
        w.writeheader()
        w.writerows(cities)

    print(f"✅ Guardado {len(cities)} ciudades en {out_path}")
