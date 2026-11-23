"""Bounded CSV/XLSX loading. Uploaded bytes are never written to disk."""

from io import BytesIO, StringIO
from pathlib import Path
import csv
import zipfile
import numpy as np
import pandas as pd
from openpyxl import load_workbook

MAX_BYTES = 15 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 100
MAX_CELLS = 2_000_000
MAX_MEMORY = 80 * 1024 * 1024


class DataError(ValueError):
    """An actionable, safe-to-display input error."""


def validate_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise DataError(
            "The dataset has no records. Include a header and at least one data row."
        )
    if len(df) > MAX_ROWS or len(df.columns) > MAX_COLUMNS or df.size > MAX_CELLS:
        raise DataError(
            "Dataset limit: 100,000 rows, 100 columns and 2 million cells. Upload a smaller extract."
        )
    names = [str(c).strip() for c in df.columns]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise DataError(
            "Column headers must be nonempty and unique after trimming spaces."
        )
    if any(len(n) > 150 for n in names):
        raise DataError("Column names must contain at most 150 characters.")
    df.columns = names
    if df.memory_usage(index=True, deep=True).sum() > MAX_MEMORY:
        raise DataError(
            "This dataset uses too much memory. Please upload a smaller extract."
        )
    numeric = df.select_dtypes(include="number")
    if np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).any():
        raise DataError(
            "Infinite numerical values were found. Correct them in the source file first."
        )
    return df.reset_index(drop=True)


def _check_bytes(data: bytes):
    if not data:
        raise DataError("This file is empty.")
    if len(data) > MAX_BYTES:
        raise DataError("The upload limit is 15 MB. Please choose a smaller file.")


def _workbook(data: bytes):
    _check_bytes(data)
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > 2000
                or sum(x.file_size for x in entries) > 80 * 1024 * 1024
            ):
                raise DataError(
                    "The expanded Excel workbook is too large. Save a smaller extract."
                )
        return load_workbook(
            BytesIO(data), read_only=True, data_only=True, keep_links=False
        )
    except DataError:
        raise
    except Exception:
        raise DataError(
            "Cannot read this Excel workbook. Save it as a valid, unencrypted .xlsx file."
        ) from None


def sheet_names(data: bytes) -> list[str]:
    wb = _workbook(data)
    try:
        return wb.sheetnames
    finally:
        wb.close()


def load_data(
    data: bytes,
    name: str,
    sheet: str | None = None,
    encoding: str = "utf-8-sig",
    delimiter: str = ",",
) -> pd.DataFrame:
    _check_bytes(data)
    extension = Path(name).suffix.lower()
    try:
        if extension == ".csv":
            if encoding not in ("utf-8-sig", "cp1252", "latin-1") or delimiter not in (
                ",",
                ";",
                "\t",
                "|",
            ):
                raise DataError("Choose a supported CSV encoding and delimiter.")
            text = data.decode(encoding)
            reader = csv.reader(StringIO(text), delimiter=delimiter, strict=True)
            header = next(reader, [])
            if not header or len(header) > MAX_COLUMNS:
                raise DataError(
                    "CSV needs a header with 1–100 columns. Check the delimiter."
                )
            if len(set(x.strip() for x in header)) != len(header) or any(
                not x.strip() for x in header
            ):
                raise DataError("CSV headers must be nonempty and unique.")
            count = 0
            for row in reader:
                if not row:
                    continue
                count += 1
                if len(row) != len(header):
                    raise DataError(
                        "CSV rows have different numbers of fields. Check quotes and delimiter."
                    )
                if count > MAX_ROWS or count * len(header) > MAX_CELLS:
                    raise DataError(
                        "CSV exceeds the row or cell limit. Upload a smaller extract."
                    )
            df = pd.read_csv(StringIO(text), sep=delimiter)
        elif extension == ".xlsx":
            wb = _workbook(data)
            try:
                chosen = sheet or wb.sheetnames[0]
                if chosen not in wb.sheetnames:
                    raise DataError("The selected Excel sheet does not exist.")
                ws = wb[chosen]
                if (ws.max_row or 0) > MAX_ROWS + 1 or (
                    ws.max_column or 0
                ) > MAX_COLUMNS:
                    raise DataError(
                        "Excel sheet dimensions exceed the limits. Remove excess formatted rows/columns."
                    )
                rows = ws.iter_rows(values_only=True)
                header = next(rows, ())
                if not header or any(x is None for x in header):
                    raise DataError(
                        "The first Excel row must contain complete column headers."
                    )
                records = []
                for row in rows:
                    if all(x is None for x in row):
                        continue
                    records.append(row)
                    if (
                        len(records) > MAX_ROWS
                        or len(records) * len(header) > MAX_CELLS
                    ):
                        raise DataError("Excel sheet exceeds the row or cell limit.")
                df = pd.DataFrame(records, columns=header)
            finally:
                wb.close()
        else:
            raise DataError("Supported formats are .csv and .xlsx.")
        return validate_frame(df)
    except DataError:
        raise
    except UnicodeDecodeError:
        raise DataError(
            "CSV encoding could not be read. Try Windows-1252 under CSV options."
        ) from None
    except Exception:
        raise DataError(
            "The file could not be parsed. Check its format, header and values."
        ) from None
