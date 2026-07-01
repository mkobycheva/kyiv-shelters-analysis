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

# ── Custom font + global styles ───────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Commissioner:wght@100..900&family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap');

*:not(.material-icons):not(.material-symbols-outlined):not(.material-symbols-rounded):not(.material-symbols-sharp):not([class*="material-symbols"]):not([translate="no"]):not([aria-hidden="true"]) {
    font-family: 'Montserrat', sans-serif !important;
}

.material-icons,
.material-symbols-outlined,
.material-symbols-rounded,
.material-symbols-sharp,
span[class*="material-symbols"],
span[translate="no"],
span[aria-hidden="true"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}

[data-testid="metric-container"] {
    border: none !important;
    box-shadow: none !important;
}

[data-testid="stAppViewContainer"] > .main > .block-container {
    padding-top: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: 100% !important;
}

[data-testid="stHeader"] {
    background: none !important;
    height: 0 !important;
}

[data-testid="stSidebarCollapsedControl"] svg {
    display: none;
}
[data-testid="stSidebarCollapsedControl"]::after {
    content: "☰";
    font-size: 1.2rem;
}
</style>
""", unsafe_allow_html=True)


def normalize_district_name(name):
    if not isinstance(name, str):
        return name
    return name.replace("’", "'").replace("‘", "'")

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
    df["district"] = df["district"].apply(normalize_district_name)
    df['lat'] = pd.to_numeric(df['lat'].astype(str).str.rstrip(', '), errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df['accessible_mgn'] = df['accessible_mgn'].fillna(False).astype(bool)

    functional_purpose_groups = {
        "Як приміщення іншого призначення": "Підвали та техприміщення",
        "Не застосовується": "Не визначено",
        "Гаражі або стоянки автомобілів та автокарів": "Гаражі та автостоянки",
        "Приміщення для проведення навчальних занять": "Навчальні приміщення",
        "Заклади культури": "Громадські, культурні та медичні заклади",
        "Основні та допоміжні (підсобні) приміщення закладів охорони здоров'я": "Громадські, культурні та медичні заклади",
        "Спортивні приміщення (тири, зали для проведення спортивних занять)": "Громадські, культурні та медичні заклади",
        "Виставкові зали": "Громадські, культурні та медичні заклади",
        "Приміщення для торгівлі і громадського харчування (магазини, зали їдалень, буфети, кафе тощо)": "Комерційні та побутові приміщення",
        "Приміщення для побутового обслуговування населення (ательє, пункти прокату, приймальні пункти тощо)": "Комерційні та побутові приміщення",
        "Гардеробні та інші побутові приміщення": "Комерційні та побутові приміщення",
        "Адміністративні та офісні приміщення": "Адміністративні та виробничо-складські приміщення",
        "Складські приміщення": "Адміністративні та виробничо-складські приміщення",
        "Виробничі приміщення": "Адміністративні та виробничо-складські приміщення",
        "Приміщення для розміщення аварійних (ремонтних) та чергових служб": "Адміністративні та виробничо-складські приміщення",
    }
    df["functional_purpose_group"] = (
        df["functional_purpose"].map(functional_purpose_groups).fillna(df["functional_purpose"])
    )

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
    district_functional     = dist_pct("functional_purpose_group")
    kyiv_functional         = kyiv_pct("functional_purpose_group")

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
    feat["properties"]["district"] = normalize_district_name(
        feat["properties"]["NAME"].replace(" район", "")
    )

# ── Sidebar nav ───────────────────────────────────────────────────────────────
section = st.sidebar.radio(
    "Розділ",
    ["Місткість", "Типи укриттів", "Стан систем", "Доступність і відкритість"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 1. МІСТКІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
if section == "Місткість":

    # # padding back for content sections
    # st.markdown("""
    # <style>
    # [data-testid="stAppViewContainer"] > .main > .block-container {
    #     padding-left: 3rem !important;
    #     padding-right: 3rem !important;
    #     padding-bottom: 3rem !important;
    #     max-width: 100% !important;
    # }
    # </style>
    # """, unsafe_allow_html=True)

    st.title("Чи вміщається Київ в укриття?")

    kyiv = agg["kyiv_cap"].iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Кількість укриттів, шт.", f"{int(kyiv['shelter_count']):,}")
    c2.metric("Загальна місткість, осіб", f"{int(kyiv['total_capacity']):,}")
    c3.metric("Кількість населення, осіб", f"{int(kyiv['population']):,}")
    c4.metric("Людей на 1 місце", f"{kyiv['population_by_capacity']:.1f}")
    c5.metric("Загальна площа, м²", f"{int(kyiv['total_area']):,}")

    st.divider()
    st.subheader("Місткість укриттів по районах")

    cap = agg["district_cap"].copy()

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

    fig_choro = px.choropleth_mapbox(
        cap,
        geojson=geojson,
        locations="district",
        featureidkey="properties.district",
        color="population_by_capacity",
        color_continuous_scale="Reds",
        mapbox_style="carto-positron",
        zoom=9.3,
        center={"lat": 50.40, "lon": 30.57},
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

    fig_choro.update_traces(
        marker_line_width=0.5,
        marker_line_color="grey",
    )

    df_pts = df.dropna(subset=["lat", "lon"])
    fig_choro.add_trace(go.Scattermapbox(
        lat=df_pts["lat"],
        lon=df_pts["lon"],
        mode="markers",
        marker=dict(size=3, color="#1a1a2e", opacity=0.3),
        hoverinfo="skip",
        showlegend=False,
        name="",
    ))

    fig_choro.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=560,
        coloraxis_colorbar=dict(
            title=dict(
                text="Людей на місце",
                font=dict(size=11)
            ),
            thickness=15,
            len=0.9,
            x=1,
            y=0,
            xanchor="right",
            yanchor="bottom",
            bgcolor="rgba(255, 255, 255, 0.5)",
            tickfont=dict(size=10)
        )
    )
    st.plotly_chart(fig_choro, width="stretch")

    st.html(
        """
        <div style="
            background-color: #ffeef0; 
            border-left: 5px solid #ff4b4b; 
            padding: 16px; 
            border-radius: 8px;
            margin: 10px 0;
            font-size: 14px;
            color: #262730;
            line-height: 1.5;
        ">
            На ~2 900 000 осіб існує ~2 000 000 місць в укриттях. 
            Тож навіть за ідеального сценарію, якщо всі укриття відкриті та доступні, 
            близько 30% населення міста залишаються поза захистом.
        </div>
        """
    )

    st.divider()

    st.subheader("Площа укриття на людину")

    bar_df = cap[["district", "area_per_person"]].sort_values("area_per_person", ascending=True)
    district_order = bar_df["district"].tolist()
    fig_bar = px.bar(
        bar_df,
        x="area_per_person",
        y="district",
        orientation="h",
        color="area_per_person",
        color_continuous_scale="Oranges_r",
        text="area_per_person",
        category_orders={"district": district_order},
        labels={"area_per_person": "М² на людину", "district": "Район"},
        height=420,
    )
    fig_bar.add_vline(
        x=0.6,
        line_width=2,
        line_dash="dash",
        line_color="rgba(255, 0, 0, 0.4)",
        annotation_text="Норма площі",
        annotation_position="top right"
    )
    fig_bar.update_traces(texttemplate="%{text:.2f} м²", textposition="outside")
    fig_bar.update_layout(
        coloraxis_showscale=False,
        margin=dict(l=0, r=80, t=0, b=0),
        yaxis=dict(tickfont=dict(size=12)),
    )
    st.plotly_chart(fig_bar, width="stretch")

    st.html(
        """
        <div style="
            background-color: #ffeef0; 
            border-left: 5px solid #ff4b4b; 
            padding: 16px; 
            border-radius: 8px;
            margin: 10px 0;
            font-size: 14px;
            color: #262730;
            line-height: 1.5;
        ">
            Згідно з Державними будівельними нормами України, 
            мінімальна норма площі в укритті становить 0,6 м² на особу.
            Цю вимогу проходить половина районів.
        </div>
        """
    )

# ══════════════════════════════════════════════════════════════════════════════
# 2. ТИПИ УКРИТТІВ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "Типи укриттів":
    st.title("Типи укриттів")

    def aggregate_kpi_row(heading, kyiv_df):
        if heading == "Вид споруди":
            order = ["Найпростіше укриття", "Сховище", "Інше"]
            kpi_df = kyiv_df.copy()
            kpi_df["Тип"] = kpi_df["Тип"].where(kpi_df["Тип"].isin(order[:2]), "Інше")
        elif heading == "Призначення":
            order = ["Підвали та техприміщення", "Не визначено", "Інше"]
            purpose_labels = {
                "Як приміщення іншого призначення": "Підвали та техприміщення",
                "Підвали та техприміщення": "Підвали та техприміщення",
                "Не застосовується": "Не визначено",
                "Не визначено": "Не визначено",
            }
            kpi_df = kyiv_df.copy()
            kpi_df["Тип"] = kpi_df["Тип"].map(purpose_labels).fillna("Інше")
        else:
            return kyiv_df.head(4)

        kpi_df = (
            kpi_df.groupby("Тип", as_index=False)
            .agg(shelter_count=("shelter_count", "sum"))
        )
        total = kpi_df["shelter_count"].sum()
        kpi_df["percent"] = (kpi_df["shelter_count"] / total * 100).round(1)
        kpi_df["Тип"] = pd.Categorical(kpi_df["Тип"], categories=order, ordered=True)
        return kpi_df.sort_values("Тип")

    def render_kpi_row(heading, kyiv_df):
        kpi_df = aggregate_kpi_row(heading, kyiv_df)
        kpi_cols = st.columns(len(kpi_df))
        for metric_col, (_, row) in zip(kpi_cols, kpi_df.iterrows()):
            with metric_col:
                st.metric(row["Тип"], f"{row['percent']:.1f}%")
                st.caption(f"{int(row['shelter_count']):,} укриттів")

    st.subheader("Вид споруди")
    shelter_kind_kyiv = agg["kyiv_shelter_kinds"].rename(columns={"shelter_kind": "Тип"})
    render_kpi_row("Вид споруди", shelter_kind_kyiv)

    shelter_kind_percent = st.toggle("Показати у %", key="toggle_shelter_kind_percent")

    shelter_kind_dist = agg["district_shelter_kinds"].rename(columns={"shelter_kind": "Тип"})
    shelter_kind_dist["values"] = shelter_kind_dist["percent"] if shelter_kind_percent else shelter_kind_dist["shelter_count"]

    shelter_district_series = (
        shelter_kind_dist[shelter_kind_dist["Тип"] == "Сховище"]
        .set_index("district")["percent"]
        .sort_values(ascending=True)
    )

    shelter_kind_dist["district"] = pd.Categorical(
        shelter_kind_dist["district"],
        categories=shelter_district_series.index,
        ordered=True
    )

    shelter_kind_dist = shelter_kind_dist.sort_values("district")

    shelter_kinds_categories = [
        "Сховище",
        "Споруда подвійного призначення із захисними властивостями сховища",
        "Споруда подвійного призначення із захисними властивостями протирадіаційного укриття",
        "Первинне (мобільне) укриття",
        "Найпростіше укриття"
    ]

    num_categories = len(shelter_kinds_categories)
    start = 0.1
    end = 0.47
    step = (end - start) / (num_categories - 1)
    sample_points = [start + i * step for i in range(num_categories)]

    shelter_kinds_colors = px.colors.sample_colorscale("Reds_r", sample_points)
    shelter_kinds_color_map = dict(zip(shelter_kinds_categories, shelter_kinds_colors))

    fig_shelter_kind = px.bar(
        shelter_kind_dist,
        x="values",
        y="district",
        color="Тип",
        category_orders={
            "Тип": shelter_kinds_categories
        },
        color_discrete_map=shelter_kinds_color_map,
        orientation="h",
        barmode="stack",
        labels={"values": "% укриттів" if shelter_kind_percent else "Кількість"},
        height=440,
    )
    fig_shelter_kind.update_layout(
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=0, r=0, t=10, b=70)
    )
    st.plotly_chart(fig_shelter_kind, width="stretch")

    st.divider()
    st.subheader("Тип локації")
    location_type_kyiv = agg["kyiv_location_types"].rename(columns={"location_type": "Тип"})
    render_kpi_row("Тип локації", location_type_kyiv)

    location_type_percent = st.toggle("Показати у %", key="toggle_location_type_percent")

    location_type_dist = agg["district_location_types"].rename(columns={"location_type": "Тип"})
    location_type_dist["values"] = location_type_dist["percent"] if location_type_percent else location_type_dist["shelter_count"]
    location_sorting_series = (
        location_type_dist[location_type_dist["Тип"] == "Заглиблена"]
        .set_index("district")["percent"]
        .sort_values(ascending=True)
    )

    location_type_dist["district"] = pd.Categorical(
        location_type_dist["district"],
        categories=location_sorting_series.index,
        ordered=True
    )

    location_type_dist = location_type_dist.sort_values("district")

    location_type_categories = [
        "Заглиблена",
        "Надземна",
        "Напівзаглиблена"
    ]

    num_categories = len(location_type_categories)
    start = 0.4
    end = 0.67
    step = (end - start) / (num_categories - 1)
    sample_points = [start + i * step for i in range(num_categories)]

    location_type_colors = px.colors.sample_colorscale("Oranges_r", sample_points)
    location_type_color_map = dict(zip(location_type_categories, location_type_colors))

    fig_location_type = px.bar(
        location_type_dist,
        x="values",
        y="district",
        color="Тип",
        category_orders={
            "Тип": location_type_categories
        },
        color_discrete_map=location_type_color_map,
        orientation="h",
        barmode="stack",
        labels={"values": "% укриттів" if location_type_percent else "Кількість"},
        height=440,
    )
    fig_location_type.update_layout(
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=0, r=0, t=10, b=70)
    )
    st.plotly_chart(fig_location_type, width="stretch")

    st.divider()
    st.subheader("Призначення")
    functional_kyiv = agg["kyiv_functional"].rename(columns={"functional_purpose_group": "Тип"})
    render_kpi_row("Призначення", functional_kyiv)

    functional_percent = st.toggle("Показати у %", key="toggle_functional_percent")

    functional_dist = agg["district_functional"].rename(columns={"functional_purpose_group": "Тип"})
    functional_dist["values"] = functional_dist["percent"] if functional_percent else functional_dist["shelter_count"]

    functional_sorting_series = (
        functional_dist[functional_dist["Тип"] == "Підвали та техприміщення"]
        .set_index("district")["percent"]
        .sort_values(ascending=True)
    )

    # 2. Перетворюємо "district" на категоріальний тип Pandas із чітким порядком
    functional_dist["district"] = pd.Categorical(
        functional_dist["district"],
        categories=functional_sorting_series.index,
        ordered=True
    )

    # 3. Сортуємо сам датафрейм
    functional_dist = functional_dist.sort_values("district")

    fig_functional = px.bar(
        functional_dist,
        x="values",
        y="district",
        color="Тип",
        color_discrete_sequence=px.colors.qualitative.G10,
        orientation="h",
        barmode="stack",
        labels={"values": "% укриттів" if shelter_kind_percent else "Кількість"},
        height=440,
    )
    fig_functional.update_layout(
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=0, r=0, t=10, b=70)
    )
    st.plotly_chart(fig_functional, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# 3. СТАН СИСТЕМ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "Стан систем":
    st.title("Стан інженерних систем")

    status = agg["df_total_status"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Опалення", f"{status['Опалення']}%")
    c2.metric("Електропостачання", f"{status['Електропостачання']}%")
    c3.metric("Інтернет", f"{status['Інтернет']}%")
    c4.metric("Водопостачання", f"{status['Водопостачання']}%")
    st.caption("% укриттів з наявною/справною системою по Києву")

    st.divider()
    st.subheader("По районах — % наявна/справна")

    water   = agg["water_report"][["Район міста", "Наявна/Справна (%)"]].rename(columns={"Наявна/Справна (%)": "Вода"})
    heating = agg["heating_report"][["Район міста", "Наявна/Справна (%)"]].rename(columns={"Наявна/Справна (%)": "Опалення"})
    power   = agg["power_report"][["Район міста", "Наявна/Справна (%)"]].rename(columns={"Наявна/Справна (%)": "Електрика"})

    comm_col = "Є інтернет (Wi-Fi/Дротовий) (%)" if "Є інтернет (Wi-Fi/Дротовий) (%)" in agg["comm_report"].columns else "Є інтернет (%)"
    comm = agg["comm_report"][["Район міста", comm_col]].rename(columns={comm_col: "Інтернет"})

    heatmap_df = heating.merge(power, on="Район міста").merge(comm, on="Район міста").merge(water, on="Район міста")
    heatmap_df = heatmap_df.sort_values("Опалення", ascending=False)

    system_order = ["Опалення", "Електрика", "Інтернет", "Вода"]
    z = heatmap_df[system_order].values
    y = heatmap_df["Район міста"].tolist()
    x = system_order

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
    st.plotly_chart(fig_heat, width="stretch")

    st.html(
        """
        <div style="
            background-color: #ffeef0; 
            border-left: 5px solid #ff4b4b; 
            padding: 16px; 
            border-radius: 8px;
            margin: 10px 0;
            font-size: 14px;
            color: #262730;
            line-height: 1.5;
        ">
            Електрикою забезпечені майже всі укриття, водою - більше половини, а от опалення і інтернет наявні лише в третині укриттів Києва. 
            Враховуючи низькі температури минулої зими, це фактично означає, що 2/3 укриттів непридатні для тривалого перебування в холодну пору року. 
            Інтернет, хоча і не є критичною інфраструктурою, уможливлює зв'язок з рідними та оперативний доступ до новин, 
            тож його відсутність створює інформаційний вакуум та підвищує рівень стресу містян.
        </div>
        """
    )

# ══════════════════════════════════════════════════════════════════════════════
# 4. ДОСТУПНІСТЬ І ВІДКРИТІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "Доступність і відкритість":
    st.title("Доступність і відкритість укриттів")

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
    st.plotly_chart(fig_mgn, width="stretch")

    st.divider()

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
        st.plotly_chart(fig_oa_bar, width="stretch")

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
        st.plotly_chart(fig_donut, width="stretch")
