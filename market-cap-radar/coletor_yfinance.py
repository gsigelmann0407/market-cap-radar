# ============================================================
#  MARKET CAP RADAR — Coletor yfinance
#  Scraping : companiesmarketcap.com  (top 500)
#  Dados    : yfinance (setor, preço, variação do dia)
#  Destino  : Supabase tabela snapshots
#  Uso      : python coletor_yfinance.py
# ============================================================

import sys
import subprocess

# ── Auto-instalação de dependências ──────────────────────────
_PKGS = ["requests", "beautifulsoup4", "lxml", "yfinance", "pandas"]
for _p in _PKGS:
    _imp = _p.replace("-", "_").split("[")[0]
    try:
        __import__(_imp)
    except ImportError:
        print(f"[setup] Instalando {_p} ...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", _p, "-q"])

# ── SSL: certificado corporativo (rede com inspeção SSL) ──────
# As variáveis de ambiente DEVEM ser definidas ANTES do import yfinance,
# pois o curl_cffi lê CURL_CA_BUNDLE na inicialização da sessão.
import os, ssl
from pathlib import Path

_PEM = Path(__file__).parent / "empresa.pem"

if _PEM.exists():
    # Usa o certificado corporativo exportado pelo exportar_certificado.py
    _pem_str = str(_PEM)
    os.environ["CURL_CA_BUNDLE"]     = _pem_str  # curl_cffi / yfinance
    os.environ["REQUESTS_CA_BUNDLE"] = _pem_str  # requests (fallback do yfinance)
    os.environ["SSL_CERT_FILE"]      = _pem_str  # openssl
else:
    # empresa.pem não encontrado — desabilita verificação como fallback
    print("[ssl] AVISO: empresa.pem não encontrado. Execute exportar_certificado.py primeiro.", flush=True)
    print("[ssl] Usando fallback: verificação SSL desabilitada.", flush=True)
    os.environ["CURL_CA_BUNDLE"]     = ""
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    os.environ["SSL_CERT_FILE"]      = ""
    ssl._create_default_https_context = ssl._create_unverified_context

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd
import requests
import urllib3
import yfinance as yf
from bs4 import BeautifulSoup

from config import SUPABASE_KEY, SUPABASE_URL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Log ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("coleta.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

TOP_N   = 500
PAGINAS = 5      # ~100 empresas/página → 500 total
WORKERS = 10     # threads para buscas de setor
DELAY   = 1.5    # segundos entre páginas (politeness)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Sessão global — verify=False para rede corporativa com firewall
_sess = requests.Session()
_sess.verify = False
_sess.headers["User-Agent"] = _UA


# ── Helpers ──────────────────────────────────────────────────

# ── Scraping ─────────────────────────────────────────────────
#
# Estrutura real do site (inspecionada em 2025-05):
#   table.marketcap-table tbody tr
#     td.fav                          → ignorar (estrela favorito)
#     td.rank-td[data-sort="1"]       → rank (inteiro no atributo)
#     td.name-td
#       div.company-name              → nome
#       div.company-code              → ticker (contém span.rank vazio a ignorar)
#     td[data-sort="5230436024320"]   → market cap em USD (raw int no atributo)
#     td                              → preço
#     td.rh-sm                        → variação % do dia
#     td.sparkline-td                 → mini gráfico (ignorar)
#     td  span.responsive-hidden      → país (código 3 letras, ex: "USA")

def _scrape_pagina(num: int) -> list[dict]:
    url = "https://companiesmarketcap.com/" if num == 1 else f"https://companiesmarketcap.com/page/{num}/"

    resp = _sess.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    empresas = []

    for row in soup.select("table.marketcap-table tbody tr"):
        try:
            # ── Rank ─────────────────────────────────────────
            rank_td = row.select_one("td.rank-td")
            if not rank_td:
                continue
            rank = int(rank_td["data-sort"])

            # ── Nome ─────────────────────────────────────────
            nome_el = row.select_one("div.company-name")
            if not nome_el:
                continue
            nome = nome_el.get_text(strip=True)

            # ── Ticker ───────────────────────────────────────
            code_el = row.select_one("div.company-code")
            if not code_el:
                continue
            # Remove o span.rank invisível antes de extrair o texto
            for span in code_el.select("span.rank"):
                span.decompose()
            ticker = code_el.get_text(strip=True)

            # ── Market Cap (USD, valor exato do atributo data-sort) ──
            # A 4ª <td> (índice 3 contando fav=0, rank=1, name=2, cap=3)
            cells = row.find_all("td")
            cap_td = cells[3] if len(cells) > 3 else None
            if cap_td and cap_td.has_attr("data-sort"):
                market_cap_usd = float(cap_td["data-sort"])
            else:
                market_cap_usd = None

            # ── País ─────────────────────────────────────────
            pais_el = row.select_one("span.responsive-hidden")
            pais = pais_el.get_text(strip=True) if pais_el else ""

            if not nome or not ticker:
                continue

            empresas.append({
                "nome":           nome,
                "ticker":         ticker,
                "market_cap_usd": market_cap_usd,
                "pais":           pais,
                "_rank_site":     rank,
            })

        except Exception:
            continue

    return empresas


def scrape_top500() -> pd.DataFrame:
    log.info("Scraping companiesmarketcap.com — top 500...")
    todas = []

    for pg in range(1, PAGINAS + 1):
        log.info(f"  Página {pg}/{PAGINAS} ...")
        try:
            chunk = _scrape_pagina(pg)
            log.info(f"    {len(chunk)} empresas encontradas")
            todas.extend(chunk)
        except Exception as exc:
            log.warning(f"    Erro na página {pg}: {exc}")
        if pg < PAGINAS:
            time.sleep(DELAY)

    if not todas:
        return pd.DataFrame()

    df = (
        pd.DataFrame(todas)
        .drop_duplicates(subset=["ticker"])
        .dropna(subset=["market_cap_usd"])
    )

    # Re-rankeia por market cap (o scraping pode ter gaps entre páginas)
    df = (
        df.sort_values("market_cap_usd", ascending=False)
        .reset_index(drop=True)
        .head(TOP_N)
    )
    df["rank"] = df.index + 1
    df = df.drop(columns=["_rank_site"], errors="ignore")

    log.info(f"Scraping concluído: {len(df)} empresas únicas.")
    return df


# ── Enriquecimento yfinance ──────────────────────────────────

def _setor_ticker(ticker: str) -> dict:
    """Busca setor GICS para um único ticker via yfinance."""
    try:
        info = yf.Ticker(ticker).info
        setor = (
            info.get("sector")
            or info.get("sectorDisp")
            or ""
        )
        return {"ticker": ticker, "setor": setor}
    except Exception:
        return {"ticker": ticker, "setor": ""}


def enriquecer_yfinance(df: pd.DataFrame) -> pd.DataFrame:
    tickers = df["ticker"].tolist()

    # ── 1. Preço e variação — download em lote ────────────────
    log.info(f"Baixando preços (yfinance batch, {len(tickers)} tickers)...")
    preco_map     = {}
    variacao_map  = {}
    try:
        raw = yf.download(
            tickers,
            period="2d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        # Normaliza MultiIndex (múltiplos tickers) vs Index simples (1 ticker)
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})

        if not close.empty and len(close) >= 1:
            preco_map = close.iloc[-1].dropna().to_dict()
        if not close.empty and len(close) >= 2:
            pct = close.pct_change().iloc[-1] * 100
            variacao_map = pct.dropna().to_dict()

        log.info(f"  Preços obtidos para {len(preco_map)} tickers.")
    except Exception as exc:
        log.warning(f"  Erro no download batch de preços: {exc}")

    # ── 2. Setor — chamadas individuais em paralelo ───────────
    log.info(f"Buscando setores ({WORKERS} threads paralelas)...")
    setor_map = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = {ex.submit(_setor_ticker, t): t for t in tickers}
        done = 0
        for fut in as_completed(futuros):
            res = fut.result()
            setor_map[res["ticker"]] = res["setor"]
            done += 1
            if done % 100 == 0:
                log.info(f"  {done}/{len(tickers)} setores processados...")
    log.info(f"  Setores preenchidos: {sum(1 for v in setor_map.values() if v)}/{len(tickers)}")

    # ── 3. Mescla ─────────────────────────────────────────────
    df["preco"]            = df["ticker"].map(preco_map)
    df["variacao_dia_pct"] = df["ticker"].map(variacao_map)
    df["setor"]            = df["ticker"].map(setor_map)

    return df


# ── Supabase ─────────────────────────────────────────────────

_COLUNAS = [
    "data", "ticker", "nome", "rank",
    "market_cap_usd", "preco", "variacao_dia_pct", "setor", "pais",
]
_LOTE_SIZE = 200  # registros por POST


def _serializar(row: dict) -> dict:
    """Converte tipos numpy/float para tipos JSON-serializáveis."""
    out = {}
    for k, v in row.items():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            out[k] = None
        elif isinstance(v, float):
            out[k] = round(float(v), 6)
        elif hasattr(v, "item"):      # numpy scalar
            out[k] = v.item()
        else:
            out[k] = v
    return out


def salvar_supabase(df: pd.DataFrame):
    log.info("Salvando no Supabase...")

    df = df.copy()
    df["data"] = date.today().isoformat()
    df["rank"] = df["rank"].astype(int)

    registros = [
        _serializar(row)
        for row in df[_COLUNAS].to_dict(orient="records")
    ]

    url = f"{SUPABASE_URL}/rest/v1/snapshots?on_conflict=ticker,data"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates",
    }

    total = 0
    for i in range(0, len(registros), _LOTE_SIZE):
        lote = registros[i : i + _LOTE_SIZE]
        resp = _sess.post(url, json=lote, headers=headers)
        if resp.status_code not in (200, 201):
            log.error(f"Supabase erro {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
        total += len(lote)
        log.info(f"  {total}/{len(registros)} registros gravados...")

    log.info(f"Supabase: {total} registros salvos com sucesso.")


# ── Main ─────────────────────────────────────────────────────

def main():
    log.info("=" * 55)
    log.info(f"  COLETA INICIADA — {date.today().isoformat()}")
    log.info("=" * 55)

    try:
        df = scrape_top500()
        if df.empty:
            log.error("Scraping retornou 0 empresas. Verifique a estrutura HTML do site.")
            sys.exit(1)

        df = enriquecer_yfinance(df)
        salvar_supabase(df)

        log.info("=" * 55)
        log.info("  COLETA CONCLUIDA COM SUCESSO")
        log.info("=" * 55)

    except Exception as exc:
        log.exception(f"Coleta falhou: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
