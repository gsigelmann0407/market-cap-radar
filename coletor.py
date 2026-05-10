# ============================================================
#  MARKET CAP RADAR — Coletor Bloomberg
#  Roda diariamente via Task Scheduler na máquina Bloomberg
# ============================================================

import sys
import logging
from datetime import date, datetime
import pandas as pd
from xbbg import blp
from supabase import create_client
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    BLOOMBERG_UNIVERSO, BLOOMBERG_TOP_N, JANELAS_DIAS
)

# --- Log ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("coleta.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# --- Bloomberg ---------------------------------------------

def buscar_empresas_bloomberg() -> pd.DataFrame:
    """
    Puxa as top N empresas por market cap via BQL.
    Retorna DataFrame com uma linha por empresa.
    """
    log.info(f"Buscando top {BLOOMBERG_TOP_N} empresas no Bloomberg...")

    query_universo  = f"top(members('{BLOOMBERG_UNIVERSO}'), by(CUR_MKT_CAP), {BLOOMBERG_TOP_N})"
    query_campos    = [
        "NAME()",
        "CUR_MKT_CAP()",           # Market cap atual em USD
        "GICS_SECTOR_NAME()",      # Setor
        "CNTRY_OF_RISK()",         # País de risco
        "PX_LAST()",               # Último preço
        "CHG_PCT_1D()",            # Variação % no dia
    ]

    try:
        df = blp.bql(query_universo, query_campos)
    except Exception as e:
        log.error(f"Erro ao conectar no Bloomberg: {e}")
        log.error("Certifique-se de que o Bloomberg Terminal está aberto e logado.")
        raise

    # Renomear colunas para nomes amigáveis
    df = df.rename(columns={
        "NAME()":              "nome",
        "CUR_MKT_CAP()":      "market_cap_usd",
        "GICS_SECTOR_NAME()": "setor",
        "CNTRY_OF_RISK()":    "pais",
        "PX_LAST()":          "preco",
        "CHG_PCT_1D()":       "variacao_dia_pct",
    })

    # Ticker limpo (sem " Equity" no final)
    df["ticker"] = df.index.str.replace(" Equity", "", regex=False).str.strip()

    # Ranking por market cap (1 = maior)
    df = df.sort_values("market_cap_usd", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    # Data da coleta
    df["data"] = date.today().isoformat()

    log.info(f"  {len(df)} empresas coletadas com sucesso.")
    return df


# --- Supabase ----------------------------------------------

def salvar_no_banco(df: pd.DataFrame):
    """
    Salva o snapshot diário no Supabase.
    Ignora duplicatas (mesma empresa + mesma data).
    """
    log.info("Conectando ao Supabase...")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    registros = df[[
        "data", "ticker", "nome", "rank",
        "market_cap_usd", "preco", "variacao_dia_pct",
        "setor", "pais"
    ]].to_dict(orient="records")

    # Upsert: atualiza se já existir (ticker + data), insere se não existir
    sb.table("snapshots").upsert(
        registros,
        on_conflict="ticker,data"
    ).execute()

    log.info(f"  {len(registros)} registros salvos no banco.")


# --- Main --------------------------------------------------

def main():
    log.info("=" * 55)
    log.info(f"  COLETA INICIADA — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info("=" * 55)

    try:
        df = buscar_empresas_bloomberg()
        salvar_no_banco(df)
        log.info("Coleta concluída com sucesso. ✓")
    except Exception as e:
        log.error(f"Coleta falhou: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
