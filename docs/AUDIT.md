# Source audit

Input: `insightai-main.zip`, archive comment `27e20107dc670a06a5c9ff63e4a290a33a2158e8`.

The archive contained `app.py`, `README.md`, `requirements.txt`, `.gitignore`, and `sample_data/sales.csv`. It did not contain a chat module, automated tests, Excel loading, report exports, modular core, or deployment workflow. No `.git` history or API secrets were present in the supplied archive.

The app identified itself as v0.3.1; its README still described v0.1 and claimed AI was absent. Actual code included optional OpenAI Responses calls, hardcoded to a model ID, plus useful error diagnostics. Requirements were unpinned `streamlit`, `pandas`, `openai`.

Preserved behavior: sample-data loading, preview, row/column/missing/duplicate counts, recorded revenue validation, region filtering, revenue/product comparisons, KPI cards, numeric summary, computed facts and optional AI commentary. Sales results are protected by regression tests.

Changes: automatic filling of missing regions is replaced by an explicit reversible action; currency conversion is explicit and previewable. The original app is retained under `legacy/app_v0_3_1.py` for comparison, not used as a second production entrypoint. Its historical model choice is preserved only in that backup.

Private GitHub access returned 404 earlier in the conversation. The uploaded ZIP was used as the actual source. No remote branch was changed, no commit history was fabricated and nothing was deployed.
