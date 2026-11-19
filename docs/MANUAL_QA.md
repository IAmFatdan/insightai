# Manual browser and release review

The automated Streamlit tests run the actual app script and widget/session behavior. They do not establish browser rendering, JavaScript chart export or mobile layout quality.

Use fictional datasets for these checks. Mark actual results and attach screenshots only after observing them. Do not label this checklist as passed until performed.

## Desktop and mobile

- [ ] Open Home at desktop width (about 1440 px); verify typography, cards and data preview.
- [ ] Open all eight navigation areas; check sidebar scrolling and keyboard focus.
- [ ] Repeat at 390 px and 768 px widths; verify sidebar open/close, card stacking, forms, downloads and chat input.
- [ ] Test light/dark themes and text contrast.
- [ ] Hover every chart type, change controls and export PNG using the camera icon.
- [ ] Capture Home, a Lagos dashboard, Cleaning and Chat screenshots for the README.

## Files and cleaning

- [ ] Upload CSV; upload an XLSX with at least two sheets and switch sheets.
- [ ] Confirm a bad file shows a useful error and valid upload recovers.
- [ ] Test UTF-8 and Windows-1252 with comma/semicolon delimiters.
- [ ] Preview a fill, apply, undo, reset; original should remain unchanged.
- [ ] Try a failed numeric/date conversion with consent off, then on.
- [ ] Remove all records using an intentional cleaning action, then reset.
- [ ] Try an employee dataset and a text-only survey.

## Filters, chat and exports

- [ ] Filter Lagos: eight records; NGN 9,140,000 total; NGN 7,430,000 laptop total.
- [ ] Select no category values; show an empty state rather than all data.
- [ ] Verify inclusive last-day date filtering and missing-date option.
- [ ] Ask “total revenue in Lagos”; follow with “what about Abuja?”
- [ ] Ask the laptop-share question within Lagos; expect 81.29%.
- [ ] Ask an unsupported question; expect guidance rather than an invented answer.
- [ ] Change filters/dataset; old conversation and exports should clear.
- [ ] Download the full cleaned CSV, filtered CSV, Excel and PDF; compare their scope.
- [ ] Check long labels, negative amounts and non-Latin text in reports.

## Optional AI — may incur charges

- [ ] Confirm no API request occurs while external AI is disabled.
- [ ] Configure a private API key locally, enable consent and deliberately generate one explanation.
- [ ] Confirm numeric facts stay in calculated cards; narrative appears in separate labelled sections.
- [ ] Request a plan for an unsupported question; review columns/filters before running it.
- [ ] Check invalid-key, quota, unavailable-model and connectivity errors without exposing secrets.
- [ ] Switch datasets; consent should be disabled again and the session attempt count retained.

## Hosting

- [ ] Complete explicit deployment approval and platform authentication.
- [ ] Verify signed-out visitors cannot access a private app.
- [ ] Confirm two sessions do not see each other's uploads/chat.
- [ ] Test resource limits and global API usage controls for the intended audience.
