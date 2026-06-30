# -*- coding: utf-8 -*-
from pathlib import Path

import geopandas as gpd
import pandas as pd
import networkx as nx

from vector_encoding import read_vector, write_csv_with_fallback


# =========================
# 1. 경로 설정
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]
QGIS_DIR = BASE_DIR / "QGIS"
RESULT_DIR = BASE_DIR / "코드" / "결과"
RESULT_DIR.mkdir(exist_ok=True)


# =========================
# 2. 수요 지점 shp 설정
# =========================
POINT_SOURCES = {
    "Company": [
        "2026년_상호출자제한기업_핵심거점들.shp"
    ],
    "MICE": [
        "MICE_선정_Convention.shp",
    ],
    "Korea_Tourist": [
        "한국관광100선_수도권_관광지_주소_좌표숫자변환.shp"
    ],
    "Shopping_Mall": [
        "복합쇼핑몰.shp",
    ],
}


# =========================
# 3. 수요 지점 통합
# =========================
gdfs = []

for point_type, file_list in POINT_SOURCES.items():
    for filename in file_list:
        path = QGIS_DIR / filename

        if not path.exists():
            print(f"파일 없음: {path}")
            continue

        gdf = read_vector(path)

        # 좌표계 없으면 EPSG:4326으로 가정
        # 이미 QGIS에서 좌표계가 지정되어 있다면 이 부분은 자동 처리됩니다.
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=5186)

        # 거리 계산용 좌표계
        gdf = gdf.to_crs(epsg=5186)

        gdf["type"] = point_type
        gdf["source_file"] = filename

        # 이름 컬럼 자동 탐색
        possible_name_cols = [
            "name",
            "NAME",
            "이름",
            "상호",
            "점포명",
            "시설명",
            "시설명칭",
            "MICE 건",
            "MICE 건물",
            "관광지명",
            "관광지",
            "기업명",
            "회사명",
            "명칭",
            ]
        name_col = None

        for col in possible_name_cols:
            if col in gdf.columns:
                name_col = col
                break

        if name_col is not None:
            gdf["node_name"] = gdf[name_col].astype(str)
        else:
            gdf["node_name"] = point_type + "_" + gdf.index.astype(str)

        gdfs.append(gdf[["node_name", "type", "source_file", "geometry"]])

if not gdfs:
    raise RuntimeError("읽을 수 있는 수요 지점 shp가 없습니다.")

points = pd.concat(gdfs, ignore_index=True)
points = gpd.GeoDataFrame(points, geometry="geometry", crs="EPSG:5186")

# 혹시 MultiPoint 등이 있으면 centroid로 처리
points["geometry"] = points.geometry.centroid

print(f"전체 수요 지점 수: {len(points)}")


# =========================
# 4. 노드 가중치 설정
# =========================
TYPE_WEIGHT = {
    "MICE": 1.0,
    "Korea_Tourist": 1.0,
    "Shopping_Mall": 1.0,
    "Company": 1.0,
}

points["weight"] = points["type"].map(TYPE_WEIGHT).fillna(1.0)


# =========================
# 5. 거리 기준 그래프 생성
# =========================
DIST_THRESHOLD_M = 5000  # 5km 기준. 필요하면 3000으로 변경

G = nx.Graph()

# 노드 추가
for idx, row in points.iterrows():
    G.add_node(
        idx,
        name=row["node_name"],
        type=row["type"],
        weight=row["weight"],
        geometry=row.geometry,
    )

# 간선 추가
for i in range(len(points)):
    geom_i = points.geometry.iloc[i]

    for j in range(i + 1, len(points)):
        geom_j = points.geometry.iloc[j]
        dist = geom_i.distance(geom_j)

        if dist <= DIST_THRESHOLD_M:
            G.add_edge(i, j, distance_m=dist)


print(f"노드 수: {G.number_of_nodes()}")
print(f"간선 수: {G.number_of_edges()}")


# =========================
# 6. Clique 탐색
# =========================
cliques = list(nx.find_cliques(G))

result_columns = [
    "clique_id",
    "node_count",
    "type_count",
    "total_weight",
    "radius_m",
    "center_x_5186",
    "center_y_5186",
    "members",
    "types",
]
records = []

for c_id, clique in enumerate(cliques, start=1):
    if len(clique) < 3:
        continue

    clique_points = points.loc[clique].copy()

    total_weight = clique_points["weight"].sum()
    type_count = clique_points["type"].nunique()
    node_count = len(clique_points)

    # 권역 중심점: weighted centroid 대신 단순 centroid 사용
    center_x = clique_points.geometry.x.mean()
    center_y = clique_points.geometry.y.mean()

    # 권역 반경: 중심점에서 가장 먼 점까지 거리
    center_geom = gpd.points_from_xy([center_x], [center_y], crs="EPSG:5186")[0]
    radius_m = clique_points.geometry.distance(center_geom).max()

    records.append({
        "clique_id": c_id,
        "node_count": node_count,
        "type_count": type_count,
        "total_weight": total_weight,
        "radius_m": radius_m,
        "center_x_5186": center_x,
        "center_y_5186": center_y,
        "members": ", ".join(clique_points["node_name"].tolist()),
        "types": ", ".join(clique_points["type"].tolist()),
    })

clique_result = pd.DataFrame(records, columns=result_columns)

# 점수 정렬
if not clique_result.empty:
    clique_result = clique_result.sort_values(
        by=["total_weight", "type_count", "node_count"],
        ascending=False
    ).reset_index(drop=True)

clique_result["rank"] = clique_result.index + 1


# =========================
# 7. 결과 저장
# =========================
out_csv = RESULT_DIR / f"clique_후보권역_{DIST_THRESHOLD_M}m.csv"
write_csv_with_fallback(clique_result, out_csv)

print(f"저장 완료: {out_csv}")
print(clique_result.head(10))
