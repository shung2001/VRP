""" 해당 스크립트는 각 지역 간의 거리를 matrix 형태로 만들기 위해 제작된 것. 따라서, main script는 VRP에서 진행될 예정"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_CSV = BASE_DIR / "자료" / "지역별_결과" / "최종선정지역.csv"


def matrix_distance(
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    unit: Literal["m", "km"] = "m",
    decimals: int | None = None,
    return_format: Literal["dataframe", "list"] = "dataframe",
) -> pd.DataFrame | list[list[int | float]]:
    selected_regions = pd.read_csv(input_csv, encoding="utf-8-sig")

    required_columns = ["origin_label", "x_5186", "y_5186"]
    missing_columns = [
        column for column in required_columns if column not in selected_regions.columns
    ]
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing_columns)}")

    selected_regions = selected_regions[required_columns].copy()
    selected_regions["x_5186"] = pd.to_numeric(
        selected_regions["x_5186"],
        errors="coerce",
    )
    selected_regions["y_5186"] = pd.to_numeric(
        selected_regions["y_5186"],
        errors="coerce",
    )
    selected_regions = selected_regions.dropna(subset=["x_5186", "y_5186"])
    selected_regions = selected_regions.reset_index(drop=True)

    if selected_regions.empty:
        raise ValueError("거리 행렬을 만들 수 있는 좌표 데이터가 없습니다.")

    if unit == "m":
        scale = 1
        digits = 0 if decimals is None else decimals
    elif unit == "km":
        scale = 1000
        digits = 3 if decimals is None else decimals
    else:
        raise ValueError("unit은 'm' 또는 'km'만 사용할 수 있습니다.")

    labels = selected_regions["origin_label"].astype(str).tolist()
    coordinates = selected_regions[["x_5186", "y_5186"]].to_records(index=False)

    rows = []
    for origin_x, origin_y in coordinates:
        row = []
        for destination_x, destination_y in coordinates:
            distance = (
                ((origin_x - destination_x) ** 2 + (origin_y - destination_y) ** 2)
                ** 0.5
            ) / scale
            distance = round(float(distance), digits)
            if digits == 0:
                distance = int(distance)
            row.append(distance)
        rows.append(row)

    distance_matrix = pd.DataFrame(rows, index=labels, columns=labels)

    if return_format == "dataframe":
        return distance_matrix
    if return_format == "list":
        return distance_matrix.values.tolist()
    

    raise ValueError("return_format은 'dataframe' 또는 'list'만 사용할 수 있습니다.")

if __name__ == "__main__":
    distance_matrix = matrix_distance()
    print(distance_matrix)