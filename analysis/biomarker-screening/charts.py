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

# WARM tones: grant mechanism categories (C4, C5, C6)
MECHANISM_COLORS = {
    "Research (R)": "#D55E00",  # vermillion
    "Cooperative (U)": "#E69F00",  # amber
    "Program/Center (P)": "#CC79A7",  # mauve
    "Career Dev (K)": "#DDAA33",  # gold
    "Training (T)": "#BC6C25",  # sienna
    "Fellowship (F)": "#9B2226",  # dark red
    "Other": "#BBBBBB",  # grey
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

    def term_by_mechanism(
        self,
        pivot_funding: pd.DataFrame,
        pivot_count: pd.DataFrame,
        filename: str,
        title: str = "Which Grant Mechanisms Fund Which Biomarker Keywords?",
    ):
        """Stacked horizontal bars: keyword term × grant mechanism funding."""
        row_totals = pivot_funding.sum(axis=1)
        pivot_pct = pivot_funding.div(row_totals, axis=0) * 100

        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(18, 9), gridspec_kw={"width_ratios": [1.2, 1]}
        )

        mechanisms = pivot_funding.columns.tolist()
        y_pos = range(len(pivot_funding))

        # Left: absolute funding stacked bars
        left = pd.Series(0.0, index=pivot_funding.index)
        for mech in mechanisms:
            color = MECHANISM_COLORS.get(mech, "#888888")
            ax1.barh(y_pos, pivot_funding[mech], left=left, color=color, label=mech)
            left = left + pivot_funding[mech]

        ax1.set_yticks(list(y_pos))
        ax1.set_yticklabels(pivot_funding.index, fontsize=10)
        ax1.invert_yaxis()
        ax1.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax1.set_title("Funding by keyword term and grant mechanism", fontsize=12)
        ax1.legend(loc="lower right", fontsize=8)

        for i, (term, total) in enumerate(row_totals.items()):
            count = int(pivot_count.loc[term].sum())
            ax1.text(
                total,
                i,
                f"  ${total / 1e9:.1f}B ({count:,})",
                va="center",
                fontsize=9,
                fontweight="bold",
            )

        # Right: mechanism % within each term
        left_pct = pd.Series(0.0, index=pivot_pct.index)
        for mech in mechanisms:
            color = MECHANISM_COLORS.get(mech, "#888888")
            ax2.barh(y_pos, pivot_pct[mech], left=left_pct, color=color)
            left_pct = left_pct + pivot_pct[mech]

        ax2.set_yticks(list(y_pos))
        ax2.set_yticklabels([""] * len(y_pos))
        ax2.invert_yaxis()
        ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax2.set_xlim(0, 100)
        ax2.set_title("Mechanism share within each term (%)", fontsize=12)

        r_col = "Research (R)" if "Research (R)" in pivot_pct.columns else None
        if r_col:
            for i, term in enumerate(pivot_pct.index):
                r_pct = pivot_pct.loc[term, r_col]
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
            title,
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
        fig.text(0.99, -0.02, SOURCE_NOTE, ha="right", fontsize=8, color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: funding by institute over time."""
        fig, ax = plt.subplots(figsize=(14, 7))
        colors = [INSTITUTE_COLORS.get(col, "#888888") for col in pivot.columns]
        pivot_b = pivot / 1e9
        pivot_b.plot.area(ax=ax, alpha=0.8, color=colors)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title(
            "Biomarker Funding by Institute Over Time (12 pilot institutes)",
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

    def mechanism_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: funding by grant mechanism over time."""
        fig, ax = plt.subplots(figsize=(14, 7))
        colors = [MECHANISM_COLORS.get(col, "#888888") for col in pivot.columns]
        pivot_b = pivot / 1e9
        pivot_b.plot.area(ax=ax, alpha=0.8, color=colors)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title(
            "Biomarker Funding by Grant Mechanism Over Time",
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

    def term_by_mechanism(
        self,
        pivot_funding: pd.DataFrame,
        pivot_count: pd.DataFrame,
        filename: str,
        title: str = "Which Grant Mechanisms Fund Which Biomarker Keywords?",
    ):
        chart_df = (pivot_funding / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"term": "Keyword Term"})

        return self._upsert_chart(
            "d3-bars-stacked",
            title,
            chart_df,
            filename,
            metadata={
                "describe": {
                    "intro": (
                        "Funding by grant mechanism for each keyword term. "
                        "Grants matching multiple terms appear in each term's row."
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

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})
        return self._upsert_chart(
            "d3-area",
            "Biomarker Funding by Institute Over Time",
            chart_df,
            filename,
            metadata={
                "visualize": {"custom-colors": INSTITUTE_COLORS},
                "annotate": {"notes": DATA_CAVEAT},
            },
        )

    def mechanism_over_time(self, pivot: pd.DataFrame, filename: str):
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})
        return self._upsert_chart(
            "d3-area",
            "Biomarker Funding by Grant Mechanism Over Time",
            chart_df,
            filename,
            metadata={
                "visualize": {"custom-colors": MECHANISM_COLORS},
                "annotate": {"notes": DATA_CAVEAT},
            },
        )
