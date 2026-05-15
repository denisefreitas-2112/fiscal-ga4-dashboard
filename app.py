import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric,
    FilterExpression, Filter, StringFilter
)
from datetime import date, timedelta
import json

st.set_page_config(
    page_title="Fiscal.IO — Dashboard GA4",
    page_icon="📊",
    layout="wide",
)

# ── Estilo ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #1a56db;
        padding: 1rem 1.2rem;
        border-radius: 6px;
    }
    .stMetric label { font-size: 0.85rem; color: #6b7280; }
</style>
""", unsafe_allow_html=True)

# ── Credenciais ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GA4_REFRESH_TOKEN"],
        client_id=st.secrets["GA4_CLIENT_ID"],
        client_secret=st.secrets["GA4_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    creds.refresh(Request())
    return BetaAnalyticsDataClient(credentials=creds)

# ── Helpers ──────────────────────────────────────────────────────────────────
PROPERTY_ID = "307883096"

HOSTS = {
    "fiscal.io — Site": "fiscal.io",
    "conteudo.fiscal.io — Blog": "conteudo.fiscal.io",
}

def run_report(client, dimensions, metrics, start, end, host_filter=None):
    dim_list = [Dimension(name=d) for d in dimensions]
    met_list = [Metric(name=m) for m in metrics]
    kwargs = dict(
        property=f"properties/{PROPERTY_ID}",
        dimensions=dim_list,
        metrics=met_list,
        date_ranges=[DateRange(
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )],
        limit=50,
    )
    if host_filter:
        kwargs["dimension_filter"] = FilterExpression(
            filter=Filter(
                field_name="hostName",
                string_filter=StringFilter(value=host_filter),
            )
        )
    resp = client.run_report(RunReportRequest(**kwargs))
    dim_headers = [h.name for h in resp.dimension_headers]
    met_headers = [h.name for h in resp.metric_headers]
    rows = []
    for row in resp.rows:
        d = [v.value for v in row.dimension_values]
        m = [v.value for v in row.metric_values]
        rows.append(dict(zip(dim_headers + met_headers, d + m)))
    return pd.DataFrame(rows)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://fiscal.io/assets/img/logo-fiscal-io.svg", width=160)
st.sidebar.markdown("---")

propriedade = st.sidebar.selectbox("Propriedade", list(HOSTS.keys()))
host = HOSTS[propriedade]

st.sidebar.markdown("#### Período")
col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("De", value=date.today() - timedelta(days=29))
end_date = col2.date_input("Até", value=date.today() - timedelta(days=1))

if start_date > end_date:
    st.sidebar.error("Data inicial deve ser anterior à data final.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.caption("Dados via Google Analytics 4 · Property 307883096")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📊 Dashboard GA4 — Fiscal.IO")
st.caption(f"**{propriedade}** · {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}")

try:
    client = get_client()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    df_kpi = run_report(
        client,
        dimensions=["date"],
        metrics=["sessions", "activeUsers", "screenPageViews", "bounceRate", "averageSessionDuration"],
        start=start_date, end=end_date, host_filter=host,
    )

    sessions      = int(df_kpi["sessions"].astype(int).sum()) if not df_kpi.empty else 0
    users         = int(df_kpi["activeUsers"].astype(int).sum()) if not df_kpi.empty else 0
    pageviews     = int(df_kpi["screenPageViews"].astype(int).sum()) if not df_kpi.empty else 0
    bounce        = df_kpi["bounceRate"].astype(float).mean() * 100 if not df_kpi.empty else 0
    avg_dur_sec   = df_kpi["averageSessionDuration"].astype(float).mean() if not df_kpi.empty else 0
    avg_dur       = f"{int(avg_dur_sec // 60)}m {int(avg_dur_sec % 60)}s"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Sessões", f"{sessions:,.0f}".replace(",", "."))
    c2.metric("Usuários ativos", f"{users:,.0f}".replace(",", "."))
    c3.metric("Pageviews", f"{pageviews:,.0f}".replace(",", "."))
    c4.metric("Taxa de rejeição", f"{bounce:.1f}%")
    c5.metric("Duração média", avg_dur)

    st.markdown("---")

    # ── Sessões ao longo do tempo ─────────────────────────────────────────────
    if not df_kpi.empty:
        df_time = df_kpi[["date", "sessions"]].copy()
        df_time["sessions"] = df_time["sessions"].astype(int)
        df_time["date"] = pd.to_datetime(df_time["date"])
        df_time = df_time.sort_values("date")

        fig_line = px.line(
            df_time, x="date", y="sessions",
            title="Sessões ao longo do tempo",
            labels={"date": "", "sessions": "Sessões"},
            color_discrete_sequence=["#1a56db"],
        )
        fig_line.update_layout(hovermode="x unified", plot_bgcolor="white")
        st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")
    col_a, col_b = st.columns(2)

    # ── Canais de aquisição ───────────────────────────────────────────────────
    with col_a:
        df_canal = run_report(
            client,
            dimensions=["sessionDefaultChannelGroup"],
            metrics=["sessions"],
            start=start_date, end=end_date, host_filter=host,
        )
        if not df_canal.empty:
            df_canal["sessions"] = df_canal["sessions"].astype(int)
            df_canal = df_canal.sort_values("sessions", ascending=True)
            fig_canal = px.bar(
                df_canal, x="sessions", y="sessionDefaultChannelGroup",
                orientation="h", title="Sessões por canal",
                labels={"sessionDefaultChannelGroup": "", "sessions": "Sessões"},
                color_discrete_sequence=["#1a56db"],
            )
            fig_canal.update_layout(plot_bgcolor="white")
            st.plotly_chart(fig_canal, use_container_width=True)

    # ── Dispositivos ──────────────────────────────────────────────────────────
    with col_b:
        df_dev = run_report(
            client,
            dimensions=["deviceCategory"],
            metrics=["sessions"],
            start=start_date, end=end_date, host_filter=host,
        )
        if not df_dev.empty:
            df_dev["sessions"] = df_dev["sessions"].astype(int)
            fig_dev = px.pie(
                df_dev, names="deviceCategory", values="sessions",
                title="Sessões por dispositivo",
                color_discrete_sequence=["#1a56db", "#60a5fa", "#bfdbfe"],
            )
            st.plotly_chart(fig_dev, use_container_width=True)

    st.markdown("---")

    # ── Top páginas ───────────────────────────────────────────────────────────
    df_pages = run_report(
        client,
        dimensions=["pagePath"],
        metrics=["screenPageViews", "activeUsers", "averageSessionDuration"],
        start=start_date, end=end_date, host_filter=host,
    )
    if not df_pages.empty:
        df_pages["screenPageViews"] = df_pages["screenPageViews"].astype(int)
        df_pages["activeUsers"] = df_pages["activeUsers"].astype(int)
        df_pages["averageSessionDuration"] = df_pages["averageSessionDuration"].astype(float).apply(
            lambda s: f"{int(s // 60)}m {int(s % 60)}s"
        )
        df_pages = df_pages.sort_values("screenPageViews", ascending=False).head(20)
        df_pages.columns = ["Página", "Pageviews", "Usuários", "Duração média"]
        st.subheader("Top 20 páginas")
        st.dataframe(df_pages, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Source / Medium ───────────────────────────────────────────────────────
    df_src = run_report(
        client,
        dimensions=["sessionSource", "sessionMedium"],
        metrics=["sessions", "activeUsers"],
        start=start_date, end=end_date, host_filter=host,
    )
    if not df_src.empty:
        df_src["sessions"] = df_src["sessions"].astype(int)
        df_src["activeUsers"] = df_src["activeUsers"].astype(int)
        df_src = df_src.sort_values("sessions", ascending=False).head(20)
        df_src.columns = ["Source", "Medium", "Sessões", "Usuários"]
        st.subheader("Top 20 Source / Medium")
        st.dataframe(df_src, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao conectar ao GA4: {e}")
    st.info("Verifique se os secrets estão configurados corretamente no Streamlit Cloud.")
