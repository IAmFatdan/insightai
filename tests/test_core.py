from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from pydantic import ValidationError
from openpyxl import Workbook, load_workbook
from pypdf import PdfReader
from core.data_loader import load_data, sheet_names, DataError, MAX_BYTES
from core.data_analysis import kpis, profile, aggregate, filter_data, monthly, facts, date_columns
from core.data_cleaning import clean, replay
from core.chart_builder import build_chart, CHARTS
from core.chat_engine import infer_plan, execute_plan, make_plan, Plan
from core.ai_service import AIService, Commentary
from core.report_generator import csv_bytes, excel_bytes, pdf_bytes

ROOT = Path(__file__).resolve().parents[1]
@pytest.fixture
def sales():
    return load_data((ROOT/'sample_data/sales.csv').read_bytes(), 'sales.csv')

def workbook_bytes():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Employees'
    ws.append(['Name', 'Salary'])
    ws.append(['Ada', 100])
    wb.create_sheet('Second').append(['OnlyHeader'])
    b = BytesIO(); wb.save(b)
    return b.getvalue()

def test_sample_regression(sales):
    assert sales.shape == (24,5)
    assert sales.isna().sum().sum() == 2
    lagos = filter_data(sales, {'Region':['Lagos']})
    assert len(lagos) == 8
    assert kpis(lagos,'Revenue_NGN')['total'] == 9_140_000
    table = aggregate(lagos,'Product','Revenue_NGN').set_index('Group')
    assert table.loc['Laptop','Value'] == 7_430_000
    answer = execute_plan(lagos, infer_plan('What percentage of revenue comes from Laptop?',lagos,'Revenue_NGN'))
    assert '81.29%' in answer['answer']

def test_excel_sheets():
    data = workbook_bytes()
    assert sheet_names(data) == ['Employees','Second']
    assert load_data(data,'file.xlsx','Employees').iloc[0].Salary == 100
    with pytest.raises(DataError):
        load_data(data,'file.xlsx','missing')
    with pytest.raises(DataError):
        load_data(data,'file.xlsx','Second')

@pytest.mark.parametrize('data,name',[(b'','x.csv'),(b'A,B\n','x.csv'),(b'A,A\n1,2','x.csv'),(b'A,B\n1,2,3','x.csv'),(b'hello','x.xlsx'),(b'hello','x.exe'),(b'A\ninf','x.csv'),(b'A, \n1,2','x.csv')])
def test_invalid_uploads(data,name):
    with pytest.raises(DataError): load_data(data,name)

def test_encoding_and_delimiter():
    data = 'Name;Amount\nAndré;15'.encode('cp1252')
    with pytest.raises(DataError): load_data(data,'a.csv')
    assert load_data(data,'a.csv',encoding='cp1252',delimiter=';').iloc[0,0] == 'André'

def test_upload_limits():
    with pytest.raises(DataError): load_data(b'x'*(MAX_BYTES+1),'big.csv')
    with pytest.raises(DataError): load_data(('A\n'+'1\n'*100001).encode(),'big.csv')

def test_clean_reversible(sales):
    original = sales.copy(deep=True)
    actions = [{'operation':'Fill categorical missing','columns':['Region']},
               {'operation':'Fill numeric missing (median)','columns':['Revenue_NGN']}]
    result, log = replay(sales,actions)
    assert result.isna().sum().sum() == 0
    assert sum(s['cells_changed'] for s in log) == 2
    undone,_ = replay(sales,actions[:1])
    assert undone.Revenue_NGN.isna().sum() == 1
    reset,_ = replay(sales,[])
    assert_frame_equal(reset,original)
    assert_frame_equal(sales,original)

def test_duplicate_and_drop():
    df = pd.DataFrame({'A':[1,1,None]})
    clean1, log = clean(df,{'operation':'Remove duplicate rows'})
    assert len(clean1)==2 and log['rows_removed']==1
    clean2, log = clean(clean1,{'operation':'Drop rows with missing values','columns':['A']})
    assert len(clean2)==1 and log['rows_removed']==1

def test_conversion_requires_consent():
    df = pd.DataFrame({'Money':['₦1,200','bad',None]})
    action = dict(operation='Convert to number',columns=['Money'],strip_commas=True,currency_symbol='₦')
    with pytest.raises(DataError): clean(df,action)
    result, log = clean(df,dict(action,allow_invalid=True))
    assert result.Money.iloc[0]==1200 and result.Money.isna().sum()==2
    assert log['invalid_to_missing']==1

def test_explicit_dates():
    df = pd.DataFrame({'When':['01/02/2026','31/02/2026']})
    assert date_columns(df)==[]
    result, log = clean(df,dict(operation='Convert to date',columns=['When'],date_format='%d/%m/%Y',allow_invalid=True))
    assert result.When.iloc[0]==pd.Timestamp('2026-02-01')
    assert log['invalid_to_missing']==1

def test_standardize_collision():
    with pytest.raises(DataError):
        clean(pd.DataFrame({'A B':[1],'a_b':[2]}),{'operation':'Standardize column names'})

def test_text_normalization():
    df=pd.DataFrame({'A':['  Lagos ','LAGOS',None]})
    result,_=clean(df,dict(operation='Normalize category case',columns=['A']))
    assert result.A.tolist()[:2]==['lagos','lagos'] and pd.isna(result.A.iloc[2])

def test_all_missing_not_zero():
    df=pd.DataFrame({'Group':['A','A'],'Amount':[np.nan,np.nan]})
    assert kpis(df,'Amount')['total'] is None
    assert pd.isna(aggregate(df,'Group','Amount').Value.iloc[0])
    with pytest.raises(DataError): clean(df,dict(operation='Fill numeric missing (mean)',columns=['Amount']))

def test_filters_empty_missing_and_dates(sales):
    assert filter_data(sales,{'Region':[]}).empty
    assert len(filter_data(sales,{'Region':[None]}))==1
    selected=filter_data(sales,date_column='Date',start='2026-01-01',end='2026-01-31')
    assert len(selected)==4
    assert len(filter_data(sales,{'Region':['Lagos'],'Product':['Laptop']}))==3

def test_date_end_inclusive():
    df=pd.DataFrame({'Date':['2026-01-31 23:59:59','2026-02-01 00:00:00',None]})
    assert len(filter_data(df,date_column='Date',start='2026-01-01',end='2026-01-31'))==1
    assert len(filter_data(df,date_column='Date',start='2026-01-01',end='2026-01-31',include_missing=True))==2

def test_month_gaps():
    df=pd.DataFrame({'Date':['2026-01-02','2026-03-01'],'Amount':[10,20]})
    table=monthly(df,'Date','Amount')
    assert len(table)==3 and pd.isna(table.Value.iloc[1])

def test_missing_category_collision():
    df=pd.DataFrame({'C':['(Missing)',None],'N':[1,2]})
    assert len(aggregate(df,'C','N'))==2

@pytest.mark.parametrize('kind',CHARTS)
def test_charts(sales,kind):
    group='Date' if kind in ('Line','Area') else 'Product'
    fig,table=build_chart(sales,kind,'Revenue_NGN',group,'Units_Sold')
    assert fig.to_dict()['data'] and not table.empty

def test_reject_invalid_chart():
    df=pd.DataFrame({'C':['A','B'],'N':[-1,2]})
    with pytest.raises(DataError): build_chart(df,'Pie','N','C')
    with pytest.raises(DataError): build_chart(df,'Scatter','N','C','C')
    with pytest.raises(DataError): build_chart(df,'Line','N','C')

@pytest.mark.parametrize('question,fragment',[
    ('Which product generated the most revenue?','Laptop'),
    ('Which region performed best?','Lagos'),
    ('What is the average transaction value?','Mean'),
    ('How many records are missing information?','2 records'),
    ('Compare the top five products.','Product'),
    ('Which variables have the strongest correlation?','Pearson'),
    ('Summarize the most important findings.','24 records'),
    ('Compare 2026-01 and 2026-02','Change from'),
    ('What recommendations can we make from this dataset?','Recommendation')])
def test_local_questions(sales,question,fragment):
    result=execute_plan(sales,infer_plan(question,sales,'Revenue_NGN'))
    combined=result['answer'] + (result['table'].to_string() if result['table'] is not None else '')
    assert fragment in combined

def test_followup(sales):
    first=infer_plan('total revenue in Lagos',sales,'Revenue_NGN')
    second=infer_plan('what about Abuja?',sales,'Revenue_NGN',first)
    result=execute_plan(sales,second)
    assert result['records']==6
    assert second.filters[0].value=='Abuja'

@pytest.mark.parametrize('question',['execute python import os','predict profit next year','total revenue in Atlantis','who is the president?'])
def test_unsupported_chat(sales,question):
    with pytest.raises(DataError): infer_plan(question,sales,'Revenue_NGN')

def test_plan_rejects_arbitrary_fields_and_types(sales):
    with pytest.raises(ValidationError): Plan.model_validate({'operation':'exec','code':'x'})
    with pytest.raises(ValidationError): make_plan(limit=1000)
    with pytest.raises(DataError): execute_plan(sales,make_plan(operation='aggregate',metric='unknown'))
    with pytest.raises(DataError): execute_plan(sales,make_plan(filters=[{'column':'Region','value':'Atlantis'}]))

def test_percentage_zero_or_negative():
    for vals in ([0,0],[-1,3],[np.nan,np.nan]):
        df=pd.DataFrame({'C':['A','B'],'N':vals})
        with pytest.raises(DataError): execute_plan(df,make_plan(operation='share',metric='N',group='C',category='A'))

def test_other_schemas():
    employees=load_data((ROOT/'sample_data/employees.csv').read_bytes(),'employees.csv')
    assert kpis(employees,'Salary_USD')['missing']==1
    survey=load_data((ROOT/'sample_data/survey.csv').read_bytes(),'survey.csv')
    assert kpis(survey)['records']==6
    assert execute_plan(survey,infer_plan('how many records?',survey))['records']==6
    assert len(facts(survey))>=2

class FakeClient:
    def __init__(self, result=None, error=None):
        self.result,self.error,self.kwargs=result,error,None
        self.responses=self
    def parse(self,**kwargs):
        self.kwargs=kwargs
        if self.error: raise self.error
        return SimpleNamespace(output_parsed=self.result)

@pytest.mark.parametrize('status',[400,401,403,404,429,500,None])
def test_ai_failure_redacted(status):
    exc=RuntimeError('secret-api-key raw payload')
    exc.status_code=status
    api=AIService(enabled=True,client=FakeClient(error=exc))
    with pytest.raises(DataError) as got: api.explain([{'id':'F1','text':'24 records'}])
    assert 'secret' not in str(got.value) and api.budget['calls']==1

def test_ai_opt_in_and_budget():
    client=FakeClient()
    with pytest.raises(DataError): AIService(client=client).explain([])
    assert client.kwargs is None
    with pytest.raises(DataError): AIService(enabled=True).explain([])
    with pytest.raises(DataError): AIService(enabled=True,client=client,budget={'calls':10}).explain([])

def test_ai_grounding():
    valid=dict(executive_summary='Recorded values differ across categories.',evidence_ids=['F1'],hypotheses_to_investigate=[],recommendations=['Review source completeness.'],limitations=['Missing values may affect totals.'])
    client=FakeClient(valid)
    result=AIService(enabled=True,client=client).explain([{'id':'F1','text':'24 records'}])
    assert result['evidence_ids']==['F1']
    assert client.kwargs['store'] is False
    assert 'raw_rows' not in client.kwargs['input']
    for update in ({'evidence_ids':['F900']},{'executive_summary':'Profit grows 99 percent.'}):
        with pytest.raises(DataError): AIService(enabled=True,client=FakeClient(dict(valid,**update))).explain([{'id':'F1','text':'24 records'}])
    with pytest.raises(DataError): AIService(enabled=True,client=FakeClient(None)).explain([])

def test_exports(sales):
    df=pd.DataFrame({'Name':['=HYPERLINK("evil")','@SUM(1)','Normal'],'Amount':[1,2,3]})
    assert b"'=HYPERLINK" in csv_bytes(df)
    xlsx=excel_bytes(df,{'scope':'test'})
    ws=load_workbook(BytesIO(xlsx))['Cleaned data']
    assert ws['A2'].data_type=='s' and ws['A2'].value.startswith("'")
    assert ws['B2'].data_type=='n'
    pdf=pdf_bytes(sales,'sales.csv',{'scope':'all'},metric='Revenue_NGN',group='Product')
    reader=PdfReader(BytesIO(pdf))
    text=' '.join(page.extract_text() for page in reader.pages)
    assert 'Calculated findings' in text and 'Limitations' in text and len(reader.pages)>=2

def test_empty_reports(sales):
    assert pdf_bytes(sales.iloc[:0],'empty',{},metric='Revenue_NGN',group='Product').startswith(b'%PDF')
    assert excel_bytes(sales.iloc[:0],{}).startswith(b'PK')

def test_monthly_count_means_records():
    df=pd.DataFrame({'Date':['2026-01-02','2026-01-03','2026-03-01'],'Amount':[10,np.nan,20]})
    result=monthly(df,'Date','Amount','count')
    assert result.Value.iloc[0]==2 and pd.isna(result.Value.iloc[1])

def test_revenue_alias_overrides_selected_metric(sales):
    result=execute_plan(sales,infer_plan('total revenue in Lagos',sales,'Units_Sold'))
    assert '9,140,000.00' in result['answer']

@pytest.mark.parametrize('question',['total revenue excluding Lagos','total revenue above 1000','total revenue not Lagos'])
def test_no_silently_ignored_conditions(sales,question):
    with pytest.raises(DataError): infer_plan(question,sales,'Revenue_NGN')

def test_share_plan_cannot_filter_denominator(sales):
    with pytest.raises(DataError):
        execute_plan(sales,make_plan(operation='share',metric='Revenue_NGN',group='Product',category='Laptop',filters=[{'column':'Product','value':'Laptop'}]))
