"""Evidence-first analytics regression tests, independent of Gemini API availability."""
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from core.advanced_analysis import advanced_report, extra_facts
from core.data_loader import DataError, load_data

ROOT = Path(__file__).resolve().parents[1]


def test_sample_sales_exact_evidence_and_no_mutation():
    df = load_data((ROOT/'sample_data/sales.csv').read_bytes(), 'sales.csv')
    original = df.copy(deep=True)
    report = advanced_report(df, 'Revenue_NGN', 'Product', 'Date')
    q = report['quality']
    assert (q['rows'], q['columns'], q['missing_cells'], q['rows_with_missing'], q['duplicate_rows']) == (24,5,2,2,0)
    assert q['missing_pct'] == pytest.approx(100*2/120)
    assert report['measure']['total'] == pytest.approx(18_285_000)
    categories = report['categories']
    assert categories['top'][0]['category'] == 'Laptop'
    assert categories['top'][0]['total'] == pytest.approx(13_010_000)
    assert categories['top'][0]['contribution_pct'] == pytest.approx(100*13_010_000/18_285_000)
    assert categories['top'][0]['records'] == 6
    assert categories['categories_with_values'] == 4
    period = report['periods']['comparison']
    assert (period['previous_month'], period['current_month']) == ('2026-05','2026-06')
    assert period['previous_total'] == 4_085_000
    assert period['current_total'] == 3_355_000
    assert period['absolute_change'] == -730_000
    assert period['percentage_change'] == pytest.approx(-730_000/4_085_000*100)
    evidence = extra_facts(report, 9)
    assert all(item['id'] == f'F{i+9}' for i,item in enumerate(evidence))
    assert any('71.15%' in item['text'] for item in evidence)
    assert any('-17.87%' in item['text'] for item in evidence)
    assert all('verified' not in x['id'] for x in evidence)
    assert_frame_equal(df, original)


def test_empty_and_text_only():
    df = pd.DataFrame({'Label': pd.Series([], dtype='string'),
                       'Value': pd.Series([], dtype='float64')})
    r = advanced_report(df, 'Value', 'Label')
    assert r['quality']['missing_pct'] is None
    assert r['measure']['total'] is None
    assert r['categories'] is None
    assert r['periods'] is None
    assert r['outliers'] is None
    assert extra_facts(r) == []
    text = advanced_report(pd.DataFrame({'Text':['Good','Bad',None]}))
    assert text['measure'] is None and text['quality']['rows_with_missing'] == 1


def test_missing_only_group_is_excluded_from_ranking():
    df = pd.DataFrame({'G':['A','B','C','C'],'M':[5.0,9.0,None,None]})
    r = advanced_report(df, 'M','G')
    assert [x['category'] for x in r['categories']['top']] == ['B','A']
    assert r['categories']['top'][0]['contribution_pct'] == pytest.approx(9/14*100)
    assert r['categories']['categories_with_values'] == 2


def test_missing_category_name_collision():
    df = pd.DataFrame({'G':['(Missing)',None], 'M':[12,4]})
    r = advanced_report(df, 'M','G')
    assert r['categories']['categories_with_values'] == 2
    assert sum(x['contribution_pct'] for x in r['categories']['top']) == pytest.approx(100)


@pytest.mark.parametrize('amounts', [[0,0],[-10,20],[-10,-20],[None,None]])
def test_unsafe_shares_suppressed(amounts):
    df = pd.DataFrame({'G':['X','Y'],'M':pd.Series(amounts, dtype='float64')})
    r = advanced_report(df, 'M','G')
    c = r['categories']
    if c and c['top']:
        assert not c['shares_available']
        assert all(x['contribution_pct'] is None for x in c['top'])


def test_share_denominator_not_restricted_to_top_n():
    df = pd.DataFrame({'G':['A','B','C'],'M':[50,30,20]})
    r = advanced_report(df,'M','G',top_n=1)
    assert r['categories']['showing'] == 1
    assert r['categories']['top'][0]['contribution_pct'] == 50


def test_empty_months_and_missing_month_values_not_assumed_zero():
    df = pd.DataFrame({'Date':['2026-01-01','2026-03-01'],'M':[100,30]})
    r = advanced_report(df,'M',date='Date')
    assert [x['total'] for x in r['periods']['months']] == [100,None,30]
    assert r['periods']['comparison'] is None  # February has no records
    assert 'incomplete' in r['periods']['caution']


def test_zero_and_negative_baseline_change_pct_suppressed():
    for a in (0,-10):
        df = pd.DataFrame({'Date':['2026-01-01','2026-02-01'],'M':[a,10]})
        r = advanced_report(df,'M',date='Date')
        assert r['periods']['comparison']['percentage_change'] is None
        assert r['periods']['comparison']['absolute_change'] == 10-a


def test_invalid_columns_and_ambiguous_dates():
    df = pd.DataFrame({'Name':['A','B'], 'Date':['01/02/2026','02/02/2026'], 'Value':[1,2]})
    with pytest.raises(DataError): advanced_report(df,'Name')
    with pytest.raises(DataError): advanced_report(df,'Value','NotThere')
    with pytest.raises(DataError): advanced_report(df,'Value',date='Date')
    with pytest.raises(DataError): advanced_report(df,'Value',top_n=0)


def test_outliers_are_only_flags():
    df = pd.DataFrame({'Amount':[1,2,2,3,4,1000]})
    r = advanced_report(df,'Amount')
    assert r['outliers']['flagged'] == 1
    assert 'not automatically data errors' in r['outliers']['caution']
    assert 'review flags' in extra_facts(r)[-1]['text']


def test_filter_scope_is_only_supplied_dataframe():
    all_data = pd.DataFrame({'Group':['A','B','B'],'Amount':[100,50,50]})
    selected = all_data[all_data.Group=='A'].copy()
    r = advanced_report(selected,'Amount','Group')
    assert r['quality']['rows'] == 1
    assert r['measure']['total'] == 100
    assert r['categories']['top'][0]['contribution_pct'] == 100
    assert len(all_data)==3
