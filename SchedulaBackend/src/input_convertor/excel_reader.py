# src/input_convertor/excel_reader.py
"""Excel file reader for data conversion."""

import pandas as pd
from io import BytesIO


async def _read_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(file_bytes)).dropna(how="all")


read_lecturers_excel = _read_excel
read_courses_excel   = _read_excel
