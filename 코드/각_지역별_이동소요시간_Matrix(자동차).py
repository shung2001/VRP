import time
from pathlib import Path

import pandas as pd
import requests


# =========================
# 1. 경로 설정
# =========================
BASE_DIR = Path(r"C:\Users\c\Desktop\대학생활\학연생\새로운_경로방식\자료\버티포트")
BASE_DIR_1 = Path(r"C:\Users\c\Desktop\대학생활\학연생\새로운_경로방식\자료\지역별_결과")

INPUT_XLSX = BASE_DIR / "각_지역별_버티포트_후보군(중심점)_주소추가_최종.xlsx"
OUTPUT_XLSX = BASE_DIR / "카카오_후보지_자동차_소요시간_matrix.xlsx"


# =========================
# 2. Kakao REST API KEY
# =========================
KAKAO_REST_API_KEY = "f1161b2a855cf332983a74de75da4167"


# =========================
# 3. 실행 설정
# =========================
TEST_LIMIT = None          # 테스트 10건만 실행. 전체 실행하려면 None
DEPARTURE_TIME = "2026-06-26T13:00:00"


# =========================
# 4. 입력 데이터
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
# 5. 카카오 자동차 길찾기 API
# =========================
def get_kakao_drive_time(start_lon, start_lat, end_lon, end_lat):
    url = "https://apis-navi.kakaomobility.com/v1/directions"

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}",
        "Content-Type": "application/json"
    }

    params = {
        "origin": f"{start_lon},{start_lat}",
        "destination": f"{end_lon},{end_lat}",
        "priority": "RECOMMEND",
        "departure_time": DEPARTURE_TIME
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)

    if response.status_code != 200:
        return None, None, f"ERROR {response.status_code}: {response.text[:200]}"

    data = response.json()
    routes = data.get("routes", [])

    if not routes:
        return None, None, "NO_ROUTE"

    summary = routes[0].get("summary", {})

    duration_sec = summary.get("duration")
    distance_m = summary.get("distance")

    duration_min = round(duration_sec / 60, 1) if duration_sec is not None else None
    distance_km = round(distance_m / 1000, 2) if distance_m is not None else None

    return duration_min, distance_km, "OK"


# =========================
# 6. 표시용 함수
# =========================
def format_duration(value):
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.1f}"


def format_distance(value):
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.2f}"


# =========================
# 7. 모든 OD 계산
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

        if pd.isna(origin_lon) or pd.isna(origin_lat) or pd.isna(dest_lon) or pd.isna(dest_lat):
            duration_min, distance_km, status = None, None, "MISSING_COORD"
        else:
            try:
                duration_min, distance_km, status = get_kakao_drive_time(
                    origin_lon,
                    origin_lat,
                    dest_lon,
                    dest_lat
                )
            except Exception as e:
                duration_min, distance_km, status = None, None, f"ERROR: {e}"

        duration_text = format_duration(duration_min)
        distance_text = format_distance(distance_km)

        route_label = f"{origin_label} -> {dest_label}"
        denominator = TEST_LIMIT if TEST_LIMIT is not None else total_cases

        vs_code_output = (
            f"{case_no}/{denominator} "
            f"{route_label} | "
            f"{duration_text}분 | "
            f"{distance_text}km | "
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
            "duration_min": duration_min,
            "distance_km": distance_km,
            "duration_text": duration_text,
            "distance_text": distance_text,
            "status": status,

            "VS_Code_출력": vs_code_output
        })

        print(vs_code_output)

        time.sleep(0.15)

    if stop_loop:
        break


result_df = pd.DataFrame(records)


# =========================
# 8. 컬럼 분리 요약표 생성
# =========================
summary_df = result_df[
    [
        "case_no",
        "total_cases",
        "origin_id",
        "origin_region",
        "origin_label",
        "dest_id",
        "dest_region",
        "dest_label",
        "route_label",
        "duration_min",
        "distance_km",
        "status"
    ]
].copy()

summary_df = summary_df.rename(columns={
    "case_no": "순번",
    "total_cases": "전체건수",
    "origin_id": "출발지_ID",
    "origin_region": "출발지",
    "origin_label": "ID_출발지",
    "dest_id": "도착지_ID",
    "dest_region": "도착지",
    "dest_label": "ID_도착지",
    "route_label": "ID_출발지_to_ID_도착지",
    "duration_min": "소요시간_분",
    "distance_km": "이동거리_km",
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
        "ID_출발지",
        "ID_도착지",
        "출발지_to_도착지",
        "소요시간_분",
        "이동거리_km",
    ]
]


# =========================
# 9. Matrix 생성
# =========================
time_matrix = result_df.pivot(
    index="origin_label",
    columns="dest_label",
    values="duration_min"
)

distance_matrix = result_df.pivot(
    index="origin_label",
    columns="dest_label",
    values="distance_km"
)


# =========================
# 10. 엑셀 저장
# =========================
try:
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        # 사용자가 원하는 컬럼 분리 결과
        summary_df.to_excel(
            writer,
            sheet_name="OD_컬럼분리",
            index=False
        )

        # VS Code 출력과 동일한 문자열
        result_df[["VS_Code_출력"]].to_excel(
            writer,
            sheet_name="VS_Code_출력",
            index=False
        )

        # 전체 원본 결과
        result_df.to_excel(
            writer,
            sheet_name="전체_OD_결과",
            index=False
        )

        # 계산용 matrix
        time_matrix.to_excel(
            writer,
            sheet_name="소요시간_matrix"
        )

        distance_matrix.to_excel(
            writer,
            sheet_name="거리_matrix"
        )

        df.to_excel(
            writer,
            sheet_name="후보지_목록",
            index=False
        )

    print(f"\n완료: {OUTPUT_XLSX}")

except PermissionError:
    alt_output = BASE_DIR / f"카카오_후보지_자동차_소요시간_matrix_{int(time.time())}.xlsx"

    with pd.ExcelWriter(alt_output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="OD_컬럼분리", index=False)
        result_df[["VS_Code_출력"]].to_excel(writer, sheet_name="VS_Code_출력", index=False)
        result_df.to_excel(writer, sheet_name="전체_OD_결과", index=False)
        time_matrix.to_excel(writer, sheet_name="소요시간_matrix")
        distance_matrix.to_excel(writer, sheet_name="거리_matrix")
        df.to_excel(writer, sheet_name="후보지_목록", index=False)

    print("\n기존 엑셀 파일이 열려 있어서 새 파일명으로 저장했습니다.")
    print(f"완료: {alt_output}")