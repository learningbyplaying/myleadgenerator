# ./run.sh datainnovation_com comunicare_es websites

import csv
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


MAX_ITEMS = None  # pon 10 para test; None para todo

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Captura teléfonos España (incluye (+34) ...)
PHONE_RE = re.compile(
    r"""
    (?:
        # (+34) 91 016 75 00 | +34 91 016 75 00 | 0034 91 016 75 00
        (?:\(\s*\+34\s*\)|\+34|0034)\s*[\-\.]?\s*(?:\d[\s\-\.]?){8,12}
        |
        # 9 dígitos ES típicos (con separadores)
        \b(?:6|7|8|9)(?:[\s\-\.]?\d){8}\b
    )
    """,
    re.VERBOSE,
)

BAD_EMAIL_SUFFIXES = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf",
    ".mp4", ".mov", ".avi", ".zip", ".rar"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


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


def _is_valid_email(email: str) -> bool:
    e = (email or "").strip().lower()
    if not e or e.count("@") != 1:
        return False
    # filtra falsos "emails" que son assets (png/jpg/etc.)
    if any(e.endswith(suf) for suf in BAD_EMAIL_SUFFIXES):
        return False
    # filtra casos raros con rutas
    if "/@" in e:
        return False
    return True


def _pick_best_email(html: str, domain: str) -> str:
    emails = sorted(set(EMAIL_RE.findall(html)))
    emails = [e for e in emails if _is_valid_email(e)]
    if not emails:
        return ""

    if domain:
        # 1) match exacto del dominio
        for e in emails:
            if e.lower().endswith("@" + domain.lower()):
                return e

        # 2) acepta subdominios (mail.miweb.com) si acaban en .domain
        for e in emails:
            at_dom = e.split("@", 1)[-1].lower()
            if at_dom.endswith("." + domain.lower()):
                return e

    return emails[0]


def _normalize_phone(raw: str) -> str:
    raw = (raw or "").strip()
    # quita separadores comunes, conserva +
    raw = re.sub(r"[^\d\+]", "", raw)

    if raw.startswith("0034"):
        raw = "+34" + raw[4:]

    if raw.startswith("34") and not raw.startswith("+34") and len(raw) >= 11:
        raw = "+34" + raw[2:]

    return raw


def _format_es_phone(norm: str) -> str:
    """
    Formato legible si es +34 y 9 dígitos nacionales:
      +34910167500 -> (+34) 91 016 75 00
      +34634544507 -> (+34) 634 54 45 07
    """
    digits = re.sub(r"\D", "", norm)
    if norm.startswith("+34") and len(digits) == 11:
        nat = digits[2:]  # 9 dígitos
        if nat[0] in ("8", "9"):
            return f"(+34) {nat[0:2]} {nat[2:5]} {nat[5:7]} {nat[7:9]}"
        return f"(+34) {nat[0:3]} {nat[3:5]} {nat[5:7]} {nat[7:9]}"
    return norm


def _pick_best_phone(html: str) -> str:
    matches = PHONE_RE.findall(html)
    if not matches:
        return ""

    candidates = []
    for m in matches:
        p = _normalize_phone(m)
        digits = re.sub(r"\D", "", p)
        if 9 <= len(digits) <= 15:
            candidates.append(p)

    if not candidates:
        return ""

    # Prioriza los que llevan prefijo +34
    for p in candidates:
        if p.startswith("+34"):
            return _format_es_phone(p)

    return _format_es_phone(candidates[0])


def _parse_timeout(kwargs) -> tuple[float, float]:
    raw = kwargs.get("timeout", os.getenv("SCRAPE_TIMEOUT", "30"))
    try:
        t = float(raw)
    except Exception:
        t = 30.0
    connect_t = min(10.0, t)
    read_t = t
    return (connect_t, read_t)


def _fetch_contact_data(session: requests.Session, base_url: str, timeout) -> tuple[str, str]:
    """
    Devuelve (email, telefono) buscando en rutas típicas.
    - Prioriza email del mismo dominio de la web.
    - Filtra falsos emails de assets (png/jpg con @2x etc.)
    - Teléfono busca +34 / (+34) / 0034 y 9 dígitos ES.
    """
    base_url = _ensure_url(base_url)
    domain = _domain_from_url(base_url)

    paths = [
        "",
        "contacto/",
        "contacto",
        "contact/",
        "aviso-legal/",
        "aviso-legal",
        "legal/",
        "privacy/",
        "politica-de-privacidad/",
        "politica-privacidad/",
        "privacidad/",
    ]

    best_email = ""
    best_phone = ""

    for p in paths:
        try:
            url = urljoin(base_url.rstrip("/") + "/", p)
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code >= 400:
                continue

            if not best_email:
                e = _pick_best_email(r.text, domain)
                if e:
                    best_email = e

            if not best_phone:
                ph = _pick_best_phone(r.text)
                if ph:
                    best_phone = ph

            if best_email and best_phone:
                return best_email, best_phone

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.RequestException:
            continue

    return best_email, best_phone


def _load_already_processed(output_csv: Path) -> set[str]:
    """
    Para reanudar: consideramos procesada una fila si su 'web' ya está en el output.
    """
    processed = set()
    if not output_csv.exists():
        return processed

    with output_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "web" not in reader.fieldnames:
            return processed

        for row in reader:
            web = (row.get("web") or "").strip()
            if web:
                processed.add(web)

    return processed


def run(out_dir: str, **kwargs):
    """
    Input:
      /data/<customer>/<base>/empresas.csv
        columnas esperadas: ciudad, ciudad_url, empresa, web

    Output:
      <out_dir>/website.csv
        columnas: ciudad, ciudad_url, empresa, web, email, telefono
    """
    customer = kwargs.get("customer")
    base = kwargs.get("base")
    if not customer or not base:
        raise ValueError("Faltan kwargs: customer y base")

    timeout = _parse_timeout(kwargs)
    print(f"⏱️ Timeout configurado (connect, read): {timeout}")

    empresas_csv = Path("/data") / customer / base / "empresas.csv"
    if not empresas_csv.exists():
        raise FileNotFoundError(f"No existe el input: {empresas_csv}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "website.csv"

    processed = _load_already_processed(out_path)
    if processed:
        print(f"↩️ Reanudando: {len(processed)} webs ya estaban en {out_path}")

    session = requests.Session()
    session.headers.update(HEADERS)

    write_header = not out_path.exists() or out_path.stat().st_size == 0
    f_out = out_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        f_out,
        fieldnames=["ciudad", "ciudad_url", "empresa", "web", "email", "telefono"],
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

                ciudad = (row.get("ciudad") or "").strip()
                ciudad_url = (row.get("ciudad_url") or "").strip()
                empresa = (row.get("empresa") or "").strip()
                web = _ensure_url(row.get("web") or "")

                if not web:
                    continue

                considered += 1

                if web in processed:
                    continue

                print(f"▶ {empresa} | {ciudad} | {web}")

                email, telefono = _fetch_contact_data(session, web, timeout=timeout)

                writer.writerow(
                    {
                        "ciudad": ciudad,
                        "ciudad_url": ciudad_url,
                        "empresa": empresa,
                        "web": web,
                        "email": email,
                        "telefono": telefono,
                    }
                )
                f_out.flush()

                processed.add(web)
                written += 1

    finally:
        f_out.close()

    print(f"✅ Añadidas {written} filas nuevas en {out_path}")
