from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pandas as pd


DEFAULT_ZIP = Path("data/GPIPS系统数据库与知识库.zip")

XLSX_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass(frozen=True)
class SourceFiles:
    root: Path
    rating: Path
    reviews: Path
    product_matrix: Path
    idc: Path
    docs: tuple[Path, ...]


def extract_source(zip_path: Path = DEFAULT_ZIP) -> SourceFiles:
    if not zip_path.exists():
        raise FileNotFoundError("Source ZIP is not available. Upload the GPIPS source ZIP from the sidebar.")

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()[:12]
    target = Path(tempfile.gettempdir()) / f"gpips_india_demo_source_{digest}"
    if not target.exists() or not list(target.rglob("*.xlsx")):
        target.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path) as zf:
            zf.extractall(target)

    files = list(target.rglob("*"))

    def pick(name_part: str) -> Path:
        matches = [p for p in files if p.is_file() and name_part in p.name]
        if not matches:
            raise FileNotFoundError(f"Could not find file containing: {name_part}")
        return matches[0]

    docs = tuple(sorted(p for p in files if p.suffix.lower() == ".docx"))
    return SourceFiles(
        root=target,
        rating=pick("评分"),
        reviews=pick("评论"),
        product_matrix=pick("产品矩阵"),
        idc=pick("IDC"),
        docs=docs,
    )


def _shared_strings(zf: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    values: list[str] = []
    for si in root.findall("a:si", XLSX_NS):
        values.append("".join(t.text or "" for t in si.iter(f"{{{XLSX_NS['a']}}}t")))
    return values


def _sheet_paths(zf: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

    paths: list[tuple[str, str]] = []
    for sheet in workbook.findall("a:sheets/a:sheet", XLSX_NS):
        rid = sheet.attrib[f"{{{XLSX_NS['r']}}}id"]
        target = rid_to_target[rid]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        paths.append((sheet.attrib["name"], target))
    return paths


def _colnum(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref or "A")
    letters = match.group(1) if match else "A"
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{{{XLSX_NS['a']}}}t"))

    value = cell.find("a:v", XLSX_NS)
    if value is None:
        return ""

    raw = value.text or ""
    if cell.attrib.get("t") == "s":
        return shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else raw
    return raw


def read_xlsx_sheet(path: Path, sheet_name: str | None = None, sheet_index: int = 0) -> list[list[str]]:
    with ZipFile(path) as zf:
        shared = _shared_strings(zf)
        sheets = _sheet_paths(zf)
        selected = next((item for item in sheets if item[0] == sheet_name), sheets[sheet_index])
        root = ET.fromstring(zf.read(selected[1]))

        rows: list[list[str]] = []
        for row in root.findall("a:sheetData/a:row", XLSX_NS):
            values: list[str] = []
            for cell in row.findall("a:c", XLSX_NS):
                col = _colnum(cell.attrib.get("r", "A"))
                while len(values) < col - 1:
                    values.append("")
                values.append(_cell_value(cell, shared))
            rows.append(values)
        return rows


def _rows_to_df(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    return pd.DataFrame(normalized[1:], columns=header)


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_ratings(path: Path) -> pd.DataFrame:
    df = _rows_to_df(read_xlsx_sheet(path))
    for col in [
        "int_price",
        "comment_num",
        "design_assess",
        "battery_assess",
        "screen_assess",
        "performance_assess",
        "cam_assess",
        "price_assess",
        "software_assess",
        "total_comment",
    ]:
        if col in df:
            df[col] = _to_number(df[col])
    if "brand" in df:
        df["brand"] = df["brand"].str.strip().str.lower()
    return df


def load_reviews(path: Path) -> pd.DataFrame:
    df = _rows_to_df(read_xlsx_sheet(path))
    if "brand" in df:
        df["brand"] = df["brand"].str.strip()
    if "country_alpha2" in df:
        df["country_alpha2"] = df["country_alpha2"].str.strip().str.upper()
    return df


def load_product_matrix(path: Path) -> pd.DataFrame:
    rows = read_xlsx_sheet(path, sheet_index=0)
    if len(rows) < 3:
        return pd.DataFrame(columns=["price_band", "brand", "product_text", "model"])

    header = rows[0]
    records: list[dict[str, str]] = []
    current_band = ""
    for row in rows[2:]:
        if row and row[0].strip():
            current_band = row[0].strip()
        if not current_band:
            continue
        for idx, brand in enumerate(header[1:], start=1):
            if not brand or idx >= len(row):
                continue
            text = row[idx].strip()
            if not text or text.startswith("http"):
                continue
            first_line = text.splitlines()[0].strip()
            model = re.split(r"[（(]", first_line)[0].strip()
            records.append(
                {
                    "price_band": current_band,
                    "brand": brand.strip(),
                    "product_text": text,
                    "model": model,
                }
            )
    return pd.DataFrame(records)


def load_idc_summary(path: Path) -> dict[str, pd.DataFrame]:
    sheets: dict[str, pd.DataFrame] = {}
    for sheet_name in ["Market", "by渠道", "5G板块"]:
        rows = read_xlsx_sheet(path, sheet_name=sheet_name)
        sheets[sheet_name] = pd.DataFrame(rows)
    return sheets


def load_docx_paragraphs(paths: Iterable[Path]) -> pd.DataFrame:
    records: list[dict[str, str | int]] = []
    for path in paths:
        with ZipFile(path) as zf:
            root = ET.fromstring(zf.read("word/document.xml"))
            paragraphs = []
            for para in root.findall(".//w:p", DOCX_NS):
                text = "".join(t.text or "" for t in para.findall(".//w:t", DOCX_NS)).strip()
                if text:
                    paragraphs.append(text)
        for idx, text in enumerate(paragraphs, start=1):
            records.append({"source": path.name, "paragraph_id": idx, "text": text})
    return pd.DataFrame(records)


def load_all(zip_path: Path = DEFAULT_ZIP) -> dict[str, object]:
    sources = extract_source(zip_path)
    return {
        "sources": sources,
        "ratings": load_ratings(sources.rating),
        "reviews": load_reviews(sources.reviews),
        "product_matrix": load_product_matrix(sources.product_matrix),
        "idc": load_idc_summary(sources.idc),
        "knowledge": load_docx_paragraphs(sources.docs),
    }
