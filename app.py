# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import types as ga4_types
from datetime import date

st.set_page_config(
    page_title="Desempenho Marketing - Fiscal.IO",
    page_icon="\U0001f4ca",
    layout="wide",
)

# ── Estilos customizados (complementam o config.toml dark) ───────────────────
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        border: 1px solid #1e3a5f;
        border-left: 4px solid #1a56db;
        border-radius: 8px;
        padding: 0.8rem 1rem;
    }
    .sec-header {
        background: linear-gradient(90deg, #1a56db 0%, #1e3a8a 100%);
        color: white;
        padding: 0.6rem 1.2rem;
        border-radius: 8px;
        margin: 1.8rem 0 0.8rem 0;
        font-size: 0.95rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ── Constantes ────────────────────────────────────────────────────────────────
PROPERTY_ID = "307883096"
MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

# chaves internas (ASCII) → labels de exibicao
CANAL_DISPLAY = {
    "blog":      "Blog / Conteudo",
    "email":     "E-mail / Automacao",
    "gads":      "Google Ads",
    "meta":      "Meta Ads",
    "instagram": "Instagram",
    "linkedin":  "LinkedIn",
    "social":    "Social",
}

CORES_CANAL = {
    "Blog / Conteudo":    "#10b981",
    "E-mail / Automacao": "#8b5cf6",
    "Google Ads":         "#3b82f6",
    "Meta Ads":           "#1877f2",
    "Instagram":          "#e1306c",
    "LinkedIn":           "#0077b5",
    "Social":             "#64748b",
}

CANAIS_MIDIA = ["Google Ads", "Meta Ads", "Instagram", "LinkedIn", "Social"]

PLOTLY_DARK = dict(
    template="plotly_dark",
    plot_bgcolor="#1a2035",
    paper_bgcolor="#1a2035",
    font_color="#e2e8f0",
)


# ── Auth ──────────────────────────────────────────────────────────────────────
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


# ── Classificador ─────────────────────────────────────────────────────────────
def classify_canal(channel_group, source, medium):
    """
    Espelha o relatorio Aquisicao de trafego do GA4.
    Blog usa UTMs: source=blog, medium=artigo (ou Blog/Blog).
    """
    cg  = str(channel_group).lower().strip()
    src = str(source).lower().strip()
    med = str(medium).lower().strip()

    # Blog: source=blog OU medium=artigo/blog OU referral de conteudo.fiscal.io
    if src == "blog" or med in ("artigo", "blog") or "conteudo.fiscal" in src:
        return "blog"

    # E-mail / Zoho
    if cg == "email" or med in ("email", "e-mail") or "zoho" in src or "email" in src:
        return "email"

    # Google Ads (Paid Search)
    if cg == "paid search" or (src == "google" and med == "cpc"):
        return "gads"

    # Social por plataforma
    if "linkedin" in src:
        return "linkedin"
    if "instagram" in src:
        return "instagram"
    if "facebook" in src or "meta" in src or src in ("fb", "l.facebook.com"):
        return "meta"

    # Social generico
    if cg in ("organic social", "paid social") or med == "social":
        return "social"

    return None


# ── GA4 queries ───────────────────────────────────────────────────────────────
DIMS_BASE = [
    "yearMonth",
    "sessionDefaultChannelGroup",
    "sessionSource",
    "sessionMedium",
    "sessionCampaignName",
]


def _parse_resp(resp):
    dh = [h.name for h in resp.dimension_headers]
    mh = [h.name for h in resp.metric_headers]
    rows = []
    for row in resp.rows:
        d = [v.value for v in row.dimension_values]
        m = [v.value for v in row.metric_values]
        rows.append(dict(zip(dh + mh, d + m)))
    return pd.DataFrame(rows)


def run_sessions(client, start, end):
    resp = client.run_report(ga4_types.RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[ga4_types.Dimension(name=d) for d in DIMS_BASE],
        metrics=[
            ga4_types.Metric(name="sessions"),
            ga4_types.Metric(name="averageSessionDuration"),
            ga4_types.Metric(name="engagedSessions"),
            ga4_types.Metric(name="engagementRate"),
        ],
        date_ranges=[ga4_types.DateRange(start_date=start, end_date=end)],
        limit=10000,
    ))
    return _parse_resp(resp)


def run_event(client, event_name, start, end):
    resp = client.run_report(ga4_types.RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[ga4_types.Dimension(name=d) for d in DIMS_BASE],
        metrics=[ga4_types.Metric(name="eventCount")],
        date_ranges=[ga4_types.DateRange(start_date=start, end_date=end)],
        dimension_filter=ga4_types.FilterExpression(
            filter=ga4_types.Filter(
                field_name="eventName",
                string_filter=ga4_types.Filter.StringFilter(
                    value=event_name,
                    match_type=ga4_types.Filter.StringFilter.MatchType.EXACT,
                ),
            )
        ),
        limit=10000,
    ))
    return _parse_resp(resp)


def enrich(df):
    df = df.copy()
    df["canal_key"] = df.apply(
        lambda r: classify_canal(
            r["sessionDefaultChannelGroup"], r["sessionSource"], r["sessionMedium"]
        ), axis=1,
    )
    df["canal"] = df["canal_key"].map(CANAL_DISPLAY)
    df["mes"]   = df["yearMonth"].apply(lambda ym: f"{MESES[int(ym[4:])-1]}/{ym[2:4]}")
    return df[df["canal"].notna()].copy()


def fmt_num(n):
    return f"{int(n):,}".replace(",", ".")


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://fiscal.io/assets/img/logo-fiscal-io.svg", width=150)
st.sidebar.markdown("---")
ano = st.sidebar.selectbox("Ano", [2026, 2025], index=0)
start_date = f"{ano}-01-01"
end_date   = date.today().strftime("%Y-%m-%d")
st.sidebar.markdown("---")
st.sidebar.caption("GA4 - Property 307883096")
st.sidebar.caption("Solicitado por Lucas Farley")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"### \U0001f4ca GA4 - Painel de Desempenho de Marketing | Fiscal.IO | {ano}")
st.markdown("---")

try:
    client = get_client()

    with st.spinner("Carregando dados..."):
        df_s  = enrich(run_sessions(client, start_date, end_date))
        df_l  = enrich(run_event(client, "generate_lead",      start_date, end_date))
        df_dl = enrich(run_event(client, "lead_form_download", start_date, end_date))

    # cast numericos
    df_s["sessions"]               = df_s["sessions"].astype(int)
    df_s["engagedSessions"]        = df_s["engagedSessions"].astype(int)
    df_s["averageSessionDuration"] = df_s["averageSessionDuration"].astype(float)
    df_s["engagementRate"]         = df_s["engagementRate"].astype(float)
    df_l["eventCount"]             = df_l["eventCount"].astype(int)
    df_dl["eventCount"]            = df_dl["eventCount"].astype(int)

    ordem_mes   = sorted(df_s["yearMonth"].unique())
    meses_label = [f"{MESES[int(m[4:])-1]}/{m[2:4]}" for m in ordem_mes]

    # ── KPIs globais ──────────────────────────────────────────────────────────
    total_sess  = df_s["sessions"].sum()
    total_eng   = df_s["engagedSessions"].sum()
    avg_eng_r   = df_s["engagementRate"].mean() * 100
    avg_dur     = df_s["averageSessionDuration"].mean()
    total_leads = df_l["eventCount"].sum()
    total_dl    = df_dl["eventCount"].sum()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Sessoes totais",    fmt_num(total_sess))
    k2.metric("Sessoes engajadas", fmt_num(total_eng))
    k3.metric("Engajamento medio", f"{avg_eng_r:.1f}%")
    k4.metric("Duracao media",     f"{int(avg_dur//60)}m {int(avg_dur%60)}s")
    k5.metric("Leads gerados",     fmt_num(total_leads))
    k6.metric("Downloads gratis",  fmt_num(total_dl))

    st.markdown("---")

    # ── Visao geral por canal ─────────────────────────────────────────────────
    st.markdown("#### Progresso por canal - mes a mes")

    df_geral = df_s.groupby(["yearMonth","mes","canal"], as_index=False).agg(
        sessions=("sessions","sum")
    ).sort_values("yearMonth")

    fig_geral = px.line(
        df_geral, x="mes", y="sessions", color="canal",
        category_orders={"mes": meses_label},
        labels={"mes":"","sessions":"Sessoes","canal":"Canal"},
        color_discrete_map=CORES_CANAL,
        markers=True,
    )
    fig_geral.update_traces(line_width=2.5)
    fig_geral.update_layout(**PLOTLY_DARK, legend_title="Canal", showlegend=True, hovermode="x unified")
    st.plotly_chart(fig_geral, use_container_width=True)

    col_ev1, col_ev2 = st.columns(2)
    with col_ev1:
        df_lm = df_l.groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum().sort_values("yearMonth")
        fig_l2 = px.line(df_lm, x="mes", y="eventCount",
            title="Leads gerados (generate_lead) - progresso",
            category_orders={"mes": meses_label},
            labels={"mes":"","eventCount":"Leads"},
            color_discrete_sequence=["#3b82f6"],
            markers=True)
        fig_l2.update_traces(line_width=2.5, fill="tozeroy", fillcolor="rgba(59,130,246,0.1)")
        fig_l2.update_layout(**PLOTLY_DARK, hovermode="x unified")
        st.plotly_chart(fig_l2, use_container_width=True)

    with col_ev2:
        df_dm = df_dl.groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum().sort_values("yearMonth")
        fig_d2 = px.line(df_dm, x="mes", y="eventCount",
            title="Downloads gratuitos (lead_form_download) - progresso",
            category_orders={"mes": meses_label},
            labels={"mes":"","eventCount":"Downloads"},
            color_discrete_sequence=["#10b981"],
            markers=True)
        fig_d2.update_traces(line_width=2.5, fill="tozeroy", fillcolor="rgba(16,185,129,0.1)")
        fig_d2.update_layout(**PLOTLY_DARK, hovermode="x unified")
        st.plotly_chart(fig_d2, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALISTA DE CONTEUDO
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-header">&#9999;&#65039; Analista de Conteudo &mdash; Blog</div>', unsafe_allow_html=True)

    df_blog     = df_s[df_s["canal_key"] == "blog"]
    df_blog_mes = df_blog.groupby(["yearMonth","mes"], as_index=False).agg(
        sessions=("sessions","sum"),
        engagedSessions=("engagedSessions","sum"),
        avgDur=("averageSessionDuration","mean"),
        engRate=("engagementRate","mean"),
    ).sort_values("yearMonth")

    leads_blog = df_l[df_l["canal_key"] == "blog"]["eventCount"].sum()

    if not df_blog_mes.empty:
        b1,b2,b3,b4,b5 = st.columns(5)
        b1.metric("Sessoes",         fmt_num(df_blog_mes["sessions"].sum()))
        b2.metric("Engajadas",       fmt_num(df_blog_mes["engagedSessions"].sum()))
        b3.metric("Tx. engajamento", f"{df_blog_mes['engRate'].mean()*100:.1f}%")
        ad = df_blog_mes["avgDur"].mean()
        b4.metric("Duracao media",   f"{int(ad//60)}m {int(ad%60)}s")
        b5.metric("Leads via Blog",  fmt_num(leads_blog))

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            fig_bs = px.line(df_blog_mes, x="mes", y="sessions",
                title="Sessoes via Blog",
                category_orders={"mes": meses_label},
                labels={"mes":"","sessions":"Sessoes"},
                color_discrete_sequence=["#10b981"], markers=True)
            fig_bs.update_traces(line_width=2.5, fill="tozeroy", fillcolor="rgba(16,185,129,0.1)")
            fig_bs.update_layout(**PLOTLY_DARK, hovermode="x unified")
            st.plotly_chart(fig_bs, use_container_width=True)
        with col_b2:
            fig_be = px.line(df_blog_mes, x="mes", y="engRate",
                title="Taxa de engajamento - Blog",
                category_orders={"mes": meses_label},
                labels={"mes":"","engRate":"Taxa"},
                color_discrete_sequence=["#10b981"], markers=True)
            fig_be.update_traces(line_width=2.5)
            fig_be.update_yaxes(tickformat=".0%")
            fig_be.update_layout(**PLOTLY_DARK, hovermode="x unified")
            st.plotly_chart(fig_be, use_container_width=True)
        with col_b3:
            df_dl_blog_mes = (
                df_dl[df_dl["canal_key"] == "blog"]
                .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
                .sort_values("yearMonth")
            )
            if not df_dl_blog_mes.empty:
                fig_dl_blog = px.line(df_dl_blog_mes, x="mes", y="eventCount",
                    title="Downloads gratuitos via Blog",
                    category_orders={"mes": meses_label},
                    labels={"mes":"","eventCount":"Downloads"},
                    color_discrete_sequence=["#34d399"], markers=True)
                fig_dl_blog.update_traces(line_width=2.5, fill="tozeroy", fillcolor="rgba(52,211,153,0.1)")
                fig_dl_blog.update_layout(**PLOTLY_DARK, hovermode="x unified")
                st.plotly_chart(fig_dl_blog, use_container_width=True)
            else:
                st.info("Sem downloads via Blog no periodo.")

        df_bc = (
            df_blog.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
            .query("sessionCampaignName != '(not set)'")
            .sort_values("sessions", ascending=False).head(20)
            .rename(columns={"sessionCampaignName":"Campanha / Artigo","sessions":"Sessoes"})
        )
        if not df_bc.empty:
            st.caption("Top campanhas / artigos do Blog")
            st.dataframe(df_bc, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de Blog no periodo.")

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALISTA DE AUTOMACAO
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-header">&#128231; Analista de Automacao &mdash; E-mail / Zoho Marketing Hub</div>', unsafe_allow_html=True)

    df_em     = df_s[df_s["canal_key"] == "email"]
    df_em_mes = df_em.groupby(["yearMonth","mes"], as_index=False).agg(
        sessions=("sessions","sum"),
        engagedSessions=("engagedSessions","sum"),
    ).sort_values("yearMonth")

    leads_em = df_l[df_l["canal_key"]  == "email"]["eventCount"].sum()
    dl_em    = df_dl[df_dl["canal_key"] == "email"]["eventCount"].sum()

    if not df_em_mes.empty:
        e1,e2,e3,e4 = st.columns(4)
        e1.metric("Sessoes",         fmt_num(df_em_mes["sessions"].sum()))
        e2.metric("Engajadas",       fmt_num(df_em_mes["engagedSessions"].sum()))
        e3.metric("Leads via E-mail", fmt_num(leads_em))
        e4.metric("Downloads via E-mail", fmt_num(dl_em))

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            fig_es = px.line(df_em_mes, x="mes", y="sessions",
                title="Sessoes via E-mail - progresso",
                category_orders={"mes": meses_label},
                labels={"mes":"","sessions":"Sessoes"},
                color_discrete_sequence=["#8b5cf6"], markers=True)
            fig_es.update_traces(line_width=2.5, fill="tozeroy", fillcolor="rgba(139,92,246,0.1)")
            fig_es.update_layout(**PLOTLY_DARK, hovermode="x unified")
            st.plotly_chart(fig_es, use_container_width=True)
        with col_e2:
            df_le = (df_l[df_l["canal_key"]=="email"]
                .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
                .sort_values("yearMonth"))
            if not df_le.empty:
                fig_el = px.line(df_le, x="mes", y="eventCount",
                    title="Leads via E-mail - progresso",
                    category_orders={"mes": meses_label},
                    labels={"mes":"","eventCount":"Leads"},
                    color_discrete_sequence=["#8b5cf6"], markers=True)
                fig_el.update_traces(line_width=2.5, fill="tozeroy", fillcolor="rgba(139,92,246,0.1)")
                fig_el.update_layout(**PLOTLY_DARK, hovermode="x unified")
                st.plotly_chart(fig_el, use_container_width=True)

        df_ec = (
            df_em.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
            .query("sessionCampaignName != '(not set)'")
            .sort_values("sessions", ascending=False).head(20)
            .rename(columns={"sessionCampaignName":"Campanha / E-mail","sessions":"Sessoes"})
        )
        if not df_ec.empty:
            st.caption("Top campanhas de e-mail")
            st.dataframe(df_ec, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de e-mail no periodo.")

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALISTA DE MIDIAS DIGITAIS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-header">&#128227; Analista de Midias Digitais &mdash; Pago e Social</div>', unsafe_allow_html=True)

    KEYS_MIDIA = ["gads","meta","instagram","linkedin","social"]
    df_mid     = df_s[df_s["canal_key"].isin(KEYS_MIDIA)]
    df_mid_mes = df_mid.groupby(["yearMonth","mes","canal"], as_index=False).agg(
        sessions=("sessions","sum"),
        engagedSessions=("engagedSessions","sum"),
    ).sort_values("yearMonth")

    leads_mid = df_l[df_l["canal_key"].isin(KEYS_MIDIA)]["eventCount"].sum()
    dl_mid    = df_dl[df_dl["canal_key"].isin(KEYS_MIDIA)]["eventCount"].sum()

    if not df_mid_mes.empty:
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Sessoes",         fmt_num(df_mid_mes["sessions"].sum()))
        m2.metric("Engajadas",       fmt_num(df_mid_mes["engagedSessions"].sum()))
        m3.metric("Leads gerados",   fmt_num(leads_mid))
        m4.metric("Downloads",       fmt_num(dl_mid))

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            fig_ms = px.line(df_mid_mes, x="mes", y="sessions", color="canal",
                title="Sessoes por canal de midia - progresso",
                category_orders={"mes": meses_label},
                labels={"mes":"","sessions":"Sessoes","canal":"Canal"},
                color_discrete_map=CORES_CANAL, markers=True)
            fig_ms.update_traces(line_width=2.5)
            fig_ms.update_layout(**PLOTLY_DARK, hovermode="x unified")
            st.plotly_chart(fig_ms, use_container_width=True)
        with col_m2:
            df_lm2 = (df_l[df_l["canal_key"].isin(KEYS_MIDIA)]
                .groupby(["yearMonth","mes","canal"], as_index=False)["eventCount"].sum()
                .sort_values("yearMonth"))
            if not df_lm2.empty:
                fig_lm = px.line(df_lm2, x="mes", y="eventCount", color="canal",
                    title="Leads por canal de midia - progresso",
                    category_orders={"mes": meses_label},
                    labels={"mes":"","eventCount":"Leads","canal":"Canal"},
                    color_discrete_map=CORES_CANAL, markers=True)
                fig_lm.update_traces(line_width=2.5)
                fig_lm.update_layout(**PLOTLY_DARK, hovermode="x unified")
                st.plotly_chart(fig_lm, use_container_width=True)

        df_mc = (
            df_mid.groupby(["canal","sessionCampaignName"], as_index=False)["sessions"].sum()
            .query("sessionCampaignName != '(not set)'")
            .sort_values("sessions", ascending=False).head(20)
            .rename(columns={"canal":"Canal","sessionCampaignName":"Campanha","sessions":"Sessoes"})
        )
        if not df_mc.empty:
            st.caption("Top campanhas de midia paga e social")
            st.dataframe(df_mc, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de midia paga/social no periodo.")

except Exception as e:
    st.error(f"Erro ao conectar ao GA4: {e}")
    st.info("Verifique os secrets no Streamlit Cloud.")
