"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

Charts focus on funding allocation and total biomarker spending:
1. spending_over_time — total biomarker spending per year
2. institute_allocation — top institutes by total funding
3. institute_over_time — stacked area of institute funding by year
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("colorblind")

SOURCE_NOTE = "Source: NIH ExPORTER (FY2004–2024), keyword-filtered"
DATA_CAVEAT = "FY2005–06 undercounted due to missing PROJECT_TERMS data"


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path) -> "ChartRenderer":
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
        """Line chart: total biomarker spending per year."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df["FY"], df["total_funding"], marker="o", linewidth=2.5,
                color=PALETTE[0], markersize=6)
        ax.fill_between(df["FY"], df["total_funding"], alpha=0.1, color=PALETTE[0])
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title("NIH Biomarker-Related Spending (FY2004–2024)", fontsize=14)
        # Annotate data quality years
        for yr in [2005, 2006]:
            ax.axvspan(yr - 0.4, yr + 0.4, alpha=0.15, color="red")
        ax.annotate(DATA_CAVEAT, xy=(0.02, 0.02), xycoords="axes fraction",
                    fontsize=8, color="red", fontstyle="italic")
        ax.text(0.99, -0.08, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_allocation(self, df: pd.DataFrame, filename: str):
        """Horizontal bar: top institutes by funding with $ and % share."""
        fig, ax = plt.subplots(figsize=(10, 7))
        total = df["total_funding"].sum()
        sns.barplot(data=df, y="label", x="total_funding", ax=ax, palette="viridis")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("NIH Biomarker Funding by Institute", fontsize=14)
        for i, row in enumerate(df.itertuples()):
            pct = 100 * row.total_funding / total
            ax.text(row.total_funding, i,
                    f"  ${row.total_funding/1e9:.1f}B ({pct:.0f}%)",
                    va="center", fontsize=9, fontweight="bold")
        ax.text(0.99, -0.06, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: funding by institute over time."""
        fig, ax = plt.subplots(figsize=(12, 7))
        colors = sns.color_palette("tab10", n_colors=len(pivot.columns))
        pivot_b = pivot / 1e9  # convert to billions for readability
        pivot_b.plot.area(ax=ax, alpha=0.75, color=colors)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title("Biomarker Funding by Institute Over Time", fontsize=14)
        ax.legend(title="", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
        for yr in [2005, 2006]:
            ax.axvspan(yr - 0.4, yr + 0.4, alpha=0.15, color="red")
        ax.text(0.99, -0.06, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)


class DatawrapperRenderer:
    """Primary renderer using Datawrapper API → published charts with formatting."""

    def __init__(self, output_dir: Path, token: str):
        from datawrapper import Datawrapper
        self.dw = Datawrapper(access_token=token)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "datawrapper"
        self.chart_urls: dict[str, str] = {}

    def _create_and_publish(self, chart_type: str, title: str, data: pd.DataFrame,
                            filename: str, metadata: dict | None = None) -> str:
        chart_info = self.dw.create_chart(title=title, chart_type=chart_type)
        chart_id = chart_info["id"]
        self.dw.add_data(chart_id, data)

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
            }
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
        """Line chart: total biomarker spending per year."""
        chart_df = df[["FY", "total_funding"]].copy()
        chart_df["total_funding"] = (chart_df["total_funding"] / 1e9).round(2)
        chart_df.columns = ["Fiscal Year", "Biomarker Spending ($B)"]

        return self._create_and_publish(
            "d3-lines",
            "NIH Biomarker-Related Spending (FY2004–2024)",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": "Biomarker-related NIH funding grew from $1.7B to $13.6B over two decades",
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "y-grid": "on",
                    "line-symbols": True,
                    "fill-below": True,
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )

    def institute_allocation(self, df: pd.DataFrame, filename: str):
        """Horizontal bar: top institutes by funding."""
        chart_df = df[["label", "total_funding"]].copy()
        chart_df["total_funding"] = (chart_df["total_funding"] / 1e9).round(1)
        chart_df.columns = ["Institute", "Funding ($B)"]

        return self._create_and_publish(
            "d3-bars",
            "Where Does $134.5B in NIH Biomarker Funding Go?",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": "NCI accounts for 21% — cancer research drove early biomarker adoption",
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "sort-bars": "desc",
                },
            },
        )

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: institute funding by year."""
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})

        return self._create_and_publish(
            "d3-area",
            "Biomarker Funding by Institute Over Time",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": "NCI has led throughout, but NIA and NHLBI grew substantially after 2010",
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )
