"""Clean NIH Reporter exports by stripping biomarker phrases and deduplicating projects.

The utility accepts either direct download URLs (SciOP snapshots remain supported) or
paths to pre-downloaded NIH Reporter exporter archives. Each archive is expected to
contain a CSV file; the script streams every row, removes biomarker-related phrases from
the selected summary column, and collapses the combined dataset to one record per
project identifier. Raw downloads are cached in ``data/raw`` (configurable), and the
cleaned output is written as a CSV under ``data/processed`` by default. When automated
downloads are not possible, pass ``--input-zip`` one or more times to process local
archives directly.

Example usage
-------------
python scripts/clean_sciop_biomarkers.py --year 2022

To speed up local testing on large files you can add ``--max-rows 50000`` which limits the
number of rows processed after download. The cleaned result will still be deduplicated
across the truncated sample.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)
DEFAULT_URL_TEMPLATE = "https://sciop.net/datasets/nih-reporter/{year}/nih-reporter-{year}.zip"
DEFAULT_PROJECT_ID_COLUMNS = (
    "APPLICATION_ID",
    "PROJECT_ID",
    "PROJECT_NUM",
    "FULL_PROJECT_NUM",
)
SUMMARY_COLUMN_CANDIDATES = (
    "PROJECT_SUMMARY",
    "PROJECT_SUMMARY_TEXT",
    "PROJECT_TITLE",
    "PROJECT_TITLE_TEXT",
    "ABSTRACT_TEXT",
    "ABSTRACT",
)
KEYWORDS = (
    "clinical marker",
    "biomarker",
    "surrogate endpoint",
    "intermediate outcome",
    "endpoints",
    "endophenotype",
    "genetic marker",
)
KEYWORD_PATTERN = re.compile(r"(?i)\b(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b")
USER_AGENT = "nih-biomarker-funding-bot/1.0 (+https://sciop.net/datasets/nih-reporter)"


@dataclass(frozen=True)
class RankingKey:
    fiscal_year: float
    total_cost: float
    row_index: int

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.fiscal_year, self.total_cost, -self.row_index)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year",
        type=int,
        help="Year of the SciOP snapshot to download (mutually exclusive with --url).",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Direct URL to a SciOP NIH Reporter zip file. Overrides --year when provided.",
    )
    parser.add_argument(
        "--input-zip",
        dest="input_zips",
        action="append",
        type=Path,
        help=(
            "Path to a pre-downloaded NIH Reporter zip archive. "
            "Provide the flag multiple times to merge several exports without re-downloading."
        ),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory where raw downloads are cached (default: data/raw).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where cleaned outputs are written (default: data/processed).",
    )
    parser.add_argument(
        "--summary-column",
        type=str,
        help="Name of the summary/abstract column to scrub. If omitted a heuristic search is used.",
    )
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        help="Project identifier column(s) used for deduplication. Can be provided multiple times.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        help="Maximum number of rows to process after loading the CSV (useful for smoke tests).",
    )
    parser.add_argument(
        "--csv-name",
        type=str,
        help="Optional explicit CSV filename inside the zip archive. Defaults to the first CSV entry.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        help="Optional stem for the output filename. Defaults to a name based on the year or URL.",
    )
    args = parser.parse_args(argv)
    if args.project_ids is None:
        args.project_ids = list(DEFAULT_PROJECT_ID_COLUMNS)
    if args.input_zips is not None and len(args.input_zips) == 0:
        args.input_zips = None
    return args


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def ensure_download(url: str, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    file_name = Path(urlparse(url).path).name or "sciop.zip"
    destination = raw_dir / file_name
    if destination.exists():
        LOGGER.info("Reusing cached download at %s", destination)
        return destination

    LOGGER.info("Downloading %s", url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=300) as response, open(destination, "wb") as fh:
            shutil.copyfileobj(response, fh)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"Failed to download {url}: {error}") from error
    LOGGER.info("Saved download to %s", destination)
    return destination


def resolve_summary_column(columns: Sequence[str], preferred: str | None = None) -> str:
    if preferred:
        if preferred not in columns:
            raise ValueError(f"Requested summary column '{preferred}' not found in dataset")
        return preferred

    for candidate in SUMMARY_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate

    for column in columns:
        lowered = column.lower()
        if "summary" in lowered or "abstract" in lowered:
            return column

    raise ValueError(
        "Could not infer a summary/abstract column. Pass --summary-column explicitly."
    )


def resolve_project_column(columns: Sequence[str], candidates: Iterable[str]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise ValueError(
        "None of the provided project ID columns were found in the dataset."
    )


def scrub_summary(text: str | None) -> str:
    if not text:
        return ""
    cleaned = KEYWORD_PATTERN.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def parse_numeric(value: str | None) -> float:
    if value is None:
        return float("-inf")
    stripped = value.replace(",", "").strip()
    if not stripped:
        return float("-inf")
    try:
        return float(stripped)
    except ValueError:
        return float("-inf")


def build_ranking(row: dict[str, str | None], index: int) -> RankingKey:
    fiscal_year = parse_numeric(row.get("FISCAL_YEAR") or row.get("FY"))
    total_cost = parse_numeric(row.get("TOTAL_COST") or row.get("TOTAL_COST_BUDGET"))
    return RankingKey(fiscal_year=fiscal_year, total_cost=total_cost, row_index=index)


def clean_snapshot(args: argparse.Namespace) -> Path:
    archives: list[Path]
    if args.input_zips is not None:
        archives = []
        for candidate in args.input_zips:
            archive_path = candidate.expanduser()
            if not archive_path.exists():
                raise FileNotFoundError(
                    f"Provided --input-zip path '{archive_path}' does not exist"
                )
            archives.append(archive_path)
        if not archives:
            raise ValueError("At least one --input-zip must be supplied when using local archives.")
        LOGGER.info("Using %d pre-downloaded archive(s)", len(archives))
    else:
        if args.url:
            url = args.url
        elif args.year is not None:
            url = DEFAULT_URL_TEMPLATE.format(year=args.year)
        else:
            raise ValueError("You must provide either --input-zip, --year, or --url.")
        csv_zip_path = ensure_download(url, args.raw_dir)
        archives = [csv_zip_path]

    best_rows: dict[str, tuple[tuple[float, float, float], dict[str, str | None]]] = {}
    all_columns: list[str] | None = None
    summary_column: str | None = None
    project_column: str | None = None
    global_index = 0
    limit_reached = False

    for archive_path in archives:
        with zipfile.ZipFile(archive_path) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not members:
                raise ValueError(f"Zip archive {archive_path} does not contain a CSV file")
            member = args.csv_name or members[0]
            if member not in archive.namelist():
                raise ValueError(
                    f"CSV '{member}' not found in archive {archive_path}. Available entries: {members}"
                )
            LOGGER.info("Loading CSV %s from archive %s", member, archive_path)
            with archive.open(member) as handle:
                text_stream = io.TextIOWrapper(handle, encoding="utf-8", newline="")
                reader = csv.DictReader(text_stream)
                if reader.fieldnames is None:
                    raise ValueError(f"CSV file in {archive_path} is missing headers")

                if all_columns is None:
                    all_columns = list(reader.fieldnames)
                    summary_column = resolve_summary_column(all_columns, args.summary_column)
                    project_column = resolve_project_column(all_columns, args.project_ids)
                else:
                    for field in reader.fieldnames:
                        if field not in all_columns:
                            all_columns.append(field)
                    assert summary_column is not None and project_column is not None
                    if summary_column not in reader.fieldnames:
                        raise ValueError(
                            f"Summary column '{summary_column}' missing from archive {archive_path}"
                        )
                    if project_column not in reader.fieldnames:
                        raise ValueError(
                            f"Project ID column '{project_column}' missing from archive {archive_path}"
                        )

                for row in reader:
                    if args.max_rows is not None and global_index >= args.max_rows:
                        LOGGER.info(
                            "Reached row limit %d; stopping ingestion early", args.max_rows
                        )
                        limit_reached = True
                        break

                    assert project_column is not None and summary_column is not None
                    project_id = (row.get(project_column) or "").strip()
                    if not project_id:
                        global_index += 1
                        continue

                    row[summary_column] = scrub_summary(row.get(summary_column))
                    ranking = build_ranking(row, global_index).as_tuple()
                    existing = best_rows.get(project_id)
                    if existing is None or ranking > existing[0]:
                        best_rows[project_id] = (ranking, dict(row))
                    global_index += 1
                if limit_reached:
                    break
        if limit_reached:
            break

    if not best_rows:
        raise ValueError("No valid project rows were ingested from the provided archives")

    assert project_column is not None
    cleaned_rows = [
        entry[1] for entry in sorted(best_rows.values(), key=lambda item: item[0], reverse=True)
    ]

    output_name = determine_output_stem(args, project_column, archives)
    assert all_columns is not None
    return write_output(cleaned_rows, all_columns, args.out_dir, output_name)


def determine_output_stem(
    args: argparse.Namespace, project_column: str, archives: Sequence[Path]
) -> str:
    if args.output_name:
        stem = args.output_name
    elif args.input_zips is not None:
        if len(archives) == 1:
            stem = archives[0].stem or "nih-reporter-cleaned"
        else:
            stem = f"{archives[0].stem}-plus{len(archives) - 1}"
    elif args.url:
        parsed = Path(urlparse(args.url).path).stem
        stem = parsed or "sciop-cleaned"
    else:
        stem = f"nih-reporter-cleaned-{args.year}"
    suffix_bits = []
    if args.max_rows is not None:
        suffix_bits.append(f"sample{args.max_rows}")
    suffix_bits.append(f"dedupe-{project_column.lower()}")
    return "-".join([stem, *suffix_bits])


def write_output(
    rows: list[dict[str, str | None]],
    columns: Sequence[str],
    output_dir: Path,
    output_name: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_name}.csv"
    LOGGER.info("Writing %d cleaned rows to %s", len(rows), output_path)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        ordered_columns = list(columns)
        writer = csv.DictWriter(fh, fieldnames=ordered_columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized_row = {column: row.get(column, "") for column in ordered_columns}
            writer.writerow(normalized_row)
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    try:
        output_path = clean_snapshot(args)
    except Exception as exc:  # pragma: no cover - CLI surface area
        LOGGER.error("Failed to clean snapshot: %s", exc)
        return 1
    LOGGER.info("Wrote cleaned dataset to %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
