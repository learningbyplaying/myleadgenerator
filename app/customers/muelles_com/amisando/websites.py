import csv
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


MAX_ITEMS = 10

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)


def _ensure_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return "https://" + raw


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    p = urlparse(_ensure_url(url))
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _extract_fields_from_ficha(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    ficha = soup.select_one("#ficha")
    if not ficha:
        return {"direccion": "", "telefono": "", "paginaweb": ""}

    direccion = ""
    telefono = ""
    paginaweb = ""

    for strong in ficha.select("strong"):
        label = strong.get_text(" ", strip=True).lower().rstrip(":")
        value = ""

        node = strong.next_sibling
        while node is not None:
            if getattr(node, "name", None) == "br":
                break
            if isinstance(node, str):
                value += node
            else:
                value += node.get_text(" ", strip=True)
            node = node.next_sibling

        value = " ".join(value.split()).strip()

        if label == "dirección":
            direccion = value
        elif label == "teléfono":
            telefono = value
        elif label == "página web":
            paginaweb = value

    if not paginaweb:
        for a in ficha.select("a[href]"):
            if "web:" in a.get_text(" ", strip=True).lower():
                paginaweb = a.get("href") or a.get_text(strip=True)

    return {
        "direccion": direccion,
        "telefono": telefono,
        "paginaweb": paginaweb,
    }


def _pick_best_email(html: str, domain: str) -> str:
    emails = sorted(set(EMAIL_RE.findall(html)))
    if not emails:
        return ""
    if domain:
        for e in emails:
            if e.lower().endswith("@" + domain.lower()):
                return e
    return emails[0]


def _fetch_email(session: requests.Session, base_url: str) -> str:
    """
    Busca email en home y páginas típicas.
    Devuelve email o string vacío.
    """
    base_url = _ensure_url(base_url)
    domain = _domain_from_url(base_url)

    paths = [
        "",
        "contacto/",
        "contact/",
        "aviso-legal/",
        "legal/",
        "privacy/",
        "politica-de-privacidad/",
        "politica-privacidad/",
    ]

    for p in paths:
        try:
            url = urljoin(base_url + "/", p)
            r = session.get(url, timeout=30, allow_redirects=True)
            if r.status_code >= 400:
                continue

            email = _pick_best_email(r.text, domain)
            if email:
                return email

        except Exception:
            continue

    return ""


def run(out_dir: str, **kwargs):
    customer = kwargs.get("customer")
    base = kwargs.get("base")
    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    empresas_csv = Path("/data") / customer / base / "empresas.csv"
    if not empresas_csv.exists():
        raise FileNotFoundError(empresas_csv)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    rows_out = []

    with empresas_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= MAX_ITEMS:
                break

            empresa_url = (row.get("empresa_url") or "").strip()
            if not empresa_url:
                continue

            print(f"▶ [{i+1}/{MAX_ITEMS}] {empresa_url}")

            try:
                r = session.get(empresa_url, timeout=30)
                r.raise_for_status()
            except Exception as e:
                print(f"  ❌ Error cargando ficha: {e}")
                continue

            ficha = _extract_fields_from_ficha(r.text)
            paginaweb_url = _ensure_url(ficha["paginaweb"])
            email = _fetch_email(session, paginaweb_url) if paginaweb_url else ""

            rows_out.append(
                {
                    "direccion": ficha["direccion"],
                    "telefono": ficha["telefono"],
                    "paginaweb": paginaweb_url,
                    "email": email,
                }
            )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "website_probe.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["direccion", "telefono", "paginaweb", "email"],
        )
        w.writeheader()
        w.writerows(rows_out)

    print(f"\n✅ Guardadas {len(rows_out)} filas en {out_path}")
