"""
GeoAI Analytics - Real-Time Operational & Analytical Dashboard.
Consumes the Gold Layer (analytics_metrics) and helper views in PostgreSQL.
Features Near Real-Time (NRT) auto-refresh using native Streamlit fragments.
"""

from datetime import datetime
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.queries import (
    fetch_city_summary,
    fetch_gold_metrics,
    fetch_kpis,
    fetch_recent_transactions,
)

# Page configuration
st.set_page_config(
    page_title="GeoAI Analytics | Operational Hub",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Dark & Modern Theme - Inter Typography & Elevated Glassmorphism)
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .block-container {
            padding-top: 1.8rem !important;
            padding-bottom: 2rem !important;
        }

        .main {
            background-color: #0e1117;
        }

        .metric-card {
            background: linear-gradient(145deg, #161f30 0%, #0d1522 100%);
            border: 1px solid #1e293b;
            border-top: 3px solid #38bdf8;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            margin-bottom: 12px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .metric-card:hover {
            transform: translateY(-3px);
            border-color: #38bdf8;
            box-shadow: 0 8px 22px -2px rgba(56, 189, 248, 0.28);
        }
        .metric-label {
            font-size: 0.8rem;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .metric-value {
            font-size: 1.85rem;
            color: #f8fafc;
            font-weight: 700;
            margin-top: 5px;
            letter-spacing: -0.02em;
        }
        .metric-sub {
            font-size: 0.8rem;
            color: #34d399;
            font-weight: 500;
            margin-top: 3px;
        }
        .section-header {
            font-size: 1.2rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-top: 20px;
            margin-bottom: 12px;
            border-left: 4px solid #38bdf8;
            padding-left: 12px;
            letter-spacing: -0.01em;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=130)
    else:
        st.title("🌍")
    st.title("GeoAI Analytics")
    st.caption("AI & Data Engineering Recovery Monitor")
    st.markdown("---")

    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.rerun()

    st.markdown("### ⏱️ Modo Near Real-Time (NRT)")
    auto_refresh = st.toggle(
        "Auto-refresco NRT",
        value=True,
        help="Actualiza métricas, gráficos y tablas automáticamente sin parpadeos ni recargas de página.",
    )
    refresh_interval = st.selectbox(
        "Frecuencia de sincronización",
        options=[5, 10, 15, 30],
        index=1,
        format_func=lambda s: f"Cada {s} segundos",
        disabled=not auto_refresh,
    )

    st.markdown("---")
    st.markdown("### Filtros Globales")
    gold_df_raw = fetch_gold_metrics()
    available_cities = sorted(gold_df_raw["city"].unique()) if not gold_df_raw.empty else []
    selected_cities = st.multiselect("Filtrar por Ciudades", options=available_cities, default=[])

    st.markdown("---")
    st.markdown("### Estado de Capas Medallón")
    st.markdown("🟢 **Bronze**: `agent_interactions`")
    st.markdown("🟢 **Silver**: `enriched_transactions`")
    st.markdown("🟢 **Gold**: `analytics_metrics`")

# Header
st.title("🌍 GeoAI Recovery Hub - Centro de Control")
st.markdown(
    "Monitoreo en tiempo real del agente de reemplazo, transacciones enriquecidas con MCP "
    "y métricas analíticas agregadas de la **Capa Gold**."
)


# Native Streamlit fragment for smooth near real-time rendering
run_every_sec = refresh_interval if auto_refresh else None


@st.fragment(run_every=run_every_sec)
def render_dashboard_view(cities_filter: list, is_nrt_active: bool, interval_sec: int):
    # Fetch fresh metrics inside the fragment
    kpis = fetch_kpis()
    gold_df_current = fetch_gold_metrics()
    if cities_filter and not gold_df_current.empty:
        gold_df_current = gold_df_current[gold_df_current["city"].isin(cities_filter)]

    # Subtitle with live synchronization indicator
    now_str = datetime.now().strftime("%H:%M:%S")
    if is_nrt_active:
        st.caption(f"🟢 **Sincronización NRT Activa**: Actualizando automáticamente cada **{interval_sec}s** • Última lectura: `{now_str}`")
    else:
        st.caption(f"⚪ **Modo Manual**: Presione *'Actualizar Datos'* en la barra lateral para refrescar • Última lectura: `{now_str}`")

    # Row 1: Executive KPI Cards
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Transacciones</div>
                <div class="metric-value">{kpis['total_transactions']:,}</div>
                <div class="metric-sub">Total registradas</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Usuarios Únicos</div>
                <div class="metric-value">{kpis['unique_users']:,}</div>
                <div class="metric-sub">Impactados</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Tokens Totales</div>
                <div class="metric-value">{kpis['total_tokens']:,}</div>
                <div class="metric-sub">Consumo LLM</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Latencia Media</div>
                <div class="metric-value">{kpis['avg_latency_ms']} ms</div>
                <div class="metric-sub">Tiempo respuesta</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with c5:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Sentimiento Positivo</div>
                <div class="metric-value">{kpis['positive_sentiment_rate']}%</div>
                <div class="metric-sub">{kpis['positive_count']} positivos</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with c6:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Urgencia Alta</div>
                <div class="metric-value">{kpis['high_urgency_rate']}%</div>
                <div class="metric-sub">{kpis['high_urg_count']} críticas</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Visualizations Row 1: Geographic Distribution & Sentiment/Urgency Matrix
    v_col1, v_col2 = st.columns([3, 2])

    with v_col1:
        st.markdown('<div class="section-header">📍 Distribución Geográfica y Clima por Ciudad</div>', unsafe_allow_html=True)
        if not gold_df_current.empty:
            city_agg = (
                gold_df_current.groupby(["city", "country"])
                .agg({
                    "total_transactions": "sum",
                    "avg_temperature": "mean",
                    "most_common_weather": "first",
                })
                .reset_index()
                .sort_values(by="total_transactions", ascending=True)
            )

            fig_geo = px.bar(
                city_agg,
                x="total_transactions",
                y="city",
                orientation="h",
                color="avg_temperature",
                color_continuous_scale=[[0, "#0369a1"], [0.5, "#0ea5e9"], [1, "#38bdf8"]],
                labels={
                    "total_transactions": "Total Transacciones",
                    "city": "",
                    "avg_temperature": "Temp Promedio (°C)",
                },
                title="Transacciones por Ciudad con Correlación de Temperatura",
                hover_data=["country", "most_common_weather"],
            )
            fig_geo.update_layout(
                template="plotly_dark",
                height=380,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis_title="",
                xaxis=dict(gridcolor="#1e293b"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_geo, use_container_width=True)
        else:
            st.info("Esperando datos de la capa Gold... Inicie el generador de transacciones.")

    with v_col2:
        st.markdown('<div class="section-header">🧠 Análisis de Sentimiento & Urgencia</div>', unsafe_allow_html=True)
        sent_data = {
            "Categoría": ["Positivo", "Neutral", "Negativo"],
            "Cantidad": [kpis["positive_count"], kpis["neutral_count"], kpis["negative_count"]],
        }
        df_sent = pd.DataFrame(sent_data)

        if df_sent["Cantidad"].sum() > 0:
            fig_donut = px.pie(
                df_sent,
                values="Cantidad",
                names="Categoría",
                hole=0.55,
                color="Categoría",
                color_discrete_map={
                    "Positivo": "#48bb78",
                    "Neutral": "#a0aec0",
                    "Negativo": "#f56565",
                },
                title="Distribución de Sentimiento Analizado por LLM",
            )
            fig_donut.update_layout(
                template="plotly_dark",
                height=380,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No hay datos de sentimiento disponibles aún.")

    # Visualizations Row 2: Operational Trends & Query Typology
    v_col3, v_col4 = st.columns(2)

    with v_col3:
        st.markdown('<div class="section-header">📈 Tendencia Diaria de Transacciones y Tokens</div>', unsafe_allow_html=True)
        if not gold_df_current.empty:
            daily = (
                gold_df_current.groupby("metric_date")
                .agg({"total_transactions": "sum", "total_tokens_used": "sum"})
                .reset_index()
                .sort_values(by="metric_date")
            )
            fig_trend = go.Figure()
            fig_trend.add_trace(
                go.Bar(
                    x=daily["metric_date"],
                    y=daily["total_transactions"],
                    name="Transacciones",
                    marker_color="#38bdf8",
                )
            )
            fig_trend.add_trace(
                go.Scatter(
                    x=daily["metric_date"],
                    y=daily["total_tokens_used"],
                    name="Tokens Consumidos",
                    yaxis="y2",
                    line=dict(color="#f59e0b", width=3),
                )
            )
            fig_trend.update_layout(
                template="plotly_dark",
                height=340,
                yaxis=dict(title="N° Transacciones", gridcolor="#1e293b"),
                yaxis2=dict(title="Tokens", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
                xaxis=dict(gridcolor="#1e293b"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Sin registros diarios en Gold.")

    with v_col4:
        st.markdown('<div class="section-header">🔍 Tipos de Consultas y Horas Pico</div>', unsafe_allow_html=True)
        if not gold_df_current.empty:
            query_dist = gold_df_current["most_common_query_type"].value_counts().reset_index()
            query_dist.columns = ["Tipo de Consulta", "Frecuencia"]
            fig_query = px.bar(
                query_dist,
                x="Tipo de Consulta",
                y="Frecuencia",
                color="Tipo de Consulta",
                color_discrete_sequence=px.colors.qualitative.Pastel,
                title="Categorías de Consultas Más Frecuentes",
            )
            fig_query.update_layout(
                template="plotly_dark",
                height=340,
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#1e293b"),
                xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_query, use_container_width=True)
        else:
            st.info("Sin clasificación de consultas disponible.")

    st.markdown("---")

    # Data Explorer Tabs
    st.markdown('<div class="section-header">🗂️ Explorador de Datos Medallón</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs([
        "🏆 Capa Gold (analytics_metrics)",
        "⚡ Transacciones Recientes (v_recent_enriched_transactions)",
        "🏙️ Resumen por Ubicación (v_location_stats)",
    ])

    with tab1:
        if not gold_df_current.empty:
            st.dataframe(gold_df_current, use_container_width=True)
            csv_gold = gold_df_current.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Descargar CSV Capa Gold", csv_gold, "gold_analytics_metrics.csv", "text/csv")
        else:
            st.info("La tabla analytics_metrics está vacía.")

    with tab2:
        recent_df = fetch_recent_transactions(limit=50)
        if not recent_df.empty:
            st.dataframe(recent_df, use_container_width=True)
        else:
            st.info("No hay transacciones recientes registradas.")

    with tab3:
        loc_stats_df = fetch_city_summary()
        if not loc_stats_df.empty:
            st.dataframe(loc_stats_df, use_container_width=True)
        else:
            st.info("No hay estadísticas por ciudad disponibles.")


# Render dashboard with selected settings
render_dashboard_view(
    cities_filter=selected_cities,
    is_nrt_active=auto_refresh,
    interval_sec=refresh_interval,
)
