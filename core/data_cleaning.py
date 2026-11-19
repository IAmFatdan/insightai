"""Explicit transformations; history replays from the unchanged original."""
import re
import numpy as np
import pandas as pd
from .data_analysis import numeric_columns
from .data_loader import DataError, validate_frame

OPERATIONS = ('Remove duplicate rows', 'Drop rows with missing values', 'Fill categorical missing',
              'Fill numeric missing (mean)', 'Fill numeric missing (median)', 'Trim whitespace',
              'Normalize category case', 'Standardize column names', 'Convert to number', 'Convert to date')

def clean(df, action):
    operation = action.get('operation')
    cols = action.get('columns', [])
    if operation not in OPERATIONS or any(c not in df for c in cols):
        raise DataError('Select a supported cleaning action and valid columns.')
    if operation not in ('Remove duplicate rows', 'Standardize column names') and not cols:
        raise DataError('Select at least one column.')
    out = df.copy(deep=True)
    rejected = 0
    if operation == 'Remove duplicate rows':
        out = out.drop_duplicates()
    elif operation == 'Drop rows with missing values':
        out = out.dropna(subset=cols)
    elif operation == 'Standardize column names':
        names = [re.sub(r'[^\w]+', '_', str(c).strip().lower()).strip('_') or 'column' for c in out]
        if len(set(names)) != len(names):
            raise DataError('Standardization would create duplicate column names. Rename headers in the source first.')
        out.columns = names
    else:
        for c in cols:
            s = out[c]
            if operation.startswith('Fill numeric'):
                if c not in numeric_columns(out):
                    raise DataError('Numeric filling requires numeric columns.')
                value = s.mean() if '(mean)' in operation else s.median()
                if pd.isna(value):
                    raise DataError(f'{c} has no recorded values from which to calculate a replacement.')
                out[c] = s.astype(float).fillna(value)
            elif operation == 'Fill categorical missing':
                if c in numeric_columns(out):
                    raise DataError('Choose text columns for categorical filling.')
                out[c] = s.astype('string').fillna('Unknown')
            elif operation in ('Trim whitespace', 'Normalize category case'):
                if c in numeric_columns(out) or pd.api.types.is_datetime64_any_dtype(s):
                    raise DataError('Choose text columns for text cleaning.')
                out[c] = s.astype('string').str.strip()
                if operation == 'Normalize category case':
                    out[c] = out[c].str.casefold()
            elif operation == 'Convert to number':
                t = s.astype('string').str.strip()
                symbol = action.get('currency_symbol', '')
                if symbol:
                    t = t.str.replace(symbol, '', regex=False)
                if action.get('strip_commas', False):
                    t = t.str.replace(',', '', regex=False)
                out[c] = pd.to_numeric(t, errors='coerce').astype(float)
                out[c] = out[c].replace([np.inf, -np.inf], np.nan)
                rejected += int((s.notna() & out[c].isna()).sum())
            elif operation == 'Convert to date':
                fmt = action.get('date_format', '%Y-%m-%d')
                if fmt not in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%b-%Y', '%Y-%m-%d %H:%M:%S'):
                    raise DataError('Choose one of the supported explicit date formats.')
                if c in numeric_columns(out):
                    raise DataError('Numeric dates are ambiguous. Convert Excel serial dates in the source file first.')
                out[c] = pd.to_datetime(s, format=fmt, errors='coerce')
                rejected += int((s.notna() & out[c].isna()).sum())
    if rejected and not action.get('allow_invalid', False):
        raise DataError(f'{rejected} values would become missing. Review the source or explicitly allow invalid values to become missing.')
    removed = len(df) - len(out)
    changed = 0
    if not removed and operation != 'Standardize column names':
        same = df.eq(out) | (df.isna() & out.isna())
        changed = int((~same.fillna(False)).sum().sum())
    report = {'operation': operation, 'columns': ', '.join(cols), 'rows_removed': removed,
              'cells_changed': changed, 'invalid_to_missing': rejected,
              'headers_changed': sum(a != b for a, b in zip(df.columns, out.columns)),
              'before_rows': len(df), 'after_rows': len(out)}
    # Empty cleaned selections are valid; the original remains recoverable.
    if not out.empty:
        validate_frame(out)
    return out.reset_index(drop=True), report

def replay(original, actions):
    current, reports = original.copy(), []
    for action in actions:
        current, report = clean(current, action)
        reports.append(report)
    return current, reports
