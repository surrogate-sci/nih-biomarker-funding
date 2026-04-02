"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

Charts focus on funding allocation and total biomarker spending.
Uses Paul Tol's colorblind-safe qualitative palette throughout.
Datawrapper charts are updated in place if chart IDs exist in .url files.
"""

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

# Paul Tol's qualitative palette — colorblind-safe, publication-ready
# https://personal.sron.nl/~pault/data/colourschemes.pdf
TOL_QUALITATIVE = [
    "#332288",  # indigo
    "#88CCEE",  # cyan
    "#44AA99",  # teal
    "#117733",  # green
    "#999933",  # olive
    "#DDCC77",  # sand
    "#CC6677",  # rose
    "#882255",  # wine
    "#AA4499",  # purple
    "#BBBBBB",  # grey (for "Other")
]

# Map institute codes to palette positions (consistent across all charts)
INSTITUTE_COLORS = {
    "NCI": TOL_QUALITATIVE[0],
    "NIA": TOL_QUALITATIVE[1],
    "NHLBI": TOL_QUALITATIVE[2],
    "NIAID": TOL_QUALITATIVE[3],
    "NINDS": TOL_QUALITATIVE[4],
    "NIMH": TOL_QUALITATIVE[5],
    "NIDDK": TOL_QUALITATIVE[6],
    "NLM": TOL_QUALITATIVE[7],
    "NIGMS": TOL_QUALITATIVE[8],
    "NIBIB": TOL_QUALITATIVE[2],  # reuse teal
    "Other": TOL_QUALITATIVE[9],
}

# Readable institute labels for bar charts
INSTITUTE_LABELS = {
    "NCI (Cancer)": INSTITUTE_COLORS["NCI"],
    "NIA (Aging)": INSTITUTE_COLORS["NIA"],
    "NHLBI (Heart/Lung/Blood)": INSTITUTE_COLORS["NHLBI"],
    "NIAID (Allergy/Infectious)": INSTITUTE_COLORS["NIAID"],
    "NINDS (Neurological)": INSTITUTE_COLORS["NINDS"],
    "NIMH (Mental Health)": INSTITUTE_COLORS["NIMH"],
    "NIDDK (Diabetes/Digestive)": INSTITUTE_COLORS["NIDDK"],
    "NLM (Library of Medicine)": INSTITUTE_COLORS["NLM"],
    "NIGMS (General Medical)": INSTITUTE_COLORS["NIGMS"],
    "NIBIB (Biomedical Imaging)": INSTITUTE_COLORS["NIBIB"],
}

sns.set_theme(style="whitegrid", font_scale=1.1)

SOURCE_NOTE = "Source: NIH ExPORTER (FY2004–2024), keyword-filtered"
DATA_CAVEAT = "FY2005–06 undercounted due to missing PROJECT_TERMS data"

SPENDING_LINE_COLOR = "#225588"


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path) -> "ChartRenderer":  # noqa: F821
    """Return Datawrapper renderer if token is set, else seaborn fallback."""
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if token:
        return DatawrapperRenderer(output_dir, token)
    print("  [charts] No DATAWRAPPER_API_TOKEN — using seaborn/matplotlib fallback")
    return SeabornRenderer(output_dir)


class SeabornRenderer:
    """Fallback renderer using seaborn/matplotlib → PNG files."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "seaborn"

    def _save(self, fig, filename):
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def spending_over_time(self, df: pd.DataFrame, filename: str):
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(
            df["FY"],
            df["total_funding"],
            marker="o",
            linewidth=2.5,
            color=SPENDING_LINE_COLOR,
            markersize=6,
        )
        ax.fill_between(
            df["FY"], df["total_funding"], alpha=0.1, color=SPENDING_LINE_COLOR
        )
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title("NIH Biomarker-Related Spending (FY2004–2024)", fontsize=14)
        for yr in [2005, 2006]:
            ax.axvspan(yr - 0.4, yr + 0.4, alpha=0.15, color="red")
        ax.annotate(
            DATA_CAVEAT,
            xy=(0.02, 0.02),
            xycoords="axes fraction",
            fontsize=8,
            color="red",
            fontstyle="italic",
        )
        ax.text(
            0.99,
            -0.08,
            SOURCE_NOTE,
            transform=ax.transAxes,
            fontsize=8,
            ha="right",
            color="gray",
        )
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_allocation(self, df: pd.DataFrame, filename: str):
        fig, ax = plt.subplots(figsize=(10, 7))
        total = df["total_funding"].sum()
        colors = [INSTITUTE_LABELS.get(label, "#888888") for label in df["label"]]
        ax.barh(range(len(df)), df["total_funding"], color=colors)
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels(df["label"])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("Where Does $134.5B in NIH Biomarker Funding Go?", fontsize=14)
        for i, row in enumerate(df.itertuples()):
            pct = 100 * row.total_funding / total
            ax.text(
                row.total_funding,
                i,
                f"  ${row.total_funding / 1e9:.1f}B ({pct:.0f}%)",
                va="center",
                fontsize=9,
                fontweight="bold",
            )
        ax.text(
            0.99,
            -0.06,
            SOURCE_NOTE,
            transform=ax.transAxes,
            fontsize=8,
            ha="right",
            color="gray",
        )
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        fig, ax = plt.subplots(figsize=(12, 7))
        colors = [INSTITUTE_COLORS.get(col, "#888888") for col in pivot.columns]
        pivot_b = pivot / 1e9
        pivot_b.plot.area(ax=ax, alpha=0.8, color=colors)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title("Biomarker Funding by Institute Over Time", fontsize=14)
        ax.legend(title="", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
        for yr in [2005, 2006]:
            ax.axvspan(yr - 0.4, yr + 0.4, alpha=0.15, color="red")
        ax.text(
            0.99,
            -0.06,
            SOURCE_NOTE,
            transform=ax.transAxes,
            fontsize=8,
            ha="right",
            color="gray",
        )
        fig.tight_layout()
        return self._save(fig, filename)


class DatawrapperRenderer:
    """Primary renderer using Datawrapper API with colorblind-safe palette.

    Reuses existing chart IDs from .url files so URLs stay stable across runs.
    """

    def __init__(self, output_dir: Path, token: str):
        from datawrapper import Datawrapper

        self.dw = Datawrapper(access_token=token)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "datawrapper"
        self.chart_urls: dict[str, str] = {}

    def _get_existing_chart_id(self, filename: str) -> str | None:
        """Check if a .url file exists with a previous chart ID."""
        url_file = self.output_dir / f"{filename}.url"
        if url_file.exists():
            url = url_file.read_text().strip()
            # Extract chart ID from https://datawrapper.dwcdn.net/{id}/
            parts = url.rstrip("/").split("/")
            if len(parts) >= 4:
                return parts[-1]
        return None

    def _upsert_chart(
        self,
        chart_type: str,
        title: str,
        data: pd.DataFrame,
        filename: str,
        metadata: dict | None = None,
    ) -> str:
        """Create or update a Datawrapper chart. Reuses chart ID if .url exists."""
        chart_id = self._get_existing_chart_id(filename)

        if chart_id:
            # Update existing chart
            self.dw.update_chart(chart_id, title=title)
            self.dw.add_data(chart_id, data)
            print(f"  Updating existing chart {chart_id}")
        else:
            # Create new chart
            chart_info = self.dw.create_chart(title=title, chart_type=chart_type)
            chart_id = chart_info["id"]
            self.dw.add_data(chart_id, data)
            print(f"  Created new chart {chart_id}")

        base_meta = {
            "describe": {
                "source-name": "NIH ExPORTER (FY2004–2024), keyword-filtered",
                "source-url": "https://reporter.nih.gov/",
                "byline": "Surrogate Science Project",
            },
            "publish": {
                "blocks": {
                    "get-the-data": True,
                    "embed": True,
                }
            },
        }
        if metadata:
            for key in metadata:
                if key in base_meta and isinstance(base_meta[key], dict):
                    base_meta[key].update(metadata[key])
                else:
                    base_meta[key] = metadata[key]

        self.dw.update_metadata(chart_id, base_meta)
        self.dw.publish_chart(chart_id)

        url = f"https://datawrapper.dwcdn.net/{chart_id}/"
        self.chart_urls[filename] = url
        ref_path = self.output_dir / f"{filename}.url"
        ref_path.write_text(url)
        print(f"  Published: {url}")
        return url

    def spending_over_time(self, df: pd.DataFrame, filename: str):
        chart_df = df[["FY", "total_funding"]].copy()
        chart_df["total_funding"] = (chart_df["total_funding"] / 1e9).round(2)
        chart_df.columns = ["Fiscal Year", "Biomarker Spending ($B)"]

        return self._upsert_chart(
            "d3-lines",
            "NIH Biomarker-Related Spending (FY2004–2024)",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Biomarker-related NIH funding grew from $1.7B "
                        "to $13.6B over two decades"
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "y-grid": "on",
                    "line-symbols": True,
                    "fill-below": True,
                    "custom-colors": {
                        "Biomarker Spending ($B)": SPENDING_LINE_COLOR,
                    },
                    "line-widths": {
                        "Biomarker Spending ($B)": 3,
                    },
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )

    def institute_allocation(self, df: pd.DataFrame, filename: str):
        chart_df = df[["label", "total_funding"]].copy()
        chart_df["total_funding"] = (chart_df["total_funding"] / 1e9).round(1)
        chart_df.columns = ["Institute", "Funding ($B)"]

        return self._upsert_chart(
            "d3-bars",
            "Where Does $134.5B in NIH Biomarker Funding Go?",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "NCI accounts for 21% — cancer research drove "
                        "early biomarker adoption"
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "sort-bars": "desc",
                    "custom-colors": INSTITUTE_LABELS,
                },
            },
        )

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})

        return self._upsert_chart(
            "d3-area",
            "Biomarker Funding by Institute Over Time",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "NCI has led throughout, but NIA and NHLBI grew "
                        "substantially after 2010"
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "custom-colors": INSTITUTE_COLORS,
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )
