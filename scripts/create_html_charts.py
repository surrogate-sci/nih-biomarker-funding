#!/usr/bin/env python3
"""
Create HTML visualizations using Chart.js for biomarker research funding
"""

import pandas as pd
import json
from pathlib import Path

def create_chart_html(title, chart_type, labels, data, filename, y_label="Total Funding (Millions $)"):
    """Create standalone HTML file with Chart.js"""

    # Convert data to JSON
    labels_json = json.dumps(labels)
    data_json = json.dumps(data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }}
        #chartContainer {{
            position: relative;
            height: 600px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div id="chartContainer">
            <canvas id="myChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('myChart').getContext('2d');
        const myChart = new Chart(ctx, {{
            type: '{chart_type}',
            data: {{
                labels: {labels_json},
                datasets: [{{
                    label: '{y_label}',
                    data: {data_json},
                    backgroundColor: '{get_color(chart_type)}',
                    borderColor: '{get_border_color(chart_type)}',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                {get_options(chart_type, y_label)}
            }}
        }});
    </script>
</body>
</html>"""

    with open(filename, 'w') as f:
        f.write(html)

    print(f"✓ Created: {filename.name}")

def get_color(chart_type):
    """Get color based on chart type"""
    if chart_type == 'bar':
        return 'rgba(46, 134, 171, 0.8)'
    else:
        return 'rgba(162, 59, 114, 0.8)'

def get_border_color(chart_type):
    """Get border color based on chart type"""
    if chart_type == 'bar':
        return 'rgba(46, 134, 171, 1)'
    else:
        return 'rgba(162, 59, 114, 1)'

def get_options(chart_type, y_label):
    """Get chart options based on type"""
    if chart_type == 'bar':
        return """scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(0) + 'M';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return '$' + context.parsed.y.toFixed(1) + 'M';
                            }
                        }
                    }
                }"""
    else:  # horizontal bar
        return """indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(0) + 'M';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return '$' + context.parsed.x.toFixed(1) + 'M';
                            }
                        }
                    }
                }"""

def main():
    # Setup paths
    script_dir = Path(__file__).parent.parent
    data_dir = script_dir / "data" / "oct-2024"
    output_dir = script_dir / "visualizations"
    output_dir.mkdir(exist_ok=True)

    print("=" * 80)
    print("CREATING HTML VISUALIZATIONS")
    print("=" * 80)
    print()

    # 1. Biomarker Discovery
    print("Biomarker Discovery Charts:")
    bd_file = data_dir / "biomarker_discovery_filtered.csv"
    bd_df = pd.read_csv(bd_file, low_memory=False)
    bd_df['Total Cost Numeric'] = pd.to_numeric(bd_df['Total Cost'], errors='coerce')

    # By year
    yearly = bd_df.groupby('Fiscal Year')['Total Cost Numeric'].sum() / 1_000_000
    create_chart_html(
        "Biomarker Discovery: Total Funding by Fiscal Year",
        "bar",
        [int(y) for y in yearly.index.tolist()],
        [round(v, 2) for v in yearly.values.tolist()],
        output_dir / "biomarker_discovery_by_year.html"
    )

    # By institute
    institute = bd_df.groupby('Administering IC')['Total Cost Numeric'].sum() / 1_000_000
    institute = institute.sort_values(ascending=False).head(10)
    create_chart_html(
        "Biomarker Discovery: Top 10 Institutes by Total Funding",
        "bar",
        institute.index.tolist(),
        [round(v, 2) for v in institute.values.tolist()],
        output_dir / "biomarker_discovery_by_institute.html"
    )

    print()

    # 2. Surrogate Endpoints
    print("Surrogate Endpoints Charts:")
    se_file = data_dir / "surrogate_endpoints_filtered.csv"
    se_df = pd.read_csv(se_file, low_memory=False)
    se_df['Total Cost Numeric'] = pd.to_numeric(se_df['Total Cost'], errors='coerce')

    # By year
    yearly = se_df.groupby('Fiscal Year')['Total Cost Numeric'].sum() / 1_000_000
    create_chart_html(
        "Surrogate/Intermediate Endpoints: Total Funding by Fiscal Year",
        "bar",
        [int(y) for y in yearly.index.tolist()],
        [round(v, 2) for v in yearly.values.tolist()],
        output_dir / "surrogate_endpoints_by_year.html"
    )

    # By institute
    institute = se_df.groupby('Administering IC')['Total Cost Numeric'].sum() / 1_000_000
    institute = institute.sort_values(ascending=False).head(10)
    create_chart_html(
        "Surrogate/Intermediate Endpoints: Top 10 Institutes by Total Funding",
        "bar",
        institute.index.tolist(),
        [round(v, 2) for v in institute.values.tolist()],
        output_dir / "surrogate_endpoints_by_institute.html"
    )

    print()

    # 3. Biomarker Validation
    print("Biomarker Validation Charts:")
    bv_file = data_dir / "biomarker_validation_filtered.csv"
    if bv_file.exists():
        bv_df = pd.read_csv(bv_file, low_memory=False)
        bv_df['Total Cost Numeric'] = pd.to_numeric(bv_df['Total Cost'], errors='coerce')

        # By year
        yearly = bv_df.groupby('Fiscal Year')['Total Cost Numeric'].sum() / 1_000_000
        create_chart_html(
            "Biomarker Validation: Total Funding by Fiscal Year",
            "bar",
            [int(y) for y in yearly.index.tolist()],
            [round(v, 2) for v in yearly.values.tolist()],
            output_dir / "biomarker_validation_by_year.html"
        )

        # By institute
        institute = bv_df.groupby('Administering IC')['Total Cost Numeric'].sum() / 1_000_000
        institute = institute.sort_values(ascending=False).head(10)
        create_chart_html(
            "Biomarker Validation: Top 10 Institutes by Total Funding",
            "bar",
            institute.index.tolist(),
            [round(v, 2) for v in institute.values.tolist()],
            output_dir / "biomarker_validation_by_institute.html"
        )
    else:
        print("  Skipping - biomarker_validation_filtered.csv not found")

    print()

    # 4. All Biomarkers
    print("All Biomarkers Charts:")
    ab_file = data_dir / "all_biomarkers_filtered.csv"
    if ab_file.exists():
        ab_df = pd.read_csv(ab_file, low_memory=False)
        ab_df['Total Cost Numeric'] = pd.to_numeric(ab_df['Total Cost'], errors='coerce')

        # By year
        yearly = ab_df.groupby('Fiscal Year')['Total Cost Numeric'].sum() / 1_000_000
        create_chart_html(
            "All Biomarker Research: Total Funding by Fiscal Year",
            "bar",
            [int(y) for y in yearly.index.tolist()],
            [round(v, 2) for v in yearly.values.tolist()],
            output_dir / "all_biomarkers_by_year.html"
        )

        # By institute
        institute = ab_df.groupby('Administering IC')['Total Cost Numeric'].sum() / 1_000_000
        institute = institute.sort_values(ascending=False).head(10)
        create_chart_html(
            "All Biomarker Research: Top 10 Institutes by Total Funding",
            "bar",
            institute.index.tolist(),
            [round(v, 2) for v in institute.values.tolist()],
            output_dir / "all_biomarkers_by_institute.html"
        )
    else:
        print("  Skipping - all_biomarkers_filtered.csv not found")

    print()
    print("=" * 80)
    print(f"All visualizations saved to: visualizations/")
    print("Open the HTML files in any browser to view the charts")
    print("=" * 80)

if __name__ == "__main__":
    main()
