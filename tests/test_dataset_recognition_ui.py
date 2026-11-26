"""Phase 5 Streamlit smoke checks; run with requirements-dev.txt installed."""
from pathlib import Path
import pytest

st = pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def app():
    return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()


def dropdown(at, label):
    return next(widget for widget in at.selectbox if widget.label == label)


def test_sales_type_visible_on_executive_page():
    at = app()
    assert not at.exception
    assert at.session_state['dataset_type_override'] == 'Auto-detect'
    assert dropdown(at, 'Metric').value == 'Revenue_NGN'
    at.radio(key='page').set_value('Executive Report').run()
    assert not at.exception
    assert any('Analysis context: Sales' in item.value for item in at.markdown)


def test_schema_override_persists_and_resets_when_dataset_changes():
    at = app()
    dropdown(at, 'Dataset type').set_value('Finance').run()
    assert not at.exception
    assert at.session_state['dataset_type_override'] == 'Finance'
    at.radio(key='page').set_value('Data Overview').run()
    assert not at.exception
    assert at.session_state['dataset_type_override'] == 'Finance'
    dropdown(at, 'Sample dataset').set_value('Employees · example').run()
    assert not at.exception
    assert at.session_state['dataset_type_override'] == 'Auto-detect'
    assert dropdown(at, 'Metric').value == 'Salary_USD'
    at.radio(key='page').set_value('Executive Report').run()
    assert not at.exception
    assert any('Analysis context: Human Resources' in item.value for item in at.markdown)


def test_text_only_survey_safely_uses_record_counts():
    at = app()
    dropdown(at, 'Sample dataset').set_value('Survey · text only').run()
    assert not at.exception
    assert dropdown(at, 'Metric').value is None
    at.radio(key='page').set_value('Executive Report').run()
    assert not at.exception
    assert any('Analysis context: Survey' in item.value for item in at.markdown)
