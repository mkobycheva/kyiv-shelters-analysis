import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Аналіз укриттів Києва",
    page_icon="🏠",
    layout="wide",
)

# ── Custom font (Google Fonts) ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Commissioner:wght@100..900&family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap');

* {
    font-family: 'Montserrat', sans-serif !important;
}

[data-testid="metric-container"] {
    border: none !important;
    box-shadow: none !important;
}

[data-testid="collapsedControl"] {
    display: none !important;
}

</style>
""", unsafe_allow_html=True)

import base64
with open("header.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()
st.markdown(f"""
<div style="position:relative; margin-bottom:2rem;">
    <img src="data:image/jpeg;base64,{img_b64}" style="width:100%; height:350px; object-fit:cover; border-radius:8px;">
    <div style="position:absolute; bottom:2rem; left:2rem; color:white;">
        <h1 style="font-size:2.5rem; margin:0; text-shadow:0 2px 8px rgba(0,0,0,0.7);">Чи вміщається Київ в укриття?</h1>
        <p style="margin:0.5rem 0 0; text-shadow:0 1px 4px rgba(0,0,0,0.7);">Аналіз стану і доступності захисних споруд за даними з відкритих джерел</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    filepath = 'kyiv_shelters.json'
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    def nested(record, key):
        obj = record.get(key)
        if isinstance(obj, dict):
            return obj.get("imya")
        return None

    rows = []
    for d in data:
        street = d.get("nazvaVulytsi") or ""
        number = d.get("inshiRekvizytyAdresy") or ""
        address = f"{street}, {number}".strip(", ")
        rows.append({
            "id":                 d.get("id"),
            "district":           nested(d, "NazvaRayonuMista"),
            "address":            address,
            "lat":                d.get("shyrota"),
            "lon":                d.get("dovhota"),
            "capacity":           d.get("mistkistOsib"),
            "area_m2":            d.get("ploshcha"),
            "shelter_kind":       nested(d, "VydSporudy"),
            "location_type":      nested(d, "VidnosneRozmishchennya"),
            "functional_purpose": nested(d, "FunktsionalnePryznachennya"),
            "water":              d.get("systemaVodopostachannya"),
            "heating":            d.get("systemaOpalennya"),
            "power":              d.get("systemaEletrozhyvlennya"),
            "communication":      nested(d, "NayavniZasobyZvyazku"),
            "accessible_mgn":     d.get("nayavnistDostupuMalomobilnykhVerstvNaselennya"),
            "open_access":        nested(d, "BezpereshkodnyyDostup"),
        })

    df = pd.DataFrame(rows)
    df['lat'] = pd.to_numeric(df['lat'].astype(str).str.rstrip(', '), errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df['accessible_mgn'] = df['accessible_mgn'].fillna(False).astype(bool)

    def clean_utility_status(text):
        if pd.isna(text) or text is None:
            return "Невідомо"
        t = str(text).strip().lower()
        bad = ["відсутн", "не передбачен", "немає", "несправн", "відключ",
               "-", "не має", "не застосовується", "не визначалась"]
        if any(k in t for k in bad):
            return "Відсутня/Несправна"
        good = ["наяв", "централ", "передбач", "мереж", "забезпеч", "справн",
                "електр", "зовнішн", "працює", "водян", "радіатор", "резервуар",
                "баки", "бутл", "ємност", "укомплектов", "бутильован"]
        if any(k in t for k in good):
            return "Наявна/Справна"
        return "Інше/Невідомо"

    def clean_communication(text):
        if pd.isna(text) or text is None:
            return "Невідомо"
        t = str(text).strip().lower()
        if "несправна" in t:
            return "Зв'язок відсутній"
        if "справна" in t and ("wi-fi" in t or "провідна" in t):
            return "Є інтернет (Wi-Fi/Дротовий)"
        if "відсутні" in t:
            return "Зв'язок відсутній"
        return "Інше/Невідомо"

    df["clean_water"]         = df["water"].apply(clean_utility_status)
    df["clean_heating"]       = df["heating"].apply(clean_utility_status)
    df["clean_power"]         = df["power"].apply(clean_utility_status)
    df["clean_communication"] = df["communication"].apply(clean_communication)

    return df


@st.cache_data
def build_aggregates(df):
    district_population_data = {
        "Дніпровський": 354_700, "Святошинський": 340_700,
        "Подільський": 198_100,  "Деснянський": 358_300,
        "Голосіївський": 247_600, "Солом'янський": 383_259,
        "Оболонський": 319_000,  "Печерський": 152_000,
        "Шевченківський": 218_900, "Дарницький": 314_700,
    }
    district_population = pd.DataFrame(
        district_population_data.items(), columns=["district", "population"]
    )

    district_cap = (
        df.groupby("district")
        .agg(total_capacity=("capacity", "sum"),
             total_area=("area_m2", "sum"),
             shelter_count=("capacity", "count"))
        .reset_index()
        .merge(district_population, on="district", how="left")
    )
    district_cap["population_by_capacity"] = (
        district_cap["population"] / district_cap["total_capacity"]
    ).round(1)
    district_cap["area_per_person"] = (
        district_cap["total_area"] / district_cap["population"]
    ).round(2)

    kyiv_cap = pd.DataFrame([{
        "total_capacity": df["capacity"].sum(),
        "total_area":     df["area_m2"].sum(),
        "shelter_count":  len(df),
        "population":     district_population["population"].sum(),
    }])
    kyiv_cap["population_by_capacity"] = (
        kyiv_cap["population"] / kyiv_cap["total_capacity"]
    ).round(1)

    def dist_pct(col):
        g = df.groupby(["district", col]).agg(shelter_count=(col, "count")).reset_index()
        g["percent"] = (
            g["shelter_count"] / g.groupby("district")["shelter_count"].transform("sum") * 100
        ).round(1)
        return g

    def kyiv_pct(col):
        g = df.groupby(col).agg(shelter_count=(col, "count")).reset_index()
        g["percent"] = (g["shelter_count"] / g["shelter_count"].sum() * 100).round(1)
        return g.sort_values("shelter_count", ascending=False)

    district_shelter_kinds  = dist_pct("shelter_kind")
    kyiv_shelter_kinds      = kyiv_pct("shelter_kind")
    district_location_types = dist_pct("location_type")
    kyiv_location_types     = kyiv_pct("location_type")
    district_functional     = dist_pct("functional_purpose")
    kyiv_functional         = kyiv_pct("functional_purpose")

    def make_report(clean_col, good_label, bad_label):
        counts = pd.crosstab(df["district"], df[clean_col])
        pcts   = pd.crosstab(df["district"], df[clean_col], normalize="index") * 100
        r = pd.DataFrame(index=counts.index)
        r["Всього укриттів"] = df["district"].value_counts()
        r[f"{good_label} (abs)"] = counts.get(good_label, 0)
        r[f"{good_label} (%)"]   = pcts.get(good_label, pd.Series(0, index=pcts.index)).round(1)
        r[f"{bad_label} (abs)"]  = counts.get(bad_label, 0)
        r[f"{bad_label} (%)"]    = pcts.get(bad_label, pd.Series(0, index=pcts.index)).round(1)
        r = r.loc[pcts.sort_values(by=good_label, ascending=False).index]
        return r.reset_index().rename(columns={"district": "Район міста"})

    water_report   = make_report("clean_water",   "Наявна/Справна", "Відсутня/Несправна")
    heating_report = make_report("clean_heating",  "Наявна/Справна", "Відсутня/Несправна")
    power_report   = make_report("clean_power",    "Наявна/Справна", "Відсутня/Несправна")
    comm_report    = make_report("clean_communication", "Є інтернет (Wi-Fi/Дротовий)", "Зв'язок відсутній")

    df_total_status = {
        "Водопостачання": round((df["clean_water"] == "Наявна/Справна").mean() * 100, 1),
        "Опалення":       round((df["clean_heating"] == "Наявна/Справна").mean() * 100, 1),
        "Електропостачання": round((df["clean_power"] == "Наявна/Справна").mean() * 100, 1),
        "Інтернет":       round((df["clean_communication"] == "Є інтернет (Wi-Fi/Дротовий)").mean() * 100, 1),
    }

    mgn_counts = pd.crosstab(df["district"], df["accessible_mgn"])
    mgn_pcts   = pd.crosstab(df["district"], df["accessible_mgn"], normalize="index") * 100
    mgn_report = pd.DataFrame(index=mgn_counts.index)
    mgn_report["Всього укриттів"]        = df["district"].value_counts()
    mgn_report["Доступно для МГН (abs)"] = mgn_counts.get(True, 0)
    mgn_report["Доступно для МГН (%)"]   = mgn_pcts.get(True, pd.Series(0, index=mgn_pcts.index)).round(1)
    mgn_report["Недоступно (abs)"]       = mgn_counts.get(False, 0)
    mgn_report["Недоступно (%)"]         = mgn_pcts.get(False, pd.Series(0, index=mgn_pcts.index)).round(1)
    mgn_report = mgn_report.loc[mgn_pcts.sort_values(by=True, ascending=False).index]
    mgn_report = mgn_report.reset_index().rename(columns={"district": "Район міста"})
    df_total_mgn = round(df["accessible_mgn"].mean() * 100, 1)

    district_open_access = dist_pct("open_access")
    kyiv_open_access     = kyiv_pct("open_access")

    return dict(
        district_cap=district_cap, kyiv_cap=kyiv_cap,
        district_shelter_kinds=district_shelter_kinds, kyiv_shelter_kinds=kyiv_shelter_kinds,
        district_location_types=district_location_types, kyiv_location_types=kyiv_location_types,
        district_functional=district_functional, kyiv_functional=kyiv_functional,
        water_report=water_report, heating_report=heating_report,
        power_report=power_report, comm_report=comm_report,
        df_total_status=df_total_status,
        mgn_report=mgn_report, df_total_mgn=df_total_mgn,
        district_open_access=district_open_access, kyiv_open_access=kyiv_open_access,
    )


# ── Load ──────────────────────────────────────────────────────────────────────
df = load_data()
agg = build_aggregates(df)

with open("kyiv.34272c8c.geojson", encoding="utf-8") as f:
    geojson = json.load(f)

for feat in geojson["features"]:
    feat["properties"]["district"] = feat["properties"]["NAME"].replace(" район", "")

# ── Sidebar nav ───────────────────────────────────────────────────────────────
# st.sidebar.title("Укриття Києва")
section = st.sidebar.radio(
    "Розділ",
    ["Місткість", "Типи укриттів", "Стан систем", "Доступність і відкритість"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 1. МІСТКІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
if section == "Місткість":

    # ── Header image ─────────────────────────────────────────────────────────
    # Заміни шлях на свій файл або URL
    st.image("header.png", use_container_width=True)

    st.title("Чи вміщається Київ в укриття?")
    st.markdown("Аналіз стану і доступності захисних споруд за даними з відкритих джерел")
    st.divider()

    kyiv = agg["kyiv_cap"].iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Кількість укриттів, шт.", f"{kyiv['shelter_count']:,}")
    c2.metric("Загальна місткість, осіб", f"{int(kyiv['total_capacity']):,}")
    c3.metric("Кількість населення, осіб", f"{int(kyiv['population']):,}")
    c4.metric("Людей на 1 місце", f"{kyiv['population_by_capacity']:.1f}")
    c5.metric("Загальна площа, м²", f"{int(kyiv['total_area']):,}")

    st.divider()
    st.subheader("Місткість укриттів по районах")

    cap = agg["district_cap"].copy()

    # tooltip extras
    kinds_wide = (
        agg["district_shelter_kinds"]
        .pivot(index="district", columns="shelter_kind", values="percent")
        .fillna(0)
        .reset_index()
    )
    mgn_tooltip = agg["mgn_report"][["Район міста", "Доступно для МГН (%)"]].rename(
        columns={"Район міста": "district"}
    )
    cap = cap.merge(kinds_wide, on="district", how="left")
    cap = cap.merge(mgn_tooltip, on="district", how="left")

    # ── Map + bar side by side ────────────────────────────────────────────────
    map_col, bar_col = st.columns([3, 1])

    with map_col:
        # Choropleth
        fig_choro = px.choropleth_mapbox(
            cap,
            geojson=geojson,
            locations="district",
            featureidkey="properties.district",
            color="population_by_capacity",
            color_continuous_scale="RdYlGn_r",
            mapbox_style="carto-positron",
            zoom=9,                          # ← zoom out to fit all districts
            center={"lat": 50.45, "lon": 30.52},
            opacity=0.65,
            hover_name="district",
            hover_data={
                "population_by_capacity": ":.1f",
                "shelter_count": True,
                "Доступно для МГН (%)": ":.1f",
                "district": False,
            },
            labels={
                "population_by_capacity": "Людей на місце",
                "shelter_count": "Укриттів",
            },
        )

        # All shelters as tiny dots on top
        df_pts = df.dropna(subset=["lat", "lon"])
        fig_choro.add_trace(go.Scattermapbox(
            lat=df_pts["lat"],
            lon=df_pts["lon"],
            mode="markers",
            marker=dict(size=2, color="#1a1a2e", opacity=0.4),
            hoverinfo="skip",
            showlegend=False,
            name="",
        ))

        fig_choro.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            height=500,
            coloraxis_colorbar=dict(title="Людей<br>на місце", thickness=12),
        )
        st.plotly_chart(fig_choro, use_container_width=True)

    with bar_col:
        # м² на людину, sorted worst→best
        bar_df = cap[["district", "area_per_person"]].sort_values("area_per_person")

        # Match colorscale to choropleth (RdYlGn_r reversed → low = red)
        fig_bar = px.bar(
            bar_df,
            x="area_per_person",
            y="district",
            orientation="h",
            color="area_per_person",
            color_continuous_scale="RdYlGn",
            text="area_per_person",
            labels={"area_per_person": "м² на людину", "district": ""},
            height=500,
        )
        fig_bar.update_traces(texttemplate="%{text:.2f} м²", textposition="outside")
        fig_bar.update_layout(
            coloraxis_showscale=False,
            margin=dict(l=0, r=80, t=30, b=0),
            title=dict(text="м² укриття на людину", font=dict(size=14)),
            yaxis=dict(tickfont=dict(size=12)),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 2. ТИПИ УКРИТТІВ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "Типи укриттів":
    st.title("Типи укриттів")

    tabs = st.tabs(["Вид споруди", "Тип локації", "Призначення"])

    configs = [
        ("shelter_kind",       "district_shelter_kinds",  "kyiv_shelter_kinds"),
        ("location_type",      "district_location_types", "kyiv_location_types"),
        ("functional_purpose", "district_functional",     "kyiv_functional"),
    ]

    for tab, (col, dist_key, kyiv_key) in zip(tabs, configs):
        with tab:
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("##### По районах")
                dist_df = agg[dist_key].rename(columns={col: "Тип"})
                fig_bar = px.bar(
                    dist_df,
                    x="percent",
                    y="district",
                    color="Тип",
                    orientation="h",
                    barmode="stack",
                    labels={"percent": "%", "district": ""},
                    height=400,
                )
                fig_bar.update_layout(
                    legend=dict(orientation="h", y=-0.25),
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis=dict(categoryorder="total ascending"),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with col2:
                st.markdown("##### По Києву загалом")
                kyiv_df = agg[kyiv_key].rename(columns={col: "Тип"})
                fig_donut = px.pie(
                    kyiv_df,
                    names="Тип",
                    values="shelter_count",
                    hole=0.5,
                    height=400,
                )
                fig_donut.update_traces(textposition="inside", textinfo="percent+label")
                fig_donut.update_layout(
                    showlegend=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig_donut, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 3. СТАН СИСТЕМ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "Стан систем":
    st.title("Стан інженерних систем")

    status = agg["df_total_status"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Водопостачання", f"{status['Водопостачання']}%")
    c2.metric("Опалення",       f"{status['Опалення']}%")
    c3.metric("Електропостачання", f"{status['Електропостачання']}%")
    c4.metric("Інтернет",       f"{status['Інтернет']}%")
    st.caption("% укриттів з наявною/справною системою по Києву")

    st.divider()
    st.subheader("По районах — % наявна/справна")

    water   = agg["water_report"][["Район міста", "Наявна/Справна (%)"]].rename(columns={"Наявна/Справна (%)": "Вода"})
    heating = agg["heating_report"][["Район міста", "Наявна/Справна (%)"]].rename(columns={"Наявна/Справна (%)": "Опалення"})
    power   = agg["power_report"][["Район міста", "Наявна/Справна (%)"]].rename(columns={"Наявна/Справна (%)": "Електро"})

    comm_col = "Є інтернет (Wi-Fi/Дротовий) (%)" if "Є інтернет (Wi-Fi/Дротовий) (%)" in agg["comm_report"].columns else "Є інтернет (%)"
    comm = agg["comm_report"][["Район міста", comm_col]].rename(columns={comm_col: "Інтернет"})

    heatmap_df = water.merge(heating, on="Район міста").merge(power, on="Район міста").merge(comm, on="Район міста")
    heatmap_df["avg"] = heatmap_df[["Вода", "Опалення", "Електро", "Інтернет"]].mean(axis=1)
    heatmap_df = heatmap_df.sort_values("avg", ascending=True).drop(columns="avg")

    z = heatmap_df[["Вода", "Опалення", "Електро", "Інтернет"]].values
    y = heatmap_df["Район міста"].tolist()
    x = ["Вода", "Опалення", "Електро", "Інтернет"]

    fig_heat = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        colorscale="RdYlGn",
        zmin=0, zmax=100,
        text=[[f"{v:.1f}%" for v in row] for row in z],
        texttemplate="%{text}",
        hovertemplate="%{y} — %{x}: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="%"),
    ))
    fig_heat.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 4. ДОСТУПНІСТЬ І ВІДКРИТІСТЬ (об'єднано)
# ══════════════════════════════════════════════════════════════════════════════
elif section == "Доступність і відкритість":
    st.title("Доступність і відкритість укриттів")

    # ── MGN ──────────────────────────────────────────────────────────────────
    st.subheader("Доступність для маломобільних груп населення (МГН)")

    total_mgn = agg["df_total_mgn"]
    st.metric("Доступних укриттів у Києві", f"{total_mgn}%")

    mgn = agg["mgn_report"].sort_values("Доступно для МГН (%)", ascending=True)
    fig_mgn = px.bar(
        mgn,
        x="Доступно для МГН (%)",
        y="Район міста",
        orientation="h",
        color="Доступно для МГН (%)",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="Доступно для МГН (%)",
        labels={"Доступно для МГН (%)": "%", "Район міста": ""},
        height=380,
    )
    fig_mgn.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_mgn.update_layout(
        coloraxis_showscale=False,
        margin=dict(l=0, r=80, t=10, b=0),
    )
    st.plotly_chart(fig_mgn, use_container_width=True)

    st.divider()

    # ── Open access ───────────────────────────────────────────────────────────
    st.subheader("Відкритість укриттів")

    oa_col1, oa_col2 = st.columns([2, 1])

    with oa_col1:
        dist_oa = agg["district_open_access"]
        always_open = dist_oa[dist_oa["open_access"] == "Постійно відчинене для населення"][["district", "percent"]]
        order = always_open.sort_values("percent")["district"].tolist()

        fig_oa_bar = px.bar(
            dist_oa,
            x="percent",
            y="district",
            color="open_access",
            orientation="h",
            barmode="stack",
            category_orders={"district": order},
            labels={"percent": "%", "district": "", "open_access": "Доступ"},
            height=400,
        )
        fig_oa_bar.update_layout(
            legend=dict(orientation="h", y=-0.3, title=""),
            margin=dict(l=0, r=0, t=10, b=60),
        )
        st.plotly_chart(fig_oa_bar, use_container_width=True)

    with oa_col2:
        kyiv_oa = agg["kyiv_open_access"]
        fig_donut = px.pie(
            kyiv_oa,
            names="open_access",
            values="shelter_count",
            hole=0.5,
            height=400,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent")
        fig_donut.update_layout(
            legend=dict(orientation="v", y=0.5),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_donut, use_container_width=True)