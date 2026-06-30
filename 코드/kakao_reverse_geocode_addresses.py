import time
from pathlib import Path

import pandas as pd
import requests
from pyproj import Transformer


BASE_DIR = Path(r"C:\Users\c\Desktop\대학생활\학연생\새로운_경로방식\자료\버티포트")

INPUT_XLSX = BASE_DIR / "각_지역별_버티포트_후보군(중심점)_1.xlsx"
OUTPUT_XLSX = BASE_DIR / "각_지역별_버티포트_후보군(중심점)_주소추가.xlsx"

KAKAO_REST_API_KEY = "f1161b2a855cf332983a74de75da4167"

df = pd.read_excel(INPUT_XLSX)

x_col = "MEAN_X"
y_col = "MEAN_Y"

if x_col not in df.columns or y_col not in df.columns:
    raise RuntimeError(f"엑셀에 '{x_col}', '{y_col}' 컬럼이 필요합니다.")

transformer = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)

lon_col = "경도"
lat_col = "위도"
addr_col = "주소"

lons = []
lats = []

for _, row in df.iterrows():
    x = row[x_col]
    y = row[y_col]

    if pd.isna(x) or pd.isna(y):
        lons.append(None)
        lats.append(None)
        continue

    lon, lat = transformer.transform(float(x), float(y))
    lons.append(lon)
    lats.append(lat)

df[lon_col] = lons
df[lat_col] = lats

if addr_col not in df.columns:
    df[addr_col] = ""


def kakao_reverse_geocode(lon, lat):
    if pd.isna(lon) or pd.isna(lat):
        return ""

    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
    }

    params = {
        "x": str(lon),
        "y": str(lat)
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)

    if response.status_code != 200:
        return f"ERROR {response.status_code}: {response.text[:200]}"

    data = response.json()
    documents = data.get("documents", [])

    if not documents:
        return ""

    doc = documents[0]

    road = doc.get("road_address")
    address = doc.get("address")

    if road and road.get("address_name"):
        return road["address_name"]

    if address and address.get("address_name"):
        return address["address_name"]

    return ""


for idx, row in df.iterrows():
    lon = row[lon_col]
    lat = row[lat_col]

    try:
        address = kakao_reverse_geocode(lon, lat)
        df.at[idx, addr_col] = address
        print(f"{idx + 1}/{len(df)} 완료: {address}")

    except Exception as e:
        df.at[idx, addr_col] = f"ERROR: {e}"
        print(f"{idx + 1}/{len(df)} 오류: {e}")

    time.sleep(0.15)

df.to_excel(OUTPUT_XLSX, index=False)

print(f"\n완료: {OUTPUT_XLSX}")