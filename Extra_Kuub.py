import streamlit as st
import pandas as pd
import numpy as np
import io
import locale

# ======= Locale instellingen =======
try:
    locale.setlocale(locale.LC_TIME, 'nl_NL.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'nl_NL')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'C')

# ======= Pagina setup =======
st.set_page_config(page_title="Extra Afval Dashboard", layout="wide")

# ======= CSS inladen =======
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")

# ======= Titel =======
st.title("🚛 Extra Afval Dashboard")
st.write("""
Analyseer automatisch extra afval per order en zie direct hoeveel **extra bakken** zijn geledigd.  
Deze versie berekent het aantal extra bakken op basis van **Extra m³ / Volume per bak**.
""")

# ======= Upload bestand =======
uploaded_file = st.file_uploader("📂 Upload je Excel-bestand", type=["xlsx"])

if uploaded_file:

    # --- Slimme Excel-lezer ---
    def read_excel_smart(uploaded_file):
        temp_df = pd.read_excel(uploaded_file, header=None)
        for i in range(len(temp_df)):
            row_values = temp_df.iloc[i].astype(str).tolist()
            if any(x in row_values for x in ["Ophaaldatum", "Locatienummer", "Klantnaam", "# uitgevoerd", "Extra m3"]):
                df = pd.read_excel(uploaded_file, skiprows=i)
                return df, i
        df = pd.read_excel(uploaded_file)
        return df, 0

    df, header_row = read_excel_smart(uploaded_file)
    st.success(f"✅ Bestand geladen vanaf rij {header_row + 1}")

    # --- Controle verplichte kolommen ---
    required_cols = ["Locatienummer", "Klantnaam", "Ophaaldatum", "Volume", "# uitgevoerd", "Extra m3"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"❌ Ontbrekende kolommen: {', '.join(missing_cols)}")
        st.stop()

    # --- Dataverwerking ---
    df["Ophaaldatum_dt"] = pd.to_datetime(df["Ophaaldatum"], errors="coerce", dayfirst=True)
    df["Ophaaldatum"] = df["Ophaaldatum"].dt.strftime("%d-%m-%Y")

    def clean_to_float(series):
        return (
            series.astype(str)
            .str.replace(",", ".", regex=False)
            .str.replace(r"[^\d\.]", "", regex=True)
            .replace("", np.nan)
            .astype(float)
            .fillna(0)
        )

    for col in ["Volume", "# uitgevoerd", "Extra m3"]:
        if col in df.columns:
            df[col] = clean_to_float(df[col])

    df["Volume_m3"] = df["Volume"] / 1000  
    df["Extra_bakken"] = df["Extra m3"] / df["Volume_m3"]
    df["Extra_kuub"] = df["Extra m3"] + (df["Volume_m3"] * df["# uitgevoerd"])

    # ========== FILTERS BLOK ==========
    st.markdown('<div class="block-box">', unsafe_allow_html=True)
    st.markdown('<div class="block-title">🎚️ Instellingen voor signalering</div>', unsafe_allow_html=True)

    min_extra_bakken = st.slider("Minimaal aantal extra bakken (boven gepland)", 0.0, 10.0, 2.0, 0.1)
    min_extra_kuub = st.slider("Minimaal totaal extra volume (m³)", 0.0, 10.0, 1.0, 0.1)

    df["Ophaaldatum_dt"] = pd.to_datetime(df["Ophaaldatum"], errors="coerce", dayfirst=True)
    df["Ophaaldatum_nl"] = df["Ophaaldatum_dt"].dt.strftime("%d-%m-%Y")

    min_date = df["Ophaaldatum_dt"].min()
    max_date = df["Ophaaldatum_dt"].max()

    start_date, end_date = st.date_input(
        "📅 Kies een datumbereik",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD-MM-YYYY"
    )

    st.write(f"📆 Geselecteerde periode: {start_date.strftime('%d-%m-%Y')} t/m {end_date.strftime('%d-%m-%Y')}")

    df = df[(df["Ophaaldatum_dt"] >= pd.to_datetime(start_date)) & (df["Ophaaldatum_dt"] <= pd.to_datetime(end_date))]

    st.markdown('</div>', unsafe_allow_html=True)

    # ========== DASHBOARD BLOK ==========
    st.markdown('<div class="block-box">', unsafe_allow_html=True)
    st.markdown('<div class="block-title">📈 Dashboard-overzicht</div>', unsafe_allow_html=True)

    total_kuub = df["Extra m3"].sum()
    avg_kuub = df["Extra m3"].mean()
    total_orders = len(df)
    avg_extra_bakken = df["Extra_bakken"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totale extra kuub", f"{total_kuub:,.1f} m³")
    c2.metric("Gemiddeld per order", f"{avg_kuub:,.2f} m³")
    c3.metric("Gemiddelde extra bakken", f"{avg_extra_bakken:,.2f}")
    c4.metric("Aantal orders", f"{total_orders:,}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ========== GRAFIEKEN BLOK ==========
    st.markdown('<div class="block-box">', unsafe_allow_html=True)
    st.markdown('<div class="block-title">📊 Grafieken</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Per dag", "Per klant", "Per locatie"])

    with tab1:
        daily = df.groupby("Ophaaldatum")["Extra m3"].sum().reset_index()
        st.subheader("📆 Totaal extra m³ per dag")
        st.line_chart(daily.set_index("Ophaaldatum"))

    with tab2:
        klant = df.groupby("Klantnaam")["Extra m3"].sum().sort_values(ascending=False).head(20)
        st.subheader("👥 Top 20 klanten met meeste extra afval")
        st.bar_chart(klant)

    with tab3:
        locatie = (
            df.groupby("Locatienummer")
            .agg(
                Aantal_orders=("Ophaaldatum", "count"),
                Gemiddeld_extra_bakken=("Extra_bakken", "mean"),
                Totaal_extra_bakken=("Extra_bakken", "sum"),
                Totaal_extra_kuub=("Extra m3", "sum"),
            )
            .sort_values("Aantal_orders", ascending=False)
        )
        st.subheader("🏭 Locaties met herhaald extra afval")
        st.dataframe(locatie)
        st.bar_chart(locatie["Aantal_orders"].head(10))

        csv = locatie.to_csv().encode("utf-8")
        st.download_button("📥 Download overzicht per locatie", csv, "overzicht_per_locatie.csv")

    st.markdown('</div>', unsafe_allow_html=True)

    # ========== GEFLAGDE ORDERS BLOK ==========
    st.markdown('<div class="block-box">', unsafe_allow_html=True)
    st.markdown(f'<div class="block-title">🚩 Geflagde orders (> {min_extra_bakken} bakken of > {min_extra_kuub} m³)</div>', unsafe_allow_html=True)

    df_filtered_volume = df[df["Extra m3"] > min_extra_kuub]
    df_flagged = df_filtered_volume[df_filtered_volume["Extra_bakken"] > min_extra_bakken]

    st.dataframe(df_flagged)

    if not df_flagged.empty:
        originele_kolommen = list(df.columns)
        export_df = df_flagged.copy()

        for col in ["Extra_bakken", "Totaal_bakken"]:
            if col not in export_df.columns:
                export_df[col] = np.nan

        export_df = export_df[originele_kolommen + ["Extra_bakken", "Totaal_bakken"]]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Geflagde orders")

        st.download_button(
            label="📥 Download geflagde orders (Excel)",
            data=output.getvalue(),
            file_name="geflagde_orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Geen geflagde orders om te exporteren.")

    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("Upload eerst een Excel-bestand om te beginnen.")
