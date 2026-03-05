"""
Shared utility for loading abstracts from NIH RePORTER zip files.

Abstract files live at ~/Downloads/RePORTER_PRJABS_C_FY{year}.zip.
Each zip contains a single CSV with columns APPLICATION_ID and ABSTRACT_TEXT.
FY2016 is missing (confirmed).
"""

import csv
import io
import zipfile
from pathlib import Path


def load_abstracts_for_year(year: int, abs_dir: Path) -> dict[str, str]:
    """Read abstracts from a RePORTER zip file for a single fiscal year.

    Parameters
    ----------
    year : int
        Fiscal year (e.g. 2012).
    abs_dir : Path
        Directory containing RePORTER_PRJABS_C_FY{year}.zip files.

    Returns
    -------
    dict mapping APPLICATION_ID (str) -> ABSTRACT_TEXT (str).
    Empty dict if the zip file is not found.
    """
    zip_path = Path(abs_dir) / f"RePORTER_PRJABS_C_FY{year}.zip"
    if not zip_path.exists():
        print(f"  WARNING: abstract zip not found for FY{year}: {zip_path}")
        return {}

    abstracts: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            print(f"  WARNING: no CSV found inside {zip_path}")
            return {}

        with zf.open(csv_names[0]) as raw:
            text_wrapper = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_wrapper)
            for row in reader:
                app_id = row.get("APPLICATION_ID", "").strip()
                abstract = row.get("ABSTRACT_TEXT", "").strip()
                if app_id and abstract:
                    abstracts[app_id] = abstract

    return abstracts


def load_abstracts_for_ids(
    app_ids_by_year: dict[int, list[str]],
    abs_dir: Path,
) -> dict[str, str]:
    """Load abstracts for specific APPLICATION_IDs, grouped by fiscal year.

    Only reads zip files for years that have requested IDs, avoiding
    unnecessary I/O.

    Parameters
    ----------
    app_ids_by_year : dict
        Mapping of fiscal year (int) -> list of APPLICATION_ID strings.
    abs_dir : Path
        Directory containing RePORTER_PRJABS_C_FY{year}.zip files.

    Returns
    -------
    dict mapping APPLICATION_ID (str) -> ABSTRACT_TEXT (str).
    IDs not found in the zip are silently omitted.
    """
    result: dict[str, str] = {}
    for year in sorted(app_ids_by_year):
        needed = set(app_ids_by_year[year])
        if not needed:
            continue
        year_abstracts = load_abstracts_for_year(year, abs_dir)
        for app_id in needed:
            if app_id in year_abstracts:
                result[app_id] = year_abstracts[app_id]
    return result
