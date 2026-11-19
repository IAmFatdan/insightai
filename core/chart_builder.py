"""Type-checked chart preparation, shared by UI and exports."""
import pandas as pd
import plotly.express as px
from .data_analysis import aggregate, monthly, numeric_columns, date_columns
from .data_loader import DataError

CHARTS = ('Bar', 'Line', 'Area', 'Pie', 'Donut', 'Histogram', 'Scatter', 'Box', 'Correlation')
COLORS = ['#14b8a6', '#6366f1', '#f59e0b', '#38bdf8', '#fb7185', '#a78bfa']

def build_chart(df, kind, metric=None, group=None, second=None, operation='sum', limit=15, ascending=False):
    if kind not in CHARTS or df.empty:
        raise DataError('Choose a chart and a nonempty selection.')
    if metric not in numeric_columns(df) and kind != 'Correlation' and not (kind in ('Bar', 'Pie', 'Donut') and operation == 'count'):
        raise DataError('This chart needs a numeric metric.')
    title = f'{operation.title()} of {metric}' if operation != 'count' else 'Record count'
    if kind in ('Bar', 'Pie', 'Donut'):
        table = aggregate(df, group, metric, operation).dropna(subset=['Value'])
        table = table.sort_values('Value', ascending=ascending).head(limit)
        if table.empty:
            raise DataError('No recorded values are available for this chart.')
        if kind == 'Bar':
            fig = px.bar(table, x='Group', y='Value', title=f'{title} by {group}')
        else:
            if (table.Value < 0).any() or table.Value.sum() <= 0:
                raise DataError('Pie/donut charts need nonnegative values and a positive total.')
            if operation not in ('sum', 'count'):
                raise DataError('Use sum or record count for a part-to-whole chart.')
            # Do not silently present top-N as a share of the entire dataset.
            fig = px.pie(table, names='Group', values='Value', hole=.55 if kind == 'Donut' else 0,
                         title=f'{title}: shares within displayed categories only')
    elif kind in ('Line', 'Area'):
        if group not in date_columns(df):
            raise DataError('Line/area charts require a valid date column.')
        table = monthly(df, group, metric, operation)
        fig = (px.line if kind == 'Line' else px.area)(table, x='Month', y='Value', title=f'Monthly {title}')
        fig.update_traces(connectgaps=False)
    elif kind == 'Histogram':
        table = df[[metric]].dropna().head(10_000)
        fig = px.histogram(table, x=metric, title=f'Distribution of {metric} (up to 10,000 rows)')
    elif kind == 'Scatter':
        if second not in numeric_columns(df):
            raise DataError('Scatter plots need two numeric columns.')
        table = df[list(dict.fromkeys([metric, second]))].dropna().head(10_000)
        fig = px.scatter(table, x=metric, y=second, title='Paired observations (up to 10,000 rows)')
    elif kind == 'Box':
        selected = list(dict.fromkeys([metric] + ([group] if group else [])))
        table = df[selected].head(10_000)
        if group and df[group].nunique() > 30:
            raise DataError('Box charts support up to 30 categories. Filter your data first.')
        fig = px.box(table, x=group, y=metric, title=f'Spread of {metric} (up to 10,000 rows)')
    else:
        cols = numeric_columns(df)[:30]
        if len(cols) < 2:
            raise DataError('Correlation needs at least two numeric columns.')
        table = df[cols].corr(min_periods=3)
        fig = px.imshow(table, zmin=-1, zmax=1, color_continuous_scale='RdBu_r',
                        title='Pearson correlation · at least 3 paired records · first 30 numeric columns')
    fig.update_layout(colorway=COLORS, margin=dict(l=20, r=20, t=65, b=30), height=440,
                      font=dict(family='Arial', size=13), paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)')
    return fig, table
