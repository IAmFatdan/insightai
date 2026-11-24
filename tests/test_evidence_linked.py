"""Phase 3: evidence-linked commentary, no real API or secrets needed."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from pypdf import PdfReader

from core.ai_service import AIService
from core.data_analysis import facts
from core.advanced_analysis import advanced_report, extra_facts
from core.data_loader import DataError, load_data
from core.report_generator import pdf_bytes

ROOT = Path(__file__).resolve().parents[1]

FACTS = [
    {'id': 'F1', 'text': 'Highest recorded Revenue_NGN: Laptop generated 13,010,000.00 (71.15% of total).'},
    {'id': 'F2', 'text': 'Recorded revenue changed by -730,000.00 between two months; completeness unknown.'},
]

VALID = {
    'executive_summary': 'Recorded value concentration and a period difference merit closer investigation.',
    'insights': [
        {
            'evidence_id': 'F1',
            'business_implication': 'The overall recorded amount may be sensitive to changes in the leading category.',
            'recommended_next_step': 'Review category definitions and compare the leading category with other groups.',
            'hypothesis_to_test': 'Product mix may contribute to the observed concentration.',
            'priority': 'High',
        },
        {
            'evidence_id': 'F2',
            'business_implication': 'The observed period difference may not represent a sustained trend.',
            'recommended_next_step': 'Verify completeness of the compared periods before interpreting the change.',
            'hypothesis_to_test': 'Incomplete reporting may account for some of the apparent difference.',
            'priority': 'Medium',
        },
    ],
    'limitations': ['Findings describe the selected dataset only; missing records can affect totals.'],
}


class FakeOpenAI:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None
        self.responses = self

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.payload)


class FakeGemini:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None
        self.beta = SimpleNamespace(chat=SimpleNamespace(completions=self))

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=self.payload))])


@pytest.mark.parametrize('provider,client_factory', [('OpenAI', FakeOpenAI), ('Gemini', FakeGemini)])
def test_linked_brief_contains_exact_verified_evidence(provider, client_factory):
    client = client_factory(VALID)
    service = AIService(enabled=True, client=client, provider=provider)
    result = service.explain_linked(FACTS)
    assert result['format'] == 'linked'
    assert result['evidence_ids'] == ['F1', 'F2']
    assert result['insights'][0]['verified_finding'] == FACTS[0]['text']
    assert result['insights'][1]['verified_finding'] == FACTS[1]['text']
    assert result['recommendations'][0] == VALID['insights'][0]['recommended_next_step']
    assert result['limitations'] == VALID['limitations']
    assert service.budget['calls'] == 1
    if provider == 'OpenAI':
        assert client.kwargs['store'] is False
        sent = json.loads(client.kwargs['input'])
    else:
        sent = json.loads(client.kwargs['messages'][-1]['content'])
    assert sent == {'verified_facts': FACTS}  # No raw rows are transmitted.
    assert client.kwargs['model'] == service.model


@pytest.mark.parametrize('variant', [
    {'insights': [dict(VALID['insights'][0], evidence_id='F999')]},
    {'insights': [dict(VALID['insights'][0]), dict(VALID['insights'][0])]},
    {'insights': []},
    {'insights': VALID['insights'] * 2},
    {'insights': [dict(VALID['insights'][0], recommended_next_step='Increase revenue by 25 percent.')]},
    {'executive_summary': 'The data proves a 40 percent profit increase.'},
    {'insights': [dict(VALID['insights'][0], recommended_next_step='')]},
])
def test_invalid_ai_claims_rejected(variant):
    content = {**VALID, **variant}
    with pytest.raises(DataError):
        AIService(enabled=True, client=FakeOpenAI(content)).explain_linked(FACTS)


def test_bad_source_evidence_rejected_without_api_request():
    client = FakeOpenAI(VALID)
    for evidence in ([], [{'id': 'F1', 'text': ''}], [FACTS[0], FACTS[0]],
                     [{'id': 'X1', 'text': 'untrusted'}]):
        with pytest.raises(DataError):
            AIService(enabled=True, client=client).explain_linked(evidence)
    assert client.kwargs is None


def test_opt_in_and_limit_still_enforced():
    client = FakeGemini(VALID)
    with pytest.raises(DataError):
        AIService(enabled=False, client=client, provider='Gemini').explain_linked(FACTS)
    with pytest.raises(DataError):
        AIService(enabled=True, client=client, provider='Gemini', budget={'calls': 10}).explain_linked(FACTS)
    assert client.kwargs is None


def test_report_export_includes_linked_facts():
    data = load_data((ROOT / 'sample_data/sales.csv').read_bytes(), 'sales.csv')
    result = AIService(enabled=True, client=FakeGemini(VALID), provider='Gemini').explain_linked(FACTS)
    pdf = pdf_bytes(data, 'sales.csv', {'scope':'test'}, metric='Revenue_NGN', group='Product', ai=result)
    text = ' '.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert 'Evidence-linked insights' in text
    assert 'Verified calculation' in text
    assert '13,010,000.00' in text
    assert 'Next step' in text
    assert 'Limitations' in text


def test_sample_analytics_produce_evidence_without_appended_ai_numbers():
    df = load_data((ROOT / 'sample_data/sales.csv').read_bytes(), 'sales.csv')
    basic = facts(df, 'Revenue_NGN', 'Product', 'Date')
    evidence = basic + extra_facts(advanced_report(df, 'Revenue_NGN', 'Product', 'Date'), next_id=len(basic) + 1)
    assert any('71.15%' in f['text'] for f in evidence)
    assert any('-17.87%' in f['text'] for f in evidence)
    assert len(set(f['id'] for f in evidence)) == len(evidence)
