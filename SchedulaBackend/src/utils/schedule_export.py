# src/utils/schedule_export.py
"""
Build CSV / PDF exports of a schedule's assignments.

Both builders take the rows returned by
``schedule_queries.get_detailed_schedule`` and produce the bytes for a
downloadable file. The column set is intentionally the same across formats so
the CSV and PDF stay consistent.
"""

import csv
import io
import os
from datetime import time
from typing import Any, Dict, List, Optional

DAY_LABELS = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
}

# (header, row-key) pairs in display order.
COLUMNS = [
    ("Course Name", "course_name"),
    ("Course Number", "course_number"),
    ("Group", "group_number"),
    ("Lecturer", "lecturer_name"),
    ("Day", "day_label"),
    ("Start Time", "start_label"),
    ("End Time", "end_label"),
]


# Bundled fonts (registered with reportlab so PDF exports render Hebrew/Unicode
# without relying on host/container system fonts).
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts", "dejavu-sans")
_FONT_REGULAR = "DejaVuSans"
_FONT_BOLD = "DejaVuSans-Bold"
_fonts_registered = False


def _register_fonts() -> None:
    """Register the bundled DejaVu Sans fonts with reportlab (idempotent)."""
    global _fonts_registered
    if _fonts_registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont(_FONT_REGULAR, os.path.join(_FONTS_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")))
    _fonts_registered = True


def _shape_rtl(text: str) -> str:
    """Reorder bidirectional (e.g. Hebrew) text for correct visual display.

    reportlab lays glyphs out left-to-right in logical order and does not do
    BiDi resolution, so right-to-left text must be pre-reordered to its visual
    form. ``get_display`` is a no-op for pure left-to-right text, so English
    and numbers are unaffected.
    """
    if not text:
        return text
    try:
        from bidi.algorithm import get_display

        return get_display(text)
    except Exception:
        # If python-bidi is unavailable, fall back to the raw text rather than
        # failing the whole export.
        return text


def _format_time(value: Any) -> str:
    """Render a TIME value as HH:MM (accepts datetime.time or string)."""
    if value is None:
        return ""
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value)
    # Strings often arrive as 'HH:MM:SS' -> trim to HH:MM.
    return text[:5] if len(text) >= 5 else text


def _normalize_rows(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project raw session rows onto the export columns."""
    normalized: List[Dict[str, Any]] = []
    for s in sessions:
        normalized.append(
            {
                "course_name": s.get("course_name") or "",
                "course_number": s.get("course_number") if s.get("course_number") is not None else "",
                "group_number": s.get("group_number") if s.get("group_number") is not None else "",
                "lecturer_name": s.get("lecturer_name") or "",
                "day_label": DAY_LABELS.get(s.get("day_of_week"), f"Day {s.get('day_of_week')}"),
                "start_label": _format_time(s.get("start_time")),
                "end_label": _format_time(s.get("end_time")),
            }
        )
    return normalized


def build_csv(sessions: List[Dict[str, Any]]) -> bytes:
    """Build a UTF-8 CSV (with BOM, so Excel reads Hebrew/Unicode correctly)."""
    rows = _normalize_rows(sessions)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _ in COLUMNS])
    for row in rows:
        writer.writerow([row[key] for _, key in COLUMNS])
    # utf-8-sig adds a BOM so spreadsheet apps detect UTF-8.
    return buffer.getvalue().encode("utf-8-sig")


def build_pdf(sessions: List[Dict[str, Any]], title: Optional[str] = None) -> bytes:
    """Build a landscape A4 PDF table of the assignments.

    Uses the bundled DejaVu Sans font and BiDi reshaping so Hebrew (and other
    RTL) text renders correctly.
    """
    # Imported lazily so the CSV path never depends on reportlab being present.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )

    _register_fonts()

    rows = _normalize_rows(sessions)
    buffer = io.BytesIO()
    doc_title = title or "Schedule Assignments"
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=doc_title,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.fontName = _FONT_BOLD

    elements = []
    elements.append(Paragraph(_shape_rtl(doc_title), title_style))
    elements.append(Spacer(1, 0.4 * cm))

    table_data = [[_shape_rtl(header) for header, _ in COLUMNS]]
    for row in rows:
        table_data.append([_shape_rtl(str(row[key])) for _, key in COLUMNS])

    if not rows:
        table_data.append(["No assignments to display."] + [""] * (len(COLUMNS) - 1))

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6d5de7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), _FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f0ff")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d2f5")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()
