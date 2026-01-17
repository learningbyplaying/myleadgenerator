# ./run.sh datainnovation_com seraportiendasonline_com websites

import csv
import os
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# =========================
# CONFIG
# =========================
MAX_ITEMS = None        # 10 para test; None para todo
SLEEP = 0.35

OUT_FIELDS = ["empresa", "website", "platform", "is_alive", "email", "telefono", "ficha_url"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)

PHONE_RE = re.compile(
    r"""
    (?:
        (?:\(\s*\+34\s*\)|\+34|0034)\s*[\-\.]?\s*(?:\d[\s\-\.]?){8,12}
        |
        \b(?:6|7|8|9)(?:[\s\-\.]?\d){8}\b
    )
    """,
    re.VERBOSE,
)

BAD_EMAIL_SUFFIXES = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf",
    ".mp4", ".mov", ".avi", ".zip", ".rar"
)

BAD_EMAIL_DOMAINS = {
    "prestashop.com",
    "shopify.com",
    "myshopify.com",
    "mailchimp.com",
    "klaviyo.com",
    "sendgrid.net",
}

FREE_EMAIL_DOMAINS = {
    "gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "icloud.com",
}

SHOPIFY_RE = re.compile(r"(cdn\.shopify\.com|shopifyassets\.com|myshopify\.com)", re.I)
WP_RE = re.compile(r"(wp-content/|wp-includes/|wp-json|xmlrpc\.php)", re.I)
PRESTA_RE = re.compile(r"(prestashop|/modules/|/themes/|controller=)", re.I)

PARKING_RE = re.compile(
    r"(domain (is )?for sale|comprar dominio|this domain is for sale|sedo|dan\.com|afternic|parking|parked domain)",
    re.I,
)


# =========================
# HELPERS
# =========================
def _parse_timeout(kwargs) -> tuple[float, float]:
    raw = kwargs.get("timeout", os.getenv("SCRAPE_TIMEOUT", "8"))
    try:
        t = float(raw)
    except Exception:
        t = 8.0
    connect_t = min(4.0, t)
    read_t = t
    return (connect_t, read_t)


def _ensure_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return "https://" + raw


def _looks_like_url(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    if ("," in s or " " in s) and ("://" not in s):
        if "." not in s:
            return False
    if "://" not in s and "." not in s and not s.startswith("/"):
        return False
    return True


def _safe_website(raw: str) -> str:
    raw = (raw or "").strip()
    if not _looks_like_url(raw):
        return ""
    return _ensure_url(raw)


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    host = urlparse(_ensure_url(url)).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize_empresa(name: str) -> str:
    s = (name or "").strip().lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("™", "").replace("®", "")
    s = re.sub(r"\s+", " ", s)
    s = s.strip(' "\'')
    return s


def detect_platform(html: str) -> str:
    h = html or ""
    if SHOPIFY_RE.search(h):
        return "shopify"
    if WP_RE.search(h):
        return "wordpress"
    if PRESTA_RE.search(h):
        return "prestashop"
    return ""


def _is_valid_email(email: str) -> bool:
    e = (email or "").strip().lower()
    if not e or e.count("@") != 1:
        return False
    if any(e.endswith(suf) for suf in BAD_EMAIL_SUFFIXES):
        return False
    if "/@" in e:
        return False
    return True


def _pick_email_strict(html: str, domain: str) -> str:
    if not domain:
        return ""
    emails = sorted(set(EMAIL_RE.findall(html or "")))
    emails = [e for e in emails if _is_valid_email(e)]
    d = domain.lower()
    for e in emails:
        at_dom = e.split("@", 1)[-1].lower()
        if at_dom == d or at_dom.endswith("." + d):
            return e
    return ""


def _pick_email_fallback(html: str) -> str:
    emails = sorted(set(EMAIL_RE.findall(html or "")))
    emails = [e for e in emails if _is_valid_email(e)]
    for e in emails:
        at_dom = e.split("@", 1)[-1].lower()
        if at_dom in BAD_EMAIL_DOMAINS:
            continue
        if at_dom in FREE_EMAIL_DOMAINS:
            continue
        return e
    return ""


def _normalize_phone(raw: str) -> str:
    raw = (raw or "").strip()
    raw = re.sub(r"[^\d\+]", "", raw)
    if raw.startswith("0034"):
        raw = "+34" + raw[4:]
    if raw.startswith("34") and not raw.startswith("+34") and len(raw) >= 11:
        raw = "+34" + raw[2:]
    return raw


def _pick_best_phone(text: str) -> str:
    matches = PHONE_RE.findall(text or "")
    if not matches:
        return ""
    return _normalize_phone(matches[0])


def check_alive(session: requests.Session, website: str, timeout) -> tuple[int, str]:
    website = _safe_website(website)
    if not website:
        return 0, ""
    try:
        r = session.get(website, timeout=timeout, allow_redirects=True)
        if r.status_code >= 400:
            return 0, ""
        html = r.text or ""
        if html and PARKING_RE.search(html):
            return 0, html
        return 1, html
    except requests.exceptions.RequestException:
        return 0, ""


def _extract_from_ficha(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")

    website = ""
    telefono = ""

    a_shop = soup.select_one("div.linkshop a[href]")
    if a_shop:
        website = (a_shop.get("href") or "").strip()

    for lab in soup.select("p.infoLabel"):
        k = (lab.get_text(" ", strip=True) or "").strip().lower()
        if k == "tags":
            continue

        v_el = lab.find_next_sibling("p")
        if not v_el:
            continue
        v = v_el.get_text(" ", strip=True)

        if not website and k == "url":
            website = v.strip()

        if not telefono and k.startswith("tel"):
            telefono = _pick_best_phone(v) or v

    website = _safe_website(website)
    telefono = _pick_best_phone(telefono) or telefono
    return website, telefono


def _load_processed_empresas(output_csv: Path) -> set[str]:
    done = set()
    if not output_csv.exists() or output_csv.stat().st_size == 0:
        return done
    with output_csv.open("r", encoding="utf-8", newline="") as f:
        dr = csv.DictReader(f)
        if not dr.fieldnames or "empresa" not in dr.fieldnames:
            return done
        for row in dr:
            k = normalize_empresa(row.get("empresa") or "")
            if k:
                done.add(k)
    return done


def _print_summary(csv_path: Path):
    """
    Resumen final:
      - empresas (filas)
      - websites no vacíos
      - alive
      - teléfonos de alive
      - emails de alive
      - plataformas (alive) y contadores
    """
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        print("\n📊 RESUMEN\n- No hay output aún.")
        return

    total = 0
    websites = 0
    alive = 0
    alive_phone = 0
    alive_email = 0

    plat_all = Counter()
    plat_alive = Counter()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        dr = csv.DictReader(f)
        for row in dr:
            total += 1

            w = (row.get("website") or "").strip()
            if w:
                websites += 1

            p = (row.get("platform") or "").strip() or "(unknown)"
            plat_all[p] += 1

            is_alive = (row.get("is_alive") or "").strip()
            is_alive = 1 if is_alive in ("1", "true", "True") else 0

            if is_alive:
                alive += 1
                plat_alive[p] += 1

                if (row.get("telefono") or "").strip():
                    alive_phone += 1
                if (row.get("email") or "").strip():
                    alive_email += 1

    print("\n📊 RESUMEN")
    print(f"- Empresas (filas): {total}")
    print(f"- Websites (no vacíos): {websites}")
    print(f"- Alive: {alive}")
    print(f"- Teléfonos (solo alive): {alive_phone}")
    print(f"- Emails (solo alive): {alive_email}")

    # Plataformas
    print("\n🧩 Plataformas (solo alive):")
    for k, v in plat_alive.most_common():
        print(f"  - {k}: {v}")

    print("\n🧩 Plataformas (total):")
    for k, v in plat_all.most_common():
        print(f"  - {k}: {v}")


# =========================
# RUNNER ENTRYPOINT
# =========================
def run(out_dir: str, **kwargs):
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
    out_path = out_dir / "websites.csv"

    processed = _load_processed_empresas(out_path)
    if processed:
        print(f"↩️ Breakpoint: {len(processed)} empresas ya estaban en {out_path}")

    session = requests.Session()
    session.headers.update(HEADERS)

    write_header = not out_path.exists() or out_path.stat().st_size == 0
    f_out = out_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f_out, fieldnames=OUT_FIELDS)
    if write_header:
        writer.writeheader()

    seen_empresas = set(processed)
    considered = 0
    written = 0

    try:
        with empresas_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if MAX_ITEMS is not None and considered >= MAX_ITEMS:
                    break

                empresa = (row.get("empresa") or "").strip()
                ficha_url = (row.get("ficha_url") or "").strip()
                if not empresa or not ficha_url:
                    continue

                key = normalize_empresa(empresa)
                if not key:
                    continue

                # DISTINCT por empresa
                if key in seen_empresas:
                    continue

                considered += 1
                print(f"▶ {empresa} | {ficha_url}")

                website = ""
                telefono = ""
                platform = ""
                is_alive = 0
                email = ""

                # 1) ficha seraportiendasonline
                try:
                    r = session.get(_ensure_url(ficha_url), timeout=timeout, allow_redirects=True)
                    r.raise_for_status()
                    website, telefono = _extract_from_ficha(r.text)
                except requests.exceptions.RequestException:
                    writer.writerow({
                        "empresa": empresa,
                        "website": "",
                        "platform": "",
                        "is_alive": 0,
                        "email": "",
                        "telefono": "",
                        "ficha_url": ficha_url,
                    })
                    f_out.flush()
                    seen_empresas.add(key)
                    written += 1
                    time.sleep(SLEEP)
                    continue

                # 2) web real
                if website:
                    is_alive, html_home = check_alive(session, website, timeout=timeout)
                    if html_home:
                        platform = detect_platform(html_home)
                        domain = _domain_from_url(website)
                        email = _pick_email_strict(html_home, domain) or _pick_email_fallback(html_home)
                        if not telefono:
                            telefono = _pick_best_phone(html_home) or ""

                writer.writerow({
                    "empresa": empresa,
                    "website": website,
                    "platform": platform,
                    "is_alive": is_alive,
                    "email": email,
                    "telefono": telefono,
                    "ficha_url": ficha_url,
                })
                f_out.flush()

                seen_empresas.add(key)
                written += 1
                time.sleep(SLEEP)

    finally:
        f_out.close()

    print(f"✅ Añadidas {written} filas nuevas en {out_path}")

    # 🔥 RESUMEN FINAL
    _print_summary(out_path)
