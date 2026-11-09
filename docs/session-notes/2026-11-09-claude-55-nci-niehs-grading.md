# Session: Claude 5.5 grading of the NCI and NIEHS samples — 2026-11-06 to 2026-11-09

## State reference

- Code: `main` @ `f488612` (squash merge of PR #50, branch `grade/rubric-assay-code-claude-rerun`)
- Rubric: `data/RUBRIC.md` at commit `11d47af` (22 biomarker-use codes, 10 research-design codes, 5 evidence-strength codes)
- Scorer: `inspect_task.py` and `scripts/utils.py` at commit `52da7cd`
- Samples: `data/nci_sample_v31_seed42.csv` (3,770 NCI grants, 3,718 with abstracts); `data/niehs300_plus_grant_abstracts_v31.csv` (320 grants)
- Logs to analyze: `logs/2026-11-09_nci-3718-niehs-320_opus-sonnet-5.5_consolidated/` (manifest rows marked "CONSOLIDATED — USE THIS")
- Inspect AI 0.3.287, `anthropic` SDK 2.6.0, in the existing `.venv`

*Notes written against this state. Later scorer or rubric changes may supersede these counts.*

## What we did

**Goal.** Re-grade the NCI sample with the rubric that now includes the Step 0 exit codes (`not_applicable`, `disease_non_biomarker`), using about $100 of Anthropic API credit that was about to expire, through Inspect AI rather than the legacy scripts.

**Rubric changes, dictated by Manjari (commit `11d47af`).** After a review of the judge prompt and `RUBRIC.md`, Manjari directed three additions:
1. A new biomarker-use code, `assay_technology_unspecified`, for grants that develop biomarker assay technology with no determinable intended use. Her wording: this is rare, there is usually an implicit diagnostic purpose, and if the purpose is implicitly diagnostic, stratification or any other biomarker-use code, that code is assigned instead. Discovery of candidate biomarkers is classified by its implicit intended purpose.
2. A scope sentence for the biomarker-use decision hierarchy: it separates risk biomarkers into `prognostic_risk` and `susceptibility_risk`, since both feed clinical prediction models.
3. A mediation rule: Baron–Kenny style structural equation models are tagged `correlational`; formal causal mediation counts as `causal_clinical`, at least in its intent. Manjari noted that she expects much "causal rigor-washing" after 2023, and that a grant cannot show whether its assumptions are taken as empirical commitments. That remains unresolved.

**Prompt changes (commit `6b8800b`).** The system prompt now says the projects matched a biomarker keyword screen and that abstracts describe proposed work. The output schema allows null research-design and evidence-strength fields when the biomarker-use code is `not_applicable` or `disease_non_biomarker`.

**Runs.** All runs used the rubric at `11d47af` and the Claude 5.5 default temperature; these models reject `--temperature`.

| Run | Model | Sample | Graded | Cost (approx.) |
|---|---|---|---|---|
| Smoke test | Sonnet 5.5 | 3 grants | 3 | $0.09 |
| Pilot | Opus 5.5 and Sonnet 5.5 | `data/selective_v1_nci.csv`, 103 grants (23 gold-labeled, 50 random NCI, 30 April Gemini/GPT-OSS disagreements) | 103 each | $3.30 |
| NCI | Opus 5.5 | NCI sample | 3,718 | $61.34 |
| NCI | Sonnet 5.5 | NCI sample | 3,718 | $29.55 |
| NIEHS | Sonnet 5.5 | 300 NIEHS grants (10 per year FY2004–2013, 20 per year FY2014–2023, seed 42) plus 20 grants from `grant_abstracts_v31.csv` | 320 | $3 |
| Refusal retry | Opus 5.5 | 6 NCI grants refused in the main run | 6 | $0.10 |

On the pilot, Opus and Sonnet each matched the gold biomarker-use label on 18 of 23 gold-labeled grants and agreed with each other on 84 of 103 biomarker-use codes. Neither model assigned `assay_technology_unspecified`. The NIEHS sample was graded on Sonnet rather than Opus, at Manjari's direction, for cost.

**Refusals.** Six Opus NCI grants returned `stop_reason == "content_filter"`, a safety-classifier refusal, not a length limit (an early report in this session called them truncations; that was wrong). One retry recovered three. Grants 10580592, 8121996 and 9558406 were refused both times and are recorded as refusals. No fallback model was used, since that would change the judge for those rows.

**Scoring fixes, without new API calls.** The first scorer counted valid answers as failures, so the saved outputs were re-scored with `inspect score` after each fix:
- Sonnet sometimes wrote prose around the JSON, left trailing commas, or emitted a second corrected JSON object. The parser now accepts only complete top-level JSON objects that contain `biomarker_use`, takes the last one, ignores stray or schema-echo objects, removes trailing commas outside strings, and treats a cut-off answer as a parse failure. These fixes followed an independent review of PR #50.
- Sonnet misspelled the code `observational_crosssectional` (triple s) as `observational_cross_sectional`, `observational_cross-sectional`, and versions ending in `_placeholder` or `_placeholder_removed`. Opus never did. All of these now map to `observational_crosssectional`, and each mapping is recorded in the grade's `code_aliases_applied` metadata. Manjari directed that these be fixed rather than left invalid.

**Final counts** (consolidated folder):

| `.eval` | Grants | Valid codes | Misspellings mapped | Refusals |
|---|---|---|---|---|
| Opus 5.5, NCI (retry merged) | 3,718 | 3,715 | 0 | 3 |
| Sonnet 5.5, NCI | 3,718 | 3,718 | 48 | 0 |
| Sonnet 5.5, NIEHS 300 + 20 | 320 | 320 | 16 | 0 |

No answer in any run was cut off at a token limit.

**Consolidation.** Inspect writes one `.eval` per model per run and has no merge command. A derived Opus NCI log was built by replacing the three refused grants with their successful retries; each replaced grade carries `merged_from_retry_run_id = MCvTUj3X7AFYkaAfeZieEk`. The derived log was then re-scored so its summary metrics are correct. Its token and cost totals cover the original run only. Three intermediate re-score folders were deleted after a check showed that every model answer was identical and no grade that was valid in them had changed or become invalid. The paid original logs remain in `logs/2026-11-06_nci-3718_opus-sonnet-5.5/`, `logs/2026-11-06_niehs-300-plus-grant-abstracts-20_sonnet-5.5/` and `logs/2026-11-06_nci-6-refused_opus-5.5_retry/`.

**Parallel work in Codex.** During this period, separate Codex sessions graded 5,240 grants of the 20,427-grant pilot sample with `gpt-6-astra` and imported them into an Inspect log; see `docs/session-notes/2026-11-06_codex-credit-grading.md` and `docs/session-notes/2026-11-07_codex-inspect-log-import.md`. Those grades used a different prompt layout (rubric and grant in one message) and a different sample. Their four manifest rows are not yet committed.

## Key decisions

1. **Run Opus 5.5 and Sonnet 5.5 on the full NCI sample in one `inspect eval-set` run** — Manjari.
2. **The three rubric additions above** — Manjari, in her wording.
3. **Grade NIEHS on Sonnet only** — Manjari, for cost.
4. **No fallback model for refusals** — the three persistent refusals stay as refusals. Session agent, following the rule that a fallback changes the judge.
5. **Fix parse failures by re-scoring, not re-judging** — Manjari.
6. **Map Sonnet's cross-sectional misspellings to the real code** — Manjari ("fix these").
7. **Structured output (issue #49) is the preferred long-term fix for code misspellings, not renaming codes in the rubric** — Manjari.
8. **Log folders are named for people, `logs/YYYY-MM-DD_<sample>-<n>_<models>[_<purpose>]/`; commit hashes go in the manifest** — Manjari.
9. **`CLAUDE.md` became `AGENTS.md`** so other agents read the same instructions — Manjari.
10. **Run paths do not go in `AGENTS.md`; `logs/manifest.csv` records which log to use** — Manjari.

## Corrections received

- The agent claimed the updated rubric existed only on another worktree. A fetch from outside the sandbox showed PR #45 had already merged it into `main`. GitHub state must be read outside the sandbox before judging it.
- The agent called the six Opus failures length truncations. They were `content_filter` refusals.
- The agent proposed renaming `observational_crosssectional` in `RUBRIC.md`. Manjari pointed out that issue #49 (constrained output) is the preferred fix and a rubric edit is unnecessary.
- The agent wrote run-specific log paths into `AGENTS.md`. These belong in the manifest.
- A background re-score stalled for two days because `inspect score` asked whether to overwrite an existing output file. Re-scores now write to a new folder with stdin from `/dev/null`; the grading-run skill says so.

## Open questions

- How should Opus and Sonnet be compared on the 3,718 NCI grants, and against the April Gemini 2.5 Flash Lite and GPT-OSS-120B runs, which used the rubric before `disease_non_biomarker`? (researcher judgment)
- How should the 20 `PRIOR_*` labels from `grant_abstracts_v31.csv` be compared with the new grades? (researcher judgment)
- Should the Codex `gpt-6-astra` grades join the comparison as a third judge, given the different prompt layout and sample? (researcher judgment)
- How should the code-to-estimand mapping be defined for the blog post's hypothesis? (researcher judgment)
- Should NIEHS also be graded on Opus with the next credit allotment? (researcher judgment)

- **Rubric wording provenance (raised Nov 9; issue #52).** Manjari stated that `disease_non_biomarker` (added Apr 12, 2026, commit `8de20d3`) was drafted by a Claude Code agent under her guidance without her full review, and was not properly vetted. As written, it cannot separate a biomarker used within mechanistic toxicology from research that is not biomarker-oriented. Her example: improving sequencing technologies or multiplexed barcoding to enable genomics measurements is not biomarker-oriented research, even though it might be a precursor to studying some biological process. Its 17 gold examples in `data/grader_calibration_examples.csv` are all NCI grants. The Nov 6 additions in commit `11d47af` also contain agent-drafted sentences (the `assay_technology_unspecified` definition sentence and the second hierarchy-scope sentence); the issue comment lists them. All agent-drafted rubric wording needs the author's review. (researcher judgment)

## Next steps

- Vet `disease_non_biomarker` and the agent-drafted Nov 6 wording (issue #52) before relying on those codes in analysis.

- Implement issue #49: build an Inspect `response_schema` from the rubric's code lists so models can only write exact codes; check how each provider handles it before the next paid run.
- Update `scripts/analyze_eval_results.py` to read zstd-compressed logs with `inspect_ai.log.read_eval_log`.
- Open a separate PR to `ruff format` the 12 files that still fail the lint check on `main`.
- Commit the four Codex manifest rows once Manjari has reviewed them.
- Decide whether to publish the data and logs (dataset release v3.2 and a grading release, or Google Drive).
- PR #48 (`scripts/build_selective_sample.py`) is still open.

## Files created/updated

- `data/RUBRIC.md` — three additions dictated by Manjari (commit `11d47af`)
- `scripts/grader_prompt.py` — keyword-screen framing; null research design and evidence strength for exit codes
- `inspect_task.py` — exit-code exemption, null normalization, `CODE_ALIASES` with recorded replacements, abstract filter
- `scripts/utils.py` — hardened JSON extraction
- `tests/test_inspect_task.py` — 41 tests
- `scripts/sample_ic_by_year.py` — new fixed-count-per-year sampler for one institute
- `scripts/run-grading.sh` — temperature now optional
- `AGENTS.md` (from `CLAUDE.md`), `CLAUDE.md` (now imports `AGENTS.md`), `README.md`, `.claude/skills/grading-run/SKILL.md` — current Inspect and Claude 5.5 procedure
- `.claude/settings.json`, `.claude/hooks/guard-rubric.sh`, `.claude/hooks/ruff-format.sh` — hooks now load; the rubric guard reads the right field; formatting uses the `.venv` ruff
- `logs/manifest.csv` — rows for every run, retry and re-score
