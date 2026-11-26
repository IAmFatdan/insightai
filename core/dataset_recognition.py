"""Phase 5: transparent, schema-only, deterministic dataset-type suggestions.

No external AI calls. Only column names and dtypes are inspected, never row data.
The output is a heuristic label, not a verified domain classification or diagnosis.
"""
from __future__ import annotations

import re
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype, is_datetime64_any_dtype


# Each concept contributes at most one signal, however many related column names exist.
# Two distinct concepts are required to suggest a specialized domain.
DOMAIN_SIGNALS = {
    'Sales': {
        'product': ('product', 'product_name', 'item', 'sku'),
        'sales activity': ('units_sold', 'quantity_sold', 'sales_quantity', 'order', 'orders', 'sale_id', 'transaction_id'),
        'recorded revenue': ('revenue', 'sales_amount', 'gross_sales', 'total_sales'),
        'customer': ('customer', 'customer_id', 'buyer'),
    },
    'Healthcare': {
        'patient': ('patient', 'patient_id', 'mrn'),
        'diagnosis': ('diagnosis', 'diagnostic', 'condition', 'icd_code'),
        'care': ('treatment', 'procedure', 'medication', 'prescription'),
        'encounter': ('admission', 'discharge', 'appointment', 'encounter', 'visit'),
        'clinical measure': ('blood_pressure', 'heart_rate', 'glucose', 'spo2', 'bmi'),
    },
    'Human Resources': {
        'employee': ('employee', 'employee_id', 'staff_id', 'worker_id'),
        'organization': ('department', 'job_title', 'team', 'role', 'position'),
        'compensation': ('salary', 'wage', 'payroll', 'compensation'),
        'employment': ('hire_date', 'years_experience', 'tenure', 'attrition', 'termination', 'start_date'),
    },
    'Finance': {
        'expense': ('expense', 'expenses', 'expenditure', 'cost'),
        'accounting': ('debit', 'credit', 'ledger', 'account', 'account_code'),
        'planning': ('budget', 'forecast', 'variance'),
        'financial position': ('balance', 'asset', 'liability', 'cash_flow', 'profit', 'net_income'),
    },
    'Education': {
        'learner': ('student', 'student_id', 'pupil', 'learner'),
        'assessment': ('grade', 'exam_score', 'test_score', 'marks', 'gpa'),
        'school activity': ('attendance', 'enrollment', 'enrolment', 'class', 'semester', 'term'),
        'subject': ('subject', 'course', 'module', 'curriculum'),
    },
    'Marketing': {
        'campaign': ('campaign', 'campaign_id', 'ad_group', 'advertisement'),
        'audience': ('impressions', 'reach', 'views'),
        'response': ('clicks', 'ctr', 'conversions', 'conversion_rate', 'leads'),
        'spend': ('ad_spend', 'marketing_spend', 'cpc', 'cpm'),
        'channel': ('channel', 'traffic_source', 'utm_source'),
    },
    'Survey': {
        'respondent': ('respondent', 'respondent_id', 'survey_id'),
        'rating': ('rating', 'satisfaction', 'likert', 'nps'),
        'question': ('question', 'question_id', 'response', 'answer', 'feedback'),
        'comment': ('comment', 'comments', 'free_text', 'open_ended'),
    },
}

DOMAIN_FOCUS = {
    'Sales': [
        'Compare recorded sales or revenue by product and region.',
        'Review category contributions and confirm missing amounts before interpreting totals.',
        'Compare calendar periods only after checking whether both periods are complete.',
    ],
    'Healthcare': [
        'Summarize counts by encounter or diagnosis category without inferring clinical outcomes.',
        'Review missing clinical fields and potential inconsistencies.',
        'Compare activity over time only when dates and reporting scope are reliable.',
    ],
    'Human Resources': [
        'Review workforce counts by department and role.',
        'Compare compensation distributions only for suitable numeric measures.',
        'Check missing values and subgroup coverage before drawing conclusions.',
    ],
    'Finance': [
        'Review recorded income and expense categories without equating revenue with profit.',
        'Compare budget and actuals only where matching definitions exist.',
        'Investigate unusual amounts and missing records before conclusions.',
    ],
    'Education': [
        'Review student counts and assessment distributions.',
        'Compare subjects or classes with verified sample sizes.',
        'Examine attendance or missing grades without assuming reasons.',
    ],
    'Marketing': [
        'Compare campaign activity by channel and campaign.',
        'Review recorded clicks, conversions and costs where those measures exist.',
        'Calculate rates only with verified compatible denominators.',
    ],
    'Survey': [
        'Show response counts and distributions by question or rating.',
        'Check missing answers and whether each question has the same respondent base.',
        'Avoid generalizing beyond the observed respondents.',
    ],
    'General': [
        'Start with record counts, missing data and distribution checks.',
        'Select a meaningful metric and category before comparing groups.',
        'Verify field definitions and reporting scope before interpreting trends.',
    ],
}

FIELD_PREFERENCES = {
    'Sales': {'metric': ('revenue', 'sales_amount', 'gross_sales', 'units_sold'),
              'group': ('product', 'region', 'category', 'customer'),
              'date': ('date', 'sale_date', 'order_date', 'transaction_date')},
    'Healthcare': {'metric': ('length_of_stay', 'visit_cost', 'treatment_cost', 'age'),
                   'group': ('diagnosis', 'department', 'clinic', 'hospital', 'treatment'),
                   'date': ('visit_date', 'admission_date', 'appointment_date', 'date')},
    'Human Resources': {'metric': ('salary', 'wage', 'years_experience', 'tenure'),
                        'group': ('department', 'job_title', 'role', 'team'),
                        'date': ('hire_date', 'start_date', 'date')},
    'Finance': {'metric': ('expense', 'amount', 'cost', 'revenue', 'balance'),
                'group': ('account', 'category', 'department'),
                'date': ('transaction_date', 'date', 'period')},
    'Education': {'metric': ('exam_score', 'test_score', 'grade', 'gpa', 'marks'),
                  'group': ('subject', 'class', 'course', 'semester'),
                  'date': ('exam_date', 'assessment_date', 'date')},
    'Marketing': {'metric': ('conversions', 'clicks', 'impressions', 'ad_spend', 'cost'),
                  'group': ('campaign', 'channel', 'traffic_source'),
                  'date': ('campaign_date', 'date', 'event_date')},
    'Survey': {'metric': ('rating', 'score'), 'group': ('question', 'course', 'rating', 'answer'),
               'date': ('response_date', 'survey_date', 'date')},
    'General': {'metric': (), 'group': (), 'date': ()},
}

SENSITIVE_DOMAINS = {'Healthcare', 'Human Resources', 'Education', 'Survey'}


def _normalize(name: object) -> str:
    """Normalize a column label to whole underscore-delimited words."""
    return re.sub(r'[^a-z0-9]+', '_', str(name).strip().lower()).strip('_')


def _matches(name: object, pattern: str) -> bool:
    normalized, target = _normalize(name), _normalize(pattern)
    return bool(target) and f'_{target}_' in f'_{normalized}_'


def _best_field(columns: list, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        for column in columns:
            if _matches(column, pattern):
                return str(column)
    return None


def recognize_dataset(df: pd.DataFrame, override: str | None = None) -> dict:
    """Suggest a domain using column names only; override changes the label, not evidence.

    Confidence is a qualitative *schema match*, not a calibrated probability.
    No column values, samples, or personal information are inspected or returned.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError('Dataset recognition requires a pandas DataFrame.')
    if override is not None and override not in (*DOMAIN_SIGNALS.keys(), 'General'):
        raise ValueError('Unknown dataset type override.')
    columns = list(df.columns)
    names_by_domain = {}
    for domain, signals in DOMAIN_SIGNALS.items():
        matched = {}
        for concept, patterns in signals.items():
            hits = [str(col) for col in columns if any(_matches(col, p) for p in patterns)]
            if hits:
                matched[concept] = hits[:4]
        names_by_domain[domain] = matched
    rankings = sorted(((domain, len(concepts)) for domain, concepts in names_by_domain.items()),
                      key=lambda item: (-item[1], item[0]))
    first, second = rankings[0][1], rankings[1][1]
    winner = rankings[0][0]
    # Conservative: short or tied schemas should not be labelled confidently.
    detected = winner if first >= 2 and first > second else 'General'
    strength = ('Strong schema match' if detected != 'General' and first >= 3 and first - second >= 2
                else 'Possible schema match' if detected != 'General' else 'Uncertain or mixed schema')
    active = override if override is not None else detected

    # Only column names and declared dtypes: no reading dataframe cells here.
    numeric = [str(c) for c in columns if is_numeric_dtype(df[c]) and not is_bool_dtype(df[c])]
    dated = [str(c) for c in columns if is_datetime64_any_dtype(df[c]) or
             (not is_numeric_dtype(df[c]) and any(_matches(c, p) for p in
              ('date', 'datetime', 'timestamp', 'month', 'period')))]
    categorical = [str(c) for c in columns if str(c) not in numeric and str(c) not in dated]
    # Avoid suggesting summed identifier/rate/age variables as generic metrics.
    safe_numeric = [c for c in numeric if not any(_matches(c, x) for x in
                    ('id', 'identifier', 'age', 'rate', 'ratio', 'percentage', 'percent', 'year'))
                    and not _normalize(c).endswith('_id')]
    prefs = FIELD_PREFERENCES[active]
    metric = _best_field(safe_numeric, prefs['metric'])
    # Ambiguous or non-domain data should start in record-counts-only mode.
    group = _best_field(categorical, prefs['group'])
    date = _best_field(dated, prefs['date']) or (str(dated[0]) if len(dated) == 1 else None)
    matches = names_by_domain.get(detected, {})
    matched_columns = sorted({name for hits in matches.values() for name in hits})
    return {
        'detected_type': detected,
        'active_type': active,
        'override_applied': override is not None,
        'match_strength': strength,
        'matched_concepts': sorted(matches),
        'matched_columns': matched_columns[:12],
        'alternative_matches': [{'type': d, 'concepts': n} for d, n in rankings if n >= 2 and d != detected][:3],
        'suggested_fields': {'metric': metric, 'group': group, 'date': date},
        'recommended_analyses': list(DOMAIN_FOCUS[active]),
        'sensitive_data_caution': active in SENSITIVE_DOMAINS,
        'method': 'Column-name and dtype heuristic. No row values inspected; not a statistical certainty.',
    }
