"""Deterministic statistics with explicit missing-value and filter semantics."""
import re
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_datetime64_any_dtype, is_bool_dtype
from .data_loader import DataError

AGGREGATIONS = ('sum', 'mean', 'median', 'min', 'max', 'count')

def numeric_columns(df):
    return [c for c in df if is_numeric_dtype(df[c]) and not is_bool_dtype(df[c])]

def date_series(series):
    if is_datetime64_any_dtype(series):
        return pd.to_datetime(series, utc=True).dt.tz_localize(None)
    # Only unambiguous ISO dates are inferred. Other formats require explicit cleaning.
    if is_numeric_dtype(series):
        return None
    nonnull = series.dropna().astype(str)
    if nonnull.empty or not nonnull.str.match(r'^\d{4}-\d{2}-\d{2}(?:[ T].*)?$').all():
        return None
    parsed = pd.to_datetime(series, format='ISO8601', errors='coerce', utc=True).dt.tz_localize(None)
    return parsed if parsed[series.notna()].notna().all() else None

def date_columns(df):
    return [c for c in df if date_series(df[c]) is not None]

def category_columns(df):
    nums, dates = numeric_columns(df), date_columns(df)
    return [c for c in df if c not in nums and c not in dates]

def profile(df):
    entries = []
    for c in df:
        s = df[c]
        outliers = 0
        hint = ''
        if c in numeric_columns(df):
            q1, q3 = s.quantile(.25), s.quantile(.75)
            iqr = q3 - q1
            if pd.notna(iqr) and iqr > 0:
                outliers = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
        elif not is_datetime64_any_dtype(s):
            t = s.dropna().astype(str)
            if not t.empty:
                parsed = pd.to_numeric(t, errors='coerce')
                if parsed.notna().any():
                    hint = f'{int(parsed.notna().sum())}/{len(t)} nonmissing values look numeric; inspect before conversion.'
                if t.str.strip().str.casefold().nunique() < t.nunique():
                    hint += ' Possible whitespace/case variants.'
                if t.str.contains(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', regex=True).any() and date_series(s) is None:
                    hint += ' Possible date values; specify their format before conversion.'
        entries.append({'Column': c, 'Type': str(s.dtype), 'Missing': int(s.isna().sum()),
                        'Missing %': round(float(s.isna().mean() * 100), 2) if len(s) else 0,
                        'Unique': int(s.nunique()), 'Possible outliers (IQR)': outliers, 'Review': hint.strip()})
    return pd.DataFrame(entries)

def kpis(df, metric=None):
    base = {'records': len(df), 'missing_cells': int(df.isna().sum().sum()),
            'duplicate_rows': int(df.duplicated().sum())}
    if metric is not None:
        if metric not in numeric_columns(df):
            raise DataError('Select a numeric metric first.')
        s = df[metric].dropna()
        base.update(metric=metric, recorded=int(s.size), missing=int(df[metric].isna().sum()),
                    total=float(s.sum()) if len(s) else None, average=float(s.mean()) if len(s) else None,
                    median=float(s.median()) if len(s) else None,
                    minimum=float(s.min()) if len(s) else None, maximum=float(s.max()) if len(s) else None)
    return base

def aggregate(df, group, metric, operation='sum'):
    if group not in df or operation not in AGGREGATIONS:
        raise DataError('Choose a valid group and aggregation.')
    if operation != 'count' and metric not in numeric_columns(df):
        raise DataError('This aggregation needs a numeric metric.')
    # Convert labels for consistent missing-category handling without merging real labels.
    labels = df[group].astype('string')
    null_label = '(Missing)'
    while null_label in set(labels.dropna()):
        null_label += '*'
    labels = labels.fillna(null_label)
    if operation == 'count':
        result = df.groupby(labels, sort=False).size()
    else:
        grouped = df.groupby(labels, sort=False)[metric]
        result = grouped.sum(min_count=1) if operation == 'sum' else grouped.agg(operation)
    return pd.DataFrame({'Group': result.index.astype(str), 'Value': result.to_numpy()})

def filter_data(df, categories=None, date_column=None, start=None, end=None, include_missing=False):
    out = df
    for col, values in (categories or {}).items():
        if col not in df:
            raise DataError('A filter column is no longer available. Reset filters.')
        mask = out[col].astype('string').isin([str(v) for v in values if v is not None])
        if None in values:
            mask |= out[col].isna()
        out = out.loc[mask]
    if date_column:
        if date_column not in df:
            raise DataError('The date filter column no longer exists.')
        dates = date_series(out[date_column])
        if dates is None:
            raise DataError('Convert this column to dates before filtering.')
        mask = dates.notna()
        if start is not None:
            mask &= dates >= pd.Timestamp(start).normalize()
        if end is not None:
            mask &= dates < pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
        if include_missing:
            mask |= dates.isna()
        out = out.loc[mask]
    return out.copy()

def monthly(df, date, metric, operation='sum'):
    if date not in df or metric not in numeric_columns(df) or operation not in AGGREGATIONS:
        raise DataError('Choose a valid date column, numeric metric and aggregation.')
    ds = date_series(df[date])
    if ds is None:
        raise DataError('This column contains ambiguous or invalid dates. Convert it first.')
    temp = pd.DataFrame({'Date': ds, 'Value': df[metric]}).dropna(subset=['Date']).set_index('Date')
    if temp.empty:
        return pd.DataFrame(columns=['Month', 'Value'])
    group = temp['Value'].resample('MS')
    result = group.sum(min_count=1) if operation == 'sum' else (group.size() if operation == 'count' else group.agg(operation))
    # Empty months are gaps even for count, not fabricated observations.
    result = result.where(group.size() > 0)
    return result.rename_axis('Month').reset_index(name='Value')

def correlation_pairs(df):
    cols = numeric_columns(df)[:30]
    corr = df[cols].corr(min_periods=3)
    records = []
    for i, a in enumerate(cols):
        for b in cols[i+1:]:
            if pd.notna(corr.loc[a, b]):
                records.append({'Column A': a, 'Column B': b, 'Correlation': float(corr.loc[a, b]),
                                'Paired records': int(df[[a, b]].dropna().shape[0])})
    return pd.DataFrame(records, columns=['Column A', 'Column B', 'Correlation', 'Paired records']).sort_values('Correlation', key=abs, ascending=False)

def facts(df, metric=None, group=None, date=None):
    values = kpis(df, metric)
    findings = [f'The current selection contains {len(df):,} records and {len(df.columns)} columns.',
                f'There are {values["missing_cells"]:,} missing cells and {values["duplicate_rows"]:,} duplicate rows.']
    if metric:
        findings.append(f'{metric}: {values["recorded"]:,} recorded values and {values["missing"]:,} missing values.')
        if values['total'] is not None:
            findings.append(f'Recorded {metric} totals {values["total"]:,.2f}; mean {values["average"]:,.2f}; median {values["median"]:,.2f}.')
        if group and not df.empty:
            table = aggregate(df, group, metric).dropna(subset=['Value']).sort_values('Value', ascending=False)
            if not table.empty:
                top = table.iloc[0]
                findings.append(f'{group} category {top["Group"]!r} has the highest recorded {metric} total: {top["Value"]:,.2f}.')
                if values['total'] and values['total'] > 0 and (df[metric].dropna() >= 0).all():
                    findings.append(f'That category represents {100 * top["Value"] / values["total"]:.2f}% of recorded {metric}.')
        if date:
            t = monthly(df, date, metric)
            if len(t) >= 2:
                a, b = t.iloc[-2], t.iloc[-1]
                if pd.notna(a.Value) and pd.notna(b.Value):
                    findings.append(f'The last two calendar months ({a.Month:%Y-%m}, {b.Month:%Y-%m}) differ by {b.Value-a.Value:,.2f} in recorded {metric}; periods may be incomplete.')
    pairs = correlation_pairs(df)
    if not pairs.empty:
        r = pairs.iloc[0]
        findings.append(f'Strongest absolute Pearson correlation: {r["Column A"]} and {r["Column B"]}, r={r.Correlation:.3f}, using {r["Paired records"]} paired records. Correlation is not causation.')
    return [{'id': f'F{i+1}', 'text': text} for i, text in enumerate(findings)]
