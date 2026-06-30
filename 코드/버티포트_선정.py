from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
QGIS_DIR = BASE_DIR / "QGIS"
RESULT_DIR = BASE_DIR / "결과"
RESULT_DIR.mkdir(exist_ok=True)

SI_DO_PATH = QGIS_DIR / "시군구.shp"

# SI_DO 안에서 개수를 셀 value 레이어들입니다.
# 같은 value로 묶고 싶은 shp는 리스트에 같이 넣으면 합산됩니다.
VALUE_SOURCES = {
    "Company": ["2026년_상호출자제한기업_핵심거점들.shp"],
    "MICE": ["MICE_선정_Convention.shp", "MICE_시설.shp"],
    "Korea_Tourist": ["한국관광100선_수도권_관광지_주소_좌표숫자변환.shp"],
    "Shopping_Mall": ["복합쇼핑몰.shp"],
    "Subway": ["지하철역_정보.shp"],
}


def read_layer(path: Path) -> gpd.GeoDataFrame:
    """Read shapefile while tolerating mixed DBF encodings."""
    errors: list[str] = []
    for encoding in (None, "utf-8", "cp949", "euc-kr", "latin1"):
        try:
            if encoding is None:
                return gpd.read_file(path)
            return gpd.read_file(path, encoding=encoding)
        except Exception as exc:
            errors.append(f"{encoding or 'default'}: {exc}")

    raise RuntimeError(f"{path.name} 파일을 읽지 못했습니다.\n" + "\n".join(errors))


def clean_geometry(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if hasattr(gdf.geometry, "make_valid"):
        gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def load_value(files: list[str], target_crs) -> gpd.GeoDataFrame:
    layers = []
    for file_name in files:
        layer = clean_geometry(read_layer(QGIS_DIR / file_name))
        if layer.crs != target_crs:
            layer = layer.to_crs(target_crs)
        layers.append(layer[["geometry"]])

    return pd.concat(layers, ignore_index=True)


def value_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Use one point per value so one object is counted once."""
    points = gdf[["geometry"]].copy()
    is_point = points.geom_type.isin(["Point", "MultiPoint"])
    if not is_point.all():
        points.loc[~is_point, "geometry"] = points.loc[
            ~is_point, "geometry"
        ].representative_point()
    return points


def count_values_in_boundary(
    boundary: gpd.GeoDataFrame,
    boundary_id_col: str,
    boundary_name_col: str,
) -> gpd.GeoDataFrame:
    output = boundary[[boundary_id_col, boundary_name_col]].copy()

    for value_name, files in VALUE_SOURCES.items():
        values = value_points(load_value(files, boundary.crs))
        joined = gpd.sjoin(
            values,
            boundary[[boundary_id_col, "geometry"]],
            how="inner",
            predicate="within",
        )

        # 경계가 겹치는 예외 상황에서도 value 하나가 한 번만 세어지도록 처리합니다.
        joined = joined[~joined.index.duplicated(keep="first")]
        counts = joined.groupby(boundary_id_col).size()
        output[value_name] = (
            output[boundary_id_col].map(counts).fillna(0).astype(int)
        )

    value_cols = list(VALUE_SOURCES)
    output["Total"] = output[value_cols].sum(axis=1)
    return output.sort_values(boundary_id_col).reset_index(drop=True)


SI_DO = clean_geometry(read_layer(SI_DO_PATH))
SI_DO["SIGUNGU_CD"] = SI_DO["SIGUNGU_CD"].astype(str)

# 1. 시군구 단위: 수원시 영통구, 성남시 분당구처럼 세부 행정구 기준
sigungu_counts = count_values_in_boundary(SI_DO, "SIGUNGU_CD", "SIGUNGU_NM")
sigungu_counts.to_csv(
    RESULT_DIR / "SI_DO_value_개수_시군구.csv",
    index=False,
    encoding="utf-8-sig",
)

# 2. 시 단위: 성남시, 수원시처럼 City_NAME 기준으로 행정구를 합쳐서 집계
SI_DO_CITY = SI_DO.copy()
SI_DO_CITY["CITY_CD"] = SI_DO_CITY["SIGUNGU_CD"].str[:4] + "0"
SI_DO_CITY["CITY_NM"] = SI_DO_CITY["City_NAME"].fillna(SI_DO_CITY["SIGUNGU_NM"])
SI_DO_CITY = SI_DO_CITY.dissolve(
    by=["CITY_CD", "CITY_NM"],
    as_index=False,
)

city_counts = count_values_in_boundary(SI_DO_CITY, "CITY_CD", "CITY_NM")
city_counts.to_csv(
    RESULT_DIR / "SI_DO_value_개수_시단위.csv",
    index=False,
    encoding="utf-8-sig",
)

print("[시단위 집계]")
print(city_counts.to_string(index=False))
print("\n[시군구 집계]")
print(sigungu_counts.to_string(index=False))
