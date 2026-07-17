import base64
import json
import os

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

#MainMenu {
    visibility: hidden;
}
footer {
    visibility: hidden;
}
[data-testid="stDecoration"] {
    display: none;
}

html {
    scroll-behavior: smooth;
}
[id] {
    scroll-margin-top: 24px;
}

h3 {
    font-size: 1.15rem !important;
}

[data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
    font-size: 13px;
}

.toc-link {
    color: #262730;
    text-decoration: none !important;
    font-size: 14px;
    line-height: 1.6;
}
.toc-link:hover {
    color: #ff4b4b;
    text-decoration: none !important;
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


# ── Shared UI helpers ─────────────────────────────────────────────────────────
def insight_card(html_content):
    """Pink/red callout — for data-driven findings and conclusions."""
    st.html(
        f"""
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
            {html_content}
        </div>
        """
    )


def info_card(html_content):
    """Neutral gray-blue callout — for reference facts: norms, legal text, glossaries."""
    st.html(
        f"""
        <div style="
            background-color: #eef2f6;
            border-left: 5px solid #6c7a89;
            padding: 16px;
            border-radius: 8px;
            margin: 10px 0;
            font-size: 14px;
            color: #262730;
            line-height: 1.5;
        ">
            {html_content}
        </div>
        """
    )


def _placeholder_box(path, height):
    show_path = height >= 150
    path_html = (
        f'<code style="font-size:10px; word-break:break-all; line-height:1.3;">{path}</code>'
        if show_path else ""
    )
    st.markdown(
        f"""
        <div style="
            height: {height}px;
            border: 2px dashed #d0d0d5;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            text-align: center;
            color: #9a9aa5;
            font-size: 12px;
            padding: 8px;
            background: #fafafc;
            overflow: hidden;
        ">
            <span>📷 TODO: фото</span>
            {path_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def image_or_placeholder(path, caption=None, height=240):
    """Renders an image if the file exists locally, otherwise a dashed
    placeholder box so the app doesn't crash before real assets are added."""
    if path and os.path.exists(path):
        st.image(path, caption=caption, use_container_width=True)
    else:
        _placeholder_box(path, height)
        if caption:
            st.caption(caption)


def card_thumbnail(path, width=200, height=150):
    """Fixed-height thumbnail for compact card rows — unlike
    image_or_placeholder, this never lets a tall/portrait photo stretch
    the row: the box height is fixed, and the whole photo is shown
    letterboxed inside it (object-fit: contain) instead of being cropped."""
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        st.markdown(
            f"""
            <div style="
                width: {width}px;
                height: {height}px;
                background: #eef0f2;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            ">
                <img src="data:image/{mime};base64,{b64}" style="
                    max-width: 100%;
                    max-height: 100%;
                    object-fit: contain;
                    display: block;
                ">
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        _placeholder_box(path, height)


def section_anchor(anchor_id):
    st.markdown(f'<div id="{anchor_id}"></div>', unsafe_allow_html=True)


def chapter_break():
    st.markdown(
        '<hr style="margin: 56px 0 40px; border: none; border-top: 3px solid #ffeef0;">',
        unsafe_allow_html=True,
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

kyiv = agg["kyiv_cap"].iloc[0]
kyiv_area_per_person = kyiv["total_area"] / kyiv["population"]

# ── Sidebar: table of contents (anchor links, page scrolls in one piece) ─────
SECTIONS = [
    ("intro",    "Вступ"),
    # ("about",    "Про дослідження"),
    ("capacity", "Місткість"),
    ("area",     "Площа на людину"),
    ("types", "Типи укриттів"),
    ("systems",  "Стан систем"),
    ("access",   "Доступність і відкритість"),
    ("next",     "Що можна зробити?"),
]

st.sidebar.markdown("**Розділ**")
toc_items = "".join(
    f'<li><a class="toc-link" href="#{anchor_id}">{label}</a></li>'
    for anchor_id, label in SECTIONS
)
st.sidebar.markdown(
    f'<ul style="list-style:disc; padding-left:20px; margin:0;">{toc_items}</ul>',
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# 1. ВСТУП
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("intro")
st.title("Чи вміщається Київ в укриття?")

st.divider()

col_intro_text, col_intro_img = st.columns([1, 1])

with col_intro_text:
    st.markdown(
        """
Ранок після масованого ракетного обстрілу. В соціальних мережах вкотре ширяться фото переповненого метро. 

У нас, як і у багатьох мешканців Києва, вчергове постало питання: **чи вистачає киянам укриттів?**
        """
    )

with col_intro_img:
    # TODO: користувач додасть фото
    image_or_placeholder("assets/metro_crowd.jpg", caption="Фото: КМДА")

st.markdown(
        """
В інтернеті **мапи укриттів** лишаються єдиним джерелом інформації про сховища Києва, втім, вони не відображають повної картини. Поодинокі відмітки не дають розуміння про співвідношення місткості та кількості населення, загальної статистики по місту та по окремих його районах.

**Ця сторінка - спроба дати цілісний погляд на проблему укриттів Києва.** Наші візуалізації відображають стан систем в укриттях, їх типи та доступність по районах міста. Також ми наводимо приклади, коли інформація з мап може вводити користувачів в оману.
        """
    )
# ══════════════════════════════════════════════════════════════════════════════
# 2. ПРО ДОСЛІДЖЕННЯ
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("Обмеження, джерела та методологія"):
    st.markdown(
        """
**Команда**

Над проєктом працювали студентки Київської школи економіки Марія Кобичева, Дарина Кальченко, Діана Алдошина, Лілія Червонецька, Валерія Михайлишина у межах курсу «Дані і суспільство».

**Обмеження дослідження**
1. Ми працюємо з даними про укриття, які нанесені на мапу, - не з тим, що існує насправді. Респонденти у нашому опитуванні неодноразово зазначали, що не всі сховища є на мапі
2. Дані про кількість населення з офіційного джерела є спрогнозованими, адже останній перепис населення був більше 20 років тому
3. Категоризація укриттів є здебільшого умовною: позначені однією категорією укриття зазвичай істотно різняться в умовах для перебування, а також сховища постійно класифікують некоректно: наприклад, метро часто відмічено як найпростіше укриття, коли за офіційними документами вони відносяться до споруд подвійного призначення.

**Джерела даних**
- Мапа укриттів Києва (єдина відкрита база даних про укриття, з якої ми витягнули інформацію за допомогою python): https://shelters.dsns.gov.ua/
- Населення районів: https://kyivcity.gov.ua/kyiv_ta_miska_vlada/pro_kyiv/raiony_kyieva/
- Геодані для мапи: https://github.com/denysboiko/kyivmap
- ДБН В.2.2-5:2023 "Захисні споруди цивільного захисту": https://e-construction.gov.ua/laws_detail/3225773063500990463?doc_type=2 
- Стаття 32 Кодексу цивільного захисту України: https://zakon.rada.gov.ua/laws/show/5403-17#Text
- Аналіз вимог до відкритості укриттів: https://tretsud.com.ua/parkinh-iak-skhovyshche-chy-mozhut-vlasnyky-obmezhuvaty-dostup-pid-chas-povitrianoi-tryvohy/

**Логіка розрахунку метрик**
- «Людей на 1 місце» = населення району ÷ місткість укриттів району
- «Площа на людину» = сумарна площа укриттів району ÷ населення району
- Забезпеченість (вода/опалення/електрика/зв'язок): % укриттів району з наявною/справною категорією
- Доступність для МГН: % укриттів району, позначених як доступні для маломобільних груп

У роботі використовували генеративний ШІ для автоматизації написання скриптів парсингу й візуалізацій та підсумування державних документів; за весь згенерований код і написаний текст несемо відповідальність.

Код і дані: [github.com/mkobycheva/kyiv-shelters-analysis](http://github.com/mkobycheva/kyiv-shelters-analysis)

Питання та фідбек: [maria.kobycheva@gmail.com](mailto:maria.kobycheva@gmail.com)
        """
    )

# chapter_break()

# ══════════════════════════════════════════════════════════════════════════════
# 3. МІСТКІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("capacity")
st.title("Місткість укриттів")

c1, c2, c3 = st.columns(3)
c1.metric("Кількість укриттів, шт.", f"{int(kyiv['shelter_count']):,}")
c2.metric("Загальна місткість, осіб", f"{int(kyiv['total_capacity']):,}")
c3.metric("Загальна площа, м²", f"{int(kyiv['total_area']):,}")

c4, c5, c6 = st.columns(3)
c4.metric("Людей на 1 місце", f"{kyiv['population_by_capacity']:.1f}")
c5.metric("Кількість населення, осіб", f"{int(kyiv['population']):,}")
c6.metric("Площа на 1 людину, м²", f"{kyiv_area_per_person:.2f}")

st.divider()

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
    color_continuous_scale="RdYlGn_r",
    color_continuous_midpoint=1,
    range_color=[0, 3.5],
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
st.plotly_chart(fig_choro, use_container_width=True)

insight_card(
    """
    На ~2 900 000 осіб існує ~2 000 000 місць в укриттях.
    Тож навіть за ідеального сценарію, якщо всі укриття відкриті та доступні,
    близько 30% населення міста залишаються поза захистом.
    """
)

# chapter_break()

# ══════════════════════════════════════════════════════════════════════════════
# 4. ПЛОЩА НА ЛЮДИНУ
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("area")
st.subheader("Площа на людину")

col_area_chart, col_area_text = st.columns([3, 1])

with col_area_chart:
    bar_df = cap[["district", "area_per_person"]].sort_values("area_per_person", ascending=True)
    district_order = bar_df["district"].tolist()
    fig_bar = px.bar(
        bar_df,
        x="area_per_person",
        y="district",
        orientation="h",
        color="area_per_person",
        color_continuous_scale="Oranges_r",
        range_color=[0, 2],
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
    st.plotly_chart(fig_bar, use_container_width=True)

with col_area_text:
    st.markdown(
        """
        **0,6 м² на одну особу** - мінімум за нормами для найпростішого укриття (ДБН В.2.2-5:2023).
        
        
        Крім того, що цю вимогу проходить половина районів, вона розрахована на **посидіти в укритті**,
        а реальність нічних масованих тривог — це **переночувати**. 
        
        Щоб лягти, людині треба ~1,8 м²
        (односпальне ліжко), що втричі більше за прогнозований простір.
        """
    )

# chapter_break()

# ══════════════════════════════════════════════════════════════════════════════
# 7. ТИПИ УКРИТТІВ
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("types")
st.title("Типи укриттів")

# ── 7a. Картки типів (карусель) ──────────────────────────────────────────
SHELTER_TYPES = [
    {
        "name": "Сховища",
        "photos": [
            "assets/shelter_types/skhovyshche.png",
            "assets/shelter_types/skhovyshche_2.png",
            "assets/shelter_types/skhovyshche_3.png",
            "assets/shelter_types/skhovyshche_4.png"
        ],
        "description": "Герметичні спеціалізовані споруди, що захищають від ударної хвилі, уламків, радіації, затоплення тощо - найнадійніші з усіх укриттів.",
        "example": "Спеціалізовані глибокі підвали (традиційно - радянські) з герметичними дверима.",
    },
    {
        "name": "СПП із захисними властивостями протирадіаційного укриття",
        "photos": [
            "assets/shelter_types/spp_pru.png",
            "assets/shelter_types/spp_pru_2.png",
            "assets/shelter_types/spp_pru_3.png",
        ],
        "description": "Споруди подвійного призначення (не спроєктовані як укриття, проте зі створеними умовами для тимчасового перебування), що можуть захистити від радіації, ударної хвилі, уламків.",
        "example": "Виробничі приміщення, заклади культури, магазини.",
    },
    {
        "name": "СПП із захисними властивостями сховища",
        "photos": [
            "assets/shelter_types/spp_skhovyshche.png"
        ],
        "description": "Споруди подвійного призначення, що можуть бути використані як сховища.",
        "example": "Виробничі приміщення, заклади культури, магазини.",
    },
    {
        "name": "Найпростіші укриття",
        "photos": [
            "assets/shelter_types/naiprostishe.png",
            "assets/shelter_types/naiprostishe_2.png",
            "assets/shelter_types/naiprostishe_3.png",
            "assets/shelter_types/naiprostishe_4.png",
            "assets/shelter_types/naiprostishe_5.png",
            "assets/shelter_types/naiprostishe_6.png",
        ],
        "description": "Споруди, в яких можливе тимчасове перебування задля зниження комбінованого ураження від небезпечних чинників.",
        "example": "Метро, тунелі, паркінги, підвали, цокольні поверхи.",
    },
    {
        "name": "Первинне (мобільне) укриття",
        "photos": [
            "assets/shelter_types/pervynne.png",
            "assets/shelter_types/pervynne_2.png",
        ],
        "description": "Тимчасові споруди, зведені для захисту від непрямої дії звичайних засобів ураження.",
        "example": "Наземні бетонні споруди.",
    },
]


def render_type_card(t, card_idx):
    photos = t["photos"]
    state_key = f"type_photo_idx_{card_idx}"
    if state_key not in st.session_state:
        st.session_state[state_key] = 0
    photo_idx = st.session_state[state_key] % len(photos)

    with st.container(height=200, border=True):
        col_img, col_text = st.columns([1, 2])
        with col_img:
            card_thumbnail(photos[photo_idx], width=260, height=180)
            if len(photos) > 1:
                nav_prev, nav_label, nav_next = st.columns([1, 2, 1])
                with nav_prev:
                    if st.button("◀", key=f"{state_key}_prev"):
                        st.session_state[state_key] = (photo_idx - 1) % len(photos)
                with nav_label:
                    st.markdown(
                        f"<div style='text-align:center; font-size:11px; color:#999;'>{photo_idx + 1}/{len(photos)}</div>",
                        unsafe_allow_html=True,
                    )
                with nav_next:
                    if st.button("▶", key=f"{state_key}_next"):
                        st.session_state[state_key] = (photo_idx + 1) % len(photos)
        with col_text:
            st.markdown(f"**{t['name']}**")
            st.caption(t["description"])
            st.markdown(
                f"<span style='font-size:12px;color:#666;'>Приклад — {t['example']}</span>",
                unsafe_allow_html=True,
            )


for card_idx, t in enumerate(SHELTER_TYPES):
    render_type_card(t, card_idx)

st.divider()

# ── 7b. Сюжет про метро ─────────────────────────────────────────────────
col_metro_text, col_metro_img = st.columns([2, 1])

with col_metro_text:
    insight_card(
        """
        <b>То чому ж метро переповнене?</b><br><br>
        Деякі станції позначені як найпростіші укриття, деякі - як СПП із захисними властивостями
        укриття. 36 з 50 станцій мапи позначені кілька разів - наприклад, кожен з виходів виділяють
        як найпростіші укриття, а саму станцію - як споруду подвійного призначення.<br><br>
        Це створює ілюзію місткості. Наприклад, станція "Берестейська" (див. зображення), враховуючи
        повторні відмітки, теоретично розрахована на 1000+1000+1048 = 3048 осіб — цифру, яку складно
        уявити.
        """
    )

with col_metro_img:
    # TODO: користувач додасть фото
    image_or_placeholder("assets/metro_corridor.jpg", caption="Фото: © AMY / Wikimedia Commons, CC BY-SA 3.0")


st.divider()


# ── 7c. Вид споруди / Тип локації (поруч) ────────────────────────────────
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

fig_shelter_kind = px.bar(
    shelter_kind_dist,
    x="values",
    y="district",
    color="Тип",
    category_orders={
        "Тип": shelter_kinds_categories
    },
    color_discrete_sequence=['#4C78A8', '#F58518', '#E45756', '#54A24B', '#72B7B2'],
    orientation="h",
    barmode="stack",
    labels={"values": "% укриттів" if shelter_kind_percent else "Кількість", "district": "Район"},
    height=440,
)
fig_shelter_kind.update_layout(
    legend=dict(orientation="h", y=-0.3),
    margin=dict(l=0, r=20, t=10, b=90)
)

fig_shelter_kind.update_xaxes(
    range=[0, 100] if shelter_kind_percent else [0,
                                                 shelter_kind_dist.groupby("district")["values"].sum().max() * 1.05]
)
st.plotly_chart(fig_shelter_kind, use_container_width=True)

insight_card(
    """
    Абсолютна більшість об'єктів — це найпростіші укриття, тобто пристосовані підвали,
    що не забезпечують повноцінних захисних властивостей. Частка  сховищ у Києві
    становить лише близько 2%.
    """
)

# chapter_break()

# ══════════════════════════════════════════════════════════════════════════════
# 5. СТАН СИСТЕМ
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("systems")
st.title("Стан інженерних систем")

status = agg["df_total_status"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Опалення", f"{status['Опалення']}%")
c2.metric("Електропостачання", f"{status['Електропостачання']}%")
c3.metric("Інтернет", f"{status['Інтернет']}%")
c4.metric("Водопостачання", f"{status['Водопостачання']}%")
st.caption("% укриттів з наявною/справною системою по Києву")

st.divider()

st.markdown(
    """
    **Найпростіші укриття** мають бути забезпечені електроживленням, освітленням, системами водопроводу
    та каналізації, засобами зв'язку і оповіщення (телефоном, радіоприймачем, інтернетом, рекомендовано
    встановлення Wi-Fi) (ДБН В.2.2-5:2023). До опалення вимог не знайшлось. Крім того, у серпні 2025 року
    наказ МВС №579 змінив вимоги до водопостачання, каналізації, резервного живлення, аптечок і зв'язку
    **з обов'язкових на рекомендаційні**.
    
    
    Для **ПРУ, СПП та сховищ** вимог більше: власне джерело електрики, очищення повітря, запас питної води
    2-3 л/добу на особу і зв'язок, що не переривається - і все це має **безперервно функціонувати 48 год**.
    """
)

# st.divider()

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
st.plotly_chart(fig_heat, use_container_width=True)

insight_card(
    """
    Електрикою забезпечені майже всі укриття, водою - більше половини, а от опалення і інтернет
    наявні лише в третині укриттів Києва. Враховуючи низькі температури минулої зими, це фактично
    означає, що 2/3 укриттів непридатні для тривалого перебування в холодну пору року.
    """
)

# chapter_break()

# ══════════════════════════════════════════════════════════════════════════════
# 6. ДОСТУПНІСТЬ І ВІДКРИТІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("access")
st.title("Доступність і відкритість укриттів")

st.subheader("Доступність для маломобільних груп населення (МГН)")

total_mgn = agg["df_total_mgn"]
st.metric("Доступних укриттів у Києві", f"{total_mgn}%")

mgn = agg["mgn_report"].sort_values("Доступно для МГН (%)", ascending=False)
fig_mgn = px.bar(
    mgn,
    x="Доступно для МГН (%)",
    y="Район міста",
    orientation="h",
    color="Доступно для МГН (%)",
    color_continuous_scale="Reds_r",
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

insight_card(
    """
    Лише 13,4% київських укриттів доступні для маломобільних груп населення. Розрив між районами
     вражає: від більше третини у Подільському до ~3% у Шевченківському. Для людей з інвалідністю,
     літніх людей та батьків із дитячими візками більшість позначок на карті фактично не є реальною можливістю убезпечитися.
    """
)

st.divider()

st.subheader("Відкритість укриттів")

oa_percent = st.toggle("Показати у %", key="toggle_oa_percent")

dist_oa = agg["district_open_access"]
dist_oa["values"] = dist_oa["percent"] if oa_percent else dist_oa["shelter_count"]

oa_sorting_series = (
    dist_oa[dist_oa["open_access"] == "Постійно відчинене для населення"]
    .set_index("district")["percent"]
    .sort_values(ascending=True)
)

dist_oa["district"] = pd.Categorical(
    dist_oa["district"],
    categories=oa_sorting_series.index,
    ordered=True
)

dist_oa = dist_oa.sort_values("district")

oa_categories = [
    "Постійно відчинене для населення",
    "Для населення у робочий час",
    "Відчинене для населення лише у разі оповіщення",
    "Лише для працівників у робочий час",
    "Безперешкодний доступ не забезпечено"
]

fig_oa_bar = px.bar(
    dist_oa,
    x="values",
    y="district",
    color="open_access",
    category_orders={
        "open_access": oa_categories
    },
    orientation="h",
    barmode="stack",
    labels={"values": "% укриттів" if oa_percent else "Кількість", "district": "", "open_access": "Доступ"},
    height=400,
)
fig_oa_bar.update_layout(
    legend=dict(orientation="h", y=-0.3, title=""),
    margin=dict(l=0, r=0, t=10, b=60),
)
st.plotly_chart(fig_oa_bar, use_container_width=True)

with st.expander("Розшифрування категорій"):
    st.markdown(
        """
        ##### Що означають ці категорії?
        * **Постійно відчинене для населення** - доступ вільний у будь-який час доби
        * **Для населення у робочий час** - доступ обмежений годинами роботи закладу/установи
        * **Відчинене для населення лише у разі оповіщення** - двері відкриваються тільки під час сигналу тривоги
        * **Лише для працівників у робочий час** - доступ мають тільки співробітники об'єкта
        * **Безперешкодний доступ не забезпечено** - вхід технічно ускладнений або заблокований
        """
    )


st.markdown(
    """
    За законом, **порядок використання укриттів (і державних, і приватних) визначають військові
    адміністрації** (стаття 8 Закону України "Про правовий режим воєнного стану").
    
    Зокрема, має бути забезпечено:
        * готовність до використання;
        * цілодобовий та безперешкодний доступ до них під час повітряної тривоги;
        * відповідальність власника за утримання споруди у належному стані.
        
    **Однак у Києві документ досі не затверджено або не оприлюднено**, тому більшість укриттів
    функціонують за неформальними правилами, визначеними власником
    
    Серед зареєстрованих укриттів проводять аудити, проте **подання сховищ на облік не є обов'язковим** -
    воно ініціюється власником, місцевим самоврядування, ДСНС тощо. Відповідно, є укриття, які ніяк
    не можна проконтролювати.
    """
)

# chapter_break()
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 8. ЩО З ЦИМ РОБИТИ
# ══════════════════════════════════════════════════════════════════════════════
section_anchor("next")
st.title("Що можна зробити?")

st.markdown(
    """
Наше дослідження показало, що **наявні в інтернеті дані про укриття Києва є значною мірою "black box"**:
загальна статистика, вимоги до сховищ, класифікація за категоріями та частота оновлення інформації
не є прозорими для містян. Стан багатьох укриттів незадовільний, а їх місткість - переоцінена.

**Ці бар'єри для користування сховищами наштовхують на роздуми про культуру спускання в укриття в Києві
загалом**. Можливо, кияни мало ходять в укриття, бо не мають достатньо актуальної інформації, а нових
даних, натомість, немає, бо укриттями мало користуються? Чому мало людей спускаються регулярно, а в
масовані обстріли ми маємо хаос? Проблема в забезпеченні укриттями чи в тому, як про них комунікують?
Чому не всі укриття є на мапі? Як забезпечити оперативний обмін інформацією між громадянами та владою?

##### Ми бачимо рішення у:

- Підвищенні обізнаності громадян про реальну ситуацію з укриттями;
- Діалозі з органами місцевого самоврядування щодо регулярних аудитів, облаштування сховищ і перегляду норм на місткість;
- Створенні діджитал-платформи з актуальною інформацією від самих користувачів — аналог Google Maps, де кияни могли б лишати відгуки з фото та будувати маршрути до найближчого укриття.
    """
)
