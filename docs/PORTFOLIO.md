# Portfolio case study and interview notes

## Project description

InsightAI is a Python and Streamlit analytics application that turns uploaded CSV and Excel data into inspectable statistics, reversible cleaning steps, interactive charts and downloadable reports. Optional OpenAI integration interprets computed findings or proposes validated analytical plans. Deterministic local questions remain available without an API key.

## Problem and approach

Beginners can calculate a total yet struggle to establish what it includes, whether missing values were lost, or whether a chart reflects the same selection. InsightAI brings these tasks into a shared workspace with visible data quality, explicit transformations and consistent filters.

The project grows an existing sales dashboard into a schema-flexible tool. Keeping Streamlit and Pandas makes it possible to explain the code in an internship interview without relying on a complex infrastructure stack.

## Technical contributions to discuss after studying the code

- Refactoring a monolithic dashboard into independently testable functions.
- Preserving the original file and replaying a cleaning recipe for undo/reset.
- Defining missing-value, percentage-denominator and monthly-gap semantics.
- Validating model-proposed plans instead of executing generated code.
- Keeping AI commentary visibly separate from calculated facts.
- Producing auditable exports with filter context and formula-injection precautions.
- Testing regressions against the original data and exercising nonsales datasets.

## Evidence, not invented impact

The sample has 24 records and two missing cells. Lagos recorded revenue is NGN 9.14 million; laptops contribute NGN 7.43 million, or 81.29%. These are fictional sample-data results, not customer outcomes or real business impact.

Do not claim deployed users, production adoption, cost savings, time savings or model accuracy percentages: none were measured. Development used AI assistance; explain the code you understand and distinguish assistance from work you personally verified.

## Short interview explanation

“InsightAI helps users inspect tabular data, make reversible cleaning changes and explore consistent dashboards. Pandas calculates the numbers, Plotly draws the charts, and Streamlit manages the interface. Optional AI interprets a small set of computed facts; it never executes arbitrary code. I can demonstrate the logic using the original Lagos revenue regression and show how a missing value differs from zero.”

## Questions to practise

**Why not fill all missing revenue with zero?** Missing means unknown. Zero is a recorded amount. Treating them as equivalent can understate averages and conceal data-quality problems.

**How does undo work?** Remove the last transformation from the recipe and replay the remaining actions on the unchanged original.

**How do you prevent stale chat answers?** Dataset and analysis-context fingerprints clear chat/results when source data, cleaning or filters change.

**Can the AI still make mistakes?** Yes. Schemas and evidence references reduce certain failures but do not guarantee truthful interpretations. Flexible plans require review, and narrative remains labelled as AI commentary.

**What would you improve before a public multi-user service?** Authentication, host-level access control and rate limits, concurrency/resource testing, deployment observability, browser end-to-end tests and a real-model evaluation set.

**What should you demonstrate first?** Upload or use the sales sample, inspect missing data, apply/undo a cleaning step, filter Lagos, verify revenue, ask the laptop-share question and export the report.
