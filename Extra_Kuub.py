import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="Extra Afval Dashboard", layout="wide")

st.title("🚛 Extra Afval Dashboard")
st.write("""
Analyseer automatisch extra afval per order en zie direct hoeveel **extra bakken** zijn geledigd.  
Deze versie berekent het aantal extra bakken op basis van **Extra m³ / Volume per bak**.
""")

# --- Upload ---
uploaded_file = st.file_uploader("📂 Upload je Excel-bestand", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success(f"✅ Bestand geladen: {uploaded_file.name}")

    # Controle op verplichte kolommen
    required_cols = ["Locatienummer", "Klantnaam", "Ophaaldatum", "Volume", "# uitgevoerd", "Extra m3"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"❌ Ontbrekende kolommen: {', '.join(missing_cols)}")
        st.stop()

    # --- Data voorbereiden ---
    df["Ophaaldatum"] = pd.to_datetime(df["Ophaaldatum"], errors="coerce")

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

    # --- Berekeningen ---
    df["Volume_m3"] = df["Volume"] / 1000  # volume omzetten naar m³
    df["Extra_bakken"] = df["Extra m3"] / df["Volume_m3"]
    df["Extra_kuub"] = df["Extra m3"] + (df["Volume_m3"] * df["# uitgevoerd"])

    # --- Instellingen ---
    st.markdown("### 🎚️ Instellingen voor signalering")
    min_extra_bakken = st.slider("Minimaal aantal extra bakken (boven gepland)", 0.0, 10.0, 2.0, 0.1)
    min_extra_kuub = st.slider("Minimaal totaal extra volume (m³)", 0.0, 10.0, 1.0, 0.1)

    # --- Dynamische filtering ---
    df["Extra_bakken"] = df["Extra m3"] / (df["Volume"] / 1000)
    df["Totaal_bakken"] = df["# uitgevoerd"] + df["Extra_bakken"]

    # Alleen flaggen als er echt méér extra bakken zijn dan de drempel
    df_flagged = df[df["Extra_bakken"] > min_extra_bakken]

    st.subheader(f"🚩 Geflagde orders (> {min_extra_bakken} extra bakken of > {min_extra_kuub} m³)")
    st.dataframe(df_flagged)

    # === Dashboard Overzicht ===
    st.markdown("## 📈 Dashboard-overzicht")
    total_kuub = df["Extra m3"].sum()
    avg_kuub = df["Extra m3"].mean()
    total_orders = len(df)
    avg_extra_bakken = df["Extra_bakken"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totale extra kuub", f"{total_kuub:,.1f} m³")
    c2.metric("Gemiddeld per order", f"{avg_kuub:,.2f} m³")
    c3.metric("Gemiddelde extra bakken", f"{avg_extra_bakken:,.2f}")
    c4.metric("Aantal orders", f"{total_orders:,}")

    # === Grafieken ===
    st.markdown("## 📊 Grafieken")
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
            df_flagged.groupby("Locatienummer")
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

    # === Download flagged ===
    csv_flagged = df_flagged.to_csv(index=False).encode("utf-8")

    st.markdown("## 📤 Download geflagde orders als Excel")

    if not df_flagged.empty:
        # We behouden de kolomvolgorde van de originele data
        originele_kolommen = list(df.columns)

        # Alleen de geflagde rijen exporteren, met originele kolommen + nieuwe berekende kolommen
        export_df = df_flagged.copy()
        for col in ["Extra_bakken", "Totaal_bakken"]:
            if col not in export_df.columns:
                export_df[col] = np.nan

        # Combineer kolommen: eerst originele, dan onze berekende extra’s
        export_df = export_df[originele_kolommen + ["Extra_bakken", "Totaal_bakken"]]

        # Excel-bestand maken in geheugen
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Geflagde orders")

        # Terug naar streamlit-download knop
        st.download_button(
            label="📥 Download geflagde orders (Excel)",
            data=output.getvalue(),
            file_name="geflagde_orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Geen geflagde orders om te exporteren.")

else:
    st.info("Upload eerst een Excel-bestand om te beginnen.")
