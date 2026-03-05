"""
Generate a standalone HTML file for expert review of calibration examples.

Loads calibration examples and model results, embeds them into a single
HTML file with anti-anchoring design (model answers hidden until expert submits).

Usage:
    python3 scripts/generate_review.py
    python3 scripts/generate_review.py --output data/expert_review.html
"""

import argparse
import csv
import glob
import json
import html
from pathlib import Path


# Code lists from grader_prompt.py OUTPUT_SCHEMA
DIM1_CODES = [
    "susceptibility_risk", "diagnostic", "monitoring",
    "prognostic_risk", "prognostic_efficacy", "prognostic_enrichment",
    "predictive_optimal", "predictive_enrichment", "predictive_ambiguous",
    "pharmacodynamic", "safety", "surrogate_endpoint",
    "stratification_treatment", "stratification_diagnostic",
    "stratification_ambiguous", "methods_causal", "methods_correlational",
]

DIM2_CODES = [
    "observational_retrospective", "observational_crosssectional",
    "observational_cohort", "observational_longitudinal",
    "observational_case_cohort", "observational_quasi",
    "experimental_singlearm", "experimental_rct", "experimental_perturbation",
    "methods_secondary_analysis",
]

DIM3_CODES = [
    "correlational", "experimental_weak", "causal_preclinical",
    "causal_clinical", "methods_for_causal",
]


def load_examples(csv_path: Path) -> list[dict]:
    """Load calibration examples CSV."""
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_model_results(results_dir: Path) -> dict[str, list[dict]]:
    """Load all calibration_results_*.json files.

    Returns dict mapping model_slug -> list of result dicts.
    """
    results = {}
    pattern = str(results_dir / "calibration_results_*.json")
    for filepath in sorted(glob.glob(pattern)):
        slug = Path(filepath).stem.replace("calibration_results_", "")
        with open(filepath, encoding="utf-8") as f:
            results[slug] = json.load(f)
    return results


def build_review_data(
    examples: list[dict],
    model_results: dict[str, list[dict]],
) -> list[dict]:
    """Build the review data structure for embedding in HTML.

    Returns list of dicts sorted by APPLICATION_ID, each containing:
      - id, year, title, abstract, matched_terms, ic, activity, cost
      - model_results: dict of model_slug -> classification dict
    """
    # Build lookup: model_slug -> {application_id -> classification}
    model_lookup: dict[str, dict[str, dict]] = {}
    for slug, records in model_results.items():
        lookup = {}
        for r in records:
            app_id = r.get("application_id", "")
            if "classification" in r:
                lookup[app_id] = r["classification"]
        model_lookup[slug] = lookup

    review_items = []
    for ex in examples:
        app_id = ex.get("APPLICATION_ID", "").strip()
        item = {
            "id": app_id,
            "year": ex.get("YEAR", ""),
            "title": ex.get("PROJECT_TITLE", ""),
            "abstract": ex.get("ABSTRACT", ""),
            "matched_terms": ex.get("MATCHED_TERMS", ""),
            "ic": ex.get("ADMINISTERING_IC", ""),
            "activity": ex.get("ACTIVITY", ""),
            "cost": ex.get("TOTAL_COST", ""),
            "model_results": {},
        }
        for slug, lookup in model_lookup.items():
            if app_id in lookup:
                item["model_results"][slug] = lookup[app_id]
        review_items.append(item)

    return sorted(review_items, key=lambda x: x["id"])


def generate_html(
    review_data: list[dict],
    model_slugs: list[str],
    page_title: str = "NIH Biomarker Calibration - Expert Review",
    storage_key: str = "nih_biomarker_expert_grades_v1",
) -> str:
    """Generate the standalone HTML review application."""
    data_json = json.dumps(review_data)
    dim1_json = json.dumps(DIM1_CODES)
    dim2_json = json.dumps(DIM2_CODES)
    dim3_json = json.dumps(DIM3_CODES)
    models_json = json.dumps(model_slugs)
    storage_key_json = json.dumps(storage_key)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(page_title)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; line-height: 1.5; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 1.4rem; margin-bottom: 8px; }}
.subtitle {{ color: #666; margin-bottom: 20px; font-size: 0.9rem; }}
.progress {{ background: #e0e0e0; border-radius: 4px; height: 8px; margin-bottom: 20px; }}
.progress-bar {{ background: #4CAF50; height: 100%; border-radius: 4px; transition: width 0.3s; }}
.card {{ background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.meta {{ color: #888; font-size: 0.85rem; margin-bottom: 12px; }}
.meta span {{ margin-right: 16px; }}
.abstract {{ background: #fafafa; border-left: 3px solid #4CAF50; padding: 16px; margin: 12px 0; font-size: 0.95rem; max-height: 300px; overflow-y: auto; white-space: pre-wrap; }}
.form-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
.form-group {{ display: flex; flex-direction: column; }}
.form-group label {{ font-size: 0.8rem; font-weight: 600; color: #555; margin-bottom: 4px; }}
.form-group select {{ padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9rem; }}
.form-group.full-width {{ grid-column: 1 / -1; }}
.form-group textarea {{ padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9rem; resize: vertical; }}
.btn {{ padding: 10px 24px; border: none; border-radius: 4px; font-size: 0.95rem; cursor: pointer; font-weight: 600; }}
.btn-primary {{ background: #4CAF50; color: white; }}
.btn-primary:hover {{ background: #45a049; }}
.btn-primary:disabled {{ background: #ccc; cursor: not-allowed; }}
.btn-secondary {{ background: #2196F3; color: white; margin-left: 8px; }}
.btn-secondary:hover {{ background: #1976D2; }}
.btn-secondary:disabled {{ background: #ccc; cursor: not-allowed; }}
.btn-export {{ background: #FF9800; color: white; }}
.btn-export:hover {{ background: #F57C00; }}
.actions {{ display: flex; align-items: center; gap: 8px; margin-top: 16px; }}
.comparison {{ display: none; margin-top: 20px; }}
.comparison.visible {{ display: block; }}
.comparison h3 {{ margin-bottom: 12px; font-size: 1rem; }}
.comp-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
.comp-table th, .comp-table td {{ padding: 8px 12px; border: 1px solid #ddd; text-align: left; }}
.comp-table th {{ background: #f0f0f0; font-weight: 600; }}
.comp-table .agree {{ background: #e8f5e9; }}
.comp-table .disagree {{ background: #fff8e1; }}
.rubric-toggle {{ background: none; border: 1px solid #999; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 0.85rem; color: #555; }}
.rubric-panel {{ display: none; background: #fafafa; border: 1px solid #ddd; border-radius: 4px; padding: 16px; margin: 12px 0; max-height: 400px; overflow-y: auto; font-size: 0.82rem; }}
.rubric-panel.visible {{ display: block; }}
.rubric-panel h4 {{ margin: 12px 0 4px; color: #333; }}
.rubric-panel .code {{ margin-left: 8px; color: #555; }}
.rubric-panel .code strong {{ color: #333; }}
.summary-card {{ background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.hidden {{ display: none; }}
#review-view, #summary-view {{ transition: opacity 0.2s; }}
</style>
</head>
<body>
<div class="container">
  <h1>{html.escape(page_title)}</h1>
  <p class="subtitle">Grade each example, then compare with model outputs. <button class="rubric-toggle" onclick="toggleRubric()">Show Rubric Reference</button></p>

  <div class="rubric-panel" id="rubric-panel">
    <h4>Dimension 1: Biomarker Use (17 codes)</h4>
    <div class="code"><strong>susceptibility_risk</strong> - Risk of developing disease in disease-free individuals</div>
    <div class="code"><strong>diagnostic</strong> - Detect/confirm presence of disease</div>
    <div class="code"><strong>monitoring</strong> - Assess disease status serially over time</div>
    <div class="code"><strong>prognostic_risk</strong> - Predict outcome in established disease, no treatment claim</div>
    <div class="code"><strong>prognostic_efficacy</strong> - Predict treatment benefit, but no named drug or differential response</div>
    <div class="code"><strong>prognostic_enrichment</strong> - Prognostic for trial enrichment (explicit enrichment/regulatory context)</div>
    <div class="code"><strong>predictive_optimal</strong> - Differentiate treatment effects with named drugs + comparison</div>
    <div class="code"><strong>predictive_enrichment</strong> - Predict response to named treatment, no comparison data</div>
    <div class="code"><strong>predictive_ambiguous</strong> - Predicts treatment response but no named treatment</div>
    <div class="code"><strong>pharmacodynamic</strong> - Measures biological response to specific intervention</div>
    <div class="code"><strong>safety</strong> - Measures toxicity or adverse events</div>
    <div class="code"><strong>surrogate_endpoint</strong> - Substitute for clinical endpoint (regulatory context)</div>
    <div class="code"><strong>stratification_treatment</strong> - Subtype patients for treatment assignment</div>
    <div class="code"><strong>stratification_diagnostic</strong> - Subtype disease for biology/prognosis understanding</div>
    <div class="code"><strong>stratification_ambiguous</strong> - Stratification with unclear purpose</div>
    <div class="code"><strong>methods_causal</strong> - Methods for causal inference in biomarker context</div>
    <div class="code"><strong>methods_correlational</strong> - Methods for association/prediction/classification</div>

    <h4>Dimension 2: Research Design (10 codes)</h4>
    <div class="code"><strong>observational_retrospective</strong> - Chart review, biobank, registry</div>
    <div class="code"><strong>observational_crosssectional</strong> - Single timepoint</div>
    <div class="code"><strong>observational_cohort</strong> - Prospective follow-up</div>
    <div class="code"><strong>observational_longitudinal</strong> - Repeated measures, descriptive</div>
    <div class="code"><strong>observational_case_cohort</strong> - Nested case-control</div>
    <div class="code"><strong>observational_quasi</strong> - Natural variation (IV, RDD, MR)</div>
    <div class="code"><strong>experimental_singlearm</strong> - Pre/post without control</div>
    <div class="code"><strong>experimental_rct</strong> - Randomized controlled trial</div>
    <div class="code"><strong>experimental_perturbation</strong> - Knockdown, drug exposure, dose-response</div>
    <div class="code"><strong>methods_secondary_analysis</strong> - Methods development, secondary analysis</div>

    <h4>Dimension 3: Evidence Strength (5 codes)</h4>
    <div class="code"><strong>correlational</strong> - Association only</div>
    <div class="code"><strong>experimental_weak</strong> - Intervention exists but biomarker not validated</div>
    <div class="code"><strong>causal_preclinical</strong> - Biomarker validated in vitro/animal</div>
    <div class="code"><strong>causal_clinical</strong> - Biomarker validated in human studies (surrogacy, adaptive trial, causal mediation)</div>
    <div class="code"><strong>methods_for_causal</strong> - Methods enabling biomarker causal validation</div>
  </div>

  <div class="progress"><div class="progress-bar" id="progress-bar" style="width: 0%"></div></div>

  <div id="review-view">
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:baseline;">
        <h2 id="example-counter">Example 1 of {len(review_data)}</h2>
        <span class="meta" id="example-id"></span>
      </div>
      <h3 id="example-title" style="margin: 8px 0;"></h3>
      <div class="meta">
        <span id="example-meta-ic"></span>
        <span id="example-meta-activity"></span>
        <span id="example-meta-cost"></span>
        <span id="example-meta-year"></span>
        <span id="example-meta-terms"></span>
      </div>
      <div class="abstract" id="example-abstract"></div>

      <div class="form-grid">
        <div class="form-group">
          <label>Dim 1 Primary (Biomarker Use)</label>
          <select id="grade-dim1-primary"><option value="">-- select --</option></select>
        </div>
        <div class="form-group">
          <label>Dim 1 Secondary (optional)</label>
          <select id="grade-dim1-secondary"><option value="">-- none --</option></select>
        </div>
        <div class="form-group">
          <label>Dim 2 Primary (Research Design)</label>
          <select id="grade-dim2-primary"><option value="">-- select --</option></select>
        </div>
        <div class="form-group">
          <label>Dim 2 Secondary (optional)</label>
          <select id="grade-dim2-secondary"><option value="">-- none --</option></select>
        </div>
        <div class="form-group">
          <label>Dim 3 (Evidence Strength)</label>
          <select id="grade-dim3"><option value="">-- select --</option></select>
        </div>
        <div class="form-group">
          <label>&nbsp;</label>
          <span style="color: #888; font-size: 0.85rem; padding-top: 8px;">No secondary for Dim 3</span>
        </div>
        <div class="form-group full-width">
          <label>Notes (optional)</label>
          <textarea id="grade-notes" rows="2" placeholder="Any observations, uncertainties, or reasoning..."></textarea>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" id="btn-submit" onclick="submitGrade()">Submit My Grade</button>
        <button class="btn btn-primary hidden" id="btn-revise" onclick="reviseGrade()" style="background:#FF9800;">Revise My Grade</button>
        <button class="btn btn-secondary" id="btn-prev" onclick="prevExample()">Previous</button>
        <button class="btn btn-secondary" id="btn-next" onclick="nextExample()">Next</button>
        <span style="flex-grow:1;"></span>
        <button class="btn btn-export" id="btn-export-inline" onclick="exportCSV()">Export CSV</button>
        <span id="nav-hint" style="color:#888; font-size:0.82rem; margin-left:8px;"></span>
      </div>
    </div>

    <div class="comparison card" id="comparison-panel">
      <h3>Model Comparison</h3>
      <table class="comp-table" id="comp-table">
        <thead><tr><th>Dimension</th><th>Your Grade</th></tr></thead>
        <tbody></tbody>
      </table>
      <div id="model-reasoning" style="margin-top: 12px; font-size: 0.85rem; color: #555;"></div>
    </div>
  </div>

  <div id="summary-view" class="hidden">
    <div class="summary-card">
      <h2>Review Complete</h2>
      <p style="margin: 12px 0; color: #666;">All {len(review_data)} examples graded. Export your results below.</p>
      <table class="comp-table" id="summary-table">
        <thead><tr><th>#</th><th>App ID</th><th>Your Dim1</th><th>Your Dim2</th><th>Your Dim3</th></tr></thead>
        <tbody></tbody>
      </table>
      <div style="margin-top: 16px;">
        <button class="btn btn-export" onclick="exportCSV()">Export CSV</button>
        <button class="btn btn-secondary" onclick="goToExample(0)">Review Again</button>
      </div>
    </div>
  </div>
</div>

<script>
const DATA = {data_json};
const DIM1 = {dim1_json};
const DIM2 = {dim2_json};
const DIM3 = {dim3_json};
const MODELS = {models_json};

let currentIdx = 0;
let expertGrades = new Array(DATA.length).fill(null);

// --- localStorage persistence ---
const STORAGE_KEY = {storage_key_json};
function saveToStorage() {{
  try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(expertGrades)); }} catch(e) {{}}
}}
function loadFromStorage() {{
  try {{
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {{
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length === DATA.length) {{
        expertGrades = parsed;
        console.log(`Restored ${{expertGrades.filter(g => g !== null).length}} saved grades from localStorage`);
      }}
    }}
  }} catch(e) {{}}
}}
loadFromStorage();

// Populate dropdowns
function populateSelect(id, codes) {{
  const sel = document.getElementById(id);
  codes.forEach(c => {{
    const opt = document.createElement('option');
    opt.value = c; opt.textContent = c;
    sel.appendChild(opt);
  }});
}}
populateSelect('grade-dim1-primary', DIM1);
populateSelect('grade-dim1-secondary', DIM1);
populateSelect('grade-dim2-primary', DIM2);
populateSelect('grade-dim2-secondary', DIM2);
populateSelect('grade-dim3', DIM3);

function showExample(idx) {{
  currentIdx = idx;
  const ex = DATA[idx];
  document.getElementById('example-counter').textContent = `Example ${{idx + 1}} of ${{DATA.length}}`;
  document.getElementById('example-id').textContent = `ID: ${{ex.id}}`;
  document.getElementById('example-title').textContent = ex.title;
  document.getElementById('example-abstract').textContent = ex.abstract;
  document.getElementById('example-meta-ic').textContent = `IC: ${{ex.ic}}`;
  document.getElementById('example-meta-activity').textContent = `Activity: ${{ex.activity}}`;
  document.getElementById('example-meta-cost').textContent = `Cost: $${{Number(ex.cost).toLocaleString()}}`;
  document.getElementById('example-meta-year').textContent = `FY${{ex.year}}`;
  document.getElementById('example-meta-terms').textContent = `Terms: ${{ex.matched_terms}}`;

  // Reset form
  const submitted = expertGrades[idx] !== null;
  if (submitted) {{
    const g = expertGrades[idx];
    document.getElementById('grade-dim1-primary').value = g.dim1_primary;
    document.getElementById('grade-dim1-secondary').value = g.dim1_secondary;
    document.getElementById('grade-dim2-primary').value = g.dim2_primary;
    document.getElementById('grade-dim2-secondary').value = g.dim2_secondary;
    document.getElementById('grade-dim3').value = g.dim3;
    document.getElementById('grade-notes').value = g.notes;
    showComparison(idx);
  }} else {{
    document.getElementById('grade-dim1-primary').value = '';
    document.getElementById('grade-dim1-secondary').value = '';
    document.getElementById('grade-dim2-primary').value = '';
    document.getElementById('grade-dim2-secondary').value = '';
    document.getElementById('grade-dim3').value = '';
    document.getElementById('grade-notes').value = '';
    document.getElementById('comparison-panel').classList.remove('visible');
  }}

  // Enable/disable form controls
  setFormDisabled(submitted);
  if (submitted) {{
    document.getElementById('btn-submit').classList.add('hidden');
    document.getElementById('btn-revise').classList.remove('hidden');
  }} else {{
    document.getElementById('btn-submit').classList.remove('hidden');
    document.getElementById('btn-revise').classList.add('hidden');
  }}

  // Navigation always works — show hint if current not graded
  document.getElementById('btn-prev').disabled = (idx === 0);
  document.getElementById('btn-next').disabled = (idx === DATA.length - 1);
  const hint = document.getElementById('nav-hint');
  if (!submitted) {{
    hint.textContent = '(ungraded — you can navigate freely and come back)';
  }} else {{
    hint.textContent = '';
  }}

  // Progress
  const graded = expertGrades.filter(g => g !== null).length;
  document.getElementById('progress-bar').style.width = `${{(graded / DATA.length) * 100}}%`;

  // Show review view
  document.getElementById('review-view').classList.remove('hidden');
  document.getElementById('summary-view').classList.add('hidden');
  window.scrollTo(0, 0);
}}

function setFormDisabled(disabled) {{
  ['grade-dim1-primary','grade-dim1-secondary','grade-dim2-primary','grade-dim2-secondary','grade-dim3','grade-notes'].forEach(id => {{
    document.getElementById(id).disabled = disabled;
  }});
}}

function submitGrade() {{
  const dim1p = document.getElementById('grade-dim1-primary').value;
  const dim2p = document.getElementById('grade-dim2-primary').value;
  const dim3 = document.getElementById('grade-dim3').value;

  if (!dim1p || !dim2p || !dim3) {{
    alert('Please select at least primary codes for all 3 dimensions.');
    return;
  }}

  expertGrades[currentIdx] = {{
    dim1_primary: dim1p,
    dim1_secondary: document.getElementById('grade-dim1-secondary').value || null,
    dim2_primary: dim2p,
    dim2_secondary: document.getElementById('grade-dim2-secondary').value || null,
    dim3: dim3,
    notes: document.getElementById('grade-notes').value,
  }};

  saveToStorage();
  setFormDisabled(true);
  document.getElementById('btn-submit').classList.add('hidden');
  document.getElementById('btn-revise').classList.remove('hidden');
  showComparison(currentIdx);

  // Update progress
  const graded = expertGrades.filter(g => g !== null).length;
  document.getElementById('progress-bar').style.width = `${{(graded / DATA.length) * 100}}%`;
}}

function reviseGrade() {{
  setFormDisabled(false);
  document.getElementById('btn-submit').classList.remove('hidden');
  document.getElementById('btn-revise').classList.add('hidden');
  document.getElementById('comparison-panel').classList.remove('visible');
}}

function showComparison(idx) {{
  const ex = DATA[idx];
  const grade = expertGrades[idx];
  const panel = document.getElementById('comparison-panel');
  const tbody = panel.querySelector('tbody');
  const thead = panel.querySelector('thead tr');

  // Build header
  thead.innerHTML = '<th>Dimension</th><th>Your Grade</th>';
  MODELS.forEach(m => {{
    thead.innerHTML += `<th>${{m}}</th>`;
  }});

  // Build rows
  const dims = [
    {{ label: 'Dim 1 Primary', expert: grade.dim1_primary, getModel: (c) => c.biomarker_use?.primary || '—' }},
    {{ label: 'Dim 1 Secondary', expert: grade.dim1_secondary || '—', getModel: (c) => c.biomarker_use?.secondary || '—' }},
    {{ label: 'Dim 2 Primary', expert: grade.dim2_primary, getModel: (c) => c.research_design?.primary || '—' }},
    {{ label: 'Dim 2 Secondary', expert: grade.dim2_secondary || '—', getModel: (c) => c.research_design?.secondary || '—' }},
    {{ label: 'Dim 3', expert: grade.dim3, getModel: (c) => c.evidence_strength?.code || '—' }},
  ];

  tbody.innerHTML = '';
  dims.forEach(d => {{
    let row = `<tr><td><strong>${{d.label}}</strong></td><td>${{d.expert}}</td>`;
    MODELS.forEach(m => {{
      const cls = ex.model_results[m] ? (d.getModel(ex.model_results[m]) === d.expert ? 'agree' : 'disagree') : '';
      const val = ex.model_results[m] ? d.getModel(ex.model_results[m]) : '—';
      row += `<td class="${{cls}}">${{val}}</td>`;
    }});
    row += '</tr>';
    tbody.innerHTML += row;
  }});

  // Show reasoning from models
  let reasoningHtml = '';
  MODELS.forEach(m => {{
    if (ex.model_results[m]?.reasoning) {{
      reasoningHtml += `<p><strong>${{m}}:</strong> ${{ex.model_results[m].reasoning}}</p>`;
    }}
  }});
  document.getElementById('model-reasoning').innerHTML = reasoningHtml;

  panel.classList.add('visible');
}}

function nextExample() {{
  if (currentIdx < DATA.length - 1) {{
    showExample(currentIdx + 1);
  }} else {{
    showSummary();
  }}
}}

function prevExample() {{
  if (currentIdx > 0) {{
    showExample(currentIdx - 1);
  }}
}}

function goToExample(idx) {{
  showExample(idx);
}}

function showSummary() {{
  document.getElementById('review-view').classList.add('hidden');
  document.getElementById('summary-view').classList.remove('hidden');

  const tbody = document.getElementById('summary-table').querySelector('tbody');
  tbody.innerHTML = '';
  DATA.forEach((ex, i) => {{
    const g = expertGrades[i];
    if (!g) return;
    tbody.innerHTML += `<tr>
      <td>${{i + 1}}</td>
      <td><a href="#" onclick="goToExample(${{i}}); return false;">${{ex.id}}</a></td>
      <td>${{g.dim1_primary}}</td>
      <td>${{g.dim2_primary}}</td>
      <td>${{g.dim3}}</td>
    </tr>`;
  }});
  window.scrollTo(0, 0);
}}

function exportCSV() {{
  let csvContent = 'APPLICATION_ID,YEAR,PROJECT_TITLE,MATCHED_TERMS,expert_dim1_primary,expert_dim1_secondary,expert_dim2_primary,expert_dim2_secondary,expert_dim3,expert_notes';
  MODELS.forEach(m => {{
    csvContent += `,${{m}}_dim1_primary,${{m}}_dim1_secondary,${{m}}_dim2_primary,${{m}}_dim2_secondary,${{m}}_dim3`;
  }});
  csvContent += '\\n';

  DATA.forEach((ex, i) => {{
    const g = expertGrades[i];
    if (!g) return;
    const esc = (s) => `"${{(s || '').replace(/"/g, '""')}}"`;
    let row = [esc(ex.id), esc(ex.year), esc(ex.title), esc(ex.matched_terms),
               esc(g.dim1_primary), esc(g.dim1_secondary || ''), esc(g.dim2_primary),
               esc(g.dim2_secondary || ''), esc(g.dim3), esc(g.notes)];
    MODELS.forEach(m => {{
      const c = ex.model_results[m];
      if (c) {{
        row.push(esc(c.biomarker_use?.primary || ''));
        row.push(esc(c.biomarker_use?.secondary || ''));
        row.push(esc(c.research_design?.primary || ''));
        row.push(esc(c.research_design?.secondary || ''));
        row.push(esc(c.evidence_strength?.code || ''));
      }} else {{
        row.push('','','','','');
      }}
    }});
    csvContent += row.join(',') + '\\n';
  }});

  const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'expert_review_results.csv';
  a.click();
  URL.revokeObjectURL(url);
}}

function toggleRubric() {{
  const panel = document.getElementById('rubric-panel');
  panel.classList.toggle('visible');
  const btn = document.querySelector('.rubric-toggle');
  btn.textContent = panel.classList.contains('visible') ? 'Hide Rubric Reference' : 'Show Rubric Reference';
}}

// Initialize
showExample(0);
</script>
</body>
</html>"""


def load_disagreement_examples(json_path: Path, grade_files: dict[str, Path]) -> tuple[list[dict], list[str]]:
    """Load disagreement examples from extract_disagreements.py output.

    Returns (review_items, model_slugs) in the same format as build_review_data().
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Collect all model slugs from grade files
    model_slugs = sorted(grade_files.keys())

    # Load all grades by application_id per model
    all_grades: dict[str, dict[str, dict]] = {slug: {} for slug in model_slugs}
    for slug, path in grade_files.items():
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if "classification" in rec:
                    all_grades[slug][rec["application_id"]] = rec["classification"]

    # Load abstracts from sample CSV if available
    abstract_lookup: dict[str, dict] = {}
    sample_csv = grade_files.get(list(grade_files.keys())[0], Path()).parent / "oncology_sample_100per_year.csv"
    if sample_csv.exists():
        with open(sample_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                aid = row.get("APPLICATION_ID", "").strip()
                if aid:
                    abstract_lookup[aid] = row

    review_items = []
    seen_ids = set()
    for pattern in data["patterns"]:
        for ex in pattern["examples"]:
            app_id = ex["application_id"]
            if app_id in seen_ids:
                continue
            seen_ids.add(app_id)
            sample_row = abstract_lookup.get(app_id, {})
            item = {
                "id": app_id,
                "year": sample_row.get("FY", ""),
                "title": ex["title"],
                "abstract": sample_row.get("ABSTRACT_TEXT", sample_row.get("ABSTRACT", "")),
                "matched_terms": f"[{pattern['dimension']}: {pattern['code_a']} vs {pattern['code_b']}]",
                "ic": sample_row.get("ADMINISTERING_IC", ""),
                "activity": sample_row.get("ACTIVITY", ""),
                "cost": sample_row.get("TOTAL_COST", ""),
                "model_results": {},
            }
            for slug in model_slugs:
                if app_id in all_grades[slug]:
                    item["model_results"][slug] = all_grades[slug][app_id]
            # Pull year from any model's grade
            for slug in model_slugs:
                model_data = ex.get("models", {}).get(slug, {})
                if model_data.get("reasoning"):
                    # Store reasoning in model_results if not already there
                    if slug in item["model_results"] and "reasoning" not in item["model_results"][slug]:
                        item["model_results"][slug]["reasoning"] = model_data["reasoning"]
            review_items.append(item)

    return review_items, model_slugs


def main():
    parser = argparse.ArgumentParser(
        description="Generate expert review HTML for calibration examples"
    )
    parser.add_argument(
        "--examples",
        default=str(
            Path(__file__).resolve().parent.parent
            / "data"
            / "grader_calibration_examples.csv"
        ),
        help="Path to calibration examples CSV",
    )
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).resolve().parent.parent / "data"),
        help="Directory containing calibration_results_*.json files",
    )
    parser.add_argument(
        "--output",
        default=str(
            Path(__file__).resolve().parent.parent / "data" / "expert_review.html"
        ),
        help="Output HTML path",
    )
    parser.add_argument(
        "--title",
        default="NIH Biomarker Calibration - Expert Review",
        help="Page title",
    )
    parser.add_argument(
        "--storage-key",
        default="nih_biomarker_expert_grades_v1",
        help="localStorage key (use different keys for different review sets)",
    )
    parser.add_argument(
        "--disagreements",
        default=None,
        help="Path to disagreement_examples.json (uses disagreement mode instead of calibration CSV)",
    )
    args = parser.parse_args()

    if args.disagreements:
        print(f"Loading disagreement examples from {args.disagreements}...")
        # Find grade JSONL files
        results_dir = Path(args.results_dir)
        grade_files = {}
        import glob as glob_mod
        for f in sorted(glob_mod.glob(str(results_dir / "oncology_grades_*.jsonl"))):
            slug = Path(f).stem.replace("oncology_grades_", "")
            grade_files[slug] = Path(f)
        print(f"  Grade files: {', '.join(grade_files.keys())}")
        review_data, model_slugs = load_disagreement_examples(
            Path(args.disagreements), grade_files
        )
        print(f"  {len(review_data)} examples loaded")
    else:
        print("Loading calibration examples...")
        examples = load_examples(Path(args.examples))
        print(f"  {len(examples)} examples loaded")

        print("Loading model results...")
        model_results = load_model_results(Path(args.results_dir))
        model_slugs = sorted(model_results.keys())
        print(f"  Models: {', '.join(model_slugs)}")

        print("Building review data...")
        review_data = build_review_data(examples, model_results)

    print("Generating HTML...")
    html_content = generate_html(
        review_data, model_slugs,
        page_title=args.title,
        storage_key=args.storage_key,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"Written to {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1024:.0f} KB")
    print(f"\nOpen in browser: file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
