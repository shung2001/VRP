# 버티포트 수요조사 및 항로 분석

수도권 및 인접 지역의 UAM(도심항공교통) 버티포트 후보지를 평가하고, 선정된 후보지를 대상으로 VRP(Vehicle Routing Problem) 기반 항로를 분석하는 프로젝트입니다.

연구 문서 `자료/버티포트 수요조사 및 항로 분석.docx`의 흐름을 기준으로, 관광지, 상호출자제한기업 거점, MICE 시설, 복합쇼핑몰, 자동차 대비 UAM 시간절감 효과를 종합해 지역별 수요 잠재력을 평가합니다. 이후 `total_score`와 후보지 간 거리 행렬을 이용해 순환형 또는 시작-종료형 UAM 경로를 계산합니다.

## 연구 개요

K-UAM Grand Challenge 등으로 UAM 상용화 검증이 진행되고 있지만, 실제 도입을 위해서는 기체 성능뿐 아니라 수요 기반의 버티포트 입지와 항로 설계가 필요합니다.

이 프로젝트는 다음 질문에 답하는 것을 목표로 합니다.

1. 수도권에서 UAM 수요가 높을 가능성이 있는 지역은 어디인가?
2. 자동차 대비 UAM을 이용했을 때 시간절감 효과가 큰 구간은 어디인가?
3. 종합점수가 높은 후보지를 중심으로 UAM 항로를 구성하면 어떤 경로가 도출되는가?

분석에 사용한 핵심 지표는 다음과 같습니다.

- `T`: 자동차 대비 UAM 이동시간 절감량
- `C`: 상호출자제한기업 등 기업 거점 수
- `M`: MICE 관련 시설 수
- `R`: 주요 관광지 수
- `S`: 복합쇼핑몰 수

기본 가중치는 시간절감 `0.40`, 기업 `0.20`, MICE `0.15`, 관광지 `0.15`, 복합쇼핑몰 `0.10`입니다. 각 항목은 0점부터 100점까지 최소-최대 정규화한 뒤 가중합으로 `total_score`를 계산합니다.

## 폴더 구조

```text
.
├─ 코드/
│  ├─ 각_경로별_직선거리.py
│  ├─ 각_지역별_이동소요시간_Matrix(자동차).py
│  ├─ UAM_JobyS4_이동소요시간_예측.py
│  ├─ origin별_car_minus_uam_이동시간_집계.py
│  ├─ 지역별_종합점수_계산.py
│  ├─ 지역별_종합소요시간_및_이동거리.py
│  ├─ 버티포트_선정.py
│  ├─ Clique.py
│  ├─ kakao_reverse_geocode_addresses.py
│  ├─ vector_encoding.py
│  └─ VRP/
│     ├─ matrix_distance.py
│     ├─ VRP_new.py
│     ├─ VRP_Start_end.py
│     └─ VRP(Vehicle_Routing_Problem).py
├─ QGIS/
│  ├─ 추가.py
│  ├─ 연면적_분석.py
│  └─ 연면적_날짜_분석.py
└─ 자료/
   ├─ 버티포트/
   ├─ 지역별_결과/
   ├─ VRP_결과/
   ├─ 기업/
   ├─ 관광지/
   ├─ MICE_산업/
   └─ 복합쇼핑몰,아울렛/
```

## 실행 환경

Python 3.10 이상을 권장합니다. 별도 `requirements.txt`는 없으므로 필요한 패키지를 직접 설치해야 합니다.

```powershell
py -m pip install pandas openpyxl numpy requests pyproj geopandas networkx ortools
```

공간 데이터 처리를 위해 `geopandas`가 필요합니다. 설치 환경에 따라 `fiona`, `pyogrio`, `shapely`, `gdal` 관련 의존성이 추가로 필요할 수 있습니다.

카카오 API를 사용하는 스크립트는 코드 안의 `KAKAO_REST_API_KEY` 값을 본인 REST API 키로 교체한 뒤 실행해야 합니다.

## 전체 분석 흐름

일반적인 실행 순서는 다음과 같습니다.

```powershell
# 1. QGIS shp 레이어 기준으로 지역별 수요시설 개수 집계
py "코드/버티포트_선정.py"

# 2. 후보지 중심점 좌표에 주소 추가
py "코드/kakao_reverse_geocode_addresses.py"

# 3. 후보지 간 자동차 이동시간/이동거리 matrix 생성
py "코드/각_지역별_이동소요시간_Matrix(자동차).py"

# 4. 후보지 간 직선거리, 방위각, WKT 경로 matrix 생성
py "코드/각_경로별_직선거리.py"

# 5. Joby S4 운항 가정으로 UAM 이동시간 예측
py "코드/UAM_JobyS4_이동소요시간_예측.py"

# 6. origin별 자동차 대비 UAM 시간절감 합계 계산
py "코드/origin별_car_minus_uam_이동시간_집계.py" --output "자료/버티포트/total_car_minus_uam_moving_time.xlsx"

# 7. 지역별 종합점수 계산
py "코드/지역별_종합점수_계산.py"

# 8. 최종 선정지역 CSV를 기준으로 VRP 경로 분석
py "코드/VRP/VRP_new.py"
```

`자료/지역별_결과/최종선정지역.csv`는 VRP 입력 파일입니다. 기본 VRP 스크립트는 이 파일의 `origin_label`, `x_5186`, `y_5186`, `total_score` 컬럼을 사용합니다.

## 주요 산출물

| 산출물 | 생성 스크립트 | 설명 |
| --- | --- | --- |
| `결과/SI_DO_value_개수_시군구.csv` | `코드/버티포트_선정.py` | 시군구 단위 수요시설 개수 |
| `결과/SI_DO_value_개수_시단위.csv` | `코드/버티포트_선정.py` | 시 단위 수요시설 개수 |
| `자료/버티포트/카카오_후보지_자동차_소요시간_matrix.xlsx` | `코드/각_지역별_이동소요시간_Matrix(자동차).py` | 카카오 길찾기 기반 자동차 OD matrix |
| `자료/버티포트/좌표기반_후보지_직선거리_matrix.xlsx` | `코드/각_경로별_직선거리.py` | 후보지 간 직선거리, 방위각, WKT |
| `자료/버티포트/JobyS4_UAM_이동소요시간_예측.xlsx` | `코드/UAM_JobyS4_이동소요시간_예측.py` | UAM 구간별/총 이동시간 예측 |
| `자료/버티포트/total_car_minus_uam_moving_time.xlsx` | `코드/origin별_car_minus_uam_이동시간_집계.py` | origin별 자동차 대비 UAM 시간절감 합계 |
| `자료/지역별_결과/지역별_종합점수.csv` | `코드/지역별_종합점수_계산.py` | 지역별 종합점수 |
| `자료/지역별_결과/최종선정지역.csv` | 수동 정리 또는 후처리 | VRP에 투입할 최종 후보지 목록 |
| `자료/VRP_결과/.../VRP_이동결과_*.csv` | `코드/VRP/VRP_new.py`, `코드/VRP/VRP_Start_end.py` | VRP 최적 경로 |

## 각 Python 파일 사용법

### `코드/버티포트_선정.py`

QGIS 폴더의 행정구역 경계와 수요시설 shp 파일을 공간 조인하여 지역별 수요시설 개수를 계산합니다.

입력:

- `QGIS/시군구.shp`
- `QGIS/2026년_상호출자제한기업_핵심거점들.shp`
- `QGIS/MICE_선정_Convention.shp`
- `QGIS/MICE_시설.shp`
- `QGIS/한국관광100선_수도권_관광지_주소_좌표숫자변환.shp`
- `QGIS/복합쇼핑몰.shp`
- `QGIS/지하철역_정보.shp`

실행:

```powershell
py "코드/버티포트_선정.py"
```

출력:

- `결과/SI_DO_value_개수_시군구.csv`
- `결과/SI_DO_value_개수_시단위.csv`

### `코드/kakao_reverse_geocode_addresses.py`

EPSG:5186 중심점 좌표를 EPSG:4326 경위도로 변환하고, 카카오 좌표-주소 변환 API로 주소를 붙입니다.

입력:

- `자료/버티포트/각_지역별_버티포트_후보군(중심점)_1.xlsx`
- 필수 컬럼: `MEAN_X`, `MEAN_Y`

실행:

```powershell
py "코드/kakao_reverse_geocode_addresses.py"
```

출력:

- `자료/버티포트/각_지역별_버티포트_후보군(중심점)_주소추가.xlsx`

주의:

- 코드 안의 `KAKAO_REST_API_KEY`를 본인 키로 바꿔야 합니다.
- 현재 스크립트는 `BASE_DIR`에 로컬 절대 경로가 들어 있습니다. 저장소 위치가 달라지면 경로를 수정해야 합니다.

### `코드/각_지역별_이동소요시간_Matrix(자동차).py`

카카오 자동차 길찾기 API로 모든 후보지 OD 조합의 자동차 소요시간과 이동거리를 계산합니다.

입력:

- `자료/버티포트/각_지역별_버티포트_후보군(중심점)_주소추가_최종.xlsx`
- 필수 컬럼: `지역`, `경도`, `위도`

실행:

```powershell
py "코드/각_지역별_이동소요시간_Matrix(자동차).py"
```

출력:

- `자료/버티포트/카카오_후보지_자동차_소요시간_matrix.xlsx`

생성 시트:

- `OD_컬럼분리`
- `VS_Code_출력`
- `전체_OD_결과`
- `소요시간_matrix`
- `거리_matrix`
- `후보지_목록`

설정:

- `TEST_LIMIT = None`: 전체 OD 실행
- `DEPARTURE_TIME = "2026-06-26T13:00:00"`: 카카오 길찾기 출발 시각
- API 호출 간 `time.sleep(0.15)`가 적용되어 있습니다.

### `코드/각_경로별_직선거리.py`

후보지 간 WGS84 측지 직선거리, 방위각, QGIS 표시용 `LINESTRING` WKT를 계산합니다.

입력:

- `자료/버티포트/각_지역별_버티포트_후보군(중심점)_주소추가_최종.xlsx`
- 필수 컬럼: `지역`, `경도`, `위도`

실행:

```powershell
py "코드/각_경로별_직선거리.py"
```

출력:

- `자료/버티포트/좌표기반_후보지_직선거리_matrix.xlsx`

생성 시트:

- `OD_컬럼분리`
- `VS_Code_출력`
- `전체_OD_결과`
- `거리_matrix`
- `방위각_matrix`
- `이동경로_WKT_matrix`
- `후보지_목록`

### `코드/UAM_JobyS4_이동소요시간_예측.py`

Joby S4 기체 운항 가정을 적용해 후보지 간 UAM 이동시간을 계산하고 자동차 소요시간과 비교합니다.

기본 운항 가정:

- 최대 속도 참고값: `320 km/h`
- 계산 적용 순항속도: `300 km/h`
- 순항고도: `600 m`
- 상승각: `8도`
- 하강 시작 반경: `2 km`
- 이륙 호버링: `1분`
- 착륙 호버링: `1분`

기본 실행:

```powershell
py "코드/UAM_JobyS4_이동소요시간_예측.py"
```

주요 옵션:

```powershell
py "코드/UAM_JobyS4_이동소요시간_예측.py" `
  --input "자료/버티포트/좌표기반_후보지_직선거리_matrix.xlsx" `
  --car-time-input "자료/버티포트/카카오_후보지_자동차_소요시간_matrix.xlsx" `
  --output-dir "자료/버티포트" `
  --output-name "JobyS4_UAM_이동소요시간_예측.xlsx" `
  --cruise-speed-kmh 300
```

추가 옵션:

- `--test-limit 10`: 앞 10개 OD만 테스트
- `--cruise-speed-kmh`: 순항속도 변경

출력:

- `자료/버티포트/JobyS4_UAM_이동소요시간_예측.xlsx`

생성 시트:

- `입력가정`
- `요약`
- `전체_OD_시간`
- `총소요시간_matrix`
- `이동시간_matrix`
- `최대고도_matrix`
- `후보지_목록`

### `코드/origin별_car_minus_uam_이동시간_집계.py`

UAM 예측 결과에서 `origin_label`별 자동차 대비 UAM 시간절감 합계를 계산합니다.

기본 실행:

```powershell
py "코드/origin별_car_minus_uam_이동시간_집계.py" --output "자료/버티포트/total_car_minus_uam_moving_time.xlsx"
```

옵션:

```powershell
py "코드/origin별_car_minus_uam_이동시간_집계.py" `
  --input "자료/버티포트/JobyS4_UAM_이동소요시간_예측.xlsx" `
  --sheet "요약" `
  --output "자료/버티포트/total_car_minus_uam_moving_time.xlsx"
```

입력 시트는 `origin_label`, `car_minus_uam_moving_time_min` 컬럼이 있는 시트를 자동 탐색합니다.

출력:

- `origin별_합계` 시트: `total_car_minus_uam_moving_time_min`, OD 개수, 평균값
- `집계정보` 시트: 입력 파일과 집계 메타데이터

참고:

- 코드 기본 출력 파일명은 `totla_car_minus_uam_moving_time.xlsx`로 오타가 있습니다. 일반 분석 흐름에서는 위 예시처럼 `--output`으로 `total_car_minus_uam_moving_time.xlsx`를 지정하는 편이 좋습니다.

### `코드/지역별_종합점수_계산.py`

시간절감 합계, 좌표/주소, 지역별 수요시설 개수를 병합해 지역별 종합점수를 계산합니다.

기본 입력:

- `자료/버티포트/total_car_minus_uam_moving_time.xlsx`
- `자료/버티포트/각_지역별_버티포트_후보군(중심점)_주소추가_최종.xlsx`
- `자료/지역별_결과/SI_DO_value_개수_시단위.csv`

기본 실행:

```powershell
py "코드/지역별_종합점수_계산.py"
```

가중치 변경 예시:

```powershell
py "코드/지역별_종합점수_계산.py" `
  --weights "time=0.5,Company=0.2,MICE=0.1,Korea_Tourist=0.1,Shopping_Mall=0.1"
```

주요 옵션:

- `--time-xlsx`: 시간절감 집계 파일
- `--coord-xlsx`: 후보지 좌표 파일
- `--value-csv`: 수요시설 개수 파일
- `--time-sheet`: 시간절감 입력 시트명
- `--coord-sheet`: 좌표 입력 시트명
- `--output-csv`: CSV 저장 경로
- `--output-xlsx`: Excel 저장 경로
- `--no-xlsx`: CSV만 저장
- `--merge-how`: `left`, `inner`, `outer`, `right`
- `--weights`: 가중치 문자열

출력:

- `자료/지역별_결과/지역별_종합점수.csv`
- `자료/지역별_결과/지역별_종합점수.xlsx`

Excel 생성 시트:

- `regional_score`
- `coordinates`
- `time_input_rows`
- `value_input_rows`
- `weights`
- `not_matched`
- `invalid_time_rows`

### `코드/지역별_종합소요시간_및_이동거리.py`

자동차 OD matrix의 `OD_컬럼분리` 시트를 이용해 출발지별 자동차 총 소요시간과 총 이동거리를 집계합니다.

실행:

```powershell
py "코드/지역별_종합소요시간_및_이동거리.py"
```

입력:

- `자료/버티포트/카카오_후보지_자동차_소요시간_matrix.xlsx`

출력:

- `자료/버티포트/지역별_총 소요시간.xlsx`

### `코드/Clique.py`

기업, MICE, 관광지, 복합쇼핑몰 지점의 공간적 밀집도를 보고 후보 권역을 탐색합니다. 5km 이내 지점들을 그래프로 연결하고, clique를 찾아 권역 중심점과 반경을 계산합니다.

실행:

```powershell
py "코드/Clique.py"
```

입력:

- `QGIS/2026년_상호출자제한기업_핵심거점들.shp`
- `QGIS/MICE_선정_Convention.shp`
- `QGIS/한국관광100선_수도권_관광지_주소_좌표숫자변환.shp`
- `QGIS/복합쇼핑몰.shp`

출력:

- `코드/결과/clique_후보권역_5000m.csv`

설정:

- `DIST_THRESHOLD_M = 5000`: clique 연결 거리 기준
- `TYPE_WEIGHT`: 수요 유형별 가중치

### `코드/vector_encoding.py`

다른 GIS 스크립트에서 사용하는 보조 모듈입니다. shp, GeoPackage 등 벡터 파일을 여러 인코딩으로 읽고 CSV 또는 shp 저장 시 인코딩 fallback을 처리합니다.

직접 실행용이라기보다 `Clique.py` 등에서 import해서 사용합니다.

주요 함수:

- `read_vector(path, required_columns=None)`
- `clean_geometry(gdf)`
- `write_csv_with_fallback(df, path)`
- `write_shp_with_fallback(gdf, path)`

## VRP 스크립트

VRP 분석은 `자료/지역별_결과/최종선정지역.csv`를 기본 입력으로 사용합니다. 이 파일에는 최소한 다음 컬럼이 있어야 합니다.

- `origin_label`
- `x_5186`
- `y_5186`
- `total_score`

`matrix_distance.py`가 EPSG:5186 좌표를 이용해 후보지 간 유클리드 거리 행렬을 만들고, `VRP_new.py` 또는 `VRP_Start_end.py`가 OR-Tools로 경로를 계산합니다.

### `코드/VRP/matrix_distance.py`

최종 선정지역의 EPSG:5186 좌표를 이용해 거리 행렬을 생성합니다.

실행:

```powershell
py "코드/VRP/matrix_distance.py"
```

기본 입력:

- `자료/지역별_결과/최종선정지역.csv`

직접 import해서 사용할 수도 있습니다.

```python
from matrix_distance import matrix_distance

distance_df = matrix_distance(unit="m", return_format="dataframe")
distance_list = matrix_distance(unit="m", return_format="list")
```

### `코드/VRP/VRP_new.py`

하나의 depot에서 출발해 다시 depot으로 돌아오는 순환형 VRP를 계산합니다.

기본값:

- 결과 폴더: `자료/VRP_결과/김포공항`
- depot NODE: `17`
- 차량 수: `1`
- 최대 운항거리: `160 km`
- 근접 노드 중복 제한: `12 km`
- 미방문 노드 penalty: `1,000,000`부터 `100,000,000`
- 탐색 제한시간: `10초`

기본 실행:

```powershell
py "코드/VRP/VRP_new.py"
```

노드 번호 확인:

```powershell
py "코드/VRP/VRP_new.py" --list-nodes
```

옵션 사용 예시:

```powershell
py "코드/VRP/VRP_new.py" `
  --depot 17 `
  --vehicles 1 `
  --max-distance-km 160 `
  --near-radius-km 12 `
  --output-format csv `
  --input-csv "자료/지역별_결과/최종선정지역.csv"
```

출력:

- `VRP_이동결과_depot{depot}_vehicle_{vehicles}.csv`
- `VRP_미방문노드_depot{depot}_vehicle_{vehicles}.csv`
- `VRP_노드목록_depot{depot}_vehicle_{vehicles}.csv`
- `VRP_12km_근접쌍_depot{depot}_vehicle_{vehicles}.csv`

### `코드/VRP/VRP_Start_end.py`

시작 노드와 종료 노드를 다르게 설정하는 직선형 VRP를 계산합니다. 외곽 지역이 순환형 경로에서 누락될 때 특정 start-end 조합을 강제해 분석할 수 있습니다.

기본값:

- 결과 폴더: `자료/VRP_결과/중구`
- start NODE: `4`
- end NODE: `1`
- 차량 수: `1`
- 최대 운항거리: `160 km`
- 근접 노드 중복 제한: `12 km`

기본 실행:

```powershell
py "코드/VRP/VRP_Start_end.py"
```

노드 번호 확인:

```powershell
py "코드/VRP/VRP_Start_end.py" --list-nodes
```

강남구에서 강화군으로 가는 식의 start-end 분석 예시:

```powershell
py "코드/VRP/VRP_Start_end.py" `
  --start 4 `
  --end 1 `
  --vehicles 1 `
  --max-distance-km 160 `
  --near-radius-km 12 `
  --result-dir "자료/VRP_결과/강남구" `
  --output-format csv
```

차량별 start/end를 다르게 주는 예시:

```powershell
py "코드/VRP/VRP_Start_end.py" `
  --starts "4,5" `
  --ends "1,14" `
  --vehicles 2
```

출력:

- `VRP_이동결과_start_node_{start}_end_node_{end}_vehicle_{vehicles}.csv`
- `VRP_미방문노드_start_node_{start}_end_node_{end}_vehicle_{vehicles}.csv`
- `VRP_노드목록_start_node_{start}_end_node_{end}_vehicle_{vehicles}.csv`
- `VRP_8km_근접쌍_start_node_{start}_end_node_{end}_vehicle_{vehicles}.csv`

참고:

- 코드 기본 근접 반경은 `12 km`입니다.
- 출력 파일명에는 `8km_근접쌍`으로 표시되지만, 실제 기본 계산값은 `NEAR_NODE_RADIUS_M = 12_000`입니다.

### `코드/VRP/VRP(Vehicle_Routing_Problem).py`

OR-Tools 공식 예제 형태의 단순 VRP 샘플입니다. 프로젝트 데이터 파일을 읽지 않고 코드 내부의 작은 거리 행렬을 사용합니다.

실행:

```powershell
py "코드/VRP/VRP(Vehicle_Routing_Problem).py"
```

실제 분석에는 `VRP_new.py` 또는 `VRP_Start_end.py`를 사용합니다.

## QGIS 보조 스크립트

### `QGIS/추가.py`

건물 shp에서 `A14 > 39000`, `A26 > 11` 조건을 만족하는 건물을 필터링해 GeoPackage로 저장합니다.

입력:

- `QGIS/기존건물/Metropolitan_buildings(Incheon,Gyeong_Gi,Seoul).shp`

출력:

- `QGIS/헬기장_의무_건물/A14_39000초과_11층초과_건물.gpkg`

실행:

```powershell
py "QGIS/추가.py"
```

### `QGIS/연면적_분석.py`

건물 데이터의 누락된 바닥면적 `A12`와 연면적 `A14`를 기준 shp로 추정한 뒤, `A14 >= 10000`, `A26 >= 11` 조건을 만족하는 건물을 shp로 저장합니다.

입력:

- `QGIS/기존건물/Metropolitan_buildings(Incheon,Gyeong_Gi,Seoul).shp`
- `QGIS/기존건물/기준.shp`

출력:

- `QGIS/헬기장_의무_건물/연면적_10000m2_그리고_11층_이상_건물.shp`

실행:

```powershell
py "QGIS/연면적_분석.py"
```

### `QGIS/연면적_날짜_분석.py`

`연면적_분석.py` 조건에 날짜 조건을 추가합니다. `A13` 날짜가 `2011-12-30` 이후인 건물만 필터링합니다.

출력:

- `QGIS/헬기장_의무_건물/2011년이후_연면적10000m2_11층이상_건물.gpkg`

실행:

```powershell
py "QGIS/연면적_날짜_분석.py"
```

## 분석 방법 상세

### UAM 시간 산정

UAM 이동시간은 단순히 직선거리를 순항속도로 나누지 않고 다음 단계를 모두 반영합니다.

1. 출발지 이륙 및 호버링
2. 상승 및 가속
3. 순항
4. 도착지 접근을 위한 하강 및 감속
5. 착륙 및 호버링

순항고도 600m, 상승각 8도, 순항속도 300km/h를 기준으로 OD별 비행 프로파일을 구성합니다. 거리가 짧아 순항고도에 도달하지 못하는 구간은 단거리 프로파일로 별도 처리합니다.

### 종합점수 산정

지역별 `total_score`는 다음 지표의 정규화 점수와 가중치를 이용해 계산됩니다.

```text
total_score =
  T_score * 0.40
+ Company_score * 0.20
+ MICE_score * 0.15
+ Korea_Tourist_score * 0.15
+ Shopping_Mall_score * 0.10
```

가중치는 `지역별_종합점수_계산.py`의 `WEIGHTS` 또는 `--weights` 옵션으로 조정할 수 있습니다.

### VRP 제약조건

VRP에는 다음 조건이 반영되어 있습니다.

- 차량 또는 기체별 최대 이동거리 제한
- `total_score` 기반 미방문 노드 penalty
- 가까운 후보지가 같은 수요권을 공유한다고 보고 동시에 선택되지 않게 하는 근접 노드 제약
- Distance dimension의 span cost coefficient를 이용한 총 경로거리 증가 비용

기본 penalty는 `total_score`가 높을수록 미방문 비용이 낮아지는 방식으로 정규화되어 있습니다. 즉 높은 점수 지역은 경로에 포함될 가능성이 커지도록 설계되어 있습니다.

## 주의사항

- 일부 스크립트는 현재 PC 기준 절대 경로를 사용합니다. 저장소 위치가 바뀌면 `BASE_DIR`을 수정해야 합니다.
- 카카오 API 호출 스크립트는 API 비용, 호출 제한, 네트워크 상태의 영향을 받습니다.
- `QGIS/Metropolitan_buildings(Incheon,Gyeong_Gi,Seoul).dbf`, `.shp`는 GitHub 단일 파일 제한을 초과하므로 Git 추적 대상에서 제외되어 있습니다. 로컬 데이터가 없으면 관련 QGIS 보조 스크립트는 실행되지 않습니다.
- `자료/지역별_결과/최종선정지역.csv`는 VRP 실행 전 준비되어 있어야 합니다.
- Word나 Excel에서 열려 있는 출력 파일은 저장이 실패할 수 있습니다. 일부 스크립트는 이 경우 타임스탬프를 붙인 대체 파일명으로 저장합니다.
