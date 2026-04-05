"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

Color palette — warm/cool split, enforced globally:
  COOL tones for core vs expanded (C1, C2)
  WARM tones for grant mechanisms (C4, C5, C6)
  CATEGORICAL for the 12 pilot institutes (C2, C3)
All color assignments live in this file. No raw hex codes elsewhere.
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

# =============================================================================
# COLOR PALETTE — single source of truth, warm/cool split
# Okabe-Ito base palette for colorblind safety
# =============================================================================

# COOL tones: core vs expanded split (C1, C2)
CORE_COLOR = "#0072B2"  # strong blue — definite biomarker terms
EXPANDED_COLOR = "#56B4E9"  # sky blue — broader matches

# WARM/COOL split: Clinical vs Research grant categories (C4, C5, C6)
# Based on NIH_SPENDING_CATS tags. Edit CLINICAL_TAGS in utils.py to change.
GRANT_CATEGORY_COLORS = {
    "Clinical": "#D55E00",  # vermillion (warm)
    "Research": "#0072B2",  # blue (cool)
}

# Legacy mechanism colors (kept for backward compat, not used in current charts)
MECHANISM_COLORS = {
    "Research (R)": "#D55E00",
    "Cooperative (U)": "#E69F00",
    "Program/Center (P)": "#CC79A7",
    "Career Dev (K)": "#DDAA33",
    "Training (T)": "#BC6C25",
    "Fellowship (F)": "#9B2226",
    "Other": "#BBBBBB",
}

# CATEGORICAL: 12 pilot institutes (C2, C3)
INSTITUTE_COLORS = {
    "NCI": "#0072B2",  # blue
    "NHLBI": "#D55E00",  # vermillion
    "NIA": "#009E73",  # bluish green
    "NIAID": "#E69F00",  # orange
    "NINDS": "#CC79A7",  # reddish purple
    "NIMH": "#56B4E9",  # sky blue
    "NIDDK": "#F0E442",  # yellow
    "NICHD": "#882255",  # wine
    "NIGMS": "#332288",  # indigo
    "NIDA": "#AA4499",  # purple
    "NIBIB": "#44AA99",  # teal
    "NIAMS": "#999933",  # olive
    "Other": "#BBBBBB",  # grey
}

# 12 pilot ICs and their labels
PILOT_ICS = ["CA", "HL", "AG", "AI", "NS", "MH", "DK", "HD", "GM", "DA", "EB", "AR"]
IC_CODE_TO_NAME = {
    "CA": "NCI",
    "HL": "NHLBI",
    "AG": "NIA",
    "AI": "NIAID",
    "NS": "NINDS",
    "MH": "NIMH",
    "DK": "NIDDK",
    "HD": "NICHD",
    "GM": "NIGMS",
    "DA": "NIDA",
    "EB": "NIBIB",
    "AR": "NIAMS",
}
IC_LABELS = {
    "CA": "NCI (Cancer)",
    "HL": "NHLBI (Heart/Lung/Blood)",
    "AG": "NIA (Aging)",
    "AI": "NIAID (Allergy/Infectious)",
    "NS": "NINDS (Neurological)",
    "MH": "NIMH (Mental Health)",
    "DK": "NIDDK (Diabetes/Digestive)",
    "HD": "NICHD (Child Health)",
    "GM": "NIGMS (General Medical)",
    "DA": "NIDA (Drug Abuse)",
    "EB": "NIBIB (Biomedical Imaging)",
    "AR": "NIAMS (Arthritis/Musculoskeletal)",
}

sns.set_theme(style="whitegrid", font_scale=1.1)

SOURCE_NOTE = "Source: NIH ExPORTER (FY2004\u20132024), expanded keyword set (36 terms) + abstract text search"
DATA_CAVEAT = (
    "FY2005\u201306: sparse PROJECT_TERMS; FY2013, FY2018: anomalous keyword counts"
)


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path):  # -> SeabornRenderer | DatawrapperRenderer
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

        # Core bars
        ax.barh(y_pos, df["core_funding"], color=CORE_COLOR, label="Core terms")
        # Expanded bars stacked
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

    def term_by_category(
        self,
        df: pd.DataFrame,
        filename: str,
        title: str = "Keyword Terms by Grant Category",
    ):
        """Grouped (dodged) horizontal bars: Clinical vs Research per keyword term.

        df must have columns: term, category, total_funding, grant_count
        """
        categories = sorted(df["category"].unique())
        terms = (
            df.groupby("term")["total_funding"]
            .sum()
            .sort_values(ascending=True)
            .index.tolist()
        )

        fig, ax = plt.subplots(figsize=(12, max(6, len(terms) * 0.6)))
        bar_height = 0.35
        y_base = range(len(terms))

        for i, cat in enumerate(categories):
            cat_data = df[df["category"] == cat].set_index("term")
            vals = [
                cat_data.loc[t, "total_funding"] if t in cat_data.index else 0
                for t in terms
            ]
            y_offset = [y + i * bar_height for y in y_base]
            color = GRANT_CATEGORY_COLORS.get(cat, "#888888")
            ax.barh(y_offset, vals, height=bar_height, label=cat, color=color)

        ax.set_yticks([y + bar_height * (len(categories) - 1) / 2 for y in y_base])
        ax.set_yticklabels(terms, fontsize=10)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_title(title, fontsize=14)
        ax.legend(loc="lower right", fontsize=10)
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

    def institute_over_time(
        self, top_lines: pd.DataFrame, other_band: pd.Series, filename: str
    ):
        """Line chart: top 5 institutes as lines, rest as shaded Other band."""
        fig, ax = plt.subplots(figsize=(14, 7))

        # Shaded Other band
        other_b = other_band / 1e9
        ax.fill_between(
            other_b.index,
            0,
            other_b,
            alpha=0.2,
            color="#BBBBBB",
            label="Other institutes",
        )

        # Lines for top institutes
        for col in top_lines.columns:
            color = INSTITUTE_COLORS.get(col, "#888888")
            ax.plot(
                top_lines.index,
                top_lines[col] / 1e9,
                linewidth=2.5,
                color=color,
                label=col,
                marker="o",
                markersize=3,
            )

        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title("Biomarker Funding by Institute Over Time", fontsize=14)
        ax.legend(loc="upper left", fontsize=9, ncol=2)
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

    def category_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: Clinical vs Research funding over time."""
        fig, ax = plt.subplots(figsize=(14, 7))
        colors = [GRANT_CATEGORY_COLORS.get(col, "#888888") for col in pivot.columns]
        pivot_b = pivot / 1e9
        pivot_b.plot.area(ax=ax, alpha=0.8, color=colors)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title("Biomarker Funding: Clinical vs Research Over Time", fontsize=14)
        ax.legend(title="", loc="upper left", fontsize=10)
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

    def term_by_category(self, df, filename, title="Keyword Terms by Grant Category"):
        """Datawrapper grouped bars for term × category."""
        pivot = df.pivot(
            index="term", columns="category", values="total_funding"
        ).fillna(0)
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"term": "Keyword Term"})
        return self._upsert_chart(
            "d3-bars-stacked",
            title,
            chart_df,
            filename,
            metadata={
                "visualize": {"custom-colors": GRANT_CATEGORY_COLORS},
            },
        )

    def institute_over_time(self, top_lines, other_band, filename):
        """Datawrapper line chart for institute over time."""
        chart_df = (top_lines / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})
        return self._upsert_chart(
            "d3-lines",
            "Biomarker Funding by Institute Over Time",
            chart_df,
            filename,
            metadata={
                "visualize": {"custom-colors": INSTITUTE_COLORS},
                "annotate": {"notes": DATA_CAVEAT},
            },
        )

    def category_over_time(self, pivot, filename):
        """Datawrapper stacked area for Clinical vs Research over time."""
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})
        return self._upsert_chart(
            "d3-area",
            "Biomarker Funding: Clinical vs Research Over Time",
            chart_df,
            filename,
            metadata={
                "visualize": {"custom-colors": GRANT_CATEGORY_COLORS},
                "annotate": {"notes": DATA_CAVEAT},
            },
        )
