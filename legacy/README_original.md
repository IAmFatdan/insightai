# InsightAI (v0.1)

A beginner-friendly, Python-based data analytics dashboard. Upload a CSV file or explore an included example dataset. The app displays dataset size, missing values, duplicate records, a data preview, numeric summary statistics, and a quick bar chart.

> **Project stage:** This version is a data exploration foundation. AI capabilities have **not** been added yet.

## Requirements

- Python (recommended 3.12 or 3.13)
- A terminal (e.g., PowerShell in VS Code)

## Quick start on Windows (PowerShell)

From the folder containing `app.py`, run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

A new browser tab should open with the app. If it doesn't, visit the local URL printed in the terminal (often `http://localhost:8501`). Press Ctrl+C in the terminal to stop the app.

## Quick start on macOS/Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## How to use

1. The dashboard starts with the sample sales dataset.
2. Upload your own `.csv` file using the left sidebar to analyze your data instead.
3. Read the metrics, preview, data quality check, statistics, and bar chart.
4. Try changing the numeric column in the chart's dropdown.

## File structure

```text
insightai-starter/
├── app.py                 # Streamlit user interface and data analysis
├── requirements.txt       # Python libraries to install
├── sample_data/
│   └── sales.csv          # Fake sample sales data
├── .gitignore             # Files Git should ignore
└── README.md              # These instructions
```

## Important notes

- The included sales figures are **fictional**, for testing.
- Do not upload confidential business, customer, or personal datasets to a publicly deployed app without appropriate data protection.
- `.csv` only for now; Excel and AI-generated insights are future milestones.

## Next milestones

- Add interactive breakdowns and visualizations by category and date.
- Add safe AI-generated explanations grounded in computed statistics.
- Add data download and export.
- Add tests, polish the UI, and deploy a live demo.

## Built with

Python, Streamlit, Pandas.
