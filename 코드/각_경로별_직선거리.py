import time
from pathlib import Path

import pandas as pd
from pyproj import Geod


# =========================
# 1. 경로 설정
# =========================
BASE_DIR = Path(r"C:\Users\c\Desktop\대학생활\학연생\새로운_경로방식\자료\버티포트")

INPUT_XLSX = BASE_DIR / "각_지역별_버티포트_후보군(중심점)_주소추가_최종.xlsx"
OUTPUT_XLSX = BASE_DIR / "좌표기반_후보지_직선거리_matrix.xlsx"


# =========================
# 2. 실행 설정
# =========================
TEST_LIMIT = None
# 전체 실행하려면 아래처럼 변경
# TEST_LIMIT = None


# =========================
# 3. 입력 데이터
# =========================
region_col = "지역"
lon_col = "경도"
lat_col = "위도"

df = pd.read_excel(INPUT_XLSX)

for col in [region_col, lon_col, lat_col]:
    if col not in df.columns:
        raise RuntimeError(f"엑셀에 '{col}' 컬럼이 필요합니다.")

df = df[[region_col, lon_col, lat_col]].copy()
df = df.dropna(subset=[lon_col, lat_col]).reset_index(drop=True)

df["후보지_ID"] = df.index + 1
df["후보지_label"] = (
    df["후보지_ID"].astype(str).str.zfill(2)
    + "_"
    + df[region_col].astype(str)
)

print(f"후보지 개수: {len(df)}")


# =========================
# 4. 좌표 기반 거리 계산 함수
# =========================
geod = Geod(ellps="WGS84")


def calculate_geodesic_distance(start_lon, start_lat, end_lon, end_lat):
    """
    WGS84 경위도 좌표를 이용해 두 지점 간 측지거리 계산.
    반환:
    - distance_km: 거리 km
    - forward_azimuth: 출발지 기준 도착지 방향각
    - back_azimuth: 도착지 기준 출발지 방향각
    """

    forward_azimuth, back_azimuth, distance_m = geod.inv(
        float(start_lon),
        float(start_lat),
        float(end_lon),
        float(end_lat)
    )

    distance_km = round(distance_m / 1000, 3)
    forward_azimuth = round(forward_azimuth, 2)
    back_azimuth = round(back_azimuth, 2)

    return distance_km, forward_azimuth, back_azimuth


def make_linestring_wkt(start_lon, start_lat, end_lon, end_lat):
    """
    QGIS에서 불러올 수 있는 직선 경로 WKT 생성.
    좌표 순서: 경도 위도
    """
    return (
        f"LINESTRING("
        f"{float(start_lon)} {float(start_lat)}, "
        f"{float(end_lon)} {float(end_lat)}"
        f")"
    )


# =========================
# 5. 모든 OD 경우의 수 계산
# =========================
records = []

n = len(df)
total_cases = n * (n - 1)

case_no = 0
stop_loop = False

for i, origin in df.iterrows():
    for j, dest in df.iterrows():
        if i == j:
            continue

        if TEST_LIMIT is not None and case_no >= TEST_LIMIT:
            stop_loop = True
            break

        case_no += 1

        origin_id = int(origin["후보지_ID"])
        dest_id = int(dest["후보지_ID"])

        origin_region = str(origin[region_col])
        dest_region = str(dest[region_col])

        origin_label = str(origin["후보지_label"])
        dest_label = str(dest["후보지_label"])

        origin_lon = origin[lon_col]
        origin_lat = origin[lat_col]
        dest_lon = dest[lon_col]
        dest_lat = dest[lat_col]

        route_label = f"{origin_label} -> {dest_label}"

        if (
            pd.isna(origin_lon)
            or pd.isna(origin_lat)
            or pd.isna(dest_lon)
            or pd.isna(dest_lat)
        ):
            distance_km = None
            forward_azimuth = None
            back_azimuth = None
            route_wkt = ""
            status = "MISSING_COORD"
        else:
            try:
                distance_km, forward_azimuth, back_azimuth = calculate_geodesic_distance(
                    origin_lon,
                    origin_lat,
                    dest_lon,
                    dest_lat
                )

                route_wkt = make_linestring_wkt(
                    origin_lon,
                    origin_lat,
                    dest_lon,
                    dest_lat
                )

                status = "OK"

            except Exception as e:
                distance_km = None
                forward_azimuth = None
                back_azimuth = None
                route_wkt = ""
                status = f"ERROR: {e}"

        denominator = TEST_LIMIT if TEST_LIMIT is not None else total_cases

        vs_code_output = (
            f"{case_no}/{denominator} "
            f"{route_label} | "
            f"직선거리: {distance_km}km | "
            f"방위각: {forward_azimuth}deg | "
            f"{status}"
        )

        records.append({
            "case_no": case_no,
            "total_cases": denominator,

            "origin_id": origin_id,
            "origin_region": origin_region,
            "origin_label": origin_label,
            "origin_lon": origin_lon,
            "origin_lat": origin_lat,

            "dest_id": dest_id,
            "dest_region": dest_region,
            "dest_label": dest_label,
            "dest_lon": dest_lon,
            "dest_lat": dest_lat,

            "route_label": route_label,

            "duration_min": None,
            "distance_km": distance_km,

            "forward_azimuth_deg": forward_azimuth,
            "back_azimuth_deg": back_azimuth,

            "route_wkt": route_wkt,

            "status": status,
            "VS_Code_출력": vs_code_output
        })

        print(vs_code_output)

    if stop_loop:
        break


result_df = pd.DataFrame(records)


# =========================
# 6. 컬럼 분리 요약표 생성
# =========================
summary_df = result_df[
    [
        "case_no",
        "total_cases",

        "origin_id",
        "origin_region",
        "origin_label",
        "origin_lon",
        "origin_lat",

        "dest_id",
        "dest_region",
        "dest_label",
        "dest_lon",
        "dest_lat",

        "route_label",
        "duration_min",
        "distance_km",
        "forward_azimuth_deg",
        "back_azimuth_deg",
        "route_wkt",
        "status"
    ]
].copy()

summary_df = summary_df.rename(columns={
    "case_no": "순번",
    "total_cases": "전체건수",

    "origin_id": "출발지_ID",
    "origin_region": "출발지",
    "origin_label": "ID_출발지",
    "origin_lon": "출발지_경도",
    "origin_lat": "출발지_위도",

    "dest_id": "도착지_ID",
    "dest_region": "도착지",
    "dest_label": "ID_도착지",
    "dest_lon": "도착지_경도",
    "dest_lat": "도착지_위도",

    "route_label": "ID_출발지_to_ID_도착지",
    "duration_min": "소요시간_분",
    "distance_km": "이동거리_km",

    "forward_azimuth_deg": "출발지기준_방위각_deg",
    "back_azimuth_deg": "도착지기준_역방위각_deg",

    "route_wkt": "이동경로_WKT",
    "status": "상태"
})

summary_df["출발지_to_도착지"] = (
    summary_df["ID_출발지"].astype(str)
    + " -> "
    + summary_df["ID_도착지"].astype(str)
)

summary_df = summary_df[
    [
        "순번",
        "전체건수",

        "출발지_ID",
        "출발지",
        "ID_출발지",
        "출발지_경도",
        "출발지_위도",

        "도착지_ID",
        "도착지",
        "ID_도착지",
        "도착지_경도",
        "도착지_위도",

        "출발지_to_도착지",
        "소요시간_분",
        "이동거리_km",

        "출발지기준_방위각_deg",
        "도착지기준_역방위각_deg",

        "이동경로_WKT",
        "상태"
    ]
]


# =========================
# 7. Matrix 생성
# =========================
distance_matrix = result_df.pivot(
    index="origin_label",
    columns="dest_label",
    values="distance_km"
)

azimuth_matrix = result_df.pivot(
    index="origin_label",
    columns="dest_label",
    values="forward_azimuth_deg"
)

route_wkt_matrix = result_df.pivot(
    index="origin_label",
    columns="dest_label",
    values="route_wkt"
)


# =========================
# 8. 엑셀 저장
# =========================
try:
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary_df.to_excel(
            writer,
            sheet_name="OD_컬럼분리",
            index=False
        )

        result_df[["VS_Code_출력"]].to_excel(
            writer,
            sheet_name="VS_Code_출력",
            index=False
        )

        result_df.to_excel(
            writer,
            sheet_name="전체_OD_결과",
            index=False
        )

        distance_matrix.to_excel(
            writer,
            sheet_name="거리_matrix"
        )

        azimuth_matrix.to_excel(
            writer,
            sheet_name="방위각_matrix"
        )

        route_wkt_matrix.to_excel(
            writer,
            sheet_name="이동경로_WKT_matrix"
        )

        df.to_excel(
            writer,
            sheet_name="후보지_목록",
            index=False
        )

    print(f"\n완료: {OUTPUT_XLSX}")

except PermissionError:
    alt_output = BASE_DIR / f"좌표기반_후보지_직선거리_matrix_{int(time.time())}.xlsx"

    with pd.ExcelWriter(alt_output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="OD_컬럼분리", index=False)
        result_df[["VS_Code_출력"]].to_excel(writer, sheet_name="VS_Code_출력", index=False)
        result_df.to_excel(writer, sheet_name="전체_OD_결과", index=False)
        distance_matrix.to_excel(writer, sheet_name="거리_matrix")
        azimuth_matrix.to_excel(writer, sheet_name="방위각_matrix")
        route_wkt_matrix.to_excel(writer, sheet_name="이동경로_WKT_matrix")
        df.to_excel(writer, sheet_name="후보지_목록", index=False)

    print("\n기존 엑셀 파일이 열려 있어서 새 파일명으로 저장했습니다.")
    print(f"완료: {alt_output}")