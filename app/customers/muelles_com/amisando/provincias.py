import csv
from pathlib import Path
import requests
from bs4 import BeautifulSoup

def run(out_dir: str, **kwargs):
    url = "https://amisando.es/empresas-para-el-control-de-plagas-en-espana-por-provincia/"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    rows = []
    for a in soup.select("article a"):
        nombre = a.get_text(strip=True)
        link = a.get("href")
        if nombre and link:
            rows.append({"provincia": nombre, "url": link})

    out_path = Path(out_dir) / "provincias.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["provincia", "url"])
        w.writeheader()
        w.writerows(rows)

    print(f"✅ Guardado {len(rows)} filas en {out_path}")


import requests
from bs4 import BeautifulSoup

def run_old():

    print("Anti Pigeons")
    exit()
    url = "https://amisando.es/empresas-para-el-control-de-plagas-en-espana-por-provincia/"  # ajusta si es otra

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    provincias = []

    # Selecciona todos los enlaces dentro del artículo
    for a in soup.select("article a"):
        nombre = a.get_text(strip=True)
        link = a.get("href")

        if link and nombre:
            provincias.append({
                "provincia": nombre,
                "url": link
            })

