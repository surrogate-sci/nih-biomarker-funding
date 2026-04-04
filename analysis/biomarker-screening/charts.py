"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

Charts focus on funding allocation and total biomarker spending.
Uses Paul Tol's colorblind-safe qualitative palette throughout.
Datawrapper charts are updated in place if chart IDs exist in .url files.
"""

import json
import os
from pathlib import Path
from typing import Optional

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

# Colors for core vs expanded split
CORE_COLOR = "#225588"       # dark blue — high confidence
EXPANDED_COLOR = "#88CCEE"   # light cyan — broader matches

# Colors for match source
KEYWORD_COLOR = "#332288"    # indigo — keyword matched
ABSTRACT_COLOR = "#DDCC77"   # sand — abstract-only

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

SOURCE_NOTE = (
    "Source: NIH ExPORTER (FY2004\u20132024), expanded keyword set (36 terms) + abstract text search"
)
DATA_CAVEAT = (
    "FY2005\u201306: sparse PROJECT_TERMS; FY2013, FY2018: anomalous keyword counts"
)


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path) -> "ChartRenderer":
    """Return Datawrapper renderer if token is set, else seaborn fallback."""
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if token:
        return DatawrapperRenderer(output_dir, token)
    print("  [charts] No DATAWRAPPER_API_TOKEN \u2014 using seaborn/matplotlib fallback")
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
            labels=["Core terms (13 definite biomarker terms)", "Expanded terms only (broader matches)"],
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
        ax.annotate(DATA_CAVEAT, xy=(0.02, 0.02), xycoords="axes fraction",
                    fontsize=8, color="gray", fontstyle="italic")
        ax.text(0.99, -0.08, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_allocation(self, df: pd.DataFrame, filename: str):
        """Stacked horizontal bars: core vs expanded funding per institute."""
        fig, ax = plt.subplots(figsize=(10, 7))
        y_pos = range(len(df))

        # Core bars
        ax.barh(y_pos, df["core_funding"], color=CORE_COLOR, label="Core terms")
        # Expanded bars stacked
        ax.barh(y_pos, df["expanded_funding"], left=df["core_funding"],
                color=EXPANDED_COLOR, label="Expanded only")

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(df["label"])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("NIH Biomarker Funding by Institute\nCore terms vs. expanded matches", fontsize=14)
        ax.legend(loc="lower right", fontsize=9)

        total = df["total_funding"].sum()
        for i, row in enumerate(df.itertuples()):
            pct = 100 * row.total_funding / total
            core_pct = row.core_pct
            ax.text(row.total_funding, i,
                    f"  ${row.total_funding/1e9:.1f}B ({pct:.0f}%) \u2014 {core_pct:.0f}% core",
                    va="center", fontsize=8, fontweight="bold")

        ax.text(0.99, -0.06, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: funding by institute over time (all matched grants)."""
        fig, ax = plt.subplots(figsize=(12, 7))
        colors = [INSTITUTE_COLORS.get(col, "#888888") for col in pivot.columns]
        pivot_b = pivot / 1e9
        pivot_b.plot.area(ax=ax, alpha=0.8, color=colors)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title(
            "Biomarker Funding by Institute Over Time\n"
            "All matched grants (core + expanded + abstract)",
            fontsize=14,
        )
        ax.legend(title="", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
        ax.annotate(DATA_CAVEAT, xy=(0.02, 0.02), xycoords="axes fraction",
                    fontsize=8, color="gray", fontstyle="italic")
        ax.text(0.99, -0.06, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def explicit_adoption(self, df: pd.DataFrame, filename: str):
        """Line chart: % of matched grants using core biomarker terms per year."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df["FY"], df["explicit_pct"], marker="o", linewidth=2.5,
                color=CORE_COLOR, markersize=6)
        ax.fill_between(df["FY"], df["explicit_pct"], alpha=0.1, color=CORE_COLOR)
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("% of matched grants")
        ax.set_title(
            "Explicit Biomarker Term Adoption\n"
            "% of matched grants using 13 core biomarker terms",
            fontsize=14,
        )
        ax.set_ylim(0, max(df["explicit_pct"]) * 1.15)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax.annotate(DATA_CAVEAT, xy=(0.02, 0.02), xycoords="axes fraction",
                    fontsize=8, color="gray", fontstyle="italic")
        ax.text(0.99, -0.08, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def match_source_breakdown(self, pivot: pd.DataFrame, filename: str):
        """Stacked area: keyword-matched vs abstract-only funding per year."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.stackplot(
            pivot.index,
            pivot["keywords_only"],
            pivot["abstract_only"],
            labels=["Keyword matched (title + terms)", "Abstract-only"],
            colors=[KEYWORD_COLOR, ABSTRACT_COLOR],
            alpha=0.85,
        )
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("")
        ax.set_title(
            "How Grants Are Discovered: Keyword vs. Abstract Search\n"
            "Contribution of abstract text search to total matched grants",
            fontsize=14,
        )
        ax.legend(loc="upper left", fontsize=9)
        ax.annotate(DATA_CAVEAT, xy=(0.02, 0.02), xycoords="axes fraction",
                    fontsize=8, color="gray", fontstyle="italic")
        ax.text(0.99, -0.08, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def mechanism_breakdown(self, summary_df: pd.DataFrame, pivot: pd.DataFrame, filename: str):
        """Bar chart: funding by grant mechanism, with core/expanded split."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7),
                                        gridspec_kw={"width_ratios": [1, 1.5]})

        # Left: bar chart of total by mechanism
        y_pos = range(len(summary_df))
        ax1.barh(y_pos, summary_df["core_funding"], color=CORE_COLOR, label="Core terms")
        ax1.barh(y_pos, summary_df["expanded_funding"], left=summary_df["core_funding"],
                 color=EXPANDED_COLOR, label="Expanded only")
        ax1.set_yticks(list(y_pos))
        ax1.set_yticklabels(summary_df["mechanism"])
        ax1.invert_yaxis()
        ax1.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax1.set_title("By Mechanism (Total)", fontsize=12)
        ax1.legend(loc="lower right", fontsize=8)

        # Right: stacked area over time
        colors = [MECHANISM_COLORS.get(col, "#888888") for col in pivot.columns]
        (pivot / 1e9).plot.area(ax=ax2, alpha=0.8, color=colors)
        ax2.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
        ax2.set_xlabel("Fiscal Year")
        ax2.set_title("By Mechanism Over Time", fontsize=12)
        ax2.legend(title="", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)

        fig.suptitle("Biomarker Funding by Grant Mechanism", fontsize=14, y=1.02)
        fig.text(0.99, -0.02, SOURCE_NOTE, ha="right", fontsize=8, color="gray")
        fig.tight_layout()
        return self._save(fig, filename)

    def keyword_funding(self, df: pd.DataFrame, filename: str):
        """Horizontal bar chart: funding by primary keyword term."""
        fig, ax = plt.subplots(figsize=(10, 8))
        y_pos = range(len(df))
        colors = [CORE_COLOR if i < 5 else EXPANDED_COLOR for i in y_pos]
        ax.barh(y_pos, df["total_funding"], color=colors)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(df["PRIMARY_TERM"])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title(
            "Funding by Primary Keyword Term\n"
            "Each grant assigned its most specific matching term",
            fontsize=14,
        )
        total = df["total_funding"].sum()
        for i, row in enumerate(df.itertuples()):
            pct = 100 * row.total_funding / total
            ax.text(row.total_funding, i,
                    f"  ${row.total_funding/1e9:.1f}B ({row.grant_count:,} grants)",
                    va="center", fontsize=8)
        ax.text(0.99, -0.04, SOURCE_NOTE, transform=ax.transAxes,
                fontsize=8, ha="right", color="gray")
        fig.tight_layout()
        return self._save(fig, filename)


    @staticmethod
    def _top_terms_90pct(df: pd.DataFrame) -> pd.DataFrame:
        """Return terms accounting for ~90% of total funding, plus an 'Other' row."""
        total = df["total_funding"].sum()
        if total == 0:
            return df
        cumsum = df["total_funding"].cumsum()
        threshold = total * 0.90
        # Include all terms up to and including the one that crosses 90%
        n_keep = (cumsum <= threshold).sum() + 1
        n_keep = min(n_keep, len(df))
        top = df.head(n_keep).copy()
        rest = df.iloc[n_keep:]
        if len(rest) > 0:
            other_row = pd.DataFrame([{
                "PRIMARY_TERM": f"Other ({len(rest)} terms)",
                "total_funding": rest["total_funding"].sum(),
                "grant_count": rest["grant_count"].sum(),
            }])
            top = pd.concat([top, other_row], ignore_index=True)
        return top

    def core_vs_expanded_terms(self, core_df: pd.DataFrame, expanded_df: pd.DataFrame, filename: str):
        """Two-panel: keyword breakdown for core grants (left) vs expanded-only (right)."""
        core_total = core_df["total_funding"].sum()
        exp_total = expanded_df["total_funding"].sum()
        grand_total = core_total + exp_total
        core_pct = 100 * core_total / grand_total
        exp_pct = 100 * exp_total / grand_total

        # Keep only terms accounting for ~90% of each panel
        core_top = self._top_terms_90pct(core_df)
        exp_top = self._top_terms_90pct(expanded_df)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 9),
                                        gridspec_kw={"width_ratios": [1, 1.3]})

        # Left panel: core grants by core keyword
        y1 = range(len(core_top))
        colors1 = [CORE_COLOR if "Other" not in str(t) else TOL_QUALITATIVE[9]
                    for t in core_top["PRIMARY_TERM"]]
        ax1.barh(y1, core_top["total_funding"], color=colors1)
        ax1.set_yticks(list(y1))
        ax1.set_yticklabels(core_top["PRIMARY_TERM"], fontsize=9)
        ax1.invert_yaxis()
        ax1.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax1.set_title(
            f"Grants matching core terms\n"
            f"${core_total/1e9:.0f}B \u2014 {core_pct:.0f}% of total \u2014 "
            f"{core_df['grant_count'].sum():,} grants",
            fontsize=11, fontweight="bold",
        )
        for i, row in enumerate(core_top.itertuples()):
            ax1.text(row.total_funding, i,
                     f"  ${row.total_funding/1e9:.1f}B ({int(row.grant_count):,})",
                     va="center", fontsize=8)

        # Right panel: expanded-only grants
        y2 = range(len(exp_top))
        colors2 = [EXPANDED_COLOR if "Other" not in str(t) else TOL_QUALITATIVE[9]
                    for t in exp_top["PRIMARY_TERM"]]
        ax2.barh(y2, exp_top["total_funding"], color=colors2)
        ax2.set_yticks(list(y2))
        ax2.set_yticklabels(exp_top["PRIMARY_TERM"], fontsize=9)
        ax2.invert_yaxis()
        ax2.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax2.set_title(
            f"Additional grants from expanded terms only\n"
            f"${exp_total/1e9:.0f}B \u2014 {exp_pct:.0f}% of total \u2014 "
            f"{expanded_df['grant_count'].sum():,} additional grants",
            fontsize=11, fontweight="bold",
        )
        for i, row in enumerate(exp_top.itertuples()):
            ax2.text(row.total_funding, i,
                     f"  ${row.total_funding/1e9:.1f}B ({int(row.grant_count):,})",
                     va="center", fontsize=8)

        fig.suptitle("What Do Core vs. Expanded Keywords Capture?",
                     fontsize=14, fontweight="bold", y=1.02)
        fig.text(0.5, -0.01,
                 "No double counting: each grant appears in exactly one panel. "
                 "Left = matched any of 13 core biomarker terms. "
                 "Right = matched only by 23 additional expanded terms (not in left panel).\n"
                 "Showing terms accounting for ~90% of each panel's funding.",
                 ha="center", fontsize=8, color="gray", fontstyle="italic")
        fig.text(0.99, -0.04, SOURCE_NOTE, ha="right", fontsize=8, color="gray")
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

    def _upsert_chart(self, chart_type: str, title: str, data: pd.DataFrame,
                      filename: str, metadata: Optional[dict] = None) -> str:
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
        chart_df = df[["FY", "core_funding", "expanded_funding"]].copy()
        chart_df["core_funding"] = (chart_df["core_funding"] / 1e9).round(2)
        chart_df["expanded_funding"] = (chart_df["expanded_funding"] / 1e9).round(2)
        chart_df.columns = ["Fiscal Year", "Core Terms ($B)", "Expanded Only ($B)"]

        return self._upsert_chart(
            "d3-area",
            "NIH Biomarker-Related Spending (FY2004\u20132024)",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("Core terms = 13 definite biomarker terms; "
                              "Expanded = 23 additional broader terms"),
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
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("Stacked: core biomarker terms vs. broader expanded matches. "
                              "Core % varies widely across institutes."),
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

    def institute_over_time(self, pivot: pd.DataFrame, filename: str):
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={"FY": "Fiscal Year"})

        return self._upsert_chart(
            "d3-area",
            "Biomarker Funding by Institute Over Time",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("All matched grants (core + expanded + abstract). "
                              "NCI leads throughout; NIA grew substantially after 2010."),
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

    def explicit_adoption(self, df: pd.DataFrame, filename: str):
        chart_df = df[["FY", "explicit_pct"]].copy()
        chart_df.columns = ["Fiscal Year", "Core Term Adoption (%)"]

        return self._upsert_chart(
            "d3-lines",
            "Explicit Biomarker Term Adoption Over Time",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("% of matched grants using 13 core biomarker terms "
                              "(biomarker, surrogate endpoint, companion diagnostic, etc.)"),
                    "number-append": "%",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "y-grid": "on",
                    "line-symbols": True,
                    "custom-colors": {
                        "Core Term Adoption (%)": CORE_COLOR,
                    },
                    "line-widths": {
                        "Core Term Adoption (%)": 3,
                    },
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )

    def match_source_breakdown(self, pivot: pd.DataFrame, filename: str):
        chart_df = (pivot / 1e9).round(2).reset_index()
        chart_df = chart_df.rename(columns={
            "FY": "Fiscal Year",
            "keywords_only": "Keyword Matched ($B)",
            "abstract_only": "Abstract Only ($B)",
        })

        return self._upsert_chart(
            "d3-area",
            "How Grants Are Discovered: Keyword vs. Abstract Search",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("Keyword = matched in PROJECT_TITLE or PROJECT_TERMS; "
                              "Abstract = matched only in ABSTRACT_TEXT"),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "custom-colors": {
                        "Keyword Matched ($B)": KEYWORD_COLOR,
                        "Abstract Only ($B)": ABSTRACT_COLOR,
                    },
                },
                "annotate": {
                    "notes": DATA_CAVEAT,
                },
            },
        )

    def mechanism_breakdown(self, summary_df: pd.DataFrame, pivot: pd.DataFrame, filename: str):
        chart_df = summary_df[["mechanism", "core_funding", "expanded_funding"]].copy()
        chart_df["core_funding"] = (chart_df["core_funding"] / 1e9).round(1)
        chart_df["expanded_funding"] = (chart_df["expanded_funding"] / 1e9).round(1)
        chart_df.columns = ["Mechanism", "Core Terms ($B)", "Expanded Only ($B)"]

        return self._upsert_chart(
            "d3-bars-stacked",
            "Biomarker Funding by Grant Mechanism",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("R = research grants (R01, R21, etc.); P = program/center grants; "
                              "U = cooperative agreements"),
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

    def keyword_funding(self, df: pd.DataFrame, filename: str):
        chart_df = df[["PRIMARY_TERM", "total_funding", "grant_count"]].copy()
        chart_df["total_funding"] = (chart_df["total_funding"] / 1e9).round(2)
        chart_df.columns = ["Keyword", "Funding ($B)", "Grant Count"]

        return self._upsert_chart(
            "d3-bars",
            "Funding by Primary Keyword Term",
            chart_df, filename,
            metadata={
                "describe": {
                    "intro": ("Each grant assigned its most specific matching term "
                              "via priority ordering (most specific wins)"),
                    "number-prepend": "$",
                    "number-append": "B",
                    "number-format": "0,[.0]",
                },
                "visualize": {
                    "sort-bars": "desc",
                },
            },
        )

    def core_vs_expanded_terms(self, core_df: pd.DataFrame, expanded_df: pd.DataFrame, filename: str):
        """Two separate Datawrapper charts for core vs expanded terms."""
        # Core terms chart
        core_chart = core_df[["PRIMARY_TERM", "total_funding", "grant_count"]].copy()
        core_chart["total_funding"] = (core_chart["total_funding"] / 1e9).round(2)
        core_chart.columns = ["Term", "Funding ($B)", "Grant Count"]

        self._upsert_chart(
            "d3-bars",
            "Core Biomarker Terms (13) \u2014 Definite Biomarker Research",
            core_chart, "core_terms.png",
            metadata={
                "describe": {
                    "intro": f"Total: ${core_df['total_funding'].sum()/1e9:.1f}B across {core_df['grant_count'].sum():,} grants",
                    "number-prepend": "$",
                    "number-append": "B",
                },
                "visualize": {
                    "sort-bars": "desc",
                    "custom-colors": {"Funding ($B)": CORE_COLOR},
                },
            },
        )

        # Expanded terms chart
        exp_chart = expanded_df[["PRIMARY_TERM", "total_funding", "grant_count"]].copy()
        exp_chart["total_funding"] = (exp_chart["total_funding"] / 1e9).round(2)
        exp_chart.columns = ["Term", "Funding ($B)", "Grant Count"]

        return self._upsert_chart(
            "d3-bars",
            "Expanded Terms (+23) \u2014 Additional Broader Matches",
            exp_chart, "expanded_terms.png",
            metadata={
                "describe": {
                    "intro": f"Total: ${expanded_df['total_funding'].sum()/1e9:.1f}B across {expanded_df['grant_count'].sum():,} grants",
                    "number-prepend": "$",
                    "number-append": "B",
                },
                "visualize": {
                    "sort-bars": "desc",
                    "custom-colors": {"Funding ($B)": EXPANDED_COLOR},
                },
            },
        )
