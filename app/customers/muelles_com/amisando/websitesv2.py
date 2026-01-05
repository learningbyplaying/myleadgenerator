import csv
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


MAX_ITEMS = None  # 10  # pon None si quieres procesar todo

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

    return {"direccion": direccion, "telefono": telefono, "paginaweb": paginaweb}


def _pick_best_email(html: str, domain: str) -> str:
    emails = sorted(set(EMAIL_RE.findall(html)))
    if not emails:
        return ""
    if domain:
        for e in emails:
            if e.lower().endswith("@" + domain.lower()):
                return e
    return emails[0]


def _fetch_email(session: requests.Session, base_url: str, timeout) -> str:
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
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code >= 400:
                continue

            email = _pick_best_email(r.text, domain)
            if email:
                return email

        except requests.exceptions.Timeout:
            # timeout -> seguimos
            continue
        except requests.exceptions.RequestException:
            # cualquier otro error de requests -> seguimos
            continue

    return ""


def _load_already_processed(output_csv: Path) -> set[str]:
    processed = set()
    if not output_csv.exists():
        return processed

    with output_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return processed
        if "empresa_url" not in reader.fieldnames:
            return processed

        for row in reader:
            u = (row.get("empresa_url") or "").strip()
            if u:
                processed.add(u)
    return processed


def _parse_timeout(kwargs) -> tuple[float, float]:
    """
    Devuelve timeout como (connect_timeout, read_timeout)
    - kwargs["timeout"] si viene
    - si no, env SCRAPE_TIMEOUT
    - si no, 30s
    """
    raw = kwargs.get("timeout", os.getenv("SCRAPE_TIMEOUT", "30"))
    try:
        t = float(raw)
    except Exception:
        t = 30.0

    # connect más corto (evita cuelgues de handshake)
    connect_t = min(10.0, t)
    read_t = t
    return (connect_t, read_t)


def run(out_dir: str, **kwargs):
    customer = kwargs.get("customer")
    base = kwargs.get("base")
    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    timeout = _parse_timeout(kwargs)
    print(f"⏱️ Timeout configurado (connect, read): {timeout}")

    empresas_csv = Path("/data") / customer / base / "empresas.csv"
    if not empresas_csv.exists():
        raise FileNotFoundError(empresas_csv)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "website.csv"

    processed = _load_already_processed(out_path)
    if processed:
        print(f"↩️ Reanudando: {len(processed)} empresas ya estaban en {out_path}")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    write_header = not out_path.exists() or out_path.stat().st_size == 0
    f_out = out_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        f_out,
        fieldnames=[
            "direccion",
            "telefono",
            "paginaweb",
            "email",
            "provincia_url",
            "empresa_url",  # último
        ],
    )
    if write_header:
        writer.writeheader()

    written = 0
    considered = 0

    try:
        with empresas_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                if MAX_ITEMS is not None and considered >= MAX_ITEMS:
                    break

                provincia_url = (row.get("provincia_url") or "").strip()
                empresa_url = (row.get("empresa_url") or "").strip()
                if not empresa_url:
                    continue

                considered += 1

                if empresa_url in processed:
                    continue

                print(f"▶ Procesando: {provincia_url},{empresa_url}")

                try:
                    r = session.get(empresa_url, timeout=timeout, allow_redirects=True)
                    r.raise_for_status()
                except requests.exceptions.Timeout:
                    print("  ❌ Timeout cargando ficha")
                    ficha = {"direccion": "", "telefono": "", "paginaweb": ""}
                    paginaweb_url = ""
                    email = ""
                except requests.exceptions.RequestException as e:
                    print(f"  ❌ Error cargando ficha: {e}")
                    ficha = {"direccion": "", "telefono": "", "paginaweb": ""}
                    paginaweb_url = ""
                    email = ""
                else:
                    ficha = _extract_fields_from_ficha(r.text)
                    paginaweb_url = _ensure_url(ficha["paginaweb"])
                    email = _fetch_email(session, paginaweb_url, timeout=timeout) if paginaweb_url else ""

                writer.writerow(
                    {
                        "direccion": ficha["direccion"],
                        "telefono": ficha["telefono"],
                        "paginaweb": paginaweb_url,
                        "email": email,
                        "provincia_url": provincia_url,
                        "empresa_url": empresa_url,
                    }
                )
                f_out.flush()

                processed.add(empresa_url)
                written += 1

    finally:
        f_out.close()

    print(f"✅ Añadidas {written} filas nuevas en {out_path}")
