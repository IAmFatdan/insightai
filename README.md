# InsightAI

**Merged edition:** See [START_HERE.md](START_HERE.md) for installation and dark-mode instructions, and [MERGE_REPORT.md](docs/MERGE_REPORT.md) for current verification.

**Explore data. Explain the evidence. Keep control of every change.**

InsightAI is a Python/Streamlit analytics application for students, analysts and small teams. Upload a CSV or Excel workbook, inspect its quality, preview reversible cleaning, build a filtered dashboard, ask supported questions and export the results. Optional OpenAI features interpret computed findings or propose a calculation for human review.

This upgrade refactors the supplied v0.3.1 application. The original sales sample is unchanged. The original app and README are preserved in `legacy/`.

## What is implemented

- CSV with encoding/delimiter options; XLSX with sheet selection and expanded-size checks.
- Dataset profiling, descriptive statistics, category frequencies, missing/duplicate checks and possible outlier/type/case warnings.
- Ten cleaning operations with previews, an operation log, undo and reset to the original.
- Shared category/date filters, selectable numeric metrics and optional sales field mappings.
- Interactive bar, line, area, pie/donut, histogram, scatter, box and correlation charts.
- Recorded-value KPIs, top categories, monthly comparisons and calculated insights.
- Local question answering, follow-ups and an explicit structured calculation form.
- Optional structured AI commentary and a reviewed AI query planner. No generated code execution.
- Cleaned/filtered CSV, multi-sheet Excel and paginated PDF exports with a category chart.
- Session-scoped data, consent controls, redacted API errors and API attempt limits.
- Automated calculation, failure-path and Streamlit UI tests; a GitHub Actions workflow.

**Validation:** See [the completion report](docs/COMPLETION_REPORT.md) for executed checks and outstanding validation. Browser/mobile visual review and live API calls were not verified in the build environment. No deployment or GitHub push was performed.

## Quick start on Windows

Use **Python 3.12**. Python 3.11 is included in the CI matrix but was not executed during this build.

1. Extract this ZIP into a new folder, keeping your existing project safe.
2. Open the extracted folder in VS Code: **File → Open Folder**. Choose the folder containing `app.py`.
3. Open **Terminal → New Terminal**, then run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The terminal prints a local address, normally `http://localhost:8501`. Open it in your browser. You should see **InsightAI**, a sales sample with **24 records**, **5 fields** and **2 missing cells**.

These commands use the environment's Python directly; no PowerShell activation or execution-policy change is needed. Stop the application with **Ctrl+C**.

For later launches, run only the last command. If `py -3.12` is unavailable, install Python 3.12 from [python.org](https://www.python.org/downloads/) with the Python launcher enabled, reopen VS Code and retry.

macOS/Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## Your first walkthrough

1. Leave **Sales · original** selected.
2. Open **Data Overview**. Check the missing Region and Revenue_NGN values.
3. Open **Data Cleaning**. Choose **Fill categorical missing**, select `Region`, inspect the preview and click **Apply this change**. Use **Undo last step** to restore it.
4. Open **Dashboard**. Under **Filter columns**, select `Region`; select only `Lagos` in its values.
5. Confirm recorded revenue **NGN 9,140,000.00**. Laptop recorded revenue is **NGN 7,430,000.00**.
6. Open **Chat With Your Data** and ask: `What percentage of revenue comes from Laptop?` The answer is **81.29%** within the Lagos selection.
7. Open **Reports & Export** and build Excel/PDF reports. Their context records the active filters.
8. Try **Employees · example** or **Survey · text only** to see how different schemas behave.

All example datasets are fictional. The original sales sample is included as provided, not edited to match the tests.

## UI guide

| Area | Purpose |
|---|---|
| Home | Starting point and preview |
| Data Overview | Profile the full working dataset |
| Data Cleaning | Preview/apply/undo changes on the full working dataset |
| Dashboard | Explore the filtered selection |
| AI Insights | Read computed facts, optionally request commentary |
| Chat With Your Data | Ask local questions or review an AI-proposed plan |
| Reports & Export | Download data and evidence |
| Settings / About | External-AI consent, model selection and privacy notes |

Sidebar filters apply to dashboard, insights, chat and reports. They do **not** delete records or restrict cleaning. Empty category selections match no records. Reset filters restores all records. Changing the dataset, cleaning, metric, breakdown or filters clears analytical chat and generated results so old answers cannot appear as current ones.

The Streamlit menu supports light/dark themes. Native columns adapt to available space; final mobile browser review is still required.

### Screenshots

No browser screenshot is included because visual browser access was blocked during development. This is not a claim that responsive layouts have been visually validated. Follow [the manual review checklist](docs/MANUAL_QA.md) to capture desktop and mobile screenshots from the running application. `docs/sample_report.pdf` is a real generated report, not a UI mockup.

## Optional OpenAI configuration

All local functions work without an API key. To enable external processing:

1. In VS Code, open `.streamlit/` and create `secrets.toml`.
2. Add your key privately on your computer:

```toml
OPENAI_API_KEY = "your-private-key"
```

3. Restart the app. Open **Settings / About** and enable external AI processing for the current dataset.
4. Click an AI action only after reviewing what will be sent.

`OPENAI_API_KEY` can alternatively be an environment variable. `OPENAI_MODEL` sets the initial model; the default is `gpt-4.1-mini`. You can change it in Settings to a structured-output-compatible model available to your API project. A `.env` file is **not automatically loaded**. No key is included in this project.

The implementation follows the official [Responses API](https://developers.openai.com/api/reference/python/resources/responses) and [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). [Model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini) describes the default model; actual account access must be tested privately.

**Costs:** requests may incur API charges. Each session permits 10 attempts, no automatic retries, at least 3 seconds between calls, an 18,000-character input limit and 1,600 output tokens per call. Failed attempts also count. This is not a global spending limit: refreshing or starting another session can create a new allowance. Set provider project spending controls before hosting with a shared key. No paid API request was made during development.

### How AI stays separate from calculations

Pandas computes every displayed figure. Commentary receives only the displayed facts (including labels); its output must reference valid fact IDs, and numeric narrative is rejected. This catches invalid evidence references and numeric additions, **not every possible false verbal claim**. Commentary is explicitly unverified; hypotheses and recommendations are separated from observations.

For unsupported questions, the optional AI planner receives the question, column names/types and prior plan. It can propose a small JSON plan. The user reviews it; Pydantic and the executor validate it before trusted operations run. No `eval`, `exec`, shell or generated SQL exists in the execution path.

## Calculation rules

- `sum` excludes missing values; an entirely missing metric returns **N/A**, not zero.
- `count` means **records**, including rows whose metric is missing.
- `mean` and `median` use recorded numeric values.
- Group sums use `min_count=1`; missing categories have a distinct label.
- Shares require nonnegative observations and a positive denominator; sidebar filters define the population.
- Monthly charts preserve absent months as gaps. Partial months are not automatically comparable full periods.
- Correlations use at least three paired observations. Constant columns do not produce a correlation; correlation is not causation.
- IQR flags identify possible outliers, not errors to delete.
- Dates are inferred only from datetime columns or unambiguous ISO strings. Other formats require explicit conversion.
- Numeric conversions do not strip currency/commas until the user chooses those settings. Invalid conversions require explicit consent to become missing.
- Summing IDs, ages or rates may be inappropriate. Select the metric and aggregation deliberately.

## Architecture

```text
app.py                      Streamlit navigation, controls and session state
core/data_loader.py         Bounded file parsing and validation
core/data_cleaning.py       Pure transformations and reversible history replay
core/data_analysis.py       Filters, KPIs, profiles, trends and facts
core/chart_builder.py       Type-checked chart preparation and Plotly figures
core/chat_engine.py         Local grammar, structured plans and trusted executor
core/ai_service.py          Opt-in Responses API, schema validation and error handling
core/report_generator.py    CSV, Excel and PDF bytes; formula neutralization
sample_data/                Original sales + employee and text-only examples
assets/fonts/               Licensed bundled PDF fonts
legacy/                     Unmodified original app and README
scripts/                    Local sample-report generation
 tests/                     Core and Streamlit session tests
 docs/                      Architecture, audit, QA, deployment and portfolio notes
.streamlit/config.toml      Upload limit, telemetry preference and styling
.github/workflows/tests.yml CI definition; no deployment automation
```

See [architecture and major functions](docs/ARCHITECTURE.md) for the beginner-friendly explanation.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests do not require an API key. They mock external responses, preserve the original sales sample and exercise additional schemas. `requirements-lock.txt` records the exact fresh Python 3.12 environment used for validation; use it when reproducing that environment. Standard installation uses the smaller direct-dependency requirements files.

## Privacy and security

Uploaded rows are held in per-session state. The application does not write them to a database or put them in a cross-user data cache. Temporary working copies exist in process memory; hosting/browser/provider retention is outside these guarantees. Session reset is not a certified secure deletion mechanism. The app has no built-in login; enforce authentication at the hosting layer before exposing confidential data.

Credentials belong in environment variables or Streamlit secrets, never Git. `.gitignore` excludes both secrets and virtual environments. Formula-like spreadsheet text is prefixed with an apostrophe on export; CSV/Excel are safe display exports, not byte-identical source backups. Excel formulas are read as their cached values; formulas are not executed or recalculated.

## Limits and known gaps

- 15 MB uploaded bytes; 100,000 rows; 100 columns; 2 million cells; 80 MB estimated DataFrame memory. Expanded XLSX size is bounded to 80 MB. These do not guarantee constant peak process memory.
- 50 cleaning steps; last 30 chat messages; 500-value category picker (larger categories use exact-value text input).
- Scatter, histogram and box previews use the first 10,000 selected rows. Correlation uses the first 30 numeric columns. These limits are disclosed in the UI.
- Local chat supports a finite grammar; arbitrary natural language, numeric conditional filters and multi-dataset joins are not fully supported. Use sidebar filters, the structured form or a reviewed AI plan.
- AI interpretation is not guaranteed true. Evidence IDs and schemas do not prove semantic correctness.
- PDF includes a category-total chart, not every Plotly chart. PNG chart export uses the browser camera button; it requires manual browser validation. Complex-script PDF shaping is not guaranteed.
- No accounts, durable dataset storage, database, multi-tenant service isolation or global API-rate control.
- Browser screenshot/mobile checks, real API calls, Windows execution and deployment remain unverified. Python 3.12 installation and automated tests were run on Linux.

## Deployment and repository handoff

Read [DEPLOYMENT.md](docs/DEPLOYMENT.md) before hosting. Keep the repository private. No visibility, collaborator or hosting settings were changed. This ZIP is not a Git checkout and does not include your existing `.git` history.

To update the real repository later, create a new branch in your own clone and copy the reviewed files into it, keeping your `.git` folder and local secrets. Run the tests, inspect `git diff`, and commit the upgrade. Do not blindly copy this folder over your only original.

## Portfolio and next steps

[Portfolio case study and interview notes](docs/PORTFOLIO.md) explain the problem, technical decisions, regression evidence and limitations. [CHANGELOG.md](CHANGELOG.md) lists the upgrade. [AUDIT.md](docs/AUDIT.md) documents what was actually present in the uploaded source.

Future work: better natural-language coverage with evaluation datasets; optional persistent workspaces with authentication; richer multi-chart reports; additional date/locale formats; browser-based end-to-end tests; deployment-specific rate limiting.

Licensing: no new open-source license is granted by this upgrade. The repository owner should choose a license before public distribution. Bundled font licensing is included under `assets/fonts/`.
