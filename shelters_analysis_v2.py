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


def image_or_placeholder(path, caption=None, height=240):
    """Renders an image if the file exists locally, otherwise a dashed
    placeholder box so the app doesn't crash before real assets are added."""
    if path and os.path.exists(path):
        st.image(path, caption=caption, use_container_width=True)
    else:
        st.markdown(
            f"""
            <div style="
                height: {height}px;
                border: 2px dashed #d0d0d5;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                color: #9a9aa5;
                font-size: 13px;
                padding: 12px;
                background: #fafafc;
            ">
                📷 TODO: додати фото<br><code style="font-size:11px;">{path}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if caption:
            st.caption(caption)


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

# ── Sidebar nav ───────────────────────────────────────────────────────────────
SECTIONS = [
    "🏠 Вступ",
    "📋 Про дослідження",
    "🧮 Місткість",
    "📐 Площа на людину",
    "⚙️ Стан систем",
    "🔓 Доступність і відкритість",
    "🏗️ Типи укриттів",
    "🎯 Що далі",
]
section = st.sidebar.radio("Розділ", SECTIONS)

# ══════════════════════════════════════════════════════════════════════════════
# 1. ВСТУП
# ══════════════════════════════════════════════════════════════════════════════
if section == "🏠 Вступ":
    st.title("Чи вміщаємось ми в укриття?")

    st.markdown(
        """
Ранок після чергового масованого ракетного обстрілу. У соцмережах вкотре ширяться
фото переповнених станцій метро. У нас, як і у багатьох мешканців Києва, вкотре
постало питання: чи вистачає киянам укриттів?

В інтернеті легко знайти мапи сховищ Києва — тисячі точок, розкидані по місту.
Але якщо на мапі так багато укриттів, чому ж метро все одно переповнене?

Провівши власне опитування, ми зрозуміли: наявні мапи не показують повної картини.
Окрема точка на мапі нічого не каже про співвідношення місткості й населення —
ні по місту загалом, ні по районах.

Тож ми поставили собі просте запитання і спробували відповісти на нього цифрами.
        """
    )

    st.metric("Людей на станціях метро під час атаки 2 червня 2026", "понад 41 000")
    st.caption("Найбільше з 2024 року — джерело: звіт Омбудсмана, деталі в розділі «Про дослідження»")

    # TODO: користувач додасть фото
    image_or_placeholder("assets/metro_crowd.jpg", caption="Переповнена станція метро під час тривоги")

    st.divider()

    c1, c2, c3 = st.columns(3)
    c1.metric("Кількість укриттів, шт.", f"{int(kyiv['shelter_count']):,}")
    c2.metric("Загальна місткість, осіб", f"{int(kyiv['total_capacity']):,}")
    c3.metric("Загальна площа, м²", f"{int(kyiv['total_area']):,}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Людей на 1 місце", f"{kyiv['population_by_capacity']:.1f}")
    c5.metric("Кількість населення, осіб", f"{int(kyiv['population']):,}")
    c6.metric("Площа на 1 людину, м²", f"{kyiv_area_per_person:.2f}")

# ══════════════════════════════════════════════════════════════════════════════
# 2. ПРО ДОСЛІДЖЕННЯ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "📋 Про дослідження":
    st.title("Про дослідження")

    st.markdown(
        """
### Звідки ці дані

Дані про укриття ми зібрали з офіційної Мапи укриттів Києва (shelters.dsns.gov.ua) —
за допомогою python-скрипту витягнули всю доступну інформацію. Дані про населення
районів — з сайту КМДА; втім останній перепис населення в Києві був у 2001 році,
тож ці цифри — оцінка, а не точний підрахунок.
        """
    )

    with st.expander("Повна методологія, джерела та обмеження"):
        st.markdown(
            """
**Як рахували показники**
- «Людей на 1 місце» = населення району ÷ місткість укриттів району
- «Площа на людину» = сумарна площа укриттів району ÷ населення району
- Забезпеченість (вода/опалення/електрика/зв'язок): % укриттів району з наявною/справною категорією
- Доступність для МГН: % укриттів району, позначених як доступні для маломобільних груп

**Обмеження дослідження**
- Ми працюємо з тим, що нанесено на мапу — не з тим, що існує насправді. Респонденти
  нашого опитування неодноразово зазначали, що реальних укриттів більше, ніж позначених.
- Дані про населення — прогнозні оцінки на основі поточного обліку демографічних змін,
  реєстрації місця проживання та даних мобільних операторів, а не перепис.
- Категоризація укриттів є здебільшого умовною: об'єкти однієї категорії часто істотно
  різняться за станом. Крім того, сховища регулярно класифікують некоректно — наприклад,
  метро часто позначене як «найпростіше укриття», хоча за офіційними документами належить
  до споруд подвійного призначення (детальніше — у розділі «Типи укриттів»).

**Джерела даних**
- Мапа укриттів Києва: https://shelters.dsns.gov.ua/
- Населення районів: https://kyivcity.gov.ua/kyiv_ta_miska_vlada/pro_kyiv/raiony_kyieva/
- Методологія підрахунку населення: TODO — додати посилання (polityka.in.ua, tsn.ua)
- Геодані для мапи: https://github.com/denysboiko/kyivmap
- У роботі використовували генеративний ШІ для автоматизації написання скриптів парсингу
  й візуалізацій та підсумування державних документів; за весь згенерований код і
  написаний текст несемо відповідальність.

TODO: додати повні посилання з наданого документа (звіт Омбудсмана, аудит КМДА, обстеження Fight For Right)

**Попередні аудити (для порівняння)**
- Звіт Омбудсмана (травень 2026): 93% перевірених укриттів мали недоліки; найбільша
  проблема — доступність для маломобільних людей (27% без безбар'єрного доступу).
- Позапланова перевірка КМДА (червень 2023): лише 65% укриттів придатні до використання
  повністю; 14% не відповідають технічним вимогам взагалі.
- Обстеження Fight For Right (2023): позначені на мапі "пандуси" в Солом'янському районі
  виявились небезпечними залізними рейками, не пандусами.

**Команда**

Над проєктом працювали студентки Київської школи економіки: Марія Кобичева,
Дарина Кальченко, Діана Алдошина, Лілія Червонецька, Валерія Михайлишина —
у межах курсу «Дані і суспільство».

Код і дані відкриті: github.com/mkobycheva/kyiv-shelters-analysis
Питання та фідбек: maria.kobycheva@gmail.com
            """
        )

# ══════════════════════════════════════════════════════════════════════════════
# 3. МІСТКІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "🧮 Місткість":

    st.title("Чи вміщається Київ в укриття?")

    c1, c2, c3 = st.columns(3)
    c1.metric("Кількість укриттів, шт.", f"{int(kyiv['shelter_count']):,}")
    c2.metric("Загальна місткість, осіб", f"{int(kyiv['total_capacity']):,}")
    c3.metric("Загальна площа, м²", f"{int(kyiv['total_area']):,}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Людей на 1 місце", f"{kyiv['population_by_capacity']:.1f}")
    c5.metric("Кількість населення, осіб", f"{int(kyiv['population']):,}")
    c6.metric("Площа на 1 людину, м²", f"{kyiv_area_per_person:.2f}")

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
    st.plotly_chart(fig_choro, width="stretch")

    insight_card(
        """
        На ~2 900 000 осіб існує ~2 000 000 місць в укриттях.
        Тож навіть за ідеального сценарію, якщо всі укриття відкриті та доступні,
        близько 30% населення міста залишаються поза захистом.
        """
    )

# ══════════════════════════════════════════════════════════════════════════════
# 4. ПЛОЩА НА ЛЮДИНУ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "📐 Площа на людину":
    st.title("Площа на людину")

    st.markdown(
        """
### 0,6 м² — як воно є, як має бути

Згідно з ДБН В.2.2-5:2023, мінімальна норма площі в укритті — 0,5–3,0 м² на особу
залежно від типу об'єкта (0,6 м² — типове значення для найпростіших укриттів).
Половина районів Києва цю норму не проходить.

Але навіть там, де формально "норма" дотримана — чи достатньо 0,6 м² людині? Це площа
менша за розгорнуту газету. Норма розрахована на компактне стояння чи сидіння, а не на
реальний сценарій нічної тривоги, коли люди спускаються в укриття саме щоб поспати.

Ми вважаємо, що ця норма не відповідає здоровому глузду в умовах, для яких вона
насправді застосовується.
        """
    )

    st.divider()
    st.subheader("Площа укриття на людину")

    cap = agg["district_cap"].copy()
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
    st.plotly_chart(fig_bar, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# 5. СТАН СИСТЕМ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "⚙️ Стан систем":
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
        f"""
### Норма проти реальності

Норми ДБН В.2.2-5:2023 для сховищ передбачають: автономну роботу до 48 годин,
2 обов'язкові режими вентиляції, аварійний запас води 2-3 л/добу на особу.

Втім, у серпні 2025 року Наказ МВС №579 перевів вимоги до водопостачання,
резервного живлення, аптечок і засобів зв'язку для найпростіших укриттів
з обов'язкових у рекомендаційні.

Наша статистика показує, чому це важливо: опалення справне лише у третині
укриттів Києва ({status['Опалення']}%), інтернет — менш ніж у третині ({status['Інтернет']}%). Враховуючи
низькі температури минулої зими, це означає, що дві третини укриттів
непридатні для тривалого перебування взимку.
        """
    )

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

    insight_card(
        """
        Електрикою забезпечені майже всі укриття, водою - більше половини, а от опалення і інтернет наявні лише в третині укриттів Києва.
        Враховуючи низькі температури минулої зими, це фактично означає, що 2/3 укриттів непридатні для тривалого перебування в холодну пору року.
        Інтернет, хоча і не є критичною інфраструктурою, уможливлює зв'язок з рідними та оперативний доступ до новин,
        тож його відсутність створює інформаційний вакуум та підвищує рівень стресу містян.
        """
    )

# ══════════════════════════════════════════════════════════════════════════════
# 6. ДОСТУПНІСТЬ І ВІДКРИТІСТЬ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "🔓 Доступність і відкритість":
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
    st.plotly_chart(fig_mgn, width="stretch")

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
    st.plotly_chart(fig_oa_bar, width="stretch")

    insight_card(
        """
        Далеко не всі укриття доступні цілодобово: значна частина з них відчинена лише в робочий час,
        якась частка призначена виключно для працівників, а інші відкриваються лише за умови попереднього оповіщення.
        """
    )

    with st.expander("Що означають ці категорії відкритості?"):
        st.markdown(
            """
- **Постійно відчинене для населення** — доступ вільний у будь-який час доби
- **Для населення у робочий час** — доступ обмежений годинами роботи закладу/установи
- **Відчинене для населення лише у разі оповіщення** — двері відкриваються тільки
  під час сигналу тривоги
- **Лише для працівників у робочий час** — доступ мають тільки співробітники об'єкта
- **Безперешкодний доступ не забезпечено** — вхід технічно ускладнений або заблокований

**Чому так по-різному?**

Згідно зі ст. 8 Закону "Про правовий режим воєнного стану", саме військові
адміністрації мають визначати порядок використання захисних споруд — незалежно
від форми власності. Однак для Києва цей базовий документ досі не затверджений
або не оприлюднений, тому більшість укриттів фактично функціонують за
неформальними правилами, встановленими власником.

Подання укриття на облік також не є обов'язковим — воно ініціюється власником,
органами місцевого самоврядування або ДСНС. Але щойно об'єкт потрапляє до
реєстру, власника можна перевірити й оштрафувати за недопуск чи неналежне утримання.
            """
        )

# ══════════════════════════════════════════════════════════════════════════════
# 7. ТИПИ УКРИТТІВ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "🏗️ Типи укриттів":
    st.title("Типи укриттів")

    # ── 7a. Картки типів ────────────────────────────────────────────────────
    SHELTER_TYPES = [
        {
            "name": "Сховище",
            "photo": "assets/shelter_types/skhovyshche.jpg",
            "description": "Найзахищеніший тип споруди — герметична, розрахована на пряме влучання та повний спектр вражаючих факторів.",
            "protects_from": "Ударна хвиля (в т.ч. від зброї масового ураження), уламки, хімічні/радіоактивні/біологічні речовини, високі температури",
            "duration": "Не менше 48 год",
        },
        {
            "name": "ПРУ",
            "photo": "assets/shelter_types/pru.jpg",
            "description": "Протирадіаційне укриття — негерметична споруда, що захищає від радіації та частково від ударної хвилі, але не від хімічних чи біологічних агентів.",
            "protects_from": "Іонізуюче випромінювання, ударна хвиля (менший тиск), уламки, високі температури. НЕ захищає від хімічних/біологічних агентів (негерметична споруда)",
            "duration": "Не менше 48 год",
        },
        {
            "name": "Споруда подвійного призначення",
            "photo": "assets/shelter_types/spp.jpg",
            "description": "У мирний час — паркінг, перехід чи станція метро, але за проєктом має захисні властивості сховища або ПРУ, залежно від категорії.",
            "protects_from": "Те саме, що сховище або ПРУ — залежно від категорії проєктування",
            "duration": "Не менше 48 год",
        },
        {
            "name": "Найпростіше укриття",
            "photo": "assets/shelter_types/naiprostishe.jpg",
            "description": "Найпоширеніший тип у Києві — переобладнані підвали й техприміщення. Не розраховані на пряме влучання чи хімічну загрозу.",
            "protects_from": "Лише непряма дія звичайних засобів ураження (уламки, вибухова хвиля здалеку). НЕ захищає від прямого влучання чи хімічних/радіоактивних факторів",
            "duration": "Не менше 48 год",
        },
        {
            "name": "Первинне (мобільне) укриття",
            "photo": "assets/shelter_types/pervynne.jpg",
            "description": "Тимчасові споруди на відкритій місцевості — зупинки, павільйони в парках. Найслабший рівень захисту.",
            "protects_from": "Лише непряма дія на відкритій місцевості (зупинки, парки) — найслабший рівень захисту",
            "duration": "До 4 годин",
        },
    ]

    def render_type_card(t):
        with st.container(border=True):
            image_or_placeholder(t["photo"], height=160)
            st.markdown(f"**{t['name']}**")
            st.caption(t["description"])
            st.markdown(f"<span style='font-size:12px;color:#666;'>🛡️ Від чого захищає</span>", unsafe_allow_html=True)
            st.markdown(f"<span style='font-size:13px;'>{t['protects_from']}</span>", unsafe_allow_html=True)
            st.markdown(f"<span style='font-size:12px;color:#666;'>⏱️ Тривалість перебування</span>", unsafe_allow_html=True)
            st.markdown(f"<span style='font-size:13px;'>{t['duration']}</span>", unsafe_allow_html=True)

    row1 = st.columns(3)
    for col, t in zip(row1, SHELTER_TYPES[:3]):
        with col:
            render_type_card(t)

    row2 = st.columns(3)
    for col, t in zip(row2, SHELTER_TYPES[3:] + [None]):
        with col:
            if t:
                render_type_card(t)

    st.divider()

    # ── 7b. Мапа з прикладами ───────────────────────────────────────────────
    st.subheader("Приклади на мапі")
    st.caption(
        "Клікніть на точку, щоб побачити фото й опис конкретного укриття. "
        "TODO(маша): замінити нижче на повний список 10 підготовлених прикладів + фото."
    )

    # TODO(маша): замінити на реальні 10 прикладів з фото — schema нижче.
    SHELTER_EXAMPLES = [
        {
            "name": "Шухевича 4А",
            "type": "Сховище",
            "lat": 50.493648, "lon": 30.579104,
            "description": "TODO: додати реальний опис укриття.",
            "photo": "assets/shelter_examples/example_1.jpg",
        },
        {
            "name": "Станція метро «Берестейська»",
            "type": "Найпростіше укриття",
            "lat": 50.458400, "lon": 30.419930,
            "description": "TODO: додати реальний опис укриття.",
            "photo": "assets/shelter_examples/example_2.jpg",
        },
    ]

    example_df = pd.DataFrame(SHELTER_EXAMPLES)

    fig_examples = px.choropleth_mapbox(
        cap if "cap" in dir() else agg["district_cap"],
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
        opacity=0.5,
        hover_data={"district": False, "population_by_capacity": False},
    )
    fig_examples.update_traces(marker_line_width=0.5, marker_line_color="grey", showlegend=False)
    fig_examples.update_coloraxes(showscale=False)

    fig_examples.add_trace(go.Scattermapbox(
        lat=example_df["lat"],
        lon=example_df["lon"],
        mode="markers",
        marker=dict(size=16, color="#ff4b4b"),
        text=example_df["name"],
        customdata=example_df.index,
        hovertemplate="%{text}<extra></extra>",
        name="Приклади укриттів",
    ))

    fig_examples.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=520,
        showlegend=False,
    )

    @st.dialog("Приклад укриття")
    def show_shelter_dialog(example):
        image_or_placeholder(example["photo"], height=220)
        st.markdown(f"**{example['name']}**")
        st.caption(example["type"])
        st.write(example["description"])

    event = st.plotly_chart(
        fig_examples,
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key="example_map_select",
    )

    if event and event.get("selection") and event["selection"].get("points"):
        for point in event["selection"]["points"]:
            if point.get("curve_number") == 1:
                idx = point.get("point_index")
                if idx is not None and idx < len(SHELTER_EXAMPLES):
                    show_shelter_dialog(SHELTER_EXAMPLES[idx])
                break

    st.divider()

    # ── 7c. Сюжет про метро ─────────────────────────────────────────────────
    insight_card(
        """
        <b>То чому ж метро переповнене?</b><br><br>
        Станції метро в Києві класифікуються по-різному й непослідовно: деякі, як "Позняки",
        позначені як "найпростіше укриття", інші, як "Арсенальна" — як "споруда подвійного
        призначення із захисними властивостями сховища". Більш того, 36 з 50 станцій на мапі
        позначені кілька разів — кожен вихід окремо як найпростіше укриття, а сама станція
        окремо як споруда подвійного призначення.<br><br>
        Це створює ілюзію місткості. Наприклад, станція "Берестейська", враховуючи повторні
        відмітки, теоретично розрахована на 1000+1000+1048 = 3048 осіб — цифру, яку складно
        уявити реалістично, навіть з розрахунку 1 м² на особу.<br><br>
        Метро офіційно належить до споруд подвійного призначення — тобто, за нормативами,
        має відповідати вимогам, близьким до сховища. Але через некоректну категоризацію
        на мапі воно нерідко фігурує як "найпростіше укриття" — той самий тип, що й звичайний
        підвал. Це приклад того, як мапа, попри велику кількість точок, насправді ховає
        реальну картину доступного захисту.
        """
    )

    st.markdown(
        """
Це показовий приклад того, як великий масив даних (мапа з тисячами точок) може
одночасно виглядати прозорим і залишатися "чорною скринькою" — коли форма
(кількість позначок) створює враження повноти інформації, а зміст (реальна якість
і клас захисту) залишається непрозорим для людини, яка приймає рішення за лічені хвилини.
        """
    )

    st.divider()

    # ── Existing charts (вид споруди, тип локації) ──────────────────────────
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
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=0, r=20, t=10, b=70)
    )

    fig_shelter_kind.update_xaxes(
        range=[0, 100] if shelter_kind_percent else [0,
                                                     shelter_kind_dist.groupby("district")["values"].sum().max() * 1.05]
    )
    st.plotly_chart(fig_shelter_kind, width="stretch")

    insight_card(
        """
        Абсолютна більшість об'єктів — це найпростіші укриття, тобто пристосовані підвали,
        що не забезпечують повноцінних захисних властивостей. Частка повноцінних сховищ у Києві
        становить лише близько 2%.
        """
    )

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

    fig_location_type = px.bar(
        location_type_dist,
        x="values",
        y="district",
        color="Тип",
        category_orders={
            "Тип": location_type_categories
        },
        color_discrete_sequence=["#fa6e6e", "#ddcc77", "#88ccee"],
        orientation="h",
        barmode="stack",
        labels={"values": "% укриттів" if location_type_percent else "Кількість", "district": "Район"},
        height=440,
    )
    fig_location_type.update_layout(
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=0, r=0, t=10, b=70)
    )
    st.plotly_chart(fig_location_type, width="stretch")

    insight_card(
        """
        Майже всі укриття Києва є заглибленими, що чудовим сигналом.
        """
    )

# ══════════════════════════════════════════════════════════════════════════════
# 8. ЩО З ЦИМ РОБИТИ
# ══════════════════════════════════════════════════════════════════════════════
elif section == "🎯 Що далі":
    st.title("Що з цим робити")

    st.markdown(
        """
### Що далі

Наше дослідження показало: наявні дані про укриття Києва значною мірою є "чорною
скринькою" — загальна статистика, вимоги до сховищ, класифікація та частота
оновлення інформації не є прозорими для містян. Стан багатьох укриттів
незадовільний, а їх заявлена місткість — переоцінена.

Ми бачимо рішення у:

1. Підвищенні обізнаності громадян про реальну ситуацію з укриттями
2. Діалозі з органами місцевого самоврядування щодо регулярних аудитів,
   облаштування сховищ і перегляду норм на місткість
3. Створенні діджитал-платформи з актуальною інформацією від самих користувачів —
   аналог Google Maps, де кияни могли б лишати відгуки з фото та будувати маршрути
   до найближчого укриття

### Відкрите питання

Як наявність (чи відсутність) даних пов'язана з культурою спускання в укриття?
Чому мало людей ходять в укриття регулярно, а під час масованих обстрілів ми
маємо хаос? Проблема в забезпеченні укриттями чи в тому, як про них комунікують?
Чому не всі укриття є на мапі? Як забезпечити оперативний і правдивий обмін
інформацією між громадянами та владою?
        """
    )
