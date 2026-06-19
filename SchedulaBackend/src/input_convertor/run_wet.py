# src/input_convertor/run_wet.py
"""
Wet-run script: reads the bundled sample Excel files and runs the full
input-converter pipeline directly against the database.

The converter writes through the repository layer (no HTTP), so this script
needs a connected DB pool. We open and close one for the duration of the run.

Requirements:
  - DB must be reachable (settings.database_url)
  - Tables must already exist (run /db/init from the API once if needed)
  - The target semester referenced by the lecturer file must exist before
    /load_assignments runs

Usage:
  python -m src.input_convertor.run_wet
  python -m src.input_convertor.run_wet --lecturers-dedu path/to/dedu.xlsx \\
                                        --lecturers      path/to/full.xlsx \\
                                        --courses        path/to/courses.xlsx
"""

import argparse
import asyncio
import logging
from pathlib import Path

from src.database.database import db
from .converter import convert_and_load

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# The dedu mapper only reads identity columns and ignores the rest, so the
# full lecturer file works as the dedu input as well. Override via CLI flags
# if you maintain a separate slim dedu sheet.
DEFAULT_LECTURERS_DEDU = Path(__file__).parent / "lecturer_full.xlsx"
DEFAULT_LECTURERS_FULL = Path(__file__).parent / "lecturer_full.xlsx"
DEFAULT_COURSES = Path(__file__).parent / "courses_full.xlsx"


async def main(lecturers_dedu_path: Path, lecturers_path: Path, courses_path: Path) -> None:
    logger.info("=== WET RUN ===")
    logger.info(f"Lecturers dedu file: {lecturers_dedu_path}")
    logger.info(f"Lecturers full file: {lecturers_path}")
    logger.info(f"Courses file:        {courses_path}")

    lecturers_dedu_bytes = lecturers_dedu_path.read_bytes()
    lecturers_bytes = lecturers_path.read_bytes()
    courses_bytes = courses_path.read_bytes()

    await db.connect()
    try:
        logger.info("Running pipeline... (this may take a while)")
        result = await convert_and_load(lecturers_dedu_bytes, lecturers_bytes, courses_bytes)
    finally:
        await db.disconnect()

    logger.info("=== RESULT ===")
    for key, value in result.items():
        logger.info(f"  {key}: {value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lecturers-dedu",
        type=Path,
        default=DEFAULT_LECTURERS_DEDU,
        help="Path to the slim deduplicated lecturer Excel (identity columns only).",
    )
    parser.add_argument(
        "--lecturers",
        type=Path,
        default=DEFAULT_LECTURERS_FULL,
        help="Path to the full lecturer Excel (with course/semester assignment columns).",
    )
    parser.add_argument(
        "--courses",
        type=Path,
        default=DEFAULT_COURSES,
        help="Path to the courses Excel.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.lecturers_dedu, args.lecturers, args.courses))
