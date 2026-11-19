# InsightAI architecture and calculation guide

## The route from file to answer

The uploader supplies bytes. `load_data` validates their format/size and creates a DataFrame. The untouched original stays in Streamlit session state. `clean` makes a copy for each preview; applied actions form a recipe. `replay` starts with the original and reapplies the recipe when the user undoes or resets changes.

The working DataFrame feeds `filter_data`. That filtered selection is shared by KPI cards, chart preparation, calculated insights, chat and report generation. There is no separate hidden “AI dataset.” Every local answer uses the current selection.

A dataset fingerprint and analysis-context fingerprint invalidate conversations and generated reports when the underlying scope changes. Otherwise, old answers could look current even after a user switched from Lagos to Abuja.

## Why this design

Streamlit is retained because it already ran the user's original application and keeps the project approachable. A separate frontend/API/database would add maintenance work without solving the core portfolio problem. Pure functions in `core/` let calculations be tested independently from the UI.

History stores transformation instructions rather than dozens of full DataFrame snapshots. Original and current frames still consume memory, and preview/export operations allocate working copies. File/cell/history limits bound ordinary use, not adversarial peak memory across many users.

Session data is deliberately not globally cached. Dataset parsing only repeats when file bytes, parser settings or sheet selection change. Profiles/charts are recomputed in the current session. For a multi-user deployment, benchmark real workloads and add hosting-level resource/usage controls.

## Major functions

| Function | Responsibility | Important invariant |
|---|---|---|
| `load_data` | Parse CSV/XLSX bytes | No uploaded file is executed or saved to disk |
| `validate_frame` | Check shape, headers, memory, infinity | A rejected frame never replaces the current dataset |
| `clean` | Preview one transformation and return its summary | Input frame remains unchanged |
| `replay` | Rebuild the working copy from a recipe | Undo removes one recipe step |
| `filter_data` | Apply exact categories and inclusive date ranges | Empty selection remains empty |
| `kpis` | Record counts and recorded-value statistics | All-missing totals are `None` |
| `aggregate` | Category statistics | Missing categories are retained; sums preserve missing totals |
| `monthly` | Calendar-month aggregation | Months with no rows remain gaps |
| `facts` | Build deterministic, numbered findings | No LLM calculates the numbers |
| `build_chart` | Validate column combinations and prepare chart data | Invalid combinations return an understandable error |
| `infer_plan` | Interpret the limited local question grammar | Unsupported clauses should request clarification, not silently execute |
| `execute_plan` | Validate and run allowed analytical operations | No generated code, SQL or shell execution |
| `AIService.explain` | Request structured commentary | Opt-in, bounded input/output, valid fact references |
| `AIService.propose` | Suggest a JSON calculation plan | Human review precedes execution |
| `csv_bytes` / `excel_bytes` | Export in-memory selections | Spreadsheet formula-like text is neutralized |
| `pdf_bytes` | Build a paginated evidence report | Scope and limitations travel with the figures |

## Sales regression in plain English

Filter `Region` to Lagos. There are eight records. Add their recorded `Revenue_NGN` values: NGN 9,140,000. Within that selection, the three Laptop rows total NGN 7,430,000. Divide the laptop total by all recorded Lagos revenue and multiply by 100: 81.2910…%, displayed as 81.29%.

This is revenue concentration, not profit, causation, or a forecast. The original entire dataset has one missing revenue value outside Lagos and one missing region. Missing revenue is never automatically zero.

## The AI trust boundary

The model can select a structured operation or interpret supplied evidence. It cannot supply a new Python function. Pydantic rejects extra fields and wrong types; the executor checks real columns, filter values, aggregation names and percentage denominators. A valid JSON plan can still misunderstand a question, so flexible AI plans require human review.

AI narrative is not a verified result. Fact IDs must exist and numeric narrative is rejected, but words can still mislead. Separate sections make hypotheses/recommendations visible as such. Real model evaluation remains future validation; mocked tests establish failure handling and contract checks only.

## What is intentionally absent

No background workers, database, account system, vector database, generated SQL, persistent raw-data cache or automatic publication. The project is a local/controlled-hosting portfolio application, not a fully hardened multi-tenant analytics service.
