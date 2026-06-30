import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

print("실행 시작")

# =========================
# 현재 py 파일 기준 경로
# =========================
BASE_DIR = Path(__file__).resolve().parent
print("BASE_DIR:", BASE_DIR)

# =========================
# 경로 설정
# =========================
input_path = BASE_DIR / "기존건물" / "Metropolitan_buildings(Incheon,Gyeong_Gi,Seoul).shp"
base_path = BASE_DIR / "기존건물" / "기준.shp"
output_path = BASE_DIR / "헬기장_의무_건물" / "연면적_10000m2_그리고_11층_이상_건물.shp"

output_path.parent.mkdir(parents=True, exist_ok=True)

# =========================
# 인코딩 fallback 함수
# =========================
def read_shp_with_encoding(path):
    for enc in ["cp949", "utf-8"]:
        try:
            print(f"\n{path.name} - {enc} 인코딩 시도...")
            gdf = gpd.read_file(path, encoding=enc)
            print(f"{path.name} - {enc} 성공")
            return gdf
        except Exception as e:
            print(f"{path.name} - {enc} 실패:", e)

    raise RuntimeError(f"{path} 파일을 읽을 수 없습니다.")

# =========================
# 파일 존재 확인
# =========================
if not input_path.exists():
    raise FileNotFoundError(f"input 파일 없음: {input_path}")

if not base_path.exists():
    raise FileNotFoundError(f"기준 파일 없음: {base_path}")

# =========================
# 파일 읽기
# =========================
gdf = read_shp_with_encoding(input_path)
base_gdf = read_shp_with_encoding(base_path)

print("\n원본 피처 수:", len(gdf))
print("기준 피처 수:", len(base_gdf))

if len(base_gdf) != 1:
    raise ValueError("기준.shp에는 피처가 정확히 1개만 있어야 합니다.")

# =========================
# 필수 컬럼 확인
# =========================
required_cols = ["A12", "A14", "A26"]

for col in required_cols:
    if col not in gdf.columns:
        raise KeyError(f"원본 데이터에 {col} 컬럼이 없습니다.")

    if col not in base_gdf.columns:
        raise KeyError(f"기준 데이터에 {col} 컬럼이 없습니다.")

# =========================
# 숫자형 변환
# =========================
for col in required_cols:
    gdf[col] = pd.to_numeric(gdf[col], errors="coerce")
    base_gdf[col] = pd.to_numeric(base_gdf[col], errors="coerce")

# =========================
# 면적 계산용 좌표계 변환
# =========================
target_crs = "EPSG:5186"

gdf = gdf.to_crs(target_crs)
base_gdf = base_gdf.to_crs(target_crs)

# =========================
# polygon 면적 계산
# =========================
gdf["geom_area"] = gdf.geometry.area
base_gdf["geom_area"] = base_gdf.geometry.area

# =========================
# 기준 피처 정보
# A12 = 바닥면적
# A14 = 연면적
# =========================
base_a12 = base_gdf.iloc[0]["A12"]
base_geom_area = base_gdf.iloc[0]["geom_area"]

if pd.isna(base_a12) or base_a12 <= 0:
    raise ValueError("기준.shp의 A12 값이 유효하지 않습니다.")

if pd.isna(base_geom_area) or base_geom_area <= 0:
    raise ValueError("기준.shp의 geometry 면적이 유효하지 않습니다.")

print("\n기준 A12:", base_a12)
print("기준 polygon 면적:", base_geom_area)

# =========================
# 1단계:
# A12 추정
#
# A12_estimated =
# (input polygon 면적 / base polygon 면적)
# * base A12
# =========================
missing_a12_mask = (
    gdf["A12"].isna() |
    (gdf["A12"] == 0)
)

valid_geom_mask = (
    gdf["geom_area"].notna() &
    (gdf["geom_area"] > 0)
)

estimate_a12_mask = (
    missing_a12_mask &
    valid_geom_mask
)

print("\nA12 추정 대상:", estimate_a12_mask.sum())

gdf["A12_estimated"] = np.nan

gdf.loc[estimate_a12_mask, "A12_estimated"] = (
    gdf.loc[estimate_a12_mask, "geom_area"]
    / base_geom_area
) * base_a12

# 최종 A12
gdf["A12_final"] = gdf["A12"]

gdf.loc[estimate_a12_mask, "A12_final"] = gdf.loc[
    estimate_a12_mask,
    "A12_estimated"
]

# =========================
# 2단계:
# A14 추정
#
# A14 = A12 * A26
# =========================
missing_a14_mask = (
    gdf["A14"].isna() |
    (gdf["A14"] == 0)
)

valid_a26_mask = (
    gdf["A26"].notna() &
    (gdf["A26"] > 0)
)

estimate_a14_mask = (
    missing_a14_mask &
    valid_a26_mask &
    gdf["A12_final"].notna()
)

print("A14 추정 대상:", estimate_a14_mask.sum())

gdf["A14_estimated"] = np.nan

gdf.loc[estimate_a14_mask, "A14_estimated"] = (
    gdf.loc[estimate_a14_mask, "A12_final"]
    * gdf.loc[estimate_a14_mask, "A26"]
)

# 최종 A14
gdf["A14_final"] = gdf["A14"]

gdf.loc[estimate_a14_mask, "A14_final"] = gdf.loc[
    estimate_a14_mask,
    "A14_estimated"
]

# =========================
# 조건 필터링
# A14 >= 10000
# A26 >= 11
# =========================
filtered_gdf = gdf[
    (gdf["A14_final"].notna()) &
    (gdf["A14_final"] >= 10000) &
    (gdf["A26"].notna()) &
    (gdf["A26"] >= 11)
].copy()

print("\n조건 만족 피처 수:", len(filtered_gdf))

# =========================
# 저장
# =========================
try:
    print("\ncp949 저장 시도...")
    filtered_gdf.to_file(output_path, encoding="cp949")
    print("cp949 저장 성공")

except Exception as e:
    print("cp949 저장 실패:", e)

    print("utf-8 저장 시도...")
    filtered_gdf.to_file(output_path, encoding="utf-8")
    print("utf-8 저장 성공")

print("\n완료")