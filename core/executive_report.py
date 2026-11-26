"""InsightAI Phase 4: evidence-first, provider-independent executive reporting.

Only the passed (already filtered) DataFrame is analysed. Every number comes
from the Phase 2 deterministic engine, not Gemini. Priorities are transparent
heuristics for review, *not* business-risk scores or statistical significance.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .advanced_analysis import advanced_report


_PRIORITY_ORDER = {'High': 0, 'Medium': 1, 'Low': 2}


def _fmt(value: Any) -> str:
    return f'{value:,.2f}'


def executive_report(df: pd.DataFrame, metric: str | None = None,
                     group: str | None = None, date: str | None = None) -> dict:
    """Return a source-scoped executive summary with explicit analytic cautions.

    This function performs no external requests, predicts nothing, and never
    mutates the supplied DataFrame. Periods are not presumed complete.
    """
    raw = advanced_report(df, metric=metric, group=group, date=date)
    q, m, c, p, o = (raw[key] for key in
                      ('quality', 'measure', 'categories', 'periods', 'outliers'))
    cards = [
        {'label': 'Selected records', 'value': q['rows'], 'kind': 'count',
         'note': 'Rows after the current shared filters.'},
        {'label': 'Missing cells', 'value': q['missing_cells'], 'kind': 'count',
         'note': 'Missing cells in selected records; not imputed.'},
        {'label': 'Duplicate rows', 'value': q['duplicate_rows'], 'kind': 'count',
         'note': 'Exact duplicate rows, not duplicate identifiers.'},
    ]
    headlines = []
    if m and m['observed']:
        cards.insert(1, {'label': f'Recorded total · {metric}', 'value': m['total'],
                         'kind': 'metric',
                         'note': f'From {m["observed"]:,} nonmissing observed values; not necessarily revenue.'})
        headlines.append(f'{metric}: {_fmt(m["total"])} recorded across {m["observed"]:,} nonmissing observations.')
    else:
        headlines.append(f'{q["rows"]:,} selected records and {q["columns"]:,} fields were analysed.')
    if q['missing_cells']:
        headlines.append(f'{q["missing_cells"]:,} data cells are missing across {q["rows_with_missing"]:,} records.')

    actions = []

    def recommend(priority: str, title: str, evidence: str, next_step: str, code: str):
        actions.append({'priority': priority, 'title': title, 'evidence': evidence,
                        'next_step': next_step, 'code': code, 'origin': 'Rule-based review suggestion'})

    if q['missing_cells']:
        recommend('Medium' if q['missing_pct'] is None or q['missing_pct'] < 5 else 'High',
                  'Review incomplete records',
                  f'{q["missing_cells"]:,} of {q["rows"] * q["columns"]:,} cells are missing '
                  f'({q["missing_pct"]:.2f}% of selected cells).' if q['missing_pct'] is not None
                  else 'Missing values are present.',
                  'Check the source records and identify whether missingness affects the chosen metric or comparisons.',
                  'missing')

    if c and c['top']:
        leader = c['top'][0]
        if leader['contribution_pct'] is not None:
            headlines.append(f'Top {group}: {leader["category"]} contributes '
                             f'{leader["contribution_pct"]:.2f}% of recorded {metric}.')
            if leader['contribution_pct'] >= 50 and c['categories_with_values'] > 1:
                recommend('Medium', 'Examine category concentration',
                          f'{leader["category"]}: {leader["contribution_pct"]:.2f}% of recorded {metric}.',
                          'Verify category coverage and compare changes in the leading group against alternatives before making allocation decisions.',
                          'concentration')
        else:
            headlines.append(f'Top recorded {metric} group: {leader["category"]}, {_fmt(leader["total"])}.')
    if p:
        months = p['months']
        if any(row['total'] is None for row in months):
            recommend('Medium', 'Review missing calendar periods',
                      'At least one calendar month has no recorded metric values in the selected time range.',
                      'Check the source records and filtering before interpreting gaps or applying forecasts.',
                      'gap')
        comp = p['comparison']
        if comp:
            difference = _fmt(comp['absolute_change'])
            pct = (f' ({comp["percentage_change"]:+.2f}%)'
                   if comp['percentage_change'] is not None else '')
            headlines.append(f'Recorded {metric} changed by {difference}{pct} between '
                             f'{comp["previous_month"]} and {comp["current_month"]}; period completeness is unverified.')
            recommend('Low', 'Validate the latest period comparison',
                      f'{comp["previous_month"]} to {comp["current_month"]}: '
                      f'{difference} recorded change{pct}.',
                      'Confirm both calendar months are complete and comparable before treating the difference as a performance trend.',
                      'period')
    if o and o['flagged']:
        recommend('Low', 'Review potential numeric outliers',
                  f'{o["flagged"]:,} of {o["observed"]:,} recorded {metric} values fall outside the Tukey IQR review bounds.',
                  'Inspect unusual observations and their contexts; do not remove flagged values automatically.',
                  'outliers')

    # Priorities describe a rule-based audit order, not severity, impact or causation.
    actions.sort(key=lambda item: (_PRIORITY_ORDER[item['priority']], item['code']))
    if not actions:
        recommend('Low', 'Confirm the analytical scope',
                  f'{q["rows"]:,} records are included in the current selection.',
                  'Confirm that the selected records and metric represent the question before drawing business conclusions.',
                  'scope')

    cautions = [
        'This report describes the selected records only; filters may not represent the full population.',
        'Recorded totals exclude missing metric values. A row is not necessarily a transaction.',
        'Review priorities are transparent rules for investigation, not proven causes or measured business risks.',
    ]
    if metric is None:
        cautions.append('No numeric metric selected; financial or quantitative performance comparisons are unavailable.')
    if p is not None:
        cautions.append(p['caution'])
    if c and not c['shares_available']:
        cautions.append(c['share_note'])
    return {
        'cards': cards,
        'headlines': headlines[:5],
        'actions': actions[:6],
        'cautions': cautions,
        'quality': q,
        'measure': m,
        'category_rows': [] if not c else c['top'],
        'category_name': group,
        'category_note': None if not c else c['share_note'],
        'period_rows': [] if not p else p['months'],
        'period_note': None if not p else p['caution'],
        'scope': {'metric': metric, 'group': group, 'date': date, 'records': q['rows']},
    }
