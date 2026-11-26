# InsightAI 2.0 — Phase 4: Executive Report

This is a **changed-files-only upgrade** based on the Phase 3 evidence-linked version. It does not contain your API key or local secrets and does not change `core/ai_service.py`.

## What is new

- **Executive Report** in the sidebar (all figures calculated from the *selected*, filtered dataset).
- KPI cards: selected records, recorded metric total when applicable, missing cells and duplicate rows.
- Interactive top-category contribution (or raw category totals when shares would be misleading).
- Calendar-month trend with missing months left as gaps, not fabricated zeros.
- Prioritized, rules-based review suggestions with verified numerical basis and cautions.
- Optional existing Gemini/OpenAI interpretations shown separately when a valid report has already been generated in the same selection.
- PDF exports: executive snapshot, review actions, monthly table, detailed existing findings/chart, limits.
- Excel exports: Executive KPIs, Review priorities, Category performance, Monthly evidence and Executive limitations sheets.
- Fixed an existing empty-selection issue in `core/advanced_analysis.py` when a date column was selected.

## The files you need to copy

Copy each extracted file into the same location in your existing InsightAI folder:

| Extracted file | Destination |
| --- | --- |
| `app.py` | `insightai/app.py` |
| `core/executive_report.py` | `insightai/core/executive_report.py` (new) |
| `core/report_generator.py` | `insightai/core/report_generator.py` |
| `core/advanced_analysis.py` | `insightai/core/advanced_analysis.py` |
| `tests/test_executive_report.py` | `insightai/tests/test_executive_report.py` (new) |
| `tests/test_ui.py` | `insightai/tests/test_ui.py` |

Do **not** replace `core/ai_service.py`, `.streamlit/config.toml`, or `.streamlit/secrets.toml`. No new pip packages are required.

If you have modified any of the existing files after Phase 3, merge the changes manually rather than overwriting them. `PHASE4_changes.patch` is provided for code review.

## Safe install — Windows, VS Code, PowerShell

Start with a clean working tree (run `git status`). If your work has not yet been committed, preserve it first.

```powershell
git switch main
git pull origin main
git switch -c feature/insightai-phase4-executive
```

If that feature branch already exists, run `git switch feature/insightai-phase4-executive` instead. Copy the six files as listed above.

Run the tests:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Launch locally:

```powershell
python -m streamlit run app.py
```

In your browser, test **Executive Report**, **AI Insights**, **Reports & Export**, the sidebar filters, and the Gemini consent/model settings. Click **Build executive report files** and open both the resulting PDF and Excel files. The report should change correctly when you filter to one region, and show no metric totals when a text-only dataset is selected.

Before committing, confirm your local secret is ignored and untracked:

```powershell
git check-ignore -v .streamlit/secrets.toml
git ls-files .streamlit/secrets.toml
```

The first command should show an ignore rule, and the second should show **nothing**. If the second displays the file, stop and remove the secret from Git tracking/history before pushing. Never paste API keys into GitHub.

After local testing:

```powershell
git add app.py core/executive_report.py core/advanced_analysis.py core/report_generator.py tests/test_executive_report.py tests/test_ui.py
git diff --cached --check
git diff --cached --stat
git commit -m "Add Phase 4 executive reporting dashboard"
git push -u origin feature/insightai-phase4-executive
```

Create a GitHub pull request from `feature/insightai-phase4-executive` into `main`. Merge **only after** the complete Windows/Streamlit tests, sample data visual check, and export checks pass. Cloud will pick up the new `main` commit after merge. This package did not push or deploy code for you.

## Data integrity safeguards

- Python derives figures; Gemini only interprets verified evidence when enabled.
- The executive report runs without API keys.
- Outliers are review flags, not confirmed errors.
- Review priorities are simple heuristics, not a probability, statistical significance or objectively ranked business severity.
- Percent shares are withheld for negative values or nonpositive totals.
- Month-over-month percent change is suppressed for nonpositive baselines.
- Empty calendar months remain gaps.
- No confidential data or API keys are included in this package.

## Validation note

In the packaging environment, **106 core tests passed**, Python compilation succeeded, and a sample three-page PDF was generated, rendered and visually inspected. Streamlit was unavailable in that environment; therefore the new interface test and existing UI tests must be run on your PC before merging. No live Gemini request was made.
