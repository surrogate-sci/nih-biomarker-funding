"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

5 charts focused on the policy question: what kind of biomarker work does NIH
fund, and is surrogacy/endpoint validation an afterthought?

Uses Paul Tol's colorblind-safe qualitative palette throughout.
Datawrapper charts are updated in place if chart IDs exist in .url files.
"""

import os
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from utils import PURPOSE_COLORS, PURPOSE_ORDER

# Paul Tol's qualitative palette — colorblind-safe, publication-ready
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

# Colors for core vs expanded split
CORE_COLOR = "#225588"  # dark blue — high confidence
EXPANDED_COLOR = "#88CCEE"  # light cyan — broader matches

# Mechanism colors
MECHANISM_COLORS = {
    "Research (R)": TOL_QUALITATIVE[0],
    "Program/Center (P)": TOL_QUALITATIVE[2],
    "Cooperative (U)": TOL_QUALITATIVE[3],
    "Career Dev (K)": TOL_QUALITATIVE[5],
    "Training (T)": TOL_QUALITATIVE[6],
    "Fellowship (F)": TOL_QUALITATIVE[4],
    "Other": TOL_QUALITATIVE[9],
}

sns.set_theme(style="whitegrid", font_scale=1.1)

SOURCE_NOTE = "Source: NIH ExPORTER (FY2004\u20132024), expanded keyword set (36 terms) + abstract text search"
DATA_CAVEAT = (
    "FY2005\u201306: sparse PROJECT_TERMS; FY2013, FY2018: anomalous keyword counts"
)


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path):
    """Return Datawrapper renderer if token is set, else seaborn fallback."""
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if token:
        return DatawrapperRenderer(output_dir, token)
    print(
        "  [charts] No DATAWRAPPER_API_TOKEN \u2014 using seaborn/matplotlib fallback"
    )
    return SeabornRenderer(output_dir)


class SeabornRenderer:
    """Fallback renderer using seaborn/matplotlib \u2192 PNG files."""

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
        """Stacked area: core biomarker funding vs expanded-only funding."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.stackplot(
            df["FY"],
            df["core_funding"],
            df["expanded_funding"],
            labels=[
                "Core terms (13 definite biomarker terms)",
                "Expanded terms only (broader matches)",
            ],
            colors=[CORE_COLOR, EXPANDED_COLOR],
            alpha=0.85,
        )
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title(
            "NIH Biomarker-Related Spending (FY2004\u20132024)\n"
            "Core terms vs. expanded keyword matches",
            fontsize=14,
        )
        ax.legend(loc="upper left", fontsize=9)
        ax.annotate(
            DATA_CAVEAT,
            xy=(0.02, 0.02),
            xycoords="axes fraction",
            fontsize=8,
            color="gray",
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
        """Stacked horizontal bars: core vs expanded funding per institute."""
        fig, ax = plt.subplots(figsize=(10, 7))
        y_pos = range(len(df))

        ax.barh(y_pos, df["core_funding"], color=CORE_COLOR, label="Core terms")
        ax.barh(
            y_pos,
            df["expanded_funding"],
            left=df["core_funding"],
            color=EXPANDED_COLOR,
            label="Expanded only",
        )

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(df["label"])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title(
            "NIH Biomarker Funding by Institute\nCore terms vs. expanded matches",
            fontsize=14,
        )
        ax.legend(loc="lower right", fontsize=9)

        total = df["total_funding"].sum()
        for i, row in enumerate(df.itertuples()):
            pct = 100 * row.total_funding / total
            core_pct = row.core_pct
            ax.text(
                row.total_funding,
                i,
                f"  ${row.total_funding / 1e9:.1f}B ({pct:.0f}%) \u2014 {core_pct:.0f}% core",
                va="center",
                fontsize=8,
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

    def purpose_distribution(self, df: pd.DataFrame, filename: str):
        """Horizontal bar chart: funding by biomarker purpose category."""
        fig, ax = plt.subplots(figsize=(12, 7))
        y_pos = range(len(df))
        colors = [PURPOSE_COLORS.get(p, "#888888") for p in df["PURPOSE"]]

        ax.barh(y_pos, df["total_funding"], color=colors)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(df["PURPOSE"], fontsize=11)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_ylabel("")
        classified_total = df["total_funding"].sum()
        classified_n = df["grant_count"].sum()
        ax.set_title(
            f"How NIH Biomarker Funding Distributes by Research Purpose\n"
            f"{classified_n:,} grants, ${classified_total / 1e9:.0f}B total "
            f"(each grant assigned to one category by its most specific keyword match)",
            fontsize=13,
        )

        total = df["total_funding"].sum()
        for i, row in enumerate(df.itertuples()):
            pct = row.pct
            ax.text(
                row.total_funding,
                i,
                f"  ${row.total_funding / 1e9:.1f}B ({pct:.0f}%) \u2014 {row.grant_count:,} grants",
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

    def purpose_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: funding by purpose category over time."""
        fig, ax = plt.subplots(figsize=(12, 7))
        colors = [PURPOSE_COLORS.get(col, "#888888") for col in pivot.columns]
        pivot_b = pivot / 1e9
        pivot_b.plot.area(ax=ax, alpha=0.8, color=colors)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title(
            "Biomarker Funding by Research Purpose Over Time\n"
            "Surrogacy & endpoint validation remains a sliver across two decades",
            fontsize=14,
        )
        ax.legend(title="", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
        ax.annotate(
            DATA_CAVEAT,
            xy=(0.02, 0.02),
            xycoords="axes fraction",
            fontsize=8,
            color="gray",
            fontstyle="italic",
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

    def purpose_by_mechanism(
        self,
        pivot_funding: pd.DataFrame,
        pivot_count: pd.DataFrame,
        filename: str,
    ):
        """Grouped horizontal bars: purpose × mechanism funding."""
        # Normalize each purpose row to show mechanism share
        row_totals = pivot_funding.sum(axis=1)
        pivot_pct = pivot_funding.div(row_totals, axis=0) * 100

        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(18, 8), gridspec_kw={"width_ratios": [1.2, 1]}
        )

        # Left: absolute funding stacked bars by purpose
        mechanisms = pivot_funding.columns.tolist()
        y_pos = range(len(pivot_funding))

        left = pd.Series(0.0, index=pivot_funding.index)
        for mech in mechanisms:
            color = MECHANISM_COLORS.get(mech, "#888888")
            ax1.barh(
                y_pos,
                pivot_funding[mech],
                left=left,
                color=color,
                label=mech,
            )
            left = left + pivot_funding[mech]

        ax1.set_yticks(list(y_pos))
        ax1.set_yticklabels(pivot_funding.index, fontsize=10)
        ax1.invert_yaxis()
        ax1.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax1.set_title("Funding by purpose and mechanism", fontsize=12)
        ax1.legend(loc="lower right", fontsize=8)

        # Annotate totals
        for i, (purpose, total) in enumerate(row_totals.items()):
            ax1.text(
                total,
                i,
                f"  ${total / 1e9:.1f}B",
                va="center",
                fontsize=9,
                fontweight="bold",
            )

        # Right: % breakdown (mechanism share within each purpose)
        left_pct = pd.Series(0.0, index=pivot_pct.index)
        for mech in mechanisms:
            color = MECHANISM_COLORS.get(mech, "#888888")
            ax2.barh(
                y_pos,
                pivot_pct[mech],
                left=left_pct,
                color=color,
                label=mech,
            )
            left_pct = left_pct + pivot_pct[mech]

        ax2.set_yticks(list(y_pos))
        ax2.set_yticklabels([""] * len(y_pos))
        ax2.invert_yaxis()
        ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax2.set_xlim(0, 100)
        ax2.set_title("Mechanism share within each purpose (%)", fontsize=12)

        # Annotate R-grant % for each row
        r_col = "Research (R)" if "Research (R)" in pivot_pct.columns else None
        if r_col:
            for i, purpose in enumerate(pivot_pct.index):
                r_pct = pivot_pct.loc[purpose, r_col]
                ax2.text(
                    r_pct / 2,
                    i,
                    f"R: {r_pct:.0f}%",
                    va="center",
                    ha="center",
                    fontsize=8,
                    color="white",
                    fontweight="bold",
                )

        fig.suptitle(
            "Where Does Each Type of Biomarker Research Happen?",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
        fig.text(0.99, -0.02, SOURCE_NOTE, ha="right", fontsize=8, color="gray")
        fig.tight_layout()
        return self._save(fig, filename)


class DatawrapperRenderer:
    """Primary renderer using Datawrapper API with colorblind-safe palette."""

    def __init__(self, output_dir: Path, token: str):
        from datawrapper import Datawrapper

        self.dw = Datawrapper(access_token=token)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "datawrapper"
        self.chart_urls: dict = {}

    def _get_existing_chart_id(self, filename: str) -> Optional[str]:
        """Check if a .url file exists with a previous chart ID."""
        url_file = self.output_dir / f"{filename}.url"
        if url_file.exists():
            url = url_file.read_text().strip()
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
        metadata: Optional[dict] = None,
    ) -> str:
        """Create or update a Datawrapper chart. Reuses chart ID if .url exists."""
        chart_id = self._get_existing_chart_id(filename)

        if chart_id:
            self.dw.update_chart(chart_id, title=title)
            self.dw.add_data(chart_id, data)
            print(f"  Updating existing chart {chart_id}")
        else:
            chart_info = self.dw.create_chart(title=title, chart_type=chart_type)
            chart_id = chart_info["id"]
            self.dw.add_data(chart_id, data)
            print(f"  Created new chart {chart_id}")

        base_meta = {
            "describe": {
                "source-name": "NIH ExPORTER (FY2004\u20132024), expanded keyword set (36 terms) + abstract search",
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
        chart_df = df[["FY", "core_funding", "expanded_funding"]].copy()
        chart_df["core_funding"] = (chart_df["core_funding"] / 1e9).round(2)
        chart_df["expanded_funding"] = (chart_df["expanded_funding"] / 1e9).round(2)
        chart_df.columns = ["Fiscal Year", "Core Terms ($B)", "Expanded Only ($B)"]

        return self._upsert_chart(
            "d3-area",
            "NIH Biomarker-Related Spending (FY2004\u20132024)",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Core terms = 13 definite biomarker terms; "
                        "Expanded = 23 additional broader terms"
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "custom-colors": {
                        "Core Terms ($B)": CORE_COLOR,
                        "Expanded Only ($B)": EXPANDED_COLOR,
                    },
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )

    def institute_allocation(self, df: pd.DataFrame, filename: str):
        chart_df = df[["label", "core_funding", "expanded_funding"]].copy()
        chart_df["core_funding"] = (chart_df["core_funding"] / 1e9).round(1)
        chart_df["expanded_funding"] = (chart_df["expanded_funding"] / 1e9).round(1)
        chart_df.columns = ["Institute", "Core Terms ($B)", "Expanded Only ($B)"]

        return self._upsert_chart(
            "d3-bars-stacked",
            "NIH Biomarker Funding by Institute",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Stacked: core biomarker terms vs. broader expanded matches. "
                        "Core % varies widely across institutes."
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "sort-bars": "desc",
                    "custom-colors": {
                        "Core Terms ($B)": CORE_COLOR,
                        "Expanded Only ($B)": EXPANDED_COLOR,
                    },
                },
            },
        )

    def purpose_distribution(self, df: pd.DataFrame, filename: str):
        chart_df = df[["PURPOSE", "total_funding", "grant_count", "pct"]].copy()
        chart_df["total_funding"] = (chart_df["total_funding"] / 1e9).round(2)
        chart_df.columns = [
            "Research Purpose",
            "Funding ($B)",
            "Grant Count",
            "% of Total",
        ]

        return self._upsert_chart(
            "d3-bars",
            "How NIH Biomarker Funding Distributes by Research Purpose",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Each grant assigned to one purpose category based on its "
                        "most specific keyword match. Surrogacy & endpoint validation "
                        "receives a tiny fraction of total biomarker funding."
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "sort-bars": False,
                    "custom-colors": {
                        "Funding ($B)": PURPOSE_COLORS.get(
                            "Surrogacy & endpoint validation", "#CC6677"
                        )
                    },
                },
            },
        )

    def purpose_over_time(self, pivot: pd.DataFrame, filename: str):
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})

        return self._upsert_chart(
            "d3-area",
            "Biomarker Funding by Research Purpose Over Time",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Surrogacy & endpoint validation remains a thin sliver "
                        "across two decades of growth in biomarker research funding."
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "custom-colors": PURPOSE_COLORS,
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )

    def purpose_by_mechanism(
        self,
        pivot_funding: pd.DataFrame,
        pivot_count: pd.DataFrame,
        filename: str,
    ):
        chart_df = (pivot_funding / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"PURPOSE": "Research Purpose"})

        return self._upsert_chart(
            "d3-bars-stacked",
            "Where Does Each Type of Biomarker Research Happen?",
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Funding by grant mechanism within each purpose category. "
                        "Shows whether validation work appears in R01s or only in "
                        "cooperative agreements and center grants."
                    ),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "sort-bars": False,
                    "custom-colors": MECHANISM_COLORS,
                },
            },
        )
