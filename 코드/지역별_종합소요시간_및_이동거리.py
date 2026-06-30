"""ID_출발지별 총 소요시간과 총 이동거리를 집계해 엑셀로 저장합니다."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_EXCEL = BASE_DIR / "자료" / "버티포트" / "카카오_후보지_자동차_소요시간_matrix.xlsx"
OUTPUT_EXCEL = BASE_DIR / "자료" / "버티포트" / "지역별_총 소요시간.xlsx"
INPUT_SHEET_NAME = "OD_컬럼분리"

GROUP_COLUMN = "ID_출발지"
TIME_COLUMN = "소요시간_분"
DISTANCE_COLUMN = "이동거리_km"
OUTPUT_COLUMNS = {
    TIME_COLUMN: "total_소요시간",
    DISTANCE_COLUMN: "total_이동",
}


def validate_columns(data: pd.DataFrame) -> None:
    required_columns = [GROUP_COLUMN, TIME_COLUMN, DISTANCE_COLUMN]
    missing_columns = [column for column in required_columns if column not in data.columns]
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing_columns)}")


def build_summary(input_excel: str | Path = INPUT_EXCEL) -> pd.DataFrame:
    data = pd.read_excel(input_excel, sheet_name=INPUT_SHEET_NAME)
    validate_columns(data)

    data = data[[GROUP_COLUMN, TIME_COLUMN, DISTANCE_COLUMN]].copy()
    data[GROUP_COLUMN] = data[GROUP_COLUMN].astype(str).str.strip()
    data[TIME_COLUMN] = pd.to_numeric(data[TIME_COLUMN], errors="coerce").fillna(0)
    data[DISTANCE_COLUMN] = pd.to_numeric(data[DISTANCE_COLUMN], errors="coerce").fillna(0)
    data = data[data[GROUP_COLUMN].ne("")]

    summary = (
        data.groupby(GROUP_COLUMN, sort=False, as_index=False)
        .agg(
            total_소요시간=(TIME_COLUMN, "sum"),
            total_이동=(DISTANCE_COLUMN, "sum"),
        )
        .round({"total_소요시간": 2, "total_이동": 2})
    )

    return summary


def save_summary(summary: pd.DataFrame, output_excel: str | Path = OUTPUT_EXCEL) -> Path:
    output_excel = Path(output_excel)
    output_excel.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="지역별_총합", index=False)
        worksheet = writer.sheets["지역별_총합"]

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for cell in worksheet[1]:
            cell.style = "Headline 3"

        column_widths = {
            "A": 18,
            "B": 18,
            "C": 16,
        }
        for column_letter, width in column_widths.items():
            worksheet.column_dimensions[column_letter].width = width

        for row in worksheet.iter_rows(min_row=2, min_col=2, max_col=3):
            for cell in row:
                cell.number_format = "#,##0.00"

    return output_excel


def main() -> None:
    summary = build_summary()
    output_path = save_summary(summary)

    print(f"입력 파일: {INPUT_EXCEL}")
    print(f"저장 파일: {output_path}")
    print(f"집계 지역 수: {len(summary)}")


if __name__ == "__main__":
    main()
