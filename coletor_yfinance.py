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

TOP_N              = 500
PAGINAS            = 5      # ~100 empresas/página → 500 total
WORKERS            = 10     # threads para buscas de setor
DELAY              = 1.5    # segundos entre páginas (politeness)
MARKET_CAP_MIN_USD = 50_000_000_000  # US$ 50 bilhões

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

    # Re-rankeia por market cap e aplica filtro mínimo de US$ 50 bi
    df = (
        df.sort_values("market_cap_usd", ascending=False)
        .reset_index(drop=True)
        .head(TOP_N)
    )
    df = df[df["market_cap_usd"] >= MARKET_CAP_MIN_USD].reset_index(drop=True)
    df["rank"] = df.index + 1
    df = df.drop(columns=["_rank_site"], errors="ignore")

    log.info(f"Scraping concluído: {len(df)} empresas únicas.")
    return df


# ── Enriquecimento yfinance ──────────────────────────────────

def _setor_ticker(ticker: str) -> dict:
    """Busca setor GICS. Aquece com history('5d') e faz retry para evitar rate limit."""
    for attempt in range(3):
        try:
            tk = yf.Ticker(ticker)
            tk.history(period="5d", auto_adjust=True, progress=False)
            info  = tk.info
            setor = info.get("sector") or info.get("sectorDisp") or ""
            if setor:
                return {"ticker": ticker, "setor": setor}
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1.5)
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
            period="5d",
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


# ── Histórico 2 anos ─────────────────────────────────────────
#
# Tabela necessária no Supabase (crie via SQL editor):
#   CREATE TABLE historico_mercado (
#     ticker         TEXT    NOT NULL,
#     data           DATE    NOT NULL,
#     preco          FLOAT,
#     market_cap_usd FLOAT,
#     PRIMARY KEY (ticker, data)
#   );

def _get_shares_outstanding(ticker: str) -> tuple[str, "float | None"]:
    try:
        info   = yf.Ticker(ticker).info
        shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        return ticker, float(shares) if shares else None
    except Exception:
        return ticker, None


def _tickers_com_historico() -> set:
    url = f"{SUPABASE_URL}/rest/v1/historico_mercado?select=ticker&limit=100000"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept":        "application/json",
    }
    try:
        resp = _sess.get(url, headers=headers, timeout=20)
        if not resp.ok:
            if resp.status_code == 404:
                log.warning(
                    "Tabela historico_mercado não existe. "
                    "Crie-a no Supabase (SQL no cabeçalho deste arquivo)."
                )
            return set()
        return {r["ticker"] for r in resp.json()}
    except Exception as exc:
        log.warning(f"Erro ao consultar historico_mercado: {exc}")
        return set()


def _salvar_historico_supabase(registros: list):
    if not registros:
        return
    url = f"{SUPABASE_URL}/rest/v1/historico_mercado?on_conflict=ticker,data"
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
            log.error(f"Histórico Supabase erro {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
        total += len(lote)
        if total % 2000 == 0:
            log.info(f"  {total}/{len(registros)} registros históricos gravados...")
    log.info(f"Histórico: {total} registros salvos no Supabase.")


def puxar_e_salvar_historico(tickers: list):
    """
    Puxa 2 anos de preço/market-cap para tickers sem dados em historico_mercado.
    Execução idempotente: tickers já presentes são ignorados.
    Market cap ≈ preco × shares_outstanding (proxy com ações atuais).
    """
    log.info("Histórico 2 anos: verificando tickers pendentes...")
    existentes = _tickers_com_historico()
    pendentes  = [t for t in tickers if t not in existentes]

    if not pendentes:
        log.info("Histórico: todos os tickers já têm dados. Pulando.")
        return

    log.info(f"Histórico: {len(pendentes)} tickers sem dados. Iniciando coleta...")

    # Shares outstanding em paralelo
    log.info(f"  Buscando shares outstanding ({WORKERS} threads)...")
    shares_map: dict = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = {ex.submit(_get_shares_outstanding, t): t for t in pendentes}
        for fut in as_completed(futuros):
            ticker, shares = fut.result()
            if shares:
                shares_map[ticker] = shares
    log.info(f"  Shares obtidos: {len(shares_map)}/{len(pendentes)} tickers.")

    # Download preços 2 anos em batch
    log.info(f"  Baixando 2 anos de preços ({len(pendentes)} tickers em batch)...")
    try:
        raw = yf.download(
            pendentes,
            period="2y",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            close = raw[["Close"]].rename(columns={"Close": pendentes[0]})
        # Remove timezone para evitar problemas de serialização
        if close.index.tz is not None:
            close.index = close.index.tz_convert(None)
    except Exception as exc:
        log.error(f"  Erro ao baixar histórico de preços: {exc}")
        return

    # Monta registros
    registros = []
    for ticker in pendentes:
        if ticker not in close.columns:
            continue
        shares = shares_map.get(ticker)
        for dt, preco_val in close[ticker].dropna().items():
            preco_f = float(preco_val)
            mktcap  = round(preco_f * shares, 2) if shares else None
            registros.append({
                "ticker":         ticker,
                "data":           dt.date().isoformat(),
                "preco":          round(preco_f, 4),
                "market_cap_usd": mktcap,
            })

    log.info(f"  {len(registros)} registros a salvar no Supabase...")
    _salvar_historico_supabase(registros)


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
        puxar_e_salvar_historico(df["ticker"].tolist())

        log.info("=" * 55)
        log.info("  COLETA CONCLUIDA COM SUCESSO")
        log.info("=" * 55)

    except Exception as exc:
        log.exception(f"Coleta falhou: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
