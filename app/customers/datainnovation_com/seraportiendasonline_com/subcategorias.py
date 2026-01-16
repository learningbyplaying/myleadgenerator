# ./run.sh datainnovation_com seraportiendasonline_es subcategorias
import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}

COUNT_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<count>\d+)\)\s*$")


def _parse_name_and_count(text: str) -> tuple[str, int]:
    """
    Devuelve:
      - nombre limpio de la subcategoría
      - número de empresas listadas en ella
    """
    t = (text or "").strip()
    if not t:
        return ("", 0)

    m = COUNT_RE.match(t)
    if not m:
        return (t, 0)

    return (
        m.group("name").strip(),
        int(m.group("count")),
    )


def _extract_subcategories(html: str, category_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for block in soup.select("div.catitemHolder2"):
        for span in block.select('span[id^="subcat"]'):
            subcat_id = (span.get("id") or "").strip()

            a = span.select_one("a[href]")
            if not a:
                continue

            raw_text = a.get_text(" ", strip=True)
            subcategoria, empresas_count = _parse_name_and_count(raw_text)

            href = (a.get("href") or "").strip()
            if not href or not subcategoria:
                continue

            subcat_url = urljoin(category_url, href)

            rows.append({
                "subcat_id": subcat_id,
                "subcategoria": subcategoria,
                "subcategoria_url": subcat_url,
                "empresas_count": empresas_count,
            })

    # dedupe por url
    seen = set()
    out = []
    for r in rows:
        key = r["subcategoria_url"]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    return out


def run(out_dir: str, **kwargs):
    """
    Input:
      /data/<customer>/<base>/categorias.csv  (categoria,url)

    Output:
      <out_dir>/subcategorias.csv
        (categoria,categoria_url,subcategoria,subcategoria_url,empresas_count,subcat_id)
    """
    customer = kwargs.get("customer")
    base = kwargs.get("base")
    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    categorias_csv = Path("/data") / customer / base / "categorias.csv"
    if not categorias_csv.exists():
        raise FileNotFoundError(f"No existe el input: {categorias_csv}")

    session = requests.Session()
    session.headers.update(HEADERS)

    rows = []
    seen_global = set()

    with categorias_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            categoria = (row.get("categoria") or "").strip()
            categoria_url = (row.get("url") or "").strip()
            if not categoria or not categoria_url:
                continue

            print(f"\n▶ {categoria}: {categoria_url}")

            r = session.get(categoria_url, timeout=30)
            r.raise_for_status()

            subs = _extract_subcategories(r.text, categoria_url)
            print(f"  - encontradas {len(subs)} subcategorías")

            added = 0
            for s in subs:
                key = (categoria_url, s["subcategoria_url"])
                if key in seen_global:
                    continue
                seen_global.add(key)

                rows.append({
                    "categoria": categoria,
                    "categoria_url": categoria_url,
                    "subcategoria": s["subcategoria"],
                    "subcategoria_url": s["subcategoria_url"],
                    "empresas_count": s["empresas_count"],
                    "subcat_id": s["subcat_id"],
                })
                added += 1

            print(f"  +{added} nuevas (total: {len(rows)})")
            time.sleep(0.6)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "subcategorias.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "categoria",
                "categoria_url",
                "subcategoria",
                "subcategoria_url",
                "empresas_count",
                "subcat_id",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"\n✅ Guardadas {len(rows)} subcategorías en {out_path}")
