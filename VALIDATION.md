# Phase 4 validation

- Input baseline: previously shared Phase 3 files, overlaid on the Phase 2 analytics release.
- Core tests: `pytest -q --ignore=tests/test_ui.py` → **106 passed**.
- Python syntax: `py_compile` → passed.
- Sample sales dataset: 24 records, 23 recorded revenue values, 18,285,000 recorded Revenue_NGN, 2 missing cells, Laptop 71.15%, last two recorded months −730,000 / −17.87% (incompleteness caveat retained).
- Manual PDF verification: report rendered to 3 pages; headings and action paragraphs remain together; source facts and limitations are legible.
- Exported workbook: Executive KPIs, Review priorities, Category performance, Monthly evidence, Executive limitations; formula-like category names neutralized.
- Existing `core/ai_service.py`: unchanged, preserving Gemini/OpenAI setup, error handling, and `max_retries=2`.
- Existing call signatures `pdf_bytes(...)` and `excel_bytes(...)` remain backwards compatible.
- Streamlit interface tests and actual app interactions: **not run here** (Streamlit is not installed in the packaging environment). Must run locally before deployment.
- No GitHub or Streamlit Cloud mutation performed.
