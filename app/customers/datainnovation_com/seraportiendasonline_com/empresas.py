# ./run.sh datainnovation_com seraportiendasonline_es empresas

import csv
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}

SLEEP = 0.6


def _load_processed_pages(output_csv: Path) -> set[tuple[str, int]]:
    """
    Breakpoint por (subcategoria_url, page)
    """
    done = set()
    if not output_csv.exists():
        return done

    with output_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                done.add((r["subcategoria_url"], int(r["page"])))
            except Exception:
                continue
    return done


def _get_page_number(url: str, default: int = 1) -> int:
    """
    Extrae np= de la URL. Si no existe, página 1.
    """
    try:
        q = parse_qs(urlparse(url).query)
        return int(q.get("np", [default])[0])
    except Exception:
        return default


def _extract_items(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for block in soup.select("div.productListItem"):
        a = block.select_one("h3 a[href]")
        img = block.select_one("div.productListItemImage img[src]")

        if not a:
            continue

        items.append({
            "empresa": a.get_text(" ", strip=True),
            "ficha_url": a["href"].strip(),
            "imagen": urljoin(base_url, img["src"]) if img else "",
        })

    return items


def _find_next_page(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        if a.get_text(strip=True).lower() == "siguiente":
            return urljoin(base_url, a["href"].strip())
    return ""


def run(out_dir: str, **kwargs):
    customer = kwargs.get("customer")
    base = kwargs.get("base")
    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    subcats_csv = Path("/data") / customer / base / "subcategorias.csv"
    if not subcats_csv.exists():
        raise FileNotFoundError(subcats_csv)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "empresas.csv"

    processed_pages = _load_processed_pages(out_path)
    if processed_pages:
        print(f"↩️ Reanudando: {len(processed_pages)} páginas ya procesadas")

    session = requests.Session()
    session.headers.update(HEADERS)

    write_header = not out_path.exists() or out_path.stat().st_size == 0
    f_out = out_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        f_out,
        fieldnames=[
            "categoria",
            "subcategoria",
            "subcategoria_url",
            "page",
            "empresa",
            "imagen",
            "ficha_url",
        ],
    )
    if write_header:
        writer.writeheader()

    try:
        with subcats_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                categoria = (row.get("categoria") or "").strip()
                subcategoria = (row.get("subcategoria") or "").strip()
                subcat_url = (row.get("subcategoria_url") or "").strip()
                if not subcat_url:
                    continue

                print(f"\n▶ Subcategoría: {categoria} / {subcategoria}")

                next_url = subcat_url

                while next_url:
                    page = _get_page_number(next_url, default=1)

                    if (subcat_url, page) in processed_pages:
                        print(f"  ⏭️ página {page} ya procesada")
                        next_url = _find_next_page(
                            session.get(next_url).text, subcat_url
                        )
                        continue

                    print(f"  📄 página {page}")

                    r = session.get(next_url, timeout=30)
                    r.raise_for_status()

                    items = _extract_items(r.text, subcat_url)

                    for it in items:
                        writer.writerow({
                            "categoria": categoria,
                            "subcategoria": subcategoria,
                            "subcategoria_url": subcat_url,
                            "page": page,
                            "empresa": it["empresa"],
                            "imagen": it["imagen"],
                            "ficha_url": it["ficha_url"],
                        })

                    f_out.flush()
                    processed_pages.add((subcat_url, page))

                    next_url = _find_next_page(r.text, subcat_url)
                    time.sleep(SLEEP)

    finally:
        f_out.close()

    print(f"\n✅ Scraping de empresas finalizado: {out_path}")
