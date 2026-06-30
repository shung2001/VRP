# -*- coding: utf-8 -*-
from pathlib import Path

import geopandas as gpd


READ_FALLBACK_ENCODINGS = ("cp949", "euc-kr", "utf-8-sig", "utf-8", "latin1")
CSV_WRITE_ENCODINGS = ("cp949", "utf-8-sig")
SHP_WRITE_ENCODINGS = ("cp949", "euc-kr", "utf-8")


def _read_cpg_encoding(path: Path) -> str | None:
    cpg_path = path.with_suffix(".cpg")
    if not cpg_path.exists():
        return None

    try:
        value = cpg_path.read_text(encoding="ascii", errors="ignore").strip()
    except OSError:
        return None

    return value or None


def _encoding_candidates(path: Path) -> list[str | None]:
    candidates: list[str | None] = []
    cpg_encoding = _read_cpg_encoding(path)

    if cpg_encoding:
        candidates.append(cpg_encoding)

    candidates.extend(READ_FALLBACK_ENCODINGS)
    candidates.append(None)

    unique_candidates: list[str | None] = []
    seen: set[str] = set()
    for encoding in candidates:
        key = (encoding or "default").lower()
        if key not in seen:
            seen.add(key)
            unique_candidates.append(encoding)

    return unique_candidates


def _decode_latin1_as_utf8(value):
    if not isinstance(value, str):
        return value

    try:
        return value.encode("latin1").decode("utf-8", errors="ignore")
    except UnicodeError:
        return value


def _repair_latin1_utf8(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf.columns = [_decode_latin1_as_utf8(col) for col in gdf.columns]

    for col in gdf.select_dtypes(include=["object"]).columns:
        gdf[col] = gdf[col].map(_decode_latin1_as_utf8)

    return gdf


def read_vector(path: Path, required_columns: list[str] | None = None) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")

    errors: list[str] = []
    required_columns = required_columns or []

    for encoding in _encoding_candidates(path):
        name = encoding or "default"
        try:
            if encoding is None:
                gdf = gpd.read_file(path)
            else:
                gdf = gpd.read_file(path, encoding=encoding)

            if encoding and encoding.lower() == "latin1":
                gdf = _repair_latin1_utf8(gdf)

            missing = [col for col in required_columns if col not in gdf.columns]
            if missing:
                raise KeyError(f"필수 컬럼 없음: {', '.join(missing)}")

            print(f"{path.name} - {name} 인코딩 성공")
            return gdf
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            print(f"{path.name} - {name} 인코딩 실패: {exc}")

    raise RuntimeError(f"{path.name} 파일을 읽지 못했습니다.\n" + "\n".join(errors))


def clean_geometry(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if hasattr(gdf.geometry, "make_valid"):
        gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def write_csv_with_fallback(df, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for encoding in CSV_WRITE_ENCODINGS:
        try:
            df.to_csv(path, index=False, encoding=encoding)
            print(f"{path.name} - {encoding} 저장 성공")
            return encoding
        except UnicodeEncodeError as exc:
            errors.append(f"{encoding}: {exc}")
            print(f"{path.name} - {encoding} 저장 실패: {exc}")

    raise RuntimeError(f"{path.name} CSV 저장 실패\n" + "\n".join(errors))


def remove_vector_dataset(path: Path) -> None:
    if path.suffix.lower() == ".shp":
        for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qmd", ".fix"):
            sidecar = path.with_suffix(suffix)
            if sidecar.exists():
                sidecar.unlink()
        return

    if path.exists():
        path.unlink()


def write_shp_with_fallback(gdf: gpd.GeoDataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for encoding in SHP_WRITE_ENCODINGS:
        try:
            remove_vector_dataset(path)
            print(f"{path.name} - {encoding} 저장 시도...")
            gdf.to_file(path, encoding=encoding)
            path.with_suffix(".cpg").write_text(encoding.upper(), encoding="ascii")
            print(f"{path.name} - {encoding} 저장 성공")
            return encoding
        except Exception as exc:
            errors.append(f"{encoding}: {exc}")
            print(f"{path.name} - {encoding} 저장 실패: {exc}")

    raise RuntimeError(f"{path.name} SHP 저장 실패\n" + "\n".join(errors))
