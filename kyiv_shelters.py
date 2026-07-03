import requests
import json
import csv

URL = "https://shelters.dsns.gov.ua/api/v1/public/ukryttya/get"

PAYLOAD = {
    "search": "", "versiyaId": None, "yeVyklyuchenoyu": None, "format": "json",
    "sortBy": "", "sortOrder": "", "skip": 0, "limit": 1000000,
    "rehionId": [26],  # 26 = Київ. [] = вся Україна
    "rayonId": [], "terytorialnaHromadaId": [], "nazvaNaselenohoPunktuId": [],
    "nazvaBalansoutrymuvacha": "", "yurydychnaAdresaBalansoutrymuvacha": "",
    "oblikovyyNomerMistyt": "", "minMistkist": None, "maxMistkist": None,
    "vidomchaPrynalezhnistId": [], "formaVlasnostiId": [],
    "rezhymyFiltroventylyatsiyiId": [], "vydSporudyId": [], "typSporudyId": [],
    "stanHotovnostiId": [], "katehoriyaNaselennyaId": [], "nebezpechniZonyId": [],
    "minRikVvedennyaVEkspluatatsiyu": None, "maxRikVvedennyaVEkspluatatsiyu": None,
    "statusProvedennyaInventaryzatsiyi": None,
    "nayavnistDostupuMalomobilnykhVerstvNaselennya": None,
    "reyestrovyyNomerSporudy": "", "nayavnistYERODV": None, "zakhysniVlastyvostiId": [],
    "dataProvedennyaOtsinkyStanuHotovnosti": "", "minPloshcha": None, "maxPloshcha": None,
    "searchOnlyFields": [], "nazvaRayonuMistaId": [], "osnovnyjVydEkonDiyalnostiId": [],
    "nayavniZasobyZvyazkuId": [],
    "isMinimumInfo": False,  # False = повні дані по кожному укриттю
}

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://shelters.dsns.gov.ua/",
    "Origin": "https://shelters.dsns.gov.ua",
}

def fetch_shelters():
    print("Завантажуємо дані...")
    r = requests.post(URL, json=PAYLOAD, headers=HEADERS, timeout=120)
    r.raise_for_status()
    data = r.json()
    items = data["data"]["items"]
    print(f"✅ Знайдено: {len(items)} укриттів")
    if items:
        print(f"   Поля: {list(items[0].keys())}")
    return items

def save_json(items, filename="kyiv_shelters.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"📥 Збережено: {filename}")

def save_csv(items, filename="kyiv_shelters.csv"):
    if not items:
        return
    # Збираємо всі можливі ключі (деякі поля можуть бути відсутні в окремих записах)
    keys = list(dict.fromkeys(k for item in items for k in item.keys()))
    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)
    print(f"📥 Збережено: {filename}")

if __name__ == "__main__":
    items = fetch_shelters()
    save_json(items)
    save_csv(items)