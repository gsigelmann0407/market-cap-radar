# ============================================================
#  MARKET CAP RADAR — Dashboard
#  streamlit run dashboard.py
# ============================================================

import os
from pathlib import Path

# SSL corporativo — deve estar definido antes do import yfinance
_pem = Path(__file__).parent / "empresa.pem"
_pem_str = str(_pem) if _pem.exists() else ""
os.environ.setdefault("CURL_CA_BUNDLE", _pem_str)
os.environ.setdefault("REQUESTS_CA_BUNDLE", _pem_str)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests, urllib3
urllib3.disable_warnings()

try:
    import yfinance as yf
    _yf_ok = True
except ImportError:
    _yf_ok = False

from config import SUPABASE_URL, SUPABASE_KEY, JANELAS_DIAS

st.set_page_config(page_title="Market Cap Radar", layout="wide")

dark_mode = True  # dashboard sempre em dark mode


# ── CSS (sempre dark mode) ────────────────────────────────────
_CSS = """
html, body, [class*="css"] {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.block-container { padding-top: 0.6rem !important; padding-bottom: 2rem !important; }

/* ─ DARK MODE ─────────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background-color: #0d1117 !important; }
[data-testid="stMarkdown"] { background-color: transparent !important; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child {
    background-color: #161b22 !important;
    border-right: 1px solid #30363d !important;
}

/* Texto padrão — branco */
[data-testid="stMarkdown"] p,
[data-testid="stCaptionContainer"] p,
[data-testid="stSelectbox"] label,
[data-testid="stWidgetLabel"] p,
[data-testid="stText"] p { color: #e6edf3 !important; }

/* Selectbox — fundo e texto (incluindo valor selecionado) */
[data-baseweb="select"] > div {
    background-color: #1c2128 !important;
    border-color: #30363d !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] div,
[data-baseweb="select"] input,
[data-testid="stSelectbox"] * { color: #e6edf3 !important; }
[data-baseweb="popover"],
[data-baseweb="menu"] { background-color: #1c2128 !important; }
[data-baseweb="menu"] li { color: #e6edf3 !important; }
[data-baseweb="menu"] li:hover { background-color: #21262d !important; }

/* Search bar — dark mode */
[data-testid="stTextInput"] > div {
    background-color: #1c2128 !important;
    border-color: #30363d !important;
}
[data-testid="stTextInput"] input {
    background-color: #1c2128 !important;
    color: #e6edf3 !important;
    caret-color: #e6edf3 !important;
}
[data-testid="stTextInput"] input::placeholder { color: #8b949e !important; }

/* Botão */
[data-testid="stButton"] > button {
    background-color: #21262d !important;
    border: 1px solid #30363d !important;
    color: #e6edf3 !important;
}
[data-testid="stButton"] > button:hover { background-color: #30363d !important; }

/* Divisor */
hr { border-color: #30363d !important; }

/* ─ Cabeçalho ─────────────────────────────────────────────── */
.mcr-hdr {
    display: flex; justify-content: space-between;
    align-items: flex-end; border-bottom: 2px solid #30363d;
    padding-bottom: 10px; margin-bottom: 1rem;
}
.mcr-title {
    font-size: 1.6rem; font-weight: 800; letter-spacing: .12em;
    text-transform: uppercase; color: #e6edf3; margin: 0; line-height: 1.1;
}
.mcr-sub  { font-size: .70rem; color: #8b949e; letter-spacing: .07em; text-transform: uppercase; margin: 6px 0 0; }
.mcr-info { font-size: .7rem; color: #8b949e; text-align: right; line-height: 1.7; }

/* ─ KPI cards ──────────────────────────────────────────────── */
.kpi-strip {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 1px; background: #21262d; border: 1px solid #21262d;
    border-radius: 3px; margin-bottom: 1.1rem; overflow: hidden;
}
.kpi   { background: #1c2128; padding: 13px 20px; }
.kpi-l { font-size: .6rem; letter-spacing: .12em; text-transform: uppercase; color: #8b949e; margin-bottom: 4px; }
.kpi-v { font-size: 1.65rem; font-weight: 600; color: #e6edf3; line-height: 1; }
.kpi-d { font-size: .71rem; color: #8b949e; margin-top: 4px; }
.kup   { color: #3fb950 !important; }
.kdown { color: #f85149 !important; }

/* ─ Títulos de seção ────────────────────────────────────────── */
.sec {
    font-size: 1rem; letter-spacing: .08em; text-transform: uppercase;
    color: #e6edf3; font-weight: 700; padding: 7px 0 7px 12px;
    border-left: 3px solid #00e676; margin-bottom: 10px;
}
.sec-sub {
    font-size: .82rem; letter-spacing: .07em; text-transform: uppercase;
    color: #8b949e; font-weight: 600; padding: 5px 0 5px 10px;
    border-left: 2px solid #30363d; margin-bottom: 6px;
}

/* ─ Tabela de movimentações ─────────────────────────────────── */
.mov-tbl { width: 100%; border-collapse: collapse; font-size: .8rem; background-color: transparent; }
.mov-tbl th {
    font-size: .58rem; letter-spacing: .1em; text-transform: uppercase;
    color: #8b949e; font-weight: 600; text-align: left;
    padding: 5px 8px; border-bottom: 1px solid #21262d;
    background-color: transparent;
}
.mov-tbl td { padding: 5px 8px; border-bottom: 1px solid #21262d; color: #e6edf3; background-color: transparent; }
.mov-tbl tr:last-child td { border-bottom: none; }
.badge-in  { color: #3fb950; font-weight: 700; font-size: .68rem; }
.badge-out { color: #f85149; font-weight: 700; font-size: .68rem; }

#MainMenu, footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
"""

st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ── Funções de dados ──────────────────────────────────────────

@st.cache_data(ttl=300)
def carregar_dados() -> pd.DataFrame:
    url = f"{SUPABASE_URL}/rest/v1/snapshots?select=*&order=data.desc&limit=50000"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, verify=False, timeout=15)
    resp.raise_for_status()
    dados = resp.json()
    if not dados:
        return pd.DataFrame()
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"])
    df["market_cap_bi"] = pd.to_numeric(df["market_cap_usd"], errors="coerce") / 1e9
    return df


@st.cache_data(ttl=300)
def carregar_historico_empresa(ticker: str) -> pd.DataFrame:
    """Carrega histórico de market cap da tabela historico_mercado no Supabase."""
    url = (
        f"{SUPABASE_URL}/rest/v1/historico_mercado"
        f"?select=data,preco,market_cap_usd&ticker=eq.{ticker}"
        f"&order=data.asc&limit=5000"
    )
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        if not resp.ok:
            return pd.DataFrame()
        dados = resp.json()
        if not dados:
            return pd.DataFrame()
        df_h = pd.DataFrame(dados)
        df_h["data"] = pd.to_datetime(df_h["data"])
        df_h["market_cap_bi"] = pd.to_numeric(df_h["market_cap_usd"], errors="coerce") / 1e9
        return df_h.sort_values("data").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _debug_api() -> dict:
    url = f"{SUPABASE_URL}/rest/v1/snapshots?select=id,data,ticker&limit=5"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=10)
        return {"status": resp.status_code, "registros": resp.json()}
    except Exception as exc:
        return {"status": "erro", "registros": [], "detalhe": str(exc)}


def calcular_rank_velocity(df: pd.DataFrame, janela: int) -> pd.DataFrame:
    hoje  = df[df["data"] == df["data"].max()].copy()
    antes = df[df["data"] <= df["data"].max() - pd.Timedelta(days=janela)]
    if antes.empty:
        hoje["delta_rank"]     = pd.NA
        hoje["var_mktcap_pct"] = pd.NA
        return hoje
    data_ref = antes["data"].max()
    ref = (
        antes[antes["data"] == data_ref][["ticker", "rank", "market_cap_bi"]]
        .rename(columns={"rank": "rank_antes", "market_cap_bi": "mktcap_antes"})
    )
    merged = hoje.merge(ref, on="ticker", how="left")
    merged["delta_rank"] = (merged["rank_antes"] - merged["rank"]).astype("Int64")
    merged["var_mktcap_pct"] = (
        (merged["market_cap_bi"] - merged["mktcap_antes"])
        / merged["mktcap_antes"] * 100
    )
    return merged


def calcular_movimentacoes(
    df: pd.DataFrame, janela: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    hoje_data  = df["data"].max()
    candidatos = df[df["data"] <= hoje_data - pd.Timedelta(days=janela)]
    if candidatos.empty:
        return pd.DataFrame(), pd.DataFrame()
    data_ref   = candidatos["data"].max()
    hoje_snap  = df[df["data"] == hoje_data]
    antes_snap = df[df["data"] == data_ref]

    if hoje_snap.empty or antes_snap.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Normaliza ambos os snapshots para o mesmo N (o menor entre os dois).
    # Garante simetria: |entradas| == |saídas| sempre, porque |A|=|B|=N implica
    # |A - B| = N - |A∩B| = |B - A|.
    n = min(len(hoje_snap), len(antes_snap))
    hoje_top  = hoje_snap.nsmallest(n, "rank")
    antes_top = antes_snap.nsmallest(n, "rank")

    hoje_tickers  = set(hoje_top["ticker"])
    antes_tickers = set(antes_top["ticker"])
    cols = ["rank", "nome", "ticker", "market_cap_bi", "setor", "pais"]

    entradas = (
        hoje_top[hoje_top["ticker"].isin(hoje_tickers - antes_tickers)][cols]
        .sort_values("rank").reset_index(drop=True)
    )
    saidas = (
        antes_top[antes_top["ticker"].isin(antes_tickers - hoje_tickers)][cols]
        .sort_values("rank").reset_index(drop=True)
    )
    return entradas, saidas


def fmt_delta(v, salto: int = 20) -> str:
    if pd.isna(v): return "n/d"
    v = int(v)
    if v == 0:       return "—"
    if v >= salto:   return f"▲▲ +{v}"
    if v > 0:        return f"▲ +{v}"
    if v <= -salto:  return f"▼▼ {v}"
    return f"▼ {v}"


def fmt_pct(v) -> str:
    if pd.isna(v): return "—"
    return f"{float(v):+.2f}%"


def _destaques_html(df_sub: pd.DataFrame, tipo: str, salto: int) -> str:
    if df_sub.empty:
        return (
            '<p style="font-size:.78rem;color:#94a3b8;padding:8px 0 4px;">'
            f"Nenhuma empresa com variação ≥ {salto} posições."
            "</p>"
        )
    cls        = "badge-in" if tipo == "up" else "badge-out"
    mkt_color  = "#3fb950" if tipo == "up" else "#f85149"
    rows = ""
    for _, r in df_sub.iterrows():
        nome       = str(r.get("nome",   "—") or "—")[:28]
        ticker     = str(r.get("ticker", "—") or "—")
        rank       = int(r["rank"]) if pd.notna(r.get("rank")) else "—"
        delta      = int(r["delta_rank"])
        dstr       = f"▲ +{delta}" if delta > 0 else f"▼ {delta}"
        mkt_dep    = r.get("market_cap_bi")
        mkt_ant    = r.get("mktcap_antes")
        if pd.notna(mkt_dep) and pd.notna(mkt_ant) and mkt_ant:
            diff     = mkt_dep - mkt_ant
            pct      = diff / mkt_ant * 100
            sign     = "+" if diff >= 0 else ""
            mkt_cell = (
                f'<span style="color:#8b949e">${mkt_ant:,.0f}bi</span>'
                f' → <strong>${mkt_dep:,.0f}bi</strong><br>'
                f'<span style="color:{mkt_color};font-size:.68rem">'
                f"{sign}${diff:,.0f}bi&nbsp;({sign}{pct:.1f}%)</span>"
            )
        elif pd.notna(mkt_dep):
            mkt_cell = f"<strong>${mkt_dep:,.0f}bi</strong>"
        else:
            mkt_cell = "—"
        rows += (
            f"<tr>"
            f'<td style="color:#8b949e;font-size:.72rem">{rank}</td>'
            f"<td><strong>{nome}</strong><br>"
            f'<span style="color:#64748b;font-size:.68rem">{ticker}</span></td>'
            f"<td>{mkt_cell}</td>"
            f'<td><span class="{cls}">{dstr}</span></td>'
            f"</tr>"
        )
    return (
        '<table class="mov-tbl"><thead><tr>'
        "<th>Pos.</th><th>Empresa</th><th>Mkt Cap (antes → depois)</th><th>Δ Rank</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _mov_html(df_mov: pd.DataFrame, tipo: str) -> str:
    if df_mov.empty:
        return (
            '<p style="font-size:.78rem;color:#94a3b8;padding:8px 0 4px;">'
            "Nenhuma movimentação no período."
            "</p>"
        )
    badge_cls = "badge-in" if tipo == "entrada" else "badge-out"
    badge_txt = "ENTROU" if tipo == "entrada" else "SAIU"
    rows = ""
    for _, r in df_mov.iterrows():
        nome   = str(r.get("nome",   "—") or "—")[:34]
        ticker = str(r.get("ticker", "—") or "—")
        mkt    = f"{r['market_cap_bi']:,.1f}" if pd.notna(r.get("market_cap_bi")) else "—"
        setor  = str(r.get("setor",  "—") or "—")[:22]
        rows += (
            f"<tr>"
            f'<td><span class="{badge_cls}">{badge_txt}</span></td>'
            f"<td><strong>{nome}</strong></td>"
            f'<td style="color:#64748b">{ticker}</td>'
            f'<td style="color:#475569">{mkt}</td>'
            f'<td style="color:#94a3b8">{setor}</td>'
            f"</tr>"
        )
    return (
        '<table class="mov-tbl"><thead><tr>'
        "<th></th><th>Empresa</th><th>Ticker</th>"
        "<th>Mkt Cap (US$ bi)</th><th>Setor</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


# ── Sidebar – configurações ───────────────────────────────────
with st.sidebar:
    with st.expander("Configuracoes", expanded=False):
        if st.button("Atualizar dados", use_container_width=True):
            carregar_dados.clear()
            st.rerun()
        st.caption("Cache renovado automaticamente a cada 5 min.")


# ── Carregar dados ─────────────────────────────────────────────
try:
    df = carregar_dados()
except Exception as exc:
    st.error(f"Erro ao conectar ao Supabase: {exc}")
    st.stop()

if df.empty:
    st.warning("Nenhum dado encontrado. Execute o coletor primeiro.")
    with st.expander("Diagnostico da conexao"):
        debug = _debug_api()
        st.write(f"**Status HTTP:** `{debug['status']}`")
        if debug["registros"]:
            st.success(
                f"API retornou {len(debug['registros'])} registro(s). "
                "Clique em 'Atualizar dados' no menu lateral."
            )
            st.json(debug["registros"])
        else:
            st.error("Tabela `snapshots` vazia ou sem permissao de leitura (RLS).")
            if "detalhe" in debug:
                st.code(debug["detalhe"])
    st.stop()


# ── Dados base ─────────────────────────────────────────────────
hoje_df    = df[df["data"] == df["data"].max()]
ultima     = df["data"].max().strftime("%d/%m/%Y")
n_universo = len(hoje_df)


# ── 1. Header estático ─────────────────────────────────────────
st.markdown(f"""
<div class="mcr-hdr">
  <div>
    <div class="mcr-title">Market Cap Radar</div>
    <div class="mcr-sub">Empresas globais com market cap acima de US$&nbsp;50 bilhões</div>
  </div>
  <div class="mcr-info">
    Atualizado em {ultima}<br>
    {n_universo:,} empresas monitoradas
  </div>
</div>
""", unsafe_allow_html=True)


# ── 2. Filtros ─────────────────────────────────────────────────
fc1, fc2, fc3, fc4, fc5 = st.columns([1, 1.5, 1.5, 1, 1])
with fc1:
    janela = st.selectbox(
        "Período",
        options=JANELAS_DIAS,
        format_func=lambda x: f"{x} dia" if x == 1 else f"{x} dias",
    )
with fc2:
    setores   = ["Todos os setores"] + sorted(hoje_df["setor"].dropna().unique().tolist())
    setor_sel = st.selectbox("Setor", setores)
with fc3:
    paises   = ["Todos os países"] + sorted(hoje_df["pais"].dropna().unique().tolist())
    pais_sel = st.selectbox("País", paises)
with fc4:
    top_n = st.selectbox(
        "Exibir",
        options=[50, 100, 250, 500],
        format_func=lambda x: "Todas" if x == 500 else f"Top {x}",
        index=0,
    )
with fc5:
    salto_min = st.selectbox(
        "Salto mínimo",
        options=[5, 10, 20, 30, 50],
        index=2,
        format_func=lambda x: f"≥ {x} pos.",
    )


# ── 3. Rank velocity + filtros ─────────────────────────────────
df_vel = calcular_rank_velocity(df, janela)

if setor_sel != "Todos os setores":
    df_vel = df_vel[df_vel["setor"] == setor_sel]
if pais_sel != "Todos os países":
    df_vel = df_vel[df_vel["pais"] == pais_sel]

df_vel = df_vel.sort_values("rank").head(top_n)


# ── 4. KPIs ────────────────────────────────────────────────────
n_total  = len(df_vel)
dr_serie = df_vel["delta_rank"]
n_up     = int(dr_serie.ge(salto_min).sum())
n_down   = int(dr_serie.le(-salto_min).sum())
n_nd     = int(df_vel["delta_rank"].isna().sum())
pct_up   = f"{n_up   / n_total * 100:.0f}%" if n_total else "—"
pct_down = f"{n_down / n_total * 100:.0f}%" if n_total else "—"
nd_info  = f"{n_nd} ag. histórico" if n_nd else f"{n_universo} monitoradas"

st.markdown(f"""
<div class="kpi-strip">
  <div class="kpi">
    <div class="kpi-l">Subiram ≥ {salto_min} posições</div>
    <div class="kpi-v kup">{n_up:,}</div>
    <div class="kpi-d">{pct_up} do filtro</div>
  </div>
  <div class="kpi">
    <div class="kpi-l">Caíram ≥ {salto_min} posições</div>
    <div class="kpi-v kdown">{n_down:,}</div>
    <div class="kpi-d">{pct_down} do filtro</div>
  </div>
  <div class="kpi">
    <div class="kpi-l">Empresas no filtro</div>
    <div class="kpi-v">{n_total:,}</div>
    <div class="kpi-d">{nd_info}</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── 4b. Destaques do período ───────────────────────────────────
st.markdown(
    '<div class="sec" style="margin-top:0.4rem;">Destaques do período</div>',
    unsafe_allow_html=True,
)

dest_up   = df_vel[df_vel["delta_rank"] >= salto_min].sort_values("delta_rank", ascending=False).head(10)
dest_down = df_vel[df_vel["delta_rank"] <= -salto_min].sort_values("delta_rank").head(10)

dc1, dc2 = st.columns(2)
with dc1:
    st.markdown(
        f'<div class="sec-sub">Maiores subidas'
        f'&nbsp;<span style="color:#16a34a;font-weight:700">+{len(dest_up)}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_destaques_html(dest_up, "up", salto_min), unsafe_allow_html=True)
with dc2:
    st.markdown(
        f'<div class="sec-sub">Maiores quedas'
        f'&nbsp;<span style="color:#dc2626;font-weight:700">-{len(dest_down)}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_destaques_html(dest_down, "down", salto_min), unsafe_allow_html=True)


# ── 5. Tabela principal ────────────────────────────────────────
col_delta = f"Δ Ranking ({janela}d)"

for _col in ["preco", "setor", "pais"]:
    if _col not in df_vel.columns:
        df_vel = df_vel.copy()
        df_vel[_col] = None

raw = df_vel[[
    "rank", "nome", "ticker", "setor", "pais",
    "market_cap_bi", "preco", "variacao_dia_pct", "delta_rank",
]].copy().reset_index(drop=True)

_delta_vals = raw["delta_rank"].to_list()

raw[col_delta]          = raw["delta_rank"].apply(lambda v: fmt_delta(v, salto_min))
raw["Var. dia"]         = raw["variacao_dia_pct"].apply(fmt_pct)
raw["Mkt Cap (US$ bi)"] = raw["market_cap_bi"].apply(
    lambda v: f"{v:,.1f}" if pd.notna(v) else "—"
)
raw["Preco (USD)"] = raw["preco"].apply(
    lambda v: f"${float(v):,.2f}" if pd.notna(v) else "—"
)

tabela = raw[[
    "rank", "nome", "ticker", "setor", "pais",
    "Mkt Cap (US$ bi)", "Preco (USD)", "Var. dia", col_delta,
]].rename(columns={
    "rank":   "Pos.",
    "nome":   "Empresa",
    "ticker": "Ticker",
    "setor":  "Setor",
    "pais":   "Pais",
})

st.markdown(
    f'<div class="sec">Rank movers — ultimos {janela} {"dia" if janela == 1 else "dias"}'
    f"&nbsp;&nbsp;|&nbsp;&nbsp;"
    f'<span style="color:#14532d;font-weight:700">▲▲ / </span>'
    f'<span style="color:#991b1b;font-weight:700">▼▼</span>'
    f"&nbsp;saltos >= {salto_min} posicoes</div>",
    unsafe_allow_html=True,
)

busca = st.text_input(
    "Buscar",
    placeholder="Filtrar por nome ou ticker...",
    label_visibility="collapsed",
)

if busca.strip():
    _q    = busca.strip().lower()
    _mask = (
        tabela["Empresa"].str.lower().str.contains(_q, na=False)
        | tabela["Ticker"].str.lower().str.contains(_q, na=False)
    )
    _rows      = tabela.index[_mask].tolist()
    tabela_exib = tabela.loc[_mask].reset_index(drop=True)
    _dv        = [_delta_vals[i] for i in _rows]
else:
    tabela_exib = tabela
    _dv        = _delta_vals


def _row_style(row):
    i = row.name
    try:
        dr = _dv[i]
        if pd.isna(dr):
            return [""] * len(row)
        dr = int(dr)
    except (IndexError, TypeError, ValueError):
        return [""] * len(row)

    if dr >= salto_min:
        return ["background-color: #14532d; color: #86efac; font-weight: 700"] * len(row)
    if dr <= -salto_min:
        return ["background-color: #7f1d1d; color: #fca5a5; font-weight: 700"] * len(row)

    styles = [""] * len(row)
    col_list = list(row.index)
    if col_delta in col_list:
        idx = col_list.index(col_delta)
        styles[idx] = (
            "color: #16a34a; font-weight: 600" if dr > 0
            else "color: #dc2626; font-weight: 600"
        )
    return styles


styled = tabela_exib.style.apply(_row_style, axis=1).hide(axis="index")
st.dataframe(styled, use_container_width=True, height=560, hide_index=True)


# ── 6. Movimentações do período ────────────────────────────────
st.markdown(
    f'<div class="sec" style="margin-top:1.5rem;">'
    f'Movimentacoes do periodo — {janela} {"dia" if janela == 1 else "dias"}</div>',
    unsafe_allow_html=True,
)

entradas, saidas = calcular_movimentacoes(df, janela)

mc1, mc2 = st.columns(2)

with mc1:
    n_ent = len(entradas)
    label_ent = f"+{n_ent}" if n_ent else "0"
    st.markdown(
        f'<div class="sec-sub">Entradas no ranking'
        f'&nbsp;<span style="color:#16a34a;font-weight:700">{label_ent}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_mov_html(entradas, "entrada"), unsafe_allow_html=True)

with mc2:
    n_sai = len(saidas)
    label_sai = f"-{n_sai}" if n_sai else "0"
    st.markdown(
        f'<div class="sec-sub">Saídas do ranking'
        f'&nbsp;<span style="color:#dc2626;font-weight:700">{label_sai}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_mov_html(saidas, "saida"), unsafe_allow_html=True)


# ── 7. Evolução de empresa ─────────────────────────────────────
st.markdown(
    '<div class="sec" style="margin-top:1.5rem;">Evolução por empresa — Market Cap</div>',
    unsafe_allow_html=True,
)

empresas_lista = sorted(hoje_df["nome"].dropna().unique().tolist())
if not empresas_lista:
    st.info("Nenhuma empresa disponivel para analise de evolucao.")
else:
    empresas_sel = st.multiselect(
        "Empresas",
        options=empresas_lista,
        default=empresas_lista[:1],
        label_visibility="collapsed",
        placeholder="Selecione uma ou mais empresas para comparar...",
    )

    if not empresas_sel:
        st.info("Selecione ao menos uma empresa para visualizar o grafico.")
    else:
        # ── Paleta dark ─────────────────────────────────────────
        _bg_plot    = "#1c2128"
        _text_plot  = "#8b949e"
        _grid_plot  = "#21262d"
        _line_plot  = "#30363d"
        _title_plot = "#e6edf3"

        _CORES = ["#58a6ff", "#3fb950", "#f85149", "#d2a8ff", "#ffa657", "#79c0ff", "#7ee787"]
        _FILLS = [
            "rgba(88,166,255,0.08)", "rgba(63,185,80,0.08)", "rgba(248,81,73,0.08)",
            "rgba(210,168,255,0.08)", "rgba(255,166,87,0.08)", "rgba(121,192,255,0.08)",
            "rgba(126,231,135,0.08)",
        ]

        _layout_base = dict(
            plot_bgcolor=_bg_plot,
            paper_bgcolor=_bg_plot,
            margin=dict(l=0, r=0, t=40, b=0),
            height=360,
            xaxis=dict(
                showgrid=False,
                linecolor=_line_plot,
                color=_text_plot,
                tickfont=dict(size=10),
                type="date",
                title=None,
                nticks=7,
                tickformatstops=[
                    dict(dtickrange=[None, 86400000 * 3],  value="%d/%m/%Y"),
                    dict(dtickrange=[86400000 * 3, "M1"],  value="%d/%m/%Y"),
                    dict(dtickrange=["M1", "M12"],         value="%b %Y"),
                    dict(dtickrange=["M12", None],         value="%Y"),
                ],
            ),
            yaxis=dict(
                gridcolor=_grid_plot,
                linecolor=_line_plot,
                color=_text_plot,
                tickfont=dict(size=10),
            ),
            font=dict(family="Inter, Segoe UI, system-ui, sans-serif", color=_text_plot),
            hoverlabel=dict(bgcolor=_bg_plot, font_color=_title_plot),
        )
        _legend_cfg = dict(
            font=dict(size=10, color=_text_plot),
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            yanchor="bottom", y=1.02, xanchor="left", x=0,
        )

        # ── Botão yfinance (só com 1 empresa selecionada) ────────
        if len(empresas_sel) == 1 and _yf_ok:
            _emp1  = empresas_sel[0]
            _match = hoje_df[hoje_df["nome"] == _emp1]["ticker"]
            if not _match.empty:
                _tick1    = _match.values[0]
                _hist_key = f"hist_full_{_tick1}"
                btn_col, status_col = st.columns([3, 4])
                with btn_col:
                    if st.button(
                        "Carregar histórico completo (desde 2000)",
                        key=f"btn_hist_{_tick1}",
                        use_container_width=True,
                    ):
                        with st.spinner(f"Buscando histórico de {_emp1} via yfinance..."):
                            try:
                                tk_yf   = yf.Ticker(_tick1)
                                info_yf = tk_yf.info
                                shares  = (
                                    info_yf.get("sharesOutstanding")
                                    or info_yf.get("impliedSharesOutstanding")
                                )
                                hist_raw = tk_yf.history(period="max", auto_adjust=True)
                                if not hist_raw.empty:
                                    if hist_raw.index.tz is not None:
                                        hist_raw.index = hist_raw.index.tz_convert(None)
                                    df_yf = hist_raw[["Close"]].rename(columns={"Close": "preco"})
                                    if shares:
                                        df_yf["market_cap_bi"] = df_yf["preco"] * float(shares) / 1e9
                                    else:
                                        df_yf["market_cap_bi"] = None
                                    df_yf.index.name = "data"
                                    st.session_state[_hist_key] = df_yf
                                else:
                                    st.warning("yfinance nao retornou dados historicos.")
                            except Exception as exc:
                                st.error(f"Erro ao buscar historico: {exc}")
                with status_col:
                    _df_yf_c = st.session_state.get(_hist_key)
                    if _df_yf_c is not None and not _df_yf_c.empty:
                        anos = max(1, (_df_yf_c.index[-1] - _df_yf_c.index[0]).days // 365)
                        st.caption(
                            f"yfinance: {_df_yf_c.index[0].strftime('%Y')} - "
                            f"{_df_yf_c.index[-1].strftime('%Y')} "
                            f"({anos} anos, {len(_df_yf_c):,} pontos)"
                        )

        # ── Gráfico de Market Cap (multi-empresa) ─────────────
        fig_cap = go.Figure()
        fontes: list[str] = []
        solo = len(empresas_sel) == 1

        for i, empresa in enumerate(empresas_sel):
            cor  = _CORES[i % len(_CORES)]
            fill = _FILLS[i % len(_FILLS)]

            match = hoje_df[hoje_df["nome"] == empresa]["ticker"]
            if match.empty:
                continue
            ticker = match.values[0]
            df_emp = df[df["ticker"] == ticker].sort_values("data")

            df_hist_stored = carregar_historico_empresa(ticker)
            if not df_hist_stored.empty and not df_emp.empty:
                snap_min = df_emp["data"].min()
                df_pre   = df_hist_stored[df_hist_stored["data"] < snap_min][["data", "market_cap_bi"]]
                df_cap   = (
                    pd.concat([df_pre, df_emp[["data", "market_cap_bi"]]])
                    .sort_values("data").reset_index(drop=True)
                )
                fonte = "historico + coleta"
            elif not df_hist_stored.empty:
                df_cap = df_hist_stored[["data", "market_cap_bi"]].copy()
                fonte  = "historico 2 anos"
            else:
                df_cap = df_emp[["data", "market_cap_bi"]].copy()
                fonte  = "snapshots"

            x_cap: object = df_cap["data"]
            y_cap: object = df_cap["market_cap_bi"]

            if solo:
                _df_yf_c = st.session_state.get(f"hist_full_{ticker}")
                if _df_yf_c is not None and not _df_yf_c.empty:
                    x_cap = _df_yf_c.index
                    y_cap = _df_yf_c["market_cap_bi"]
                    fonte = f"yfinance desde {_df_yf_c.index[0].strftime('%Y')}"

            fontes.append(fonte if solo else f"{empresa}: {fonte}")

            fig_cap.add_trace(go.Scatter(
                x=x_cap,
                y=y_cap,
                mode="lines",
                name=empresa,
                line=dict(color=cor, width=2),
                fill="tozeroy" if solo else "none",
                fillcolor=fill if solo else None,
                hovertemplate=(
                    f"<b>{empresa}</b><br>"
                    "%{x|%d/%m/%Y}<br>US$ %{y:,.1f} bi<extra></extra>"
                ),
            ))

        titulo = f"Market Cap — {empresas_sel[0]}" if solo else "Market Cap comparativo"
        fig_cap.update_layout(**_layout_base)
        fig_cap.update_layout(
            title=dict(text=titulo, font=dict(size=11, color=_title_plot)),
            showlegend=not solo,
            **({} if solo else {"legend": _legend_cfg}),
        )
        fig_cap.update_yaxes(title_text="US$ bi", title_font=dict(size=9, color=_text_plot))
        st.plotly_chart(fig_cap, use_container_width=True)

        st.markdown(
            f'<p style="font-size:.62rem;color:#8b949e;margin-top:-12px;">'
            f"Fonte: {' &nbsp;|&nbsp; '.join(fontes)}</p>",
            unsafe_allow_html=True,
        )


# ── Rodapé ────────────────────────────────────────────────────
_ft_border = "#30363d"
_ft_color  = "#8b949e"
st.markdown(
    f'<div style="text-align:center;font-size:.65rem;color:{_ft_color};'
    f'margin-top:2.5rem;padding-top:.75rem;border-top:1px solid {_ft_border};">'
    "Universo: empresas globais com market cap &gt; US$ 50 bilhões"
    "</div>",
    unsafe_allow_html=True,
)
