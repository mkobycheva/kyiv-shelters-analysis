# AGENTS.md — Kyiv Shelters Analysis

## Project Overview

A Streamlit web app analyzing Kyiv's civil defense shelters by capacity, type, system condition, accessibility, and openness. Data comes from open government sources.

## Repository Structure

```
kyiv-shelters-analysis/
├── shelters_analysis.py      # Main Streamlit app
├── kyiv_shelters.json        # Raw shelter data (source of truth)
├── kyiv.34272c8c.geojson     # Kyiv district boundaries (10 districts)
├── header.png                # Hero image for the landing section
├── .gitignore                # Contains .idea/
└── AGENTS.md
```

## Running the App

```bash
pip install streamlit plotly folium streamlit-folium
streamlit run shelters_analysis.py
```

App runs at `localhost:8501`.

## App Structure

Single-file Streamlit app with sidebar radio navigation. Four sections:

- **Місткість** — capacity map + bar chart
- **Типи укриттів** — shelter type breakdown
- **Стан систем** — system condition heatmap
- **Доступність і відкритість** — accessibility + openness (merged section)

## Data Pipeline

### Raw Data (`kyiv_shelters.json`)

Each record is a shelter with nested objects. Key extraction pattern:

```python
def nested(record, key):
    obj = record.get(key)
    if isinstance(obj, dict):
        return obj.get("imya")
    return None
```

Key fields extracted: `district`, `lat` (from `shyrota`), `lon` (from `dovhota`), `capacity` (from `mistkistOsib`), `area_m2` (from `ploshcha`), `shelter_kind`, `location_type`, `functional_purpose`, `water`, `heating`, `power`, `communication`, `accessible_mgn`, `open_access`.

Note: `lat` comes as a string and needs `.str.rstrip(', ')` before `pd.to_numeric`.

### District Population (hardcoded)

```python
district_population_data = {
    "Дніпровський": 354_700, "Святошинський": 340_700,
    "Подільський": 198_100,  "Деснянський": 358_300,
    "Голосіївський": 247_600, "Солом'янський": 383_259,
    "Оболонський": 319_000,  "Печерський": 152_000,
    "Шевченківський": 218_900, "Дарницький": 314_700,
}
```

⚠️ The apostrophe in `"Солом'янський"` must be a straight apostrophe (`'`), not a curly one (`'`). If the district shows no color on the map, this is the likely cause — retype the key manually.

### GeoJSON

Districts in the GeoJSON have `NAME` like `"Солом'янський район"`. The app strips `" район"` to join with data:

```python
for feat in geojson["features"]:
    feat["properties"]["district"] = feat["properties"]["NAME"].replace(" район", "")
```

### Aggregates (built in `build_aggregates(df)`)

All computed with `@st.cache_data`:

- `district_cap` / `kyiv_cap` — capacity, area, population, people-per-spot, m²-per-person
- `district_shelter_kinds` / `kyiv_shelter_kinds` — by `shelter_kind`
- `district_location_types` / `kyiv_location_types` — by `location_type`
- `district_functional` / `kyiv_functional` — by `functional_purpose`
- `water_report`, `heating_report`, `power_report`, `comm_report` — utility status per district
- `df_total_status` — city-level % with working systems
- `mgn_report` / `df_total_mgn` — accessibility for people with limited mobility
- `district_open_access` / `kyiv_open_access` — who the shelter is open to

### Utility Cleaning Logic

Text fields for water/heating/power are cleaned into three categories: `"Наявна/Справна"`, `"Відсутня/Несправна"`, `"Інше/Невідомо"`. Communication maps to `"Є інтернет (Wi-Fi/Дротовий)"` or `"Зв'язок відсутній"`.

## Visualizations

| Section | Chart type | Library |
|---|---|---|
| Capacity — district map | Choropleth mapbox (color = people per spot) + scatter dots (all shelters) | Plotly |
| Capacity — bar | Horizontal bar, m² per person, RdYlGn color | Plotly |
| Shelter types | Stacked bar (by district) + donut (city total), 3 tabs | Plotly |
| System condition | Heatmap, districts × systems, RdYlGn | Plotly |
| MGN accessibility | Horizontal bar, RdYlGn, sorted worst→best | Plotly |
| Openness | Stacked bar (by district) + donut (city total) | Plotly |

Map config: `zoom=9`, `center={"lat": 50.45, "lon": 30.52}`, `mapbox_style="carto-positron"`.

## Styling

Font: Montserrat via Google Fonts, applied with `* { font-family: 'Montserrat', sans-serif !important; }` in `st.markdown`.

Hero image: `header.png` loaded as base64, rendered as full-bleed HTML div with gradient overlay (`linear-gradient(to top, rgba(0,0,0,0.7), transparent)`) and title text positioned bottom-left.

Key CSS overrides (all in one `st.markdown` block at the top):

- `[data-testid="metric-container"]` — removes border/shadow from metric cards
- `[data-testid="collapsedControl"]` — hides sidebar collapse arrow
- `[data-testid="stAppViewContainer"] > .main > .block-container` — removes padding for full-bleed hero; padding is restored inside content sections

## Known Issues / Watch Out For

- `"Солом'янський"` apostrophe type mismatch breaks map color and bar chart for that district
- `lat` field in raw JSON is a string with occasional trailing `, ` — must be stripped before numeric conversion
- `st.columns(5)` must match exactly 5 unpacking variables for the metrics row
- The `comm_report` good-label column is `"Є інтернет (Wi-Fi/Дротовий) (%)"` — check this key exists before accessing
- Header image only shows on the "Місткість" section (intentional)

## Deployment

Hosted on Streamlit Cloud, connected to the GitHub repo `mkobycheva/kyiv-shelters-analysis`. Push to `main` → auto-redeploy.

## Agent Workflow

After making a requested change, commit and push the change so Streamlit Cloud can deploy the updated visuals.
