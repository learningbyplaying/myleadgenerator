import csv
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://www.comunicare.es/mejores-agencias-publicidad-espana/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}

def extract_cities(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")

    rows = []
    for a in soup.select('a.ez-toc-link[href^="#"]'):
        title = (a.get("title") or a.get_text(" ", strip=True)).strip()

        # solo queremos “Agencias de publicidad en X”
        if not title.lower().startswith("agencias de publicidad en "):
            continue

        anchor = a.get("href", "").lstrip("#").strip()
        ciudad = title.split("Agencias de publicidad en", 1)[-1].strip()

        if not anchor or not ciudad:
            continue

        rows.append({
            "ciudad": ciudad,
            "anchor": anchor,
            "url": f"{base_url}#{anchor}",
        })

    # dedupe por anchor
    seen = set()
    out = []
    for r in rows:
        if r["anchor"] in seen:
            continue
        seen.add(r["anchor"])
        out.append(r)

    return out

def run(out_dir: str, **kwargs):
    """
    Compatible con el runner:
      module.run(out_dir=..., customer=..., base=..., entity=...)
    """

    # Puedes sobreescribir la URL desde CLI/runner si quieres:
    # module.run(..., url="https://.../mejores-agencias-publicidad-espana/")
    url = kwargs.get("url") or URL

    out_path = Path(out_dir) / "ciudades.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) Intento directo con requests
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        raise RuntimeError(
            f"No pude descargar la página (posible 403). "
            f"Prueba a pasar html_file='comunicare.html'. Error: {e}"
        )

    # 2) Parseo y guardo
    cities = extract_cities(html, url)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ciudad", "anchor", "url"])
        w.writeheader()
        w.writerows(cities)

    print(f"✅ Guardado {len(cities)} ciudades en {out_path}")
