"""Constrained plans, never Python/eval/SQL. Local questions and AI plans use the same executor."""
import re
import calendar
from typing import Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from .data_analysis import (aggregate, kpis, facts, numeric_columns, category_columns,
                            date_columns, filter_data, monthly, correlation_pairs)
from .data_loader import DataError

class Filter(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    column: str
    value: str

class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    operation: Literal['summary', 'missing', 'aggregate', 'group', 'share', 'correlation', 'trend', 'compare']
    metric: str | None
    group: str | None
    aggregation: Literal['sum', 'mean', 'median', 'min', 'max', 'count']
    limit: int = Field(ge=1, le=50)
    ascending: bool
    category: str | None
    filters: list[Filter] = Field(max_length=5)
    date: str | None
    periods: list[str] = Field(max_length=2)

def make_plan(**kwargs):
    defaults = dict(operation='summary', metric=None, group=None, aggregation='sum', limit=5,
                    ascending=False, category=None, filters=[], date=None, periods=[])
    defaults.update(kwargs)
    return Plan(**defaults)

def _word(text, value):
    return re.search(r'(?<!\w)' + re.escape(value.lower()) + r'(?!\w)', text) is not None

def infer_plan(question, df, metric=None, previous=None):
    """Small transparent grammar; unsupported questions must not produce guessed calculations."""
    q = question.strip().lower()
    if not q or len(q) > 2000:
        raise DataError('Ask a question of 1–2,000 characters.')
    if re.search(r'\b(exec|eval|import|python|shell|sql|delete|forecast|predict|profit|cause|why)\b', q):
        raise DataError('I cannot answer that safely from these calculations. Try a recorded total, category comparison, missing-value count or monthly trend.')
    nums, cats, dates = numeric_columns(df), category_columns(df), date_columns(df)
    if re.search(r'\b(except|excluding|exclude|not|above|below|greater|less|over|under)\b|[<>]', q):
        raise DataError('This local question includes a condition I cannot safely interpret. Apply the filter in the sidebar or request an AI plan and review it first.')
    matches = [c for c in nums if _word(q, c.replace('_', ' ')) or _word(q, c)]
    if not matches:
        for alias in ('revenue', 'salary', 'units', 'amount', 'expense', 'score'):
            if _word(q, alias):
                matches.extend(c for c in nums if alias in c.lower())
        matches = list(dict.fromkeys(matches))
    if len(matches) > 1 and 'correlat' not in q:
        raise DataError('More than one metric was named. Ask about one metric at a time.')
    selected = matches[0] if matches else metric
    if selected not in nums:
        selected = 'Revenue_NGN' if 'Revenue_NGN' in nums else (nums[0] if len(nums) == 1 else None)
    explicit_groups = [c for c in cats if _word(q, c) or _word(q, c + 's')]
    group = explicit_groups[0] if len(explicit_groups) == 1 else None
    if len(explicit_groups) > 1:
        raise DataError('Ask about one grouping column at a time.')
    # Follow-ups inherit the last verified plan, but never its result.
    followup = bool(re.search(r'\b(what about|instead|same|and for|and in|bottom|top)\b', q))
    filters = []
    if previous and followup:
        selected = matches[0] if matches else previous.metric
        group = group or previous.group
        filters = [f.model_copy() for f in previous.filters]
    values_found = []
    for c in cats:
        if df[c].nunique() > 500:
            continue
        for value in df[c].dropna().astype(str).unique():
            if value and (_word(q, value) or _word(q, value + 's')):
                values_found.append((c, value))
    for c in {c for c, _ in values_found}:
        if sum(x[0] == c for x in values_found) > 1:
            raise DataError('Use the sidebar to select multiple categories, then ask your comparison.')
    share = bool(re.search(r'\b(percentage|percent|share)\b', q))
    category = None
    for c, value in values_found:
        if share and (group is None or group == c):
            group, category = c, value
        else:
            filters = [f for f in filters if f.column != c] + [Filter(column=c, value=value)]
    # An unknown value after in/for must not silently turn into an all-data result.
    scope = re.search(r'\b(?:in|for)\s+(.+?)[?.!]*$', q)
    if scope and not values_found and not any(_word(scope.group(1), c) for c in df) and not re.search(r'\b(data|dataset|all|each|every|this|that|month|year)\b', scope.group(1)):
        raise DataError('I could not identify that filter value. Select the intended records in the sidebar and ask again.')
    agg = 'mean' if re.search(r'\b(average|mean)\b', q) else 'median' if 'median' in q else 'sum'
    limit_match = re.search(r'\b(?:top|bottom)\s+(\d+)\b', q)
    limit = min(50, max(1, int(limit_match.group(1)))) if limit_match else (1 if re.search(r'\b(highest|lowest|best|most)\b', q) else 5)
    ascending = bool(re.search(r'\b(bottom|lowest|least)\b', q))
    periods = re.findall(r'\b\d{4}-(?:0[1-9]|1[0-2])\b', q)
    named_months = [i for i in range(1, 13) if _word(q, calendar.month_name[i])]
    date = dates[0] if len(dates) == 1 else None
    if named_months and date:
        years = pd.to_datetime(df[date]).dt.year.dropna().unique()
        if len(years) == 1:
            periods = [f'{int(years[0])}-{i:02d}' for i in named_months]
        else:
            raise DataError('Specify the two months as YYYY-MM so the year is unambiguous.')
    if 'correlat' in q:
        op = 'correlation'
    elif re.search(r'\b(missing|incomplete|null)\b', q):
        op = 'missing'
    elif re.search(r'\b(summarize|summary|findings|recommendations)\b', q):
        op = 'summary'
    elif re.search(r'\b(month|months|monthly|trend|changed|change)\b', q) or periods:
        op = 'compare' if len(periods) == 2 else 'trend'
        if not date:
            raise DataError('Monthly questions need one unambiguous date column. Convert dates first, or use the structured question form.')
    elif share:
        op = 'share'
        if category is None:
            raise DataError('Name an exact category for the percentage calculation, for example: What percentage of revenue comes from Laptop?')
    elif group and re.search(r'\b(top|bottom|compare|by|which|highest|lowest|best|most|least)\b', q):
        op = 'group'
    elif re.search(r'\b(how many|count|number of)\b', q):
        op, agg = 'aggregate', 'count'
    elif re.search(r'\b(total|sum|average|mean|median)\b', q):
        op = 'aggregate'
    elif previous and followup:
        op, agg = previous.operation, previous.aggregation
    else:
        raise DataError('Supported examples: total Revenue_NGN; top 5 products; average Units_Sold; missing values; monthly revenue; strongest correlation. Use the structured question form for precise control.')
    if op in ('group', 'share', 'trend', 'compare', 'aggregate') and agg != 'count' and selected is None:
        raise DataError('Select a numeric metric in the sidebar or name its exact column in the question.')
    return make_plan(operation=op, metric=selected, group=group, aggregation=agg, limit=limit,
                     ascending=ascending, category=category, filters=filters, date=date, periods=periods)

def execute_plan(df, plan):
    if not isinstance(plan, Plan):
        plan = Plan.model_validate(plan)
    if plan.operation == 'share' and any(f.column == plan.group for f in plan.filters):
        raise DataError('A share plan cannot filter its own grouping column: that would change the denominator. Use sidebar filters explicitly if you intend a restricted denominator.')
    if plan.metric is not None and plan.metric not in numeric_columns(df):
        raise DataError('The proposed metric is not a numeric column in this dataset.')
    if plan.group is not None and plan.group not in df:
        raise DataError('The proposed grouping column does not exist.')
    for f in plan.filters:
        if f.column not in df or not df[f.column].astype('string').eq(f.value).any():
            raise DataError('The proposed filter does not match a recorded category.')
    if len({f.column for f in plan.filters}) != len(plan.filters):
        raise DataError('Duplicate filters are not allowed.')
    work = filter_data(df, {f.column: [f.value] for f in plan.filters})
    if work.empty:
        raise DataError('No records match this question and the active dashboard filters.')
    op = plan.operation
    table = None
    if op == 'summary':
        answer = '\n\n'.join(f['text'] for f in facts(work, plan.metric, plan.group))
        answer += '\n\nRecommendation: review missing data and category definitions before making decisions. No causal or forecast conclusion is supported.'
    elif op == 'missing':
        table = work.isna().sum().rename_axis('Column').reset_index(name='Missing cells')
        answer = f'{int(work.isna().any(axis=1).sum())} records have at least one missing value; {int(work.isna().sum().sum())} cells are missing.'
    elif op == 'correlation':
        table = correlation_pairs(work).head(plan.limit)
        answer = 'Pearson correlations use pairwise complete observations (at least 3). Correlation does not establish causation. Constant columns are omitted.'
    elif op == 'aggregate':
        if plan.aggregation == 'count':
            answer = f'There are {len(work):,} records in this selection.'
        else:
            if plan.metric is None:
                raise DataError('Choose a numeric metric.')
            s = work[plan.metric].dropna()
            value = s.agg(plan.aggregation) if len(s) else None
            answer = f'{plan.aggregation.title()} of recorded {plan.metric}: {value:,.2f}.' if value is not None else 'No recorded values; the result is unavailable, not zero.'
            answer += f' Uses {len(s)} recorded values; excludes {int(work[plan.metric].isna().sum())} missing values.'
    elif op == 'group':
        table = aggregate(work, plan.group, plan.metric, plan.aggregation).sort_values('Value', ascending=plan.ascending).head(plan.limit)
        answer = f'{plan.aggregation.title()} by {plan.group}; {len(table)} categories shown. Missing numeric values are excluded; all-missing totals remain unavailable.'
    elif op == 'share':
        if plan.metric is None or plan.group is None or plan.category is None:
            raise DataError('Share requires a numeric metric, grouping column and exact category.')
        s = work[plan.metric].dropna()
        if (s < 0).any() or s.empty or s.sum() <= 0:
            raise DataError('Part-to-whole percentages require nonnegative values and a positive recorded total.')
        subset = work.loc[work[plan.group].astype('string').eq(plan.category), plan.metric]
        if not len(subset) or not subset.notna().any():
            raise DataError('No recorded metric values exist for that category.')
        numerator, denominator = float(subset.sum(min_count=1)), float(s.sum())
        answer = f'{plan.category}: {numerator / denominator * 100:.2f}% of recorded {plan.metric}. Calculation: {numerator:,.2f} / {denominator:,.2f} × 100. Denominator includes all categories in the active filters; missing values are excluded.'
    elif op in ('trend', 'compare'):
        table = monthly(work, plan.date, plan.metric, plan.aggregation)
        answer = 'Calendar-month results; absent months remain gaps. First/last months may be partial. Undated records are excluded.'
        if op == 'compare':
            if len(plan.periods) != 2 or any(not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', x) for x in plan.periods):
                raise DataError('Comparison requires two months written as YYYY-MM.')
            lookup = table.assign(Period=table.Month.dt.strftime('%Y-%m')).set_index('Period')
            if any(p not in lookup.index or pd.isna(lookup.loc[p, 'Value']) for p in plan.periods):
                raise DataError('Both months need recorded values. An absent month is not zero.')
            a, b = [float(lookup.loc[p, 'Value']) for p in plan.periods]
            answer += f' Change from {plan.periods[0]} to {plan.periods[1]}: {b-a:,.2f}.'
            answer += f' Relative change: {(b-a)/a*100:.2f}%.' if a > 0 else ' Percentage change is unavailable because the baseline is not positive.'
            table = lookup.loc[plan.periods].reset_index()
    return {'answer': answer, 'table': table, 'plan': plan.model_dump(), 'records': len(work)}
