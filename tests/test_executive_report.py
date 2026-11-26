"""Phase 4 regression checks: no API, deterministic outputs and safe exports."""
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from openpyxl import load_workbook
from pypdf import PdfReader

from core.data_loader import load_data
from core.executive_report import executive_report
from core.report_generator import excel_bytes, pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def sales():
    return load_data((ROOT / 'sample_data/sales.csv').read_bytes(), 'sales.csv')


def test_executive_sample_numbers_and_priorities_are_grounded():
    df = sales()
    copy = df.copy(deep=True)
    report = executive_report(df, 'Revenue_NGN', 'Product', 'Date')
    assert report['scope'] == {'metric': 'Revenue_NGN', 'group': 'Product', 'date': 'Date', 'records': 24}
    assert report['cards'][1]['value'] == pytest.approx(18_285_000)
    assert report['category_rows'][0]['category'] == 'Laptop'
    assert report['category_rows'][0]['contribution_pct'] == pytest.approx(71.15, abs=0.01)
    assert any('-730,000.00' in x for x in report['headlines'])
    assert {a['code'] for a in report['actions']} >= {'missing','concentration','period'}
    assert all(a['origin'] == 'Rule-based review suggestion' for a in report['actions'])
    assert_frame_equal(df, copy)


def test_filter_scope_and_no_global_leakage():
    df = sales()
    lagos = df[df.Region == 'Lagos'].copy()
    report = executive_report(lagos, 'Revenue_NGN', 'Product', 'Date')
    assert report['scope']['records'] == len(lagos)
    assert report['measure']['total'] == pytest.approx(9_140_000)
    assert report['measure']['total'] != executive_report(df, 'Revenue_NGN')['measure']['total']


def test_unselected_metric_still_has_sensible_kpis():
    report = executive_report(pd.DataFrame({'Survey': ['Yes','No',None]}))
    assert report['cards'][0]['value'] == 3
    assert report['measure'] is None
    assert report['category_rows'] == []
    assert report['period_rows'] == []
    assert any('No numeric metric selected' in x for x in report['cautions'])


def test_no_records_wont_hallucinate_success_or_money():
    df = sales().iloc[0:0]
    report = executive_report(df, 'Revenue_NGN', 'Product', 'Date')
    assert report['cards'][0]['value'] == 0
    assert all(card['kind'] != 'metric' for card in report['cards'])
    assert report['actions'][-1]['code'] == 'scope'


@pytest.mark.parametrize('numbers', [[-40, 80], [0, 0], [-10, -20]])
def test_no_unsafe_contribution_shares(numbers):
    df = pd.DataFrame({'Category': ['A','B'], 'Amount': numbers})
    report = executive_report(df, 'Amount', 'Category')
    assert all(c['contribution_pct'] is None for c in report['category_rows'])
    assert any('Shares require' in c for c in report['cautions'])
    assert all('concentration' != item['code'] for item in report['actions'])


def test_monthly_gaps_are_retained_as_missing_not_zero():
    df = pd.DataFrame({'Date':['2026-01-03','2026-03-04'], 'Amount':[100,30]})
    report = executive_report(df, 'Amount', date='Date')
    assert [(r['month'],r['total']) for r in report['period_rows']] == [
        ('2026-01',100), ('2026-02',None), ('2026-03',30)]
    assert any(a['code'] == 'gap' for a in report['actions'])
    assert not any(a['code'] == 'period' for a in report['actions'])


def test_negative_baseline_avoids_misleading_percentage():
    df = pd.DataFrame({'Date': ['2026-01-02', '2026-02-03'], 'M': [-5,5]})
    report = executive_report(df, 'M', date='Date')
    assert any('10.00' in s for s in report['headlines'])
    assert not any('% relative' in s for s in report['headlines'])


def test_report_exports_include_executive_items_without_inventing_values():
    df = sales()
    brief = executive_report(df, 'Revenue_NGN','Product','Date')
    ctx = {'Dataset':'sales.csv','Selected rows':len(df)}
    wb = load_workbook(BytesIO(excel_bytes(df, ctx, executive=brief)), read_only=True)
    assert {'Executive KPIs','Review priorities','Category performance','Monthly evidence','Executive limitations'}.issubset(wb.sheetnames)
    assert wb['Executive KPIs']['B3'].value == pytest.approx(18_285_000)
    assert wb['Review priorities']['A2'].value in ('High','Medium','Low')
    assert wb['Category performance']['B2'].value == pytest.approx(13_010_000)
    assert wb['Monthly evidence']['A2'].value == '2026-01'
    wb.close()

    pdf = pdf_bytes(df,'sales.csv',ctx,metric='Revenue_NGN',group='Product',date='Date',executive=brief)
    words = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    for token in ('Executive snapshot', 'Prioritized actions', '18,285,000.00',
                  '71.15%', 'Calendar month', 'Scope and filter context', 'Executive caveats'):
        assert token in words


def test_old_export_callers_remain_valid():
    df = sales()
    old_xlsx = excel_bytes(df, {'Test': 'legacy'})
    old_pdf = pdf_bytes(df, 'sales.csv', {'Test': 'legacy'})
    assert old_xlsx[:2] == b'PK'
    assert old_pdf[:4] == b'%PDF'


def test_formula_text_neutralized_in_added_excel_sheets():
    df = pd.DataFrame({'Category': ['=HYPERLINK("bad")', 'Safe'], 'Amount': [90, 10]})
    executive = executive_report(df, 'Amount', 'Category')
    wb = load_workbook(BytesIO(excel_bytes(df, {'Scope':'testing'}, executive=executive)),read_only=True)
    values = list(wb['Category performance'].values)
    assert values[1][0].startswith("'=")
    wb.close()
