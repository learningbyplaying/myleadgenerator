import csv
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}

# Títulos que NO son empresas (secciones del artículo)
SKIP_PREFIXES = (
    "Agencia publicidad",
    "Agencias de publicidad",
    "Contactar",
    "Ventajas",
    "Aumenta",
    "Agencias marketing",
    "Marketing digital",
    "Redes sociales",
)

def _is_probably_company_heading(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # descarta secciones
    for p in SKIP_PREFIXES:
        if t.startswith(p):
            return False
    return True

def _extract_companies_from_city(html: str, city_url: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for h3 in soup.select("h3.wp-block-heading"):
        span = h3.select_one("span.ez-toc-section[id]")
        a = h3.select_one("a[href]")
        if not span or not a:
            continue

        empresa = a.get_text(" ", strip=True)
        if not _is_probably_company_heading(empresa):
            continue

        href = a.get("href", "").strip()
        if not href:
            continue

        web = urljoin(city_url, href)

        # Filtra enlaces internos de comunicare (secciones o posts del propio site)
        # Queremos la web real de la empresa (normalmente dominio externo)
        if "comunicare.es" in urlparse(web).netloc:
            continue

        rows.append({
            "empresa": empresa,
            "anchor": span.get("id", "").strip(),
            "web": web,
        })

    # dedupe por web
    seen = set()
    out = []
    for r in rows:
        key = r["web"]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    return out

def run(out_dir: str, **kwargs):
    """
    Input:
      /data/<customer>/<base>/ciudades.csv  (ciudad,url)

    Output:
      <out_dir>/empresas.csv (ciudad,ciudad_url,empresa,anchor,web)

    kwargs requeridos:
      - customer
      - base
    """
    customer = kwargs.get("customer")
    base = kwargs.get("base")
    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    ciudades_csv = Path("/data") / customer / base / "ciudades.csv"
    if not ciudades_csv.exists():
        raise FileNotFoundError(f"No existe el input: {ciudades_csv}")

    session = requests.Session()
    session.headers.update(HEADERS)

    rows = []
    seen_global = set()

    with ciudades_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ciudad = (row.get("ciudad") or "").strip()
            ciudad_url = (row.get("url") or "").strip()
            if not ciudad or not ciudad_url:
                continue

            print(f"\n▶ {ciudad}: {ciudad_url}")

            r = session.get(ciudad_url, timeout=30)
            r.raise_for_status()

            companies = _extract_companies_from_city(r.text, ciudad_url)
            print(f"  - encontradas {len(companies)} empresas")

            added = 0
            for c in companies:
                key = (ciudad, c["web"])
                if key in seen_global:
                    continue
                seen_global.add(key)

                rows.append({
                    "ciudad": ciudad,
                    "ciudad_url": ciudad_url,
                    "empresa": c["empresa"],
                    "anchor": c["anchor"],
                    "web": c["web"],
                })
                added += 1

            print(f"  +{added} nuevas (total: {len(rows)})")
            time.sleep(0.6)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "empresas.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ciudad", "ciudad_url", "empresa", "anchor", "web"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n✅ Guardadas {len(rows)} empresas en {out_path}")
