# Deployment preparation — approval still required

No app has been deployed. No private repository settings or account permissions were changed. Local verification is not proof of hosted behavior.

## Before deploying

1. Review the upgraded files in a new branch of the real private repository.
2. Run `python -m pytest -q` in the project's virtual environment.
3. Complete the desktop/mobile checklist in `MANUAL_QA.md`.
4. If AI is needed, configure your own key privately and test one deliberate request after reviewing cost and data-disclosure settings. Live API access was not tested here.
5. Confirm the approved hosting destination, its authentication model and who may access the app. Do not change repository visibility to solve an access problem.

## Streamlit Community Cloud: private deployment path

Current official instructions (checked 15 November 2026):

- [Deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Private/public sharing](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)
- [App settings and secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-settings)
- [Connect GitHub](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/connect-your-github-account)

After the owner approves deployment, sign in at [share.streamlit.io](https://share.streamlit.io), connect the appropriate GitHub account and authorize access to the private repository. Account authorization must be completed by the owner; no credentials should be pasted into chat or committed.

Choose **Create app**, select the private repository and reviewed branch, and set the entrypoint to **app.py**. In advanced settings choose **Python 3.12**. Add `OPENAI_API_KEY` to the platform's Secrets field only if AI is desired; the app works without it. The platform uses the root `requirements.txt`.

Official documentation says apps inherit initial privacy from their repository and permits only one private app at a time. After deployment, explicitly check **Settings → Sharing → Who can view this app → Only specific people can view this app**. Confirm the actual account's limits before proceeding. If a private-app allowance blocks you, stop and choose another approved private hosting arrangement; do not make an existing app public or delete it automatically.

Do not add viewers or send invitations without separate authorization. A private repository alone is not a substitute for checking the live app's access settings.

## Post-deployment verification

- Open the approved deployed URL while authenticated and verify the sales sample.
- Open it in a signed-out browser and confirm restricted access.
- Verify the eight Lagos records, NGN 9.14m revenue and NGN 7.43m laptop revenue.
- Test CSV and multi-sheet XLSX uploads using fictional data.
- Test cleaning preview, apply, undo/reset and empty filter results.
- Test local chat with no API key; then one deliberate AI request if enabled.
- Download CSV, Excel, PDF and a chart PNG.
- Review the mobile layout and two independent browser sessions.
- Record the real URL only after verifying it. No live URL is supplied in this project.

## Other hosting

Use Python 3.12, install `requirements.txt` and run:

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Bind publicly only inside an approved deployment with authentication/access controls and TLS provided by the hosting layer. The app itself has no login. Keep XSRF/CORS protections enabled. Health endpoint: `/_stcore/health`. Sample data and bundled fonts must be present alongside the code.

Deploy with host-level memory/concurrency limits and global API controls before a shared-key multi-user release. Session-only request caps are insufficient against multiple new sessions. For a local machine demo, keep the default local access.

## Rollback and repository safety

The upload was a ZIP, not a full Git checkout. Existing Git history has not been altered. Use a branch in the original clone; do not replace its `.git` directory. The `legacy/` files preserve the uploaded app and README. Revert the upgrade commit through normal Git workflow if necessary; do not rewrite history. Restore old source only after checking that its dependencies and model configuration still work.
