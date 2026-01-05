import csv
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def _extract_empresa_urls(soup: BeautifulSoup) -> list[str]:
    urls = []
    for art in soup.select("section.content-area article.article-loop"):
        a = art.select_one("a[href]")
        if a and a.get("href"):
            urls.append(a["href"])
    return urls


def _find_next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    """
    Paginación detectada:
    <nav class="pagination">
      ...
      <a class="next page-numbers" href=".../page/2/">»</a>
    </nav>
    """
    a = soup.select_one("nav.pagination a.next.page-numbers[href]")
    if a:
        return urljoin(current_url, a["href"])

    # Fallbacks comunes
    a = soup.select_one('a[rel="next"][href]')
    if a:
        return urljoin(current_url, a["href"])

    a = soup.select_one("a.page-numbers.next[href]")
    if a:
        return urljoin(current_url, a["href"])

    a = soup.select_one("a.next[href]")
    if a:
        return urljoin(current_url, a["href"])

    return None


def run(out_dir: str, **kwargs):
    """
    kwargs requeridos:
      - customer (ej: muelles_com)
      - base     (ej: amisando)

    Input:
      /data/<customer>/<base>/provincias.csv   (columnas: provincia,url)

    Output:
      <out_dir>/empresas.csv  (columnas: provincia_url,empresa_url)
    """

    customer = kwargs.get("customer")
    base = kwargs.get("base")

    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    provincias_csv = Path("/data") / customer / base / "provincias.csv"
    if not provincias_csv.exists():
        raise FileNotFoundError(f"No existe el input: {provincias_csv}")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    seen = set()
    rows = []

    with provincias_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for prov in reader:
            provincia_url = (prov.get("url") or "").strip()
            if not provincia_url:
                continue

            print(f"\n▶ Provincia: {provincia_url}")

            page_url = provincia_url
            page_num = 1
            max_pages = 200  # seguridad anti-loops

            while page_url and page_num <= max_pages:
                print(f"  - Página {page_num}: {page_url}")

                r = session.get(page_url, timeout=30)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")

                empresa_urls = _extract_empresa_urls(soup)

                # Si no hay resultados, cortamos
                if not empresa_urls:
                    print("    (sin resultados, fin)")
                    break

                added = 0
                for u in empresa_urls:
                    if u not in seen:
                        seen.add(u)
                        rows.append({"provincia_url": provincia_url, "empresa_url": u})
                        added += 1

                print(f"    +{added} nuevas (total: {len(rows)})")

                next_page = _find_next_page(soup, page_url)

                # Caso sin paginación o fin de paginación
                if not next_page:
                    print("    (no hay más páginas)")
                    break

                # Anti-loop
                if next_page == page_url:
                    print("    (next == current, cortando)")
                    break

                page_url = next_page
                page_num += 1

                # Pequeño delay
                time.sleep(0.6)

            if page_num > max_pages:
                print(f"    (alcanzado max_pages={max_pages}, cortando por seguridad)")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "empresas.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["provincia_url", "empresa_url"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n✅ Guardadas {len(rows)} empresas en {out_path}")
