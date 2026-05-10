# ============================================================
#  MARKET CAP RADAR — Dashboard
#  streamlit run dashboard.py
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, JANELAS_DIAS

# --- Configuração da página --------------------------------
st.set_page_config(
    page_title="Market Cap Radar",
    page_icon="📡",
    layout="wide",
)

# --- CSS customizado ---------------------------------------
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 16px 20px;
        border-left: 4px solid;
    }
    .subida  { border-color: #22c55e; }
    .descida { border-color: #ef4444; }
    .neutro  { border-color: #64748b; }
    .rank-up   { color: #22c55e; font-weight: 600; }
    .rank-down { color: #ef4444; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# --- Dados -------------------------------------------------

@st.cache_data(ttl=3600)
def carregar_dados() -> pd.DataFrame:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    resp = sb.table("snapshots").select("*").execute()
    df = pd.DataFrame(resp.data)
    df["data"] = pd.to_datetime(df["data"])
    df["market_cap_bi"] = df["market_cap_usd"] / 1e9
    return df


def calcular_rank_velocity(df: pd.DataFrame, janela: int) -> pd.DataFrame:
    """
    Compara o ranking de hoje com o de N dias atrás.
    Delta positivo = subiu no ranking (bom sinal).
    """
    hoje   = df[df["data"] == df["data"].max()].copy()
    antes  = df[df["data"] <= df["data"].max() - pd.Timedelta(days=janela)]

    if antes.empty:
        hoje["delta_rank"]        = None
        hoje["market_cap_antes"]  = None
        return hoje

    # Pega o snapshot mais próximo da janela solicitada
    data_antes = antes["data"].max()
    antes      = antes[antes["data"] == data_antes][["ticker", "rank", "market_cap_bi"]].rename(
        columns={"rank": "rank_antes", "market_cap_bi": "market_cap_antes_bi"}
    )

    merged = hoje.merge(antes, on="ticker", how="left")
    merged["delta_rank"]       = merged["rank_antes"] - merged["rank"]   # positivo = subiu
    merged["delta_market_cap"] = merged["market_cap_bi"] - merged["market_cap_antes_bi"]
    return merged


# --- App ---------------------------------------------------

try:
    df = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if df.empty:
    st.warning("Nenhum dado encontrado. Execute o coletor primeiro.")
    st.stop()

ultima_atualizacao = df["data"].max().strftime("%d/%m/%Y")
hoje_df = df[df["data"] == df["data"].max()]


# --- Header ------------------------------------------------
col_title, col_update = st.columns([4, 1])
with col_title:
    st.title("📡 Market Cap Radar")
    st.caption("Empresas globais com capitalização acima de US$ 50 bilhões")
with col_update:
    st.metric("Última atualização", ultima_atualizacao)
    st.caption(f"{len(hoje_df)} empresas monitoradas")

st.divider()


# --- Filtros -----------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    janela = st.selectbox(
        "Período de análise",
        options=JANELAS_DIAS,
        format_func=lambda x: f"{x} dias",
        index=1,
    )
with col2:
    setores = ["Todos"] + sorted(hoje_df["setor"].dropna().unique().tolist())
    setor_sel = st.selectbox("Setor", setores)

with col3:
    paises = ["Todos"] + sorted(hoje_df["pais"].dropna().unique().tolist())
    pais_sel = st.selectbox("País", paises)

with col4:
    top_n = st.selectbox("Mostrar top", [10, 20, 50], index=1)


# --- Calcular velocidade -----------------------------------
df_vel = calcular_rank_velocity(df, janela)

# Aplicar filtros
if setor_sel != "Todos":
    df_vel = df_vel[df_vel["setor"] == setor_sel]
if pais_sel != "Todos":
    df_vel = df_vel[df_vel["pais"] == pais_sel]


# --- KPIs --------------------------------------------------
st.subheader("Visão Geral")
k1, k2, k3, k4 = st.columns(4)

subiram  = df_vel[df_vel["delta_rank"] > 0] if "delta_rank" in df_vel else pd.DataFrame()
caíram   = df_vel[df_vel["delta_rank"] < 0] if "delta_rank" in df_vel else pd.DataFrame()

with k1:
    st.metric("Empresas monitoradas", len(df_vel))
with k2:
    st.metric("Subiram de ranking", len(subiram), delta=f"nos últimos {janela}d")
with k3:
    st.metric("Caíram de ranking", len(caíram))
with k4:
    maior_subida = df_vel.loc[df_vel["delta_rank"].idxmax()] if not df_vel["delta_rank"].isna().all() else None
    if maior_subida is not None:
        st.metric(
            "Maior subida",
            maior_subida["nome"],
            delta=f"+{int(maior_subida['delta_rank'])} posições"
        )

st.divider()


# --- Top Movers (subindo) ----------------------------------
col_up, col_down = st.columns(2)

with col_up:
    st.subheader(f"🚀 Maiores subidas — {janela} dias")
    top_subidas = (
        df_vel[df_vel["delta_rank"] > 0]
        .sort_values("delta_rank", ascending=False)
        .head(top_n)
    )

    if top_subidas.empty:
        st.info("Dados insuficientes para o período selecionado.")
    else:
        fig_up = px.bar(
            top_subidas,
            x="delta_rank",
            y="nome",
            orientation="h",
            color="delta_rank",
            color_continuous_scale="Greens",
            labels={"delta_rank": "Posições subidas", "nome": ""},
            hover_data={"rank": True, "market_cap_bi": ":.0f", "setor": True, "pais": True},
        )
        fig_up.update_layout(
            height=420,
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig_up, use_container_width=True)

with col_down:
    st.subheader(f"📉 Maiores quedas — {janela} dias")
    top_quedas = (
        df_vel[df_vel["delta_rank"] < 0]
        .sort_values("delta_rank", ascending=True)
        .head(top_n)
    )

    if top_quedas.empty:
        st.info("Dados insuficientes para o período selecionado.")
    else:
        top_quedas["delta_rank_abs"] = top_quedas["delta_rank"].abs()
        fig_down = px.bar(
            top_quedas,
            x="delta_rank_abs",
            y="nome",
            orientation="h",
            color="delta_rank_abs",
            color_continuous_scale="Reds",
            labels={"delta_rank_abs": "Posições perdidas", "nome": ""},
            hover_data={"rank": True, "market_cap_bi": ":.0f", "setor": True, "pais": True},
        )
        fig_down.update_layout(
            height=420,
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig_down, use_container_width=True)

st.divider()


# --- Mapa de poder setorial --------------------------------
st.subheader("🗺️ Distribuição por Setor")

setor_df = hoje_df.groupby("setor").agg(
    empresas=("ticker", "count"),
    market_cap_total=("market_cap_bi", "sum"),
).reset_index().sort_values("market_cap_total", ascending=False)

col_s1, col_s2 = st.columns(2)
with col_s1:
    fig_setor = px.treemap(
        setor_df,
        path=["setor"],
        values="market_cap_total",
        color="market_cap_total",
        color_continuous_scale="Blues",
        title="Market cap total por setor (US$ bi)",
    )
    fig_setor.update_layout(height=380)
    st.plotly_chart(fig_setor, use_container_width=True)

with col_s2:
    fig_pais = px.bar(
        hoje_df.groupby("pais")["market_cap_bi"].sum()
        .sort_values(ascending=False).head(15).reset_index(),
        x="pais", y="market_cap_bi",
        title="Top 15 países por market cap total (US$ bi)",
        labels={"pais": "País", "market_cap_bi": "Market Cap (US$ bi)"},
        color="market_cap_bi",
        color_continuous_scale="Blues",
    )
    fig_pais.update_layout(height=380, coloraxis_showscale=False)
    st.plotly_chart(fig_pais, use_container_width=True)

st.divider()


# --- Evolução de empresa específica ------------------------
st.subheader("🔍 Evolução de uma empresa")

empresas_lista = sorted(hoje_df["nome"].dropna().tolist())
empresa_sel = st.selectbox("Selecione a empresa", empresas_lista)

if empresa_sel:
    ticker_sel = hoje_df[hoje_df["nome"] == empresa_sel]["ticker"].values[0]
    df_emp = df[df["ticker"] == ticker_sel].sort_values("data")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        fig_rank = px.line(
            df_emp, x="data", y="rank",
            title=f"Evolução do ranking — {empresa_sel}",
            labels={"data": "Data", "rank": "Posição no ranking"},
            markers=True,
        )
        fig_rank.update_yaxes(autorange="reversed")  # rank 1 no topo
        fig_rank.update_layout(height=320)
        st.plotly_chart(fig_rank, use_container_width=True)

    with col_e2:
        fig_cap = px.line(
            df_emp, x="data", y="market_cap_bi",
            title=f"Evolução do market cap — {empresa_sel} (US$ bi)",
            labels={"data": "Data", "market_cap_bi": "Market Cap (US$ bi)"},
            markers=True,
        )
        fig_cap.update_layout(height=320)
        st.plotly_chart(fig_cap, use_container_width=True)

st.divider()


# --- Tabela completa ---------------------------------------
st.subheader("📋 Ranking completo")

tabela = df_vel[[
    "rank", "nome", "ticker", "market_cap_bi",
    "variacao_dia_pct", "delta_rank", "setor", "pais"
]].rename(columns={
    "rank":             "Posição",
    "nome":             "Empresa",
    "ticker":           "Ticker",
    "market_cap_bi":    "Market Cap (US$ bi)",
    "variacao_dia_pct": "Var. dia (%)",
    "delta_rank":       f"Δ Ranking ({janela}d)",
    "setor":            "Setor",
    "pais":             "País",
}).sort_values("Posição")

st.dataframe(
    tabela,
    use_container_width=True,
    height=500,
    column_config={
        "Market Cap (US$ bi)": st.column_config.NumberColumn(format="%.1f"),
        "Var. dia (%)":         st.column_config.NumberColumn(format="%.2f%%"),
        f"Δ Ranking ({janela}d)": st.column_config.NumberColumn(format="%+d"),
    },
)
