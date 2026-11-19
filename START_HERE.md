# InsightAI — merged responsive and dark-mode edition

## Update your Windows project

1. Stop the running app with Ctrl+C and make a backup copy of your project folder.
2. Extract this ZIP into a separate folder and open the extracted `insightai` folder.
3. Copy its contents into your existing project folder, accepting replacement of matching files. Include `.streamlit` and `.github`. Do not nest the outer insightai folder inside the project.
4. Keep your existing `.venv`, `.git` and private `.streamlit/secrets.toml`. None of those are included in this ZIP.
5. Open the existing project in VS Code and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Restart the server after updating configuration. A browser refresh alone is insufficient.

## Dark mode

Open the **⋮ menu in the app's top-right corner**, then choose **Dark**, **Light**, or **System**. Both light and dark palettes are configured, including the sidebar. The sidebar Appearance section provides guidance; the actual selector is in the native app menu. No API key is required.

## Fresh setup

If using a new folder without an environment, run `py -3.12 -m venv .venv` first, then the two commands above.

## What was merged

- Retained the latest header/navigation and desktop/tablet/mobile responsive code already present in your uploaded ZIP.
- Added native light/dark palettes and visible Appearance guidance.
- Restored the .streamlit configuration and GitHub test workflow.
- Preserved the uploaded core modules, dependencies and sample datasets.
- Relocated both backup app files to legacy/; app.py remains the active entrypoint.

Browser appearance and live OpenAI requests remain unverified. Nothing was deployed or pushed to GitHub. See docs/MERGE_REPORT.md for validation.
