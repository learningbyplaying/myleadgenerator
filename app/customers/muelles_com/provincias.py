import requests
from bs4 import BeautifulSoup

def run():

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

    # Mostrar resultados
    for p in provincias:
        print(p["provincia"], "->", p["url"])