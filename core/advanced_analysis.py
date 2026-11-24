"""InsightAI 2.0: deterministic, dataset-agnostic analytical evidence.

This module never calls an AI API. All results come from the filtered DataFrame,
with explicit missing-data handling and guards for unsafe percentage calculations.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .data_analysis import aggregate, date_series, monthly, numeric_columns
from .data_loader import DataError


def _plain(value: Any):
    """Convert pandas scalars into ordinary JSON-friendly Python values."""
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, 'item') else value


def advanced_report(df: pd.DataFrame, metric: str | None = None,
                    group: str | None = None, date: str | None = None,
                    top_n: int = 10) -> dict:
    """Calculate descriptive, comparative and quality metrics, without inference.

    Percent contribution is deliberately unavailable if the observed metric has
    negative values or a nonpositive total. Period percentage change requires
    a positive baseline. Calendar months are never assumed complete.
    """
    if metric is not None and metric not in numeric_columns(df):
        raise DataError('Advanced insights require a valid numeric metric.')
    if group is not None and group not in df:
        raise DataError('Choose an existing breakdown column.')
    if date is not None and date not in df:
        raise DataError('Choose an existing date column.')
    if not 1 <= top_n <= 50:
        raise DataError('Select between 1 and 50 categories.')

    n_rows, n_cols = df.shape
    missing_count = int(df.isna().sum().sum())
    missing_columns = sorted(
        ({'column': str(col), 'missing': int(df[col].isna().sum()),
          'pct': (100 * float(df[col].isna().sum()) / n_rows if n_rows else None)}
         for col in df.columns if df[col].isna().any()),
        key=lambda x: (-x['missing'], x['column']))
    quality = {'rows': n_rows, 'columns': n_cols, 'missing_cells': missing_count,
               'missing_pct': 100 * missing_count / (n_rows * n_cols) if n_rows and n_cols else None,
               'rows_with_missing': int(df.isna().any(axis=1).sum()),
               'duplicate_rows': int(df.duplicated().sum()),
               'missing_by_column': missing_columns}

    measure = None
    outliers = None
    if metric is not None:
        values = df[metric].dropna()
        finite = pd.to_numeric(values, errors='coerce')
        finite = finite[finite.map(math.isfinite)]
        measure = {'column': metric, 'observed': int(len(finite)),
                   'missing': int(df[metric].isna().sum()),
                   'total': float(finite.sum()) if not finite.empty else None,
                   'average': float(finite.mean()) if not finite.empty else None,
                   'median': float(finite.median()) if not finite.empty else None}
        if len(finite) >= 4:
            q1, q3 = float(finite.quantile(.25)), float(finite.quantile(.75))
            iqr = q3 - q1
            if iqr > 0:
                lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                outliers = {'column': metric, 'flagged': int(((finite < lower) | (finite > upper)).sum()),
                            'observed': len(finite), 'lower_bound': lower, 'upper_bound': upper,
                            'method': 'Tukey IQR (1.5 × IQR)',
                            'caution': 'Potential outliers are not automatically data errors.'}

    categories = None
    if metric is not None and group is not None and n_rows:
        grouped = aggregate(df, group, metric, 'sum')
        counts = aggregate(df, group, metric, 'count').rename(columns={'Value': 'Records'})
        grouped = grouped.merge(counts, on='Group', how='left', validate='one_to_one')
        grouped = grouped.loc[grouped['Value'].notna()].sort_values(['Value', 'Group'], ascending=[False, True])
        total = measure['total'] if measure else None
        eligible = bool(total is not None and total > 0 and (df[metric].dropna() >= 0).all())
        items = [{'category': str(row.Group), 'total': float(row.Value),
                  'records': int(row.Records),
                  'contribution_pct': 100 * float(row.Value) / total if eligible else None}
                 for row in grouped.head(top_n).itertuples(index=False)]
        bottom = ({'category': str(grouped.iloc[-1]['Group']),
                   'total': float(grouped.iloc[-1]['Value'])} if not grouped.empty else None)
        categories = {'column': group, 'metric': metric,
                      'categories_with_values': len(grouped), 'showing': len(items),
                      'top': items, 'bottom': bottom,
                      'shares_available': eligible,
                      'share_note': 'Shares require nonnegative observed values and a positive recorded total.'
                                    if not eligible else 'Shares use the total of all recorded nonmissing metric values; not just displayed groups.'}

    periods = None
    if metric is not None and date is not None:
        parsed = date_series(df[date])
        if parsed is None:
            raise DataError('Date comparisons require recognized dates; clean ambiguous dates first.')
        by_month = monthly(df, date, metric, 'sum')
        rows = [{'month': row.Month.strftime('%Y-%m'), 'total': _plain(row.Value)}
                for row in by_month.itertuples(index=False)]
        comparison = None
        if len(rows) >= 2:
            previous, current = rows[-2], rows[-1]
            if previous['total'] is not None and current['total'] is not None:
                delta = current['total'] - previous['total']
                baseline = previous['total']
                comparison = {'previous_month': previous['month'], 'current_month': current['month'],
                              'previous_total': previous['total'], 'current_total': current['total'],
                              'absolute_change': delta,
                              'percentage_change': 100 * delta / baseline if baseline > 0 else None,
                              'pct_note': ('Percent change omitted: previous period total is zero or negative.'
                                           if baseline <= 0 else None)}
        periods = {'date_column': date, 'metric': metric, 'months': rows,
                   'comparison': comparison,
                   'caution': 'Calendar periods may be incomplete; source completeness has not been verified.'}

    return {'quality': quality, 'measure': measure, 'categories': categories,
            'periods': periods, 'outliers': outliers}


def extra_facts(report: dict, next_id: int = 1) -> list[dict[str, str]]:
    """Convert new verified calculations into evidence IDs for the existing Gemini flow."""
    result: list[dict[str, str]] = []

    def add(message):
        result.append({'id': f'F{next_id + len(result)}', 'text': message})

    q = report['quality']
    if q['missing_pct'] is not None:
        add(f'{q["missing_cells"]:,} of {q["rows"] * q["columns"]:,} data cells are missing ({q["missing_pct"]:.2f}%); '
            f'{q["rows_with_missing"]:,} of {q["rows"]:,} records contain at least one missing cell.')
    c = report['categories']
    if c and c['top']:
        top = c['top'][0]
        text = (f'Highest recorded {c["metric"]} by {c["column"]}: {top["category"]!r}, '
                f'{top["total"]:,.2f} across {top["records"]:,} rows.')
        if top['contribution_pct'] is not None:
            text += f' Its contribution is {top["contribution_pct"]:.2f}% of the recorded total.'
        add(text)
        if len(c['top']) > 1 and c['bottom']:
            low = c['bottom']
            add(f'Lowest recorded {c["metric"]} by {c["column"]}: {low["category"]!r} '
                f'with {low["total"]:,.2f}. Missing-only categories are excluded from rankings.')
    p = report['periods']
    if p and p['comparison']:
        co = p['comparison']
        text = (f'Recorded {p["metric"]} changed by {co["absolute_change"]:,.2f} '
                f'from {co["previous_month"]} to {co["current_month"]}.')
        if co['percentage_change'] is not None:
            text += f' This is {co["percentage_change"]:+.2f}% relative to the previous recorded month.'
        text += ' Both calendar periods may be incomplete; do not assume changes reflect business performance.'
        add(text)
    outliers = report['outliers']
    if outliers:
        add(f'The {outliers["column"]} metric has {outliers["flagged"]:,} potential IQR outliers among '
            f'{outliers["observed"]:,} recorded values (lower fence {outliers["lower_bound"]:,.2f}, '
            f'upper fence {outliers["upper_bound"]:,.2f}). These are review flags, not confirmed errors.')
    return result
