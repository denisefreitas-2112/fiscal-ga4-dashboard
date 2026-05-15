import streamlit as st
import pandas as pd
import plotly.express as px
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import types as ga4_types
from datetime import date

st.set_page_config(
    page_title="Desempenho Marketing — Fiscal.IO",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .section-header {
        background: #1a56db;
        color: white;
        padding: 0.55rem 1rem;
        border-radius: 6px;
        margin: 1.5rem 0 0.8rem 0;
        font-size: 1rem;
        font-weight: 600;
    }
    .stMetric label { font-size: 0.8rem; color: #6b7280; }
</style>
""", unsafe_allow_html=True)

PROPERTY_ID = "307883096"
MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]


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


def classify_canal(source, medium, campaign):
    src = str(source).lower().strip()
    med = str(medium).lower().strip()
    cam = str(campaign).lower().strip()

    if "conteudo.fiscal" in src or "blog" in src or "blog" in cam:
        return "Conteudo / Blog"
    if med in ("email", "e-mail") or "zoho" in src or "email" in src or "newsletter" in cam or "email" in cam:
        return "E-mail / Automacao"
    if "linkedin" in src:
        return "LinkedIn"
    if "instagram" in src:
        return "Instagram"
    if "facebook" in src or "meta" in src or src == "fb":
        return "Meta Ads"
    if (src == "google" and med == "cpc") or med == "cpc":
        return "Google Ads"
    if med == "social" or src in ("twitter", "x", "tiktok", "pinterest", "youtube"):
        return "Social"
    return None


CANAL_ANALISTA = {
    "Conteudo / Blog":    "Analista de Conteudo",
    "E-mail / Automacao": "Analista de Automacao",
    "Google Ads":         "Analista de Midias Digitais",
    "Meta Ads":           "Analista de Midias Digitais",
    "Instagram":          "Analista de Midias Digitais",
    "LinkedIn":           "Analista de Midias Digitais",
    "Social":             "Analista de Midias Digitais",
}

CORES_CANAL = {
    "Conteudo / Blog":    "#059669",
    "E-mail / Automacao": "#7c3aed",
    "Google Ads":         "#1a56db",
    "Meta Ads":           "#1877f2",
    "Instagram":          "#e1306c",
    "LinkedIn":           "#0077b5",
    "Social":             "#64748b",
}

CANAIS_MIDIA = ["Google Ads", "Meta Ads", "Instagram", "LinkedIn", "Social"]


def fmt_month(ym):
    return f"{MESES[int(ym[4:]) - 1]}/{ym[2:4]}"


def run_report(client, dimensions, metrics, start, end):
    resp = client.run_report(ga4_types.RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[ga4_types.Dimension(name=d) for d in dimensions],
        metrics=[ga4_types.Metric(name=m) for m in metrics],
        date_ranges=[ga4_types.DateRange(start_date=start, end_date=end)],
        limit=10000,
    ))
    dh = [h.name for h in resp.dimension_headers]
    mh = [h.name for h in resp.metric_headers]
    rows = []
    for row in resp.rows:
        d = [v.value for v in row.dimension_values]
        m = [v.value for v in row.metric_values]
        rows.append(dict(zip(dh + mh, d + m)))
    return pd.DataFrame(rows)


def run_event_report(client, event_name, start, end):
    resp = client.run_report(ga4_types.RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[
            ga4_types.Dimension(name="yearMonth"),
            ga4_types.Dimension(name="sessionSource"),
            ga4_types.Dimension(name="sessionMedium"),
            ga4_types.Dimension(name="sessionCampaignName"),
        ],
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
    dh = [h.name for h in resp.dimension_headers]
    mh = [h.name for h in resp.metric_headers]
    rows = []
    for row in resp.rows:
        d = [v.value for v in row.dimension_values]
        m = [v.value for v in row.metric_values]
        rows.append(dict(zip(dh + mh, d + m)))
    return pd.DataFrame(rows)


def enrich(df):
    df = df.copy()
    df["canal"] = df.apply(
        lambda r: classify_canal(r["sessionSource"], r["sessionMedium"], r["sessionCampaignName"]),
        axis=1,
    )
    df["analista"] = df["canal"].map(CANAL_ANALISTA)
    df["mes"] = df["yearMonth"].apply(fmt_month)
    return df[df["canal"].notna()].copy()


# Sidebar
st.sidebar.image("https://fiscal.io/assets/img/logo-fiscal-io.svg", width=160)
st.sidebar.markdown("---")
st.sidebar.markdown("#### Periodo")
ano = st.sidebar.selectbox("Ano", [2026, 2025], index=0)
start_date = f"{ano}-01-01"
end_date = date.today().strftime("%Y-%m-%d")
st.sidebar.markdown("---")
st.sidebar.caption(f"GA4 Property 307883096 · {ano}")

# Header
st.title("Painel de Desempenho — Marketing Fiscal.IO")
st.caption(
    f"Canais: Blog · E-mail / Zoho · Google Ads · Meta · Instagram · LinkedIn · Social | {ano}"
)
st.markdown("---")

try:
    client = get_client()

    with st.spinner("Carregando dados do GA4..."):
        df_raw      = run_report(
            client,
            dimensions=["yearMonth", "sessionSource", "sessionMedium", "sessionCampaignName"],
            metrics=["sessions", "averageSessionDuration", "engagedSessions", "engagementRate"],
            start=start_date, end=end_date,
        )
        df_leads_raw = run_event_report(client, "generate_lead", start_date, end_date)
        df_dl_raw    = run_event_report(client, "lead_form_download", start_date, end_date)

    df_s  = enrich(df_raw)
    df_l  = enrich(df_leads_raw)
    df_dl = enrich(df_dl_raw)

    df_s["sessions"]               = df_s["sessions"].astype(int)
    df_s["engagedSessions"]        = df_s["engagedSessions"].astype(int)
    df_s["averageSessionDuration"] = df_s["averageSessionDuration"].astype(float)
    df_s["engagementRate"]         = df_s["engagementRate"].astype(float)
    df_l["eventCount"]             = df_l["eventCount"].astype(int)
    df_dl["eventCount"]            = df_dl["eventCount"].astype(int)

    ordem_mes   = sorted(df_s["yearMonth"].unique())
    meses_label = [fmt_month(m) for m in ordem_mes]

    # VISAO GERAL
    st.subheader(f"Visao geral · sessoes por canal · {ano}")

    df_geral = df_s.groupby(["yearMonth", "mes", "canal"], as_index=False).agg(
        sessions=("sessions", "sum"),
    ).sort_values("yearMonth")

    fig_geral = px.bar(
        df_geral, x="mes", y="sessions", color="canal",
        barmode="stack",
        category_orders={"mes": meses_label},
        labels={"mes": "", "sessions": "Sessoes", "canal": "Canal"},
        color_discrete_map=CORES_CANAL,
        title="Sessoes totais por canal",
    )
    fig_geral.update_layout(plot_bgcolor="white", legend_title="Canal")
    st.plotly_chart(fig_geral, use_container_width=True)

    col_ev1, col_ev2 = st.columns(2)
    with col_ev1:
        df_l_mes = df_l.groupby(["yearMonth", "mes"], as_index=False)["eventCount"].sum().sort_values("yearMonth")
        fig_l = px.bar(df_l_mes, x="mes", y="eventCount",
            title="Leads gerados — generate_lead (todos os canais)",
            category_orders={"mes": meses_label},
            labels={"mes": "", "eventCount": "Leads"},
            color_discrete_sequence=["#1a56db"])
        fig_l.update_layout(plot_bgcolor="white")
        st.plotly_chart(fig_l, use_container_width=True)

    with col_ev2:
        df_dl_mes = df_dl.groupby(["yearMonth", "mes"], as_index=False)["eventCount"].sum().sort_values("yearMonth")
        fig_dl2 = px.bar(df_dl_mes, x="mes", y="eventCount",
            title="Downloads gratuitos — lead_form_download (todos os canais)",
            category_orders={"mes": meses_label},
            labels={"mes": "", "eventCount": "Downloads"},
            color_discrete_sequence=["#059669"])
        fig_dl2.update_layout(plot_bgcolor="white")
        st.plotly_chart(fig_dl2, use_container_width=True)

    st.markdown("---")

    # ANALISTA DE CONTEUDO
    st.markdown("### Analista de Conteudo — Blog")

    df_blog     = df_s[df_s["canal"] == "Conteudo / Blog"]
    df_blog_mes = df_blog.groupby(["yearMonth", "mes"], as_index=False).agg(
        sessions=("sessions", "sum"),
        engagedSessions=("engagedSessions", "sum"),
        avgDur=("averageSessionDuration", "mean"),
        engRate=("engagementRate", "mean"),
    ).sort_values("yearMonth")

    leads_blog = df_l[df_l["canal"] == "Conteudo / Blog"]["eventCount"].sum()

    if not df_blog_mes.empty:
        cb1, cb2, cb3, cb4, cb5 = st.columns(5)
        cb1.metric("Sessoes totais", f"{df_blog_mes['sessions'].sum():,}".replace(",", "."))
        cb2.metric("Sessoes engajadas", f"{df_blog_mes['engagedSessions'].sum():,}".replace(",", "."))
        avg_eng = df_blog_mes["engRate"].mean() * 100
        cb3.metric("Engajamento medio", f"{avg_eng:.1f}%")
        avg_d = df_blog_mes["avgDur"].mean()
        cb4.metric("Duracao media", f"{int(avg_d // 60)}m {int(avg_d % 60)}s")
        cb5.metric("Leads via Blog", f"{leads_blog:,}".replace(",", "."))

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            fig_bs = px.line(df_blog_mes, x="mes", y="sessions",
                title="Sessoes via Blog — mes a mes",
                category_orders={"mes": meses_label},
                labels={"mes": "", "sessions": "Sessoes"},
                color_discrete_sequence=["#059669"], markers=True)
            fig_bs.update_layout(plot_bgcolor="white")
            st.plotly_chart(fig_bs, use_container_width=True)

        with col_b2:
            fig_be = px.line(df_blog_mes, x="mes", y="engRate",
                title="Taxa de engajamento via Blog",
                category_orders={"mes": meses_label},
                labels={"mes": "", "engRate": "Taxa"},
                color_discrete_sequence=["#059669"], markers=True)
            fig_be.update_yaxes(tickformat=".0%")
            fig_be.update_layout(plot_bgcolor="white")
            st.plotly_chart(fig_be, use_container_width=True)

        df_blog_camp = (
            df_blog.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
            .query("sessionCampaignName != '(not set)'")
            .sort_values("sessions", ascending=False)
            .head(20)
            .rename(columns={"sessionCampaignName": "Artigo / Campanha", "sessions": "Sessoes"})
        )
        if not df_blog_camp.empty:
            st.caption("Top artigos e campanhas do Blog")
            st.dataframe(df_blog_camp, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de Blog no periodo.")

    st.markdown("---")

    # ANALISTA DE AUTOMACAO
    st.markdown("### Analista de Automacao — E-mail / Zoho Marketing Hub")

    df_email     = df_s[df_s["canal"] == "E-mail / Automacao"]
    df_email_mes = df_email.groupby(["yearMonth", "mes"], as_index=False).agg(
        sessions=("sessions", "sum"),
        engagedSessions=("engagedSessions", "sum"),
        avgDur=("averageSessionDuration", "mean"),
    ).sort_values("yearMonth")

    leads_email = df_l[df_l["canal"] == "E-mail / Automacao"]["eventCount"].sum()
    dl_email    = df_dl[df_dl["canal"] == "E-mail / Automacao"]["eventCount"].sum()

    if not df_email_mes.empty:
        ce1, ce2, ce3, ce4 = st.columns(4)
        ce1.metric("Sessoes totais", f"{df_email_mes['sessions'].sum():,}".replace(",", "."))
        ce2.metric("Sessoes engajadas", f"{df_email_mes['engagedSessions'].sum():,}".replace(",", "."))
        ce3.metric("Leads via E-mail", f"{leads_email:,}".replace(",", "."))
        ce4.metric("Downloads via E-mail", f"{dl_email:,}".replace(",", "."))

        col_em1, col_em2 = st.columns(2)
        with col_em1:
            fig_es = px.bar(df_email_mes, x="mes", y="sessions",
                title="Sessoes via E-mail — mes a mes",
                category_orders={"mes": meses_label},
                labels={"mes": "", "sessions": "Sessoes"},
                color_discrete_sequence=["#7c3aed"])
            fig_es.update_layout(plot_bgcolor="white")
            st.plotly_chart(fig_es, use_container_width=True)

        with col_em2:
            df_l_email_mes = (
                df_l[df_l["canal"] == "E-mail / Automacao"]
                .groupby(["yearMonth", "mes"], as_index=False)["eventCount"].sum()
                .sort_values("yearMonth")
            )
            if not df_l_email_mes.empty:
                fig_el = px.bar(df_l_email_mes, x="mes", y="eventCount",
                    title="Leads gerados via E-mail — mes a mes",
                    category_orders={"mes": meses_label},
                    labels={"mes": "", "eventCount": "Leads"},
                    color_discrete_sequence=["#7c3aed"])
                fig_el.update_layout(plot_bgcolor="white")
                st.plotly_chart(fig_el, use_container_width=True)

        df_email_camp = (
            df_email.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
            .query("sessionCampaignName != '(not set)'")
            .sort_values("sessions", ascending=False)
            .head(20)
            .rename(columns={"sessionCampaignName": "Campanha / E-mail", "sessions": "Sessoes"})
        )
        if not df_email_camp.empty:
            st.caption("Top campanhas de e-mail")
            st.dataframe(df_email_camp, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de e-mail no periodo.")

    st.markdown("---")

    # ANALISTA DE MIDIAS DIGITAIS
    st.markdown("### Analista de Midias Digitais — Trafego Pago e Social")

    df_midia     = df_s[df_s["canal"].isin(CANAIS_MIDIA)]
    df_midia_mes = df_midia.groupby(["yearMonth", "mes", "canal"], as_index=False).agg(
        sessions=("sessions", "sum"),
        engagedSessions=("engagedSessions", "sum"),
        avgDur=("averageSessionDuration", "mean"),
    ).sort_values("yearMonth")

    leads_midia = df_l[df_l["canal"].isin(CANAIS_MIDIA)]["eventCount"].sum()
    dl_midia    = df_dl[df_dl["canal"].isin(CANAIS_MIDIA)]["eventCount"].sum()

    if not df_midia_mes.empty:
        cm1, cm2, cm3, cm4 = st.columns(4)
        cm1.metric("Sessoes totais (midia)", f"{df_midia_mes['sessions'].sum():,}".replace(",", "."))
        cm2.metric("Sessoes engajadas", f"{df_midia_mes['engagedSessions'].sum():,}".replace(",", "."))
        cm3.metric("Leads gerados", f"{leads_midia:,}".replace(",", "."))
        cm4.metric("Downloads", f"{dl_midia:,}".replace(",", "."))

        fig_midia_stack = px.bar(
            df_midia_mes, x="mes", y="sessions", color="canal",
            barmode="stack",
            title="Sessoes por canal de midia — mes a mes",
            category_orders={"mes": meses_label},
            labels={"mes": "", "sessions": "Sessoes", "canal": "Canal"},
            color_discrete_map=CORES_CANAL,
        )
        fig_midia_stack.update_layout(plot_bgcolor="white")
        st.plotly_chart(fig_midia_stack, use_container_width=True)

        df_l_midia_mes = (
            df_l[df_l["canal"].isin(CANAIS_MIDIA)]
            .groupby(["yearMonth", "mes", "canal"], as_index=False)["eventCount"].sum()
            .sort_values("yearMonth")
        )
        if not df_l_midia_mes.empty:
            fig_l_midia = px.bar(df_l_midia_mes, x="mes", y="eventCount", color="canal",
                barmode="group",
                title="Leads gerados por canal de midia",
                category_orders={"mes": meses_label},
                labels={"mes": "", "eventCount": "Leads", "canal": "Canal"},
                color_discrete_map=CORES_CANAL)
            fig_l_midia.update_layout(plot_bgcolor="white")
            st.plotly_chart(fig_l_midia, use_container_width=True)

        df_midia_camp = (
            df_midia.groupby(["canal", "sessionCampaignName"], as_index=False)["sessions"].sum()
            .query("sessionCampaignName != '(not set)'")
            .sort_values("sessions", ascending=False)
            .head(20)
            .rename(columns={"canal": "Canal", "sessionCampaignName": "Campanha", "sessions": "Sessoes"})
        )
        if not df_midia_camp.empty:
            st.caption("Top campanhas de midia paga e social")
            st.dataframe(df_midia_camp, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de midia paga/social no periodo.")

except Exception as e:
    st.error(f"Erro ao conectar ao GA4: {e}")
    st.info("Verifique se os secrets estao configurados no Streamlit Cloud.")
