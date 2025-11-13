from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.clean_sciop_biomarkers import FIGSHARE_API_BASE, clean_snapshot, parse_args


def build_test_zip(path: Path, rows: list[dict[str, str]]) -> None:
    csv_bytes = io.StringIO()
    writer = csv.DictWriter(
        csv_bytes,
        fieldnames=[
            "APPLICATION_ID",
            "PROJECT_SUMMARY",
            "FISCAL_YEAR",
            "TOTAL_COST",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mock.csv", csv_bytes.getvalue())


def build_zip_bytes(rows: list[dict[str, str]]) -> bytes:
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "APPLICATION_ID",
            "PROJECT_SUMMARY",
            "FISCAL_YEAR",
            "TOTAL_COST",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("mock.csv", csv_buffer.getvalue())
    return zip_buffer.getvalue()


@pytest.mark.parametrize(
    "rows, expected_summary",
    [
            (
                [
                    {
                        "APPLICATION_ID": "P1",
                        "PROJECT_SUMMARY": "This biomarker project studies clinical marker panels.",
                        "FISCAL_YEAR": "2022",
                        "TOTAL_COST": "100",
                    },
                    {
                        "APPLICATION_ID": "P1",
                        "PROJECT_SUMMARY": "Updated biomarker surrogate endpoint description",
                        "FISCAL_YEAR": "2023",
                        "TOTAL_COST": "150",
                    },
                ],
                "Updated description",
            ),
        (
            [
                {
                    "APPLICATION_ID": "P2",
                    "PROJECT_SUMMARY": "No keywords here",
                    "FISCAL_YEAR": "2021",
                    "TOTAL_COST": "250",
                }
            ],
            "No keywords here",
        ),
    ],
)
def test_clean_snapshot_prefers_best_rank_and_scrubs(tmp_path: Path, rows, expected_summary):
    archive_path = tmp_path / "sample.zip"
    build_test_zip(archive_path, rows)

    out_dir = tmp_path / "out"
    args = parse_args(
        [
            "--input-zip",
            str(archive_path),
            "--out-dir",
            str(out_dir),
            "--output-name",
            "cleaned",
            "--log-level",
            "ERROR",
        ]
    )

    output_csv = clean_snapshot(args)

    assert output_csv.exists()
    assert output_csv.parent == out_dir
    with output_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert rows[0]["APPLICATION_ID"] in {"P1", "P2"}
    assert rows[0]["PROJECT_SUMMARY"] == expected_summary


@pytest.mark.usefixtures("tmp_path")
def test_clean_snapshot_respects_project_identifier(tmp_path: Path):
    archive_path = tmp_path / "ids.zip"
    build_test_zip(
        archive_path,
        [
            {
                "APPLICATION_ID": "A1",
                "PROJECT_SUMMARY": "biomarker investigation",
                "FISCAL_YEAR": "2022",
                "TOTAL_COST": "100",
            },
            {
                "APPLICATION_ID": "",
                "PROJECT_SUMMARY": "unidentified",
                "FISCAL_YEAR": "2023",
                "TOTAL_COST": "999",
            },
        ],
    )

    out_dir = tmp_path / "processed"
    args = parse_args(
        [
            "--input-zip",
            str(archive_path),
            "--out-dir",
            str(out_dir),
            "--output-name",
            "ids",
            "--log-level",
            "ERROR",
        ]
    )

    output_csv = clean_snapshot(args)
    with output_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["APPLICATION_ID"] == "A1"
    assert rows[0]["PROJECT_SUMMARY"] == "investigation"


def test_clean_snapshot_accepts_multiple_archives(tmp_path: Path):
    archive_one = tmp_path / "fy2022.zip"
    build_test_zip(
        archive_one,
        [
            {
                "APPLICATION_ID": "B1",
                "PROJECT_SUMMARY": "Biomarker surrogate endpoint analysis",
                "FISCAL_YEAR": "2022",
                "TOTAL_COST": "100",
            }
        ],
    )

    archive_two = tmp_path / "fy2023.zip"
    build_test_zip(
        archive_two,
        [
            {
                "APPLICATION_ID": "B1",
                "PROJECT_SUMMARY": "Updated biomarker study",
                "FISCAL_YEAR": "2023",
                "TOTAL_COST": "150",
            },
            {
                "APPLICATION_ID": "B2",
                "PROJECT_SUMMARY": "Control project with genetic marker term",
                "FISCAL_YEAR": "2023",
                "TOTAL_COST": "200",
            },
        ],
    )

    out_dir = tmp_path / "merged"
    args = parse_args(
        [
            "--input-zip",
            str(archive_one),
            "--input-zip",
            str(archive_two),
            "--out-dir",
            str(out_dir),
            "--output-name",
            "merged",
            "--log-level",
            "ERROR",
        ]
    )

    output_csv = clean_snapshot(args)
    with output_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert len(rows) == 2
    summaries = {row["APPLICATION_ID"]: row["PROJECT_SUMMARY"] for row in rows}
    assert summaries["B1"] == "Updated study"
    assert summaries["B2"] == "Control project with term"


def test_clean_snapshot_downloads_figshare_archives(monkeypatch, tmp_path: Path):
    article_id = 30615185
    download_url = f"{FIGSHARE_API_BASE}/file/download/555"
    archive_bytes = build_zip_bytes(
        [
            {
                "APPLICATION_ID": "F1",
                "PROJECT_SUMMARY": "Figshare biomarker endpoints study",
                "FISCAL_YEAR": "2023",
                "TOTAL_COST": "250",
            }
        ]
    )

    article_payload = {
        "files": [
            {"id": 111, "name": "readme.txt", "download_url": "https://example.com/readme"},
            {"id": 222, "name": "fy2023.zip", "download_url": download_url},
        ]
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    def fake_urlopen(request, timeout=0):
        url = request.full_url if hasattr(request, "full_url") else request
        if url == f"{FIGSHARE_API_BASE}/articles/{article_id}":
            return FakeResponse(json.dumps(article_payload).encode("utf-8"))
        if url == download_url:
            return FakeResponse(archive_bytes)
        if url == "https://example.com/readme":
            return FakeResponse(b"not-zip")
        raise AssertionError(f"Unexpected URL requested: {url}")

    monkeypatch.setattr("scripts.clean_sciop_biomarkers.urlopen", fake_urlopen)

    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    args = parse_args(
        [
            "--figshare-article",
            str(article_id),
            "--figshare-include",
            "2023",
            "--out-dir",
            str(out_dir),
            "--raw-dir",
            str(raw_dir),
            "--output-name",
            "figshare-clean",
            "--log-level",
            "ERROR",
        ]
    )

    output_csv = clean_snapshot(args)

    assert output_csv.exists()
    raw_archive = raw_dir / "fy2023.zip"
    assert raw_archive.exists()

    with output_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["APPLICATION_ID"] == "F1"
    assert rows[0]["PROJECT_SUMMARY"] == "Figshare study"
