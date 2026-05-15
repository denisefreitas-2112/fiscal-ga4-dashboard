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

st.markdown("""
<style>
    /* ── Sidebar ───────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #080c14 !important;
        border-right: 1px solid #1e293b !important;
    }
    /* ── Metric Cards ─────────────────────────────────────── */
    div[data-testid="metric-container"] {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 1.1rem 1.4rem 1rem 1.4rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.5);
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 2.1rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        letter-spacing: -0.02em;
        line-height: 1.1;
    }
    div[data-testid="stMetricLabel"] > div {
        font-size: 0.68rem !important;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #64748b !important;
        font-weight: 500;
        margin-top: 0.2rem;
    }
    /* ── Chart Cards ──────────────────────────────────────── */
    div[data-testid="stPlotlyChart"] > div {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #1e293b;
    }
    /* ── Section Headers ──────────────────────────────────── */
    .sec-header {
        background: linear-gradient(135deg, #1a56db 0%, #1044b0 100%);
        color: #f8fafc;
        padding: 0.65rem 1.2rem;
        border-radius: 10px;
        margin: 2.6rem 0 1.4rem 0;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        box-shadow: 0 2px 12px rgba(26,86,219,0.3);
    }
    /* ── Sub-headers (Google / Meta) ──────────────────────── */
    .sub-header {
        border-left: 3px solid #3b82f6;
        padding: 0.28rem 0.85rem;
        margin: 1.8rem 0 0.9rem 0;
        font-size: 0.75rem;
        font-weight: 700;
        color: #94a3b8;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .sub-header-meta { border-left-color: #1877f2; }
    /* ── Tables ───────────────────────────────────────────── */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #1e293b !important;
    }
    /* ── Captions ─────────────────────────────────────────── */
    div[data-testid="stCaptionContainer"] p {
        font-size: 0.67rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #475569;
        margin-bottom: 0.4rem;
    }
    /* ── Divider ──────────────────────────────────────────── */
    hr { border-color: #1e293b !important; margin: 2rem 0; }
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
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="#111827",
    font_color="#e2e8f0",
    font_family="sans-serif",
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


def _str_filter(field, value):
    return ga4_types.FilterExpression(
        filter=ga4_types.Filter(
            field_name=field,
            string_filter=ga4_types.Filter.StringFilter(
                value=value,
                match_type=ga4_types.Filter.StringFilter.MatchType.EXACT,
            ),
        )
    )


def _and_filter(*exprs):
    return ga4_types.FilterExpression(
        and_group=ga4_types.FilterExpressionList(expressions=list(exprs))
    )


def run_sessions_blog(client, start, end):
    """Sessoes no blog: filtra por hostName = conteudo.fiscal.io."""
    resp = client.run_report(ga4_types.RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[
            ga4_types.Dimension(name="yearMonth"),
        ],
        metrics=[
            ga4_types.Metric(name="sessions"),
            ga4_types.Metric(name="engagedSessions"),
            ga4_types.Metric(name="averageSessionDuration"),
            ga4_types.Metric(name="engagementRate"),
        ],
        date_ranges=[ga4_types.DateRange(start_date=start, end_date=end)],
        dimension_filter=_str_filter("hostName", "conteudo.fiscal.io"),
        limit=10000,
    ))
    return _parse_resp(resp)


def run_event(client, event_name, start, end):
    resp = client.run_report(ga4_types.RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[ga4_types.Dimension(name=d) for d in DIMS_BASE],
        metrics=[ga4_types.Metric(name="eventCount")],
        date_ranges=[ga4_types.DateRange(start_date=start, end_date=end)],
        dimension_filter=_str_filter("eventName", event_name),
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
st.sidebar.markdown(
    "<div style='padding:0.6rem 0 0.4rem 0;'>"
    "<span style='font-size:1.25rem;font-weight:800;color:#f8fafc;letter-spacing:-0.02em;'>Fiscal</span>"
    "<span style='font-size:1.25rem;font-weight:800;color:#1a56db;letter-spacing:-0.02em;'>.IO</span>"
    "<br><span style='font-size:0.65rem;color:#475569;letter-spacing:0.08em;text-transform:uppercase;'>"
    "Analytics Dashboard</span></div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")
st.sidebar.markdown("**Ano de referencia**")
ano = st.sidebar.selectbox("", [2026, 2025], index=0, label_visibility="collapsed")
start_date = f"{ano}-01-01"
end_date   = date.today().strftime("%Y-%m-%d")
st.sidebar.markdown("---")
st.sidebar.caption("Google Analytics 4")
st.sidebar.caption("Property 307883096")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='margin:0 0 0.15rem 0;color:#f8fafc;font-weight:700;"
    f"font-size:1.7rem;letter-spacing:-0.02em;'>"
    f"Desempenho de Marketing</h1>"
    f"<p style='color:#64748b;font-size:0.82rem;margin:0 0 0.5rem 0;"
    f"letter-spacing:0.03em;'>"
    f"Fiscal.IO &nbsp;&nbsp;·&nbsp;&nbsp; {ano} &nbsp;&nbsp;·&nbsp;&nbsp; "
    f"Blog &nbsp;|&nbsp; E-mail &nbsp;|&nbsp; Google Ads &nbsp;|&nbsp; Meta Ads</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

try:
    client = get_client()

    with st.spinner("Carregando dados..."):
        df_s    = enrich(run_sessions(client, start_date, end_date))
        df_l    = enrich(run_event(client, "generate_lead",      start_date, end_date))
        df_dl   = enrich(run_event(client, "lead_form_download", start_date, end_date))
        # Blog: sessoes por hostName (conteudo.fiscal.io)
        df_blog_host = run_sessions_blog(client, start_date, end_date)

    # cast numericos
    df_s["sessions"]               = df_s["sessions"].astype(int)
    df_s["engagedSessions"]        = df_s["engagedSessions"].astype(int)
    df_s["averageSessionDuration"] = df_s["averageSessionDuration"].astype(float)
    df_s["engagementRate"]         = df_s["engagementRate"].astype(float)
    df_l["eventCount"]             = df_l["eventCount"].astype(int)
    df_dl["eventCount"]            = df_dl["eventCount"].astype(int)

    if not df_blog_host.empty:
        df_blog_host["sessions"]               = df_blog_host["sessions"].astype(int)
        df_blog_host["engagedSessions"]        = df_blog_host["engagedSessions"].astype(int)
        df_blog_host["averageSessionDuration"] = df_blog_host["averageSessionDuration"].astype(float)
        df_blog_host["mes"] = df_blog_host["yearMonth"].apply(
            lambda ym: f"{MESES[int(ym[4:])-1]}/{ym[2:4]}"
        )

    ordem_mes   = sorted(df_s["yearMonth"].unique())
    meses_label = [f"{MESES[int(m[4:])-1]}/{m[2:4]}" for m in ordem_mes]

    def bar_chart(df, x, y, title, color, text_col=None):
        tc = text_col or y
        text_vals = df[tc].apply(fmt_num)
        fig = px.bar(df, x=x, y=y,
            category_orders={x: meses_label},
            labels={x: "", y: ""},
            color_discrete_sequence=[color],
            text=text_vals)
        fig.update_traces(
            textposition="outside",
            textfont=dict(size=11, color="#94a3b8"),
            cliponaxis=False,
            marker_line_width=0,
            opacity=0.9,
        )
        fig.update_layout(
            **PLOTLY_DARK,
            showlegend=False,
            title=dict(
                text=title,
                font=dict(size=11, color="#64748b"),
                x=0.015,
                xanchor="left",
                y=0.97,
                yanchor="top",
            ),
            height=265,
            bargap=0.38,
            margin=dict(t=44, b=14, l=14, r=14),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=11, color="#64748b"),
                tickangle=0,
                linecolor="#1e293b",
            ),
        )
        return fig

    def bar_chart_multi(df, x, y, color_col, title):
        fig = px.bar(df, x=x, y=y, color=color_col, title=title,
            barmode="group",
            category_orders={x: meses_label},
            labels={x:"", y:"", color_col:""},
            color_discrete_map=CORES_CANAL,
            text=y)
        fig.update_traces(textposition="outside", textfont_size=11, cliponaxis=False)
        fig.update_layout(**PLOTLY_DARK,
            margin=dict(t=50, b=20, l=20, r=20),
            yaxis=dict(showgrid=True, gridcolor="#2d3748"))
        return fig

    def tabela_campanhas(canal_key, df_evento, col_nome, top=20):
        """Retorna tabela: nome da campanha x total de eventos para o canal."""
        df = (
            df_evento[df_evento["canal_key"] == canal_key]
            .groupby("sessionCampaignName", as_index=False)["eventCount"].sum()
            .query("sessionCampaignName != '(not set)' and sessionCampaignName != ''")
            .sort_values("eventCount", ascending=False)
            .head(top)
            .rename(columns={"sessionCampaignName": col_nome, "eventCount": "Total"})
        )
        return df

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALISTA DE CONTEUDO
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-header">&#9999;&#65039; Analista de Conteudo &mdash; Blog</div>', unsafe_allow_html=True)

    leads_blog    = df_l[df_l["canal_key"] == "blog"]["eventCount"].sum()
    dl_blog_total = df_dl[df_dl["canal_key"] == "blog"]["eventCount"].sum()

    if not df_blog_host.empty:
        b1,b2,b3,b4 = st.columns(4)
        b1.metric("Sessoes no Blog",    fmt_num(df_blog_host["sessions"].sum()))
        b2.metric("Leads via Blog",     fmt_num(leads_blog))
        b3.metric("Downloads via Blog", fmt_num(dl_blog_total))
        ad = df_blog_host["averageSessionDuration"].mean()
        b4.metric("Duracao media",      f"{int(ad//60)}m {int(ad%60)}s")

        # Sessoes: hostName = conteudo.fiscal.io
        st.plotly_chart(bar_chart(
            df_blog_host.sort_values("yearMonth"), "mes", "sessions",
            "Sessoes no Blog (conteudo.fiscal.io)", "#10b981"),
            use_container_width=True)

        # Leads: fiscal.io com source=blog
        df_l_blog_mes = (
            df_l[df_l["canal_key"] == "blog"]
            .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
            .sort_values("yearMonth")
        )
        if not df_l_blog_mes.empty:
            st.plotly_chart(bar_chart(df_l_blog_mes, "mes", "eventCount",
                "Leads gerados a partir do Blog (fiscal.io)", "#34d399"),
                use_container_width=True)

        # Downloads: fiscal.io com source=blog
        df_dl_blog_mes = (
            df_dl[df_dl["canal_key"] == "blog"]
            .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
            .sort_values("yearMonth")
        )
        if not df_dl_blog_mes.empty:
            st.plotly_chart(bar_chart(df_dl_blog_mes, "mes", "eventCount",
                "Downloads gratuitos a partir do Blog (fiscal.io)", "#059669"),
                use_container_width=True)

        t_leads_blog = tabela_campanhas("blog", df_l,  "Artigo / Campanha")
        t_dl_blog    = tabela_campanhas("blog", df_dl, "Artigo / Campanha")
        tc1, tc2 = st.columns(2)
        with tc1:
            st.caption("Leads gerados por artigo / campanha")
            if not t_leads_blog.empty:
                st.dataframe(t_leads_blog, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados.")
        with tc2:
            st.caption("Downloads por artigo / campanha")
            if not t_dl_blog.empty:
                st.dataframe(t_dl_blog, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados.")
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
        e1,e2 = st.columns(2)
        e1.metric("Sessoes via E-mail", fmt_num(df_em_mes["sessions"].sum()))
        e2.metric("Leads via E-mail",   fmt_num(leads_em))

        st.plotly_chart(bar_chart(df_em_mes, "mes", "sessions",
            "Sessoes via E-mail", "#8b5cf6"), use_container_width=True)

        df_le = (df_l[df_l["canal_key"]=="email"]
            .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
            .sort_values("yearMonth"))
        if not df_le.empty:
            st.plotly_chart(bar_chart(df_le, "mes", "eventCount",
                "Leads gerados via E-mail", "#7c3aed"), use_container_width=True)

        t_leads_em = tabela_campanhas("email", df_l,  "Nome do E-mail / Campanha")
        t_dl_em    = tabela_campanhas("email", df_dl, "Nome do E-mail / Campanha")
        te1, te2 = st.columns(2)
        with te1:
            st.caption("Leads gerados por campanha de e-mail")
            if not t_leads_em.empty:
                st.dataframe(t_leads_em, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados.")
        with te2:
            st.caption("Downloads por campanha de e-mail")
            if not t_dl_em.empty:
                st.dataframe(t_dl_em, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados.")
    else:
        st.info("Sem dados de e-mail no periodo.")

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALISTA DE MIDIAS DIGITAIS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-header">&#128227; Analista de Midias Digitais &mdash; Google Ads e Meta Ads</div>', unsafe_allow_html=True)

    def graficos_canal(key, label, cor, com_downloads=True):
        df_sess = (df_s[df_s["canal_key"] == key]
            .groupby(["yearMonth","mes"], as_index=False)["sessions"].sum()
            .sort_values("yearMonth"))
        df_lead = (df_l[df_l["canal_key"] == key]
            .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
            .sort_values("yearMonth"))
        df_down = (df_dl[df_dl["canal_key"] == key]
            .groupby(["yearMonth","mes"], as_index=False)["eventCount"].sum()
            .sort_values("yearMonth"))

        total_sess  = df_sess["sessions"].sum() if not df_sess.empty else 0
        total_leads = df_lead["eventCount"].sum() if not df_lead.empty else 0
        total_dl    = df_down["eventCount"].sum() if not df_down.empty else 0

        if com_downloads:
            c1, c2, c3 = st.columns(3)
            c1.metric(f"Sessoes {label}",   fmt_num(total_sess))
            c2.metric(f"Leads {label}",     fmt_num(total_leads))
            c3.metric(f"Downloads {label}", fmt_num(total_dl))
        else:
            c1, c2 = st.columns(2)
            c1.metric(f"Sessoes {label}", fmt_num(total_sess))
            c2.metric(f"Leads {label}",   fmt_num(total_leads))

        if not df_sess.empty:
            st.plotly_chart(bar_chart(df_sess, "mes", "sessions",
                f"Sessoes — {label}", cor), use_container_width=True)
        if not df_lead.empty:
            st.plotly_chart(bar_chart(df_lead, "mes", "eventCount",
                f"Leads gerados — {label}", cor), use_container_width=True)
        if com_downloads and not df_down.empty:
            st.plotly_chart(bar_chart(df_down, "mes", "eventCount",
                f"Downloads gratuitos — {label}", cor), use_container_width=True)

        # Tabelas de campanha
        t_leads = tabela_campanhas(key, df_l,  "Campanha")
        col_nome = "Campanha"
        if com_downloads:
            t_dl = tabela_campanhas(key, df_dl, col_nome)
            tm1, tm2 = st.columns(2)
            with tm1:
                st.caption(f"Leads por campanha — {label}")
                if not t_leads.empty:
                    st.dataframe(t_leads, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem dados.")
            with tm2:
                st.caption(f"Downloads por campanha — {label}")
                if not t_dl.empty:
                    st.dataframe(t_dl, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem dados.")
        else:
            st.caption(f"Leads por campanha — {label}")
            if not t_leads.empty:
                st.dataframe(t_leads, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados.")

    st.markdown('<div class="sub-header">Google Ads</div>', unsafe_allow_html=True)
    graficos_canal("gads", "Google Ads", "#3b82f6", com_downloads=True)
    st.markdown("---")
    st.markdown('<div class="sub-header sub-header-meta">Meta Ads</div>', unsafe_allow_html=True)
    graficos_canal("meta", "Meta Ads",   "#1877f2", com_downloads=False)

except Exception as e:
    st.error(f"Erro ao conectar ao GA4: {e}")
    st.info("Verifique os secrets no Streamlit Cloud.")
