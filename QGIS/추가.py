import geopandas as gpd
import pandas as pd
from pathlib import Path

print("실행 시작")

BASE_DIR = Path(__file__).resolve().parent

input_path = BASE_DIR / "기존건물" / "Metropolitan_buildings(Incheon,Gyeong_Gi,Seoul).shp"
output_path = BASE_DIR / "헬기장_의무_건물" / "A14_39000초과_11층초과_건물.gpkg"

output_path.parent.mkdir(parents=True, exist_ok=True)

# =========================
# 인코딩 fallback
# =========================
def read_shp_with_encoding(path):
    for enc in ["cp949", "utf-8"]:
        try:
            print(f"{enc} 인코딩 시도...")
            gdf = gpd.read_file(path, encoding=enc)
            print(f"{enc} 성공")
            return gdf

        except Exception as e:
            print(f"{enc} 실패:", e)

    raise RuntimeError("파일을 읽을 수 없습니다.")

# =========================
# 파일 읽기
# =========================
gdf = read_shp_with_encoding(input_path)

print("전체 피처 수:", len(gdf))

# =========================
# 숫자형 변환
# =========================
gdf["A14"] = pd.to_numeric(gdf["A14"], errors="coerce")
gdf["A26"] = pd.to_numeric(gdf["A26"], errors="coerce")

# =========================
# 조건 필터링
# A14 > 39000
# A26 > 11
# =========================
filtered_gdf = gdf[
    (gdf["A14"].notna()) &
    (gdf["A14"] > 39000) &

    (gdf["A26"].notna()) &
    (gdf["A26"] > 11)
].copy()

print("조건 만족 피처 수:", len(filtered_gdf))

# =========================
# 기존 파일 삭제
# =========================
if output_path.exists():
    output_path.unlink()
    print("기존 결과 파일 삭제 완료")

# =========================
# 저장
# =========================
filtered_gdf.to_file(
    output_path,
    layer="filtered",
    driver="GPKG"
)

print("저장 완료:", output_path)
print("완료")