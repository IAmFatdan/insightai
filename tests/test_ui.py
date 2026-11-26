"""Real Streamlit script/session tests, without a browser or external AI calls."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
ROOT = Path(__file__).resolve().parents[1]

def app():
    return AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()

def field(at, kind, label):
    return next(x for x in getattr(at,kind) if x.label==label)

def nav(at, page):
    at.radio(key='page').set_value(page).run()
    assert not at.exception, [e.message for e in at.exception]
    return at

@pytest.mark.parametrize('page',['Home','Data Overview','Data Cleaning','Dashboard','Executive Report','AI Insights','Chat With Your Data','Reports & Export','Settings / About'])
def test_pages(page):
    nav(app(),page)

def test_clean_undo_reset():
    at=nav(app(),'Data Cleaning')
    field(at,'selectbox','Cleaning action').set_value('Fill categorical missing').run()
    field(at,'multiselect','Columns to change').set_value(['Region']).run()
    field(at,'button','Apply this change').click().run()
    assert not at.exception
    assert at.session_state['current'].Region.isna().sum()==0
    assert at.session_state['original'].Region.isna().sum()==1
    field(at,'button','Undo last step').click().run()
    assert at.session_state['current'].Region.isna().sum()==1
    field(at,'selectbox','Cleaning action').set_value('Standardize column names').run()
    field(at,'button','Apply this change').click().run()
    assert not at.exception
    assert 'revenue_ngn' in at.session_state['current']
    field(at,'button','Reset to original').click().run()
    assert 'Revenue_NGN' in at.session_state['current']

def test_filter_kpis_and_chat_reset():
    at=nav(app(),'Dashboard')
    field(at,'multiselect','Filter columns').set_value(['Region']).run()
    field(at,'multiselect','Region').set_value(['Lagos']).run()
    assert not at.exception
    assert any(m.value=='NGN 9,140,000.00' for m in at.metric)
    nav(at,'Chat With Your Data')
    at.chat_input[0].set_value('Which product generated the most revenue?').run()
    assert not at.exception
    assert at.session_state['messages'][-1]['table'].iloc[0].Group=='Laptop'
    assert at.session_state['messages'][-1]['table'].iloc[0].Value==7430000
    field(at,'multiselect','Region').set_value(['Abuja']).run()
    assert at.session_state['messages']==[]
    field(at,'multiselect','Region').set_value([]).run()
    nav(at,'Dashboard')
    assert any('No records match' in x.value for x in at.info)

def test_exports_and_text_dataset():
    at=nav(app(),'Reports & Export')
    field(at,'button','Build Excel and PDF reports').click().run()
    assert not at.exception
    assert at.session_state['generated_exports']['pdf'].startswith(b'%PDF')
    field(at,'selectbox','Sample dataset').set_value('Survey · text only').run()
    assert not at.exception
    assert 'generated_exports' not in at.session_state
    nav(at,'Dashboard')
    assert not at.exception
    field(at,'selectbox','Aggregation').set_value('count').run()
    assert not at.exception
    nav(at,'Chat With Your Data')
    at.chat_input[0].set_value('how many records?').run()
    assert '6 records' in at.session_state['messages'][-1]['text']

def test_separate_sessions():
    first=nav(app(),'Data Cleaning')
    field(first,'selectbox','Cleaning action').set_value('Standardize column names').run()
    field(first,'button','Apply this change').click().run()
    second=app()
    assert 'Revenue_NGN' in second.session_state['current']
    assert 'revenue_ngn' in first.session_state['current']
    assert second.session_state['actions']==[]


def test_phase4_executive_page_and_exports():
    at = nav(app(), 'Executive Report')
    assert any(m.label == 'Recorded total · Revenue_NGN' for m in at.metric)
    field(at, 'button', 'Build executive report files').click().run()
    assert not at.exception
    assert at.session_state['generated_exports']['pdf'].startswith(b'%PDF')
    assert at.session_state['generated_exports']['xlsx'].startswith(b'PK')
