"""VRP solver with configurable start and end depot nodes.

Distances are in meters.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Sequence

import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from matrix_distance import DEFAULT_INPUT_CSV, matrix_distance


BASE_DIR = Path(__file__).resolve().parents[2]
RESULT_DIR = BASE_DIR / "자료" / "VRP_결과" / "중구"

START_NODE = 4
END_NODE = 1
VEHICLE_START_NODES: list[int] | None = None
VEHICLE_END_NODES: list[int] | None = None
NUM_VEHICLES = 1
MAX_VEHICLE_DISTANCE_M = 160_000
NEAR_NODE_RADIUS_M = 12_000
SKIP_NODE_PENALTY = 100_000_000
MIN_SKIP_NODE_PENALTY = 1_000_000
TOTAL_SCORE_COLUMN = "total_score"
SOLUTION_TIME_LIMIT_SEC = 10
OUTPUT_FORMAT = "csv"


def parse_node_list(value: str) -> list[int]:
    nodes = [node.strip() for node in value.split(",") if node.strip()]
    if not nodes:
        raise argparse.ArgumentTypeError("NODE 목록이 비어 있습니다.")

    try:
        return [int(node) for node in nodes]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "NODE 목록은 쉼표로 구분된 정수여야 합니다. 예: 4,5"
        ) from exc


def resolve_vehicle_nodes(
    default_node: int,
    vehicle_nodes: Sequence[int] | None,
    num_vehicles: int,
    node_name: str,
) -> list[int]:
    if num_vehicles < 1:
        raise ValueError("num_vehicles는 1 이상이어야 합니다.")

    if vehicle_nodes is None:
        return [default_node] * num_vehicles

    vehicle_nodes = list(vehicle_nodes)
    if len(vehicle_nodes) == 1:
        return vehicle_nodes * num_vehicles
    if len(vehicle_nodes) != num_vehicles:
        raise ValueError(
            f"{node_name} NODE 개수는 차량 수와 같아야 합니다: "
            f"{len(vehicle_nodes)}개 입력, 차량 {num_vehicles}대"
        )
    return vehicle_nodes


def compact_node_list(nodes: Sequence[int]) -> str:
    nodes = list(nodes)
    if len(set(nodes)) == 1:
        return str(nodes[0])
    return "-".join(str(node) for node in nodes)


def terminal_role(node: int, starts: Sequence[int], ends: Sequence[int]) -> str:
    is_start = node in starts
    is_end = node in ends
    if is_start and is_end:
        return "START_END"
    if is_start:
        return "START"
    if is_end:
        return "END"
    return ""


def find_column_case_insensitive(columns: Sequence[str], target_column: str) -> str | None:
    target_column = target_column.casefold()
    for column in columns:
        if str(column).casefold() == target_column:
            return str(column)
    return None


def add_score_based_penalties(node_table: pd.DataFrame) -> pd.DataFrame:
    node_table = node_table.copy()
    scores = pd.to_numeric(node_table["total_score"], errors="coerce")
    valid_scores = scores.dropna()

    if valid_scores.empty:
        node_table["total_score"] = 0
        node_table["skip_penalty"] = SKIP_NODE_PENALTY
        return node_table

    min_score = float(valid_scores.min())
    max_score = float(valid_scores.max())
    score_values = scores.fillna(min_score)
    node_table["total_score"] = score_values

    if max_score == min_score:
        node_table["skip_penalty"] = SKIP_NODE_PENALTY
        return node_table

    normalized_scores = ((score_values - min_score) / (max_score - min_score)).clip(0, 1)
    penalties = SKIP_NODE_PENALTY - normalized_scores * (
        SKIP_NODE_PENALTY - MIN_SKIP_NODE_PENALTY
    )
    node_table["skip_penalty"] = penalties.round().astype(int)
    return node_table


def build_node_table(
    input_csv: str | Path,
    node_labels: list[str],
    starts: Sequence[int],
    ends: Sequence[int],
) -> pd.DataFrame:
    source_df = pd.read_csv(input_csv, encoding="utf-8-sig")
    source_df = source_df.dropna(subset=["origin_label"]).reset_index(drop=True)
    source_df["origin_label"] = source_df["origin_label"].astype(str)
    total_score_column = find_column_case_insensitive(source_df.columns, TOTAL_SCORE_COLUMN)
    source_df = source_df.set_index("origin_label", drop=False)

    records = []
    for node_number, origin_label in enumerate(node_labels):
        if origin_label in source_df.index:
            row = source_df.loc[origin_label]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            actual_name = row.get("region_name", origin_label)
            address = row.get("address", "")
            node_type = row.get("Type", "")
            x_5186 = row.get("x_5186", "")
            y_5186 = row.get("y_5186", "")
            total_score = row.get(total_score_column, 0) if total_score_column else 0
        else:
            actual_name = origin_label
            address = ""
            node_type = ""
            x_5186 = ""
            y_5186 = ""
            total_score = 0

        if pd.isna(actual_name):
            actual_name = origin_label
        if pd.isna(address):
            address = ""
        if pd.isna(node_type):
            node_type = ""
        if pd.isna(x_5186):
            x_5186 = ""
        if pd.isna(y_5186):
            y_5186 = ""
        if pd.isna(total_score):
            total_score = 0

        records.append(
            {
                "NODE": node_number,
                "실제 명칭": str(actual_name),
                "origin_label": origin_label,
                "address": str(address),
                "x_5186": x_5186,
                "y_5186": y_5186,
                "Type": str(node_type).strip(),
                "terminal_role": terminal_role(node_number, starts, ends),
                "total_score": total_score,
            }
        )

    return add_score_based_penalties(pd.DataFrame(records))


def find_near_node_pairs(
    distance_df: pd.DataFrame,
    near_node_radius_m: int,
) -> list[tuple[int, int, int]]:
    near_pairs = []
    for from_node in range(len(distance_df)):
        for to_node in range(from_node + 1, len(distance_df)):
            distance_m = int(distance_df.iat[from_node, to_node])
            if 0 < distance_m <= near_node_radius_m:
                near_pairs.append((from_node, to_node, distance_m))
    return near_pairs


def validate_terminal_nodes(
    starts: Sequence[int],
    ends: Sequence[int],
    num_nodes: int,
) -> None:
    for node_name, nodes in [("start", starts), ("end", ends)]:
        for node in nodes:
            if not 0 <= node < num_nodes:
                raise ValueError(
                    f"{node_name}_node는 0부터 {num_nodes - 1} 사이여야 합니다: {node}"
                )


def create_data_model(
    input_csv: str | Path,
    start_nodes: Sequence[int],
    end_nodes: Sequence[int],
    num_vehicles: int,
    max_vehicle_distance_m: int,
    near_node_radius_m: int,
) -> dict:
    distance_df = matrix_distance(
        input_csv=input_csv,
        unit="m",
        decimals=0,
        return_format="dataframe",
    )
    distance_matrix = distance_df.astype(int).values.tolist()
    node_labels = distance_df.index.astype(str).tolist()

    if num_vehicles < 1:
        raise ValueError("num_vehicles는 1 이상이어야 합니다.")
    if len(start_nodes) != num_vehicles:
        raise ValueError("start_nodes 개수는 num_vehicles와 같아야 합니다.")
    if len(end_nodes) != num_vehicles:
        raise ValueError("end_nodes 개수는 num_vehicles와 같아야 합니다.")

    start_nodes = list(start_nodes)
    end_nodes = list(end_nodes)
    validate_terminal_nodes(start_nodes, end_nodes, len(distance_matrix))

    return {
        "distance_matrix": distance_matrix,
        "node_labels": node_labels,
        "node_table": build_node_table(input_csv, node_labels, start_nodes, end_nodes),
        "near_pairs": find_near_node_pairs(distance_df, near_node_radius_m),
        "num_vehicles": num_vehicles,
        "starts": start_nodes,
        "ends": end_nodes,
        "terminal_nodes": set(start_nodes) | set(end_nodes),
        "max_vehicle_distance_m": max_vehicle_distance_m,
        "near_node_radius_m": near_node_radius_m,
    }


def add_optional_node_constraints(data: dict, manager, routing) -> None:
    terminal_nodes = data["terminal_nodes"]
    node_table = data["node_table"].set_index("NODE", drop=False)
    for node in range(len(data["distance_matrix"])):
        if node in terminal_nodes:
            continue

        skip_penalty = int(node_table.loc[node, "skip_penalty"])
        routing.AddDisjunction(
            [manager.NodeToIndex(node)],
            skip_penalty,
        )


def add_near_node_constraints(data: dict, manager, routing) -> None:
    solver = routing.solver()
    terminal_nodes = data["terminal_nodes"]

    for from_node, to_node, _ in data["near_pairs"]:
        from_is_terminal = from_node in terminal_nodes
        to_is_terminal = to_node in terminal_nodes

        if from_is_terminal and to_is_terminal:
            continue
        if from_is_terminal:
            solver.Add(routing.ActiveVar(manager.NodeToIndex(to_node)) == 0)
        elif to_is_terminal:
            solver.Add(routing.ActiveVar(manager.NodeToIndex(from_node)) == 0)
        else:
            solver.Add(
                routing.ActiveVar(manager.NodeToIndex(from_node))
                + routing.ActiveVar(manager.NodeToIndex(to_node))
                <= 1
            )


def solve_vrp(data: dict):
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]),
        data["num_vehicles"],
        data["starts"],
        data["ends"],
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    routing.AddDimension(
        transit_callback_index,
        0,
        data["max_vehicle_distance_m"],
        True,
        "Distance",
    )
    distance_dimension = routing.GetDimensionOrDie("Distance")
    distance_dimension.SetGlobalSpanCostCoefficient(100)

    add_optional_node_constraints(data, manager, routing)
    add_near_node_constraints(data, manager, routing)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(SOLUTION_TIME_LIMIT_SEC)

    solution = routing.SolveWithParameters(search_parameters)
    return manager, routing, solution


def build_route_result(data: dict, manager, routing, solution) -> tuple[pd.DataFrame, pd.DataFrame]:
    node_table = data["node_table"].set_index("NODE", drop=False)
    terminal_nodes = data["terminal_nodes"]
    route_rows = []
    visited_nodes = set()

    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route_order = 0
        cumulative_distance_m = 0

        current_node = manager.IndexToNode(index)
        route_rows.append(
            build_route_row(
                node_table,
                vehicle_id,
                route_order,
                current_node,
                0,
                cumulative_distance_m,
            )
        )

        while not routing.IsEnd(index):
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            segment_distance_m = routing.GetArcCostForVehicle(
                previous_index,
                index,
                vehicle_id,
            )
            cumulative_distance_m += segment_distance_m
            route_order += 1

            current_node = manager.IndexToNode(index)
            if current_node not in terminal_nodes:
                visited_nodes.add(current_node)

            route_rows.append(
                build_route_row(
                    node_table,
                    vehicle_id,
                    route_order,
                    current_node,
                    segment_distance_m,
                    cumulative_distance_m,
                )
            )

    route_df = pd.DataFrame(route_rows)

    skipped_nodes = [
        node
        for node in range(len(data["distance_matrix"]))
        if node not in terminal_nodes and node not in visited_nodes
    ]
    skipped_df = node_table.loc[skipped_nodes].reset_index(drop=True)

    return route_df, skipped_df


def build_route_row(
    node_table: pd.DataFrame,
    vehicle_id: int,
    route_order: int,
    node_number: int,
    segment_distance_m: int,
    cumulative_distance_m: int,
) -> dict:
    node_info = node_table.loc[node_number]
    return {
        "vehicle_id": vehicle_id,
        "route_order": route_order,
        "NODE": node_number,
        "실제 명칭": node_info["실제 명칭"],
        "value": cumulative_distance_m,
        "x_5186": node_info["x_5186"],
        "y_5186": node_info["y_5186"],
        "segment_distance_m": segment_distance_m,
        "origin_label": node_info["origin_label"],
        "terminal_role": node_info["terminal_role"],
        "total_score": node_info["total_score"],
        "skip_penalty": node_info["skip_penalty"],
    }


def build_near_pair_table(data: dict) -> pd.DataFrame:
    node_table = data["node_table"].set_index("NODE", drop=False)
    rows = []
    for from_node, to_node, distance_m in data["near_pairs"]:
        rows.append(
            {
                "from_NODE": from_node,
                "from_실제 명칭": node_table.loc[from_node, "실제 명칭"],
                "from_terminal_role": node_table.loc[from_node, "terminal_role"],
                "to_NODE": to_node,
                "to_실제 명칭": node_table.loc[to_node, "실제 명칭"],
                "to_terminal_role": node_table.loc[to_node, "terminal_role"],
                "distance_m": distance_m,
            }
        )
    return pd.DataFrame(rows)


def build_output_suffix(data: dict) -> str:
    starts = compact_node_list(data["starts"])
    ends = compact_node_list(data["ends"])
    vehicles = data["num_vehicles"]
    return f"start_node_{starts}_end_node_{ends}_vehicle_{vehicles}"


def save_outputs(
    data: dict,
    route_df: pd.DataFrame,
    skipped_df: pd.DataFrame,
    output_format: str,
    result_dir: str | Path,
) -> list[Path]:
    result_dir = Path(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    suffix = build_output_suffix(data)
    node_table = data["node_table"]
    near_pair_df = build_near_pair_table(data)

    if output_format == "xlsx":
        output_path = result_dir / f"VRP_결과_{suffix}.xlsx"
        try:
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                route_df.to_excel(writer, sheet_name="이동결과", index=False)
                skipped_df.to_excel(writer, sheet_name="미방문노드", index=False)
                node_table.to_excel(writer, sheet_name="노드목록", index=False)
                near_pair_df.to_excel(writer, sheet_name="8km_근접쌍", index=False)
        except PermissionError:
            output_path = result_dir / f"VRP_결과_{suffix}_{int(time.time())}.xlsx"
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                route_df.to_excel(writer, sheet_name="이동결과", index=False)
                skipped_df.to_excel(writer, sheet_name="미방문노드", index=False)
                node_table.to_excel(writer, sheet_name="노드목록", index=False)
                near_pair_df.to_excel(writer, sheet_name="8km_근접쌍", index=False)
        return [output_path]

    if output_format != "csv":
        raise ValueError("output_format은 'csv' 또는 'xlsx'만 사용할 수 있습니다.")

    route_path = result_dir / f"VRP_이동결과_{suffix}.csv"
    skipped_path = result_dir / f"VRP_미방문노드_{suffix}.csv"
    node_path = result_dir / f"VRP_노드목록_{suffix}.csv"
    near_pair_path = result_dir / f"VRP_8km_근접쌍_{suffix}.csv"

    try:
        route_df.to_csv(route_path, index=False, encoding="utf-8-sig")
        skipped_df.to_csv(skipped_path, index=False, encoding="utf-8-sig")
        node_table.to_csv(node_path, index=False, encoding="utf-8-sig")
        near_pair_df.to_csv(near_pair_path, index=False, encoding="utf-8-sig")
    except PermissionError:
        suffix = f"{suffix}_{int(time.time())}"
        route_path = result_dir / f"VRP_이동결과_{suffix}.csv"
        skipped_path = result_dir / f"VRP_미방문노드_{suffix}.csv"
        node_path = result_dir / f"VRP_노드목록_{suffix}.csv"
        near_pair_path = result_dir / f"VRP_8km_근접쌍_{suffix}.csv"

        route_df.to_csv(route_path, index=False, encoding="utf-8-sig")
        skipped_df.to_csv(skipped_path, index=False, encoding="utf-8-sig")
        node_table.to_csv(node_path, index=False, encoding="utf-8-sig")
        near_pair_df.to_csv(near_pair_path, index=False, encoding="utf-8-sig")

    return [route_path, skipped_path, node_path, near_pair_path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=START_NODE)
    parser.add_argument("--end", type=int, default=END_NODE)
    parser.add_argument("--starts", type=parse_node_list, default=VEHICLE_START_NODES)
    parser.add_argument("--ends", type=parse_node_list, default=VEHICLE_END_NODES)
    parser.add_argument("--vehicles", type=int, default=NUM_VEHICLES)
    parser.add_argument("--max-distance-km", type=float, default=MAX_VEHICLE_DISTANCE_M / 1000)
    parser.add_argument("--near-radius-km", type=float, default=NEAR_NODE_RADIUS_M / 1000)
    parser.add_argument("--output-format", choices=["csv", "xlsx"], default=OUTPUT_FORMAT)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--result-dir", type=Path, default=RESULT_DIR)
    parser.add_argument("--list-nodes", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    start_nodes = resolve_vehicle_nodes(
        default_node=args.start,
        vehicle_nodes=args.starts,
        num_vehicles=args.vehicles,
        node_name="start",
    )
    end_nodes = resolve_vehicle_nodes(
        default_node=args.end,
        vehicle_nodes=args.ends,
        num_vehicles=args.vehicles,
        node_name="end",
    )

    if args.list_nodes:
        distance_df = matrix_distance(
            input_csv=args.input_csv,
            unit="m",
            decimals=0,
            return_format="dataframe",
        )
        node_labels = distance_df.index.astype(str).tolist()
        validate_terminal_nodes(start_nodes, end_nodes, len(node_labels))
        node_table = build_node_table(args.input_csv, node_labels, start_nodes, end_nodes)
        args.result_dir.mkdir(parents=True, exist_ok=True)
        suffix = (
            f"start_node_{compact_node_list(start_nodes)}_"
            f"end_node_{compact_node_list(end_nodes)}_"
            f"vehicle_{args.vehicles}"
        )
        node_path = args.result_dir / f"VRP_노드목록_{suffix}.csv"
        node_table.to_csv(node_path, index=False, encoding="utf-8-sig")
        print(node_table.to_string(index=False))
        print(node_path)
        return

    data = create_data_model(
        input_csv=args.input_csv,
        start_nodes=start_nodes,
        end_nodes=end_nodes,
        num_vehicles=args.vehicles,
        max_vehicle_distance_m=int(args.max_distance_km * 1000),
        near_node_radius_m=int(args.near_radius_km * 1000),
    )
    manager, routing, solution = solve_vrp(data)

    if solution is None:
        print("No solution found !")
        return

    route_df, skipped_df = build_route_result(data, manager, routing, solution)
    output_paths = save_outputs(
        data,
        route_df,
        skipped_df,
        args.output_format,
        args.result_dir,
    )

    visited_service_nodes = set(route_df["NODE"].unique()) - data["terminal_nodes"]
    print(f"start NODEs: {data['starts']}")
    print(f"end NODEs: {data['ends']}")
    print(f"vehicles: {data['num_vehicles']}")
    print(f"visited service nodes: {len(visited_service_nodes)}")
    print(f"skipped nodes: {len(skipped_df)}")
    print(f"max route distance: {route_df.groupby('vehicle_id')['value'].max().max()}m")
    print("saved files:")
    for output_path in output_paths:
        print(output_path)


if __name__ == "__main__":
    main()
