import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def run(out_dir: str, **kwargs):
    """
    kwargs esperados (opcionales):
      - provincia_url (str)
      - customer
      - base
    """

    # 🔹 De momento fija, luego la puedes pasar por kwargs
    provincia_url = kwargs.get(
        "provincia_url",
        "https://amisando.es/servicios/a-coruna/",
    )

    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(provincia_url, headers=headers, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    rows = []
    seen = set()

    for art in soup.select("section.content-area article.article-loop"):
        a = art.select_one("a[href]")
        if not a:
            continue

        link = a.get("href")
        if link and link not in seen:
            seen.add(link)
            rows.append({"empresa_url": link})

    out_path = Path(out_dir) / "empresas.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["empresa_url"])
        w.writeheader()
        w.writerows(rows)

    print(f"✅ Guardado {len(rows)} filas en {out_path}")
