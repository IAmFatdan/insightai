"""Deterministic Phase 5 dataset recognition; no provider calls or row inspection."""
import pandas as pd
import pytest

from core.dataset_recognition import recognize_dataset


@pytest.mark.parametrize('fields,expected', [
    (['Date', 'Product', 'Units_Sold', 'Revenue_NGN'], 'Sales'),
    (['Patient_ID', 'Diagnosis', 'Admission_Date'], 'Healthcare'),
    (['EmployeeID', 'Department', 'Salary_USD', 'Years_Experience'], 'Human Resources'),
    (['Ledger_Account', 'Debit', 'Credit', 'Budget'], 'Finance'),
    (['Student_ID', 'Exam_Score', 'Attendance', 'Course'], 'Education'),
    (['Campaign_ID', 'Clicks', 'Impressions', 'Ad_Spend'], 'Marketing'),
    (['Respondent', 'Course', 'Rating', 'Comment'], 'Survey'),
    (['RandomA', 'RandomB', 'RandomC'], 'General'),
    (['Revenue'], 'General'),
])
def test_recognizes_distinct_schemas(fields, expected):
    df = pd.DataFrame({name: [1, 2] for name in fields})
    result = recognize_dataset(df)
    assert result['detected_type'] == expected
    assert result['active_type'] == expected
    assert result['override_applied'] is False
    assert result['method'].startswith('Column-name')


def test_sales_field_preferences_and_no_identifier_metric():
    df = pd.DataFrame({'Date': ['2026-01-01'], 'Product': ['Laptop'],
                       'Region': ['Lagos'], 'Units_Sold': [2],
                       'Revenue_NGN': [1000], 'Order_ID': [123]})
    result = recognize_dataset(df)
    assert result['suggested_fields'] == {'metric': 'Revenue_NGN', 'group': 'Product', 'date': 'Date'}
    assert result['match_strength'] == 'Strong schema match'


def test_employee_metric_is_salary_and_groups_by_department():
    df = pd.DataFrame({'EmployeeID': ['E-1'], 'Department': ['Engineering'],
                       'Salary_USD': [6000], 'Years_Experience': [3],
                       'Start_Date': ['2025-02-01']})
    result = recognize_dataset(df)
    assert result['suggested_fields']['metric'] == 'Salary_USD'
    assert result['suggested_fields']['group'] == 'Department'
    assert result['sensitive_data_caution'] is True


def test_user_override_does_not_mutate_dataset_or_change_detected_evidence():
    df = pd.DataFrame({'Product': ['A'], 'Units_Sold': [1], 'Revenue_NGN': [200]})
    before = df.copy(deep=True)
    result = recognize_dataset(df, override='Finance')
    assert result['detected_type'] == 'Sales'
    assert result['active_type'] == 'Finance'
    assert result['override_applied'] is True
    pd.testing.assert_frame_equal(df, before)


def test_ambiguous_schema_uses_general_without_probability():
    df = pd.DataFrame({'Patient_ID': ['P1'], 'Diagnosis': ['X'],
                       'Employee_ID': ['E1'], 'Department': ['D']})
    result = recognize_dataset(df)
    assert result['detected_type'] == 'General'
    assert result['match_strength'] == 'Uncertain or mixed schema'
    assert 'probability' not in result


def test_empty_dataset_and_text_only_recommend_no_metric():
    result = recognize_dataset(pd.DataFrame(columns=['foo', 'bar']))
    assert result['detected_type'] == 'General'
    assert result['suggested_fields']['metric'] is None
    text = recognize_dataset(pd.DataFrame({'Respondent': ['R1'], 'Rating': ['Good'],
                                           'Comment': ['Nice']}))
    assert text['detected_type'] == 'Survey'
    assert text['suggested_fields']['metric'] is None
    assert text['suggested_fields']['group'] == 'Rating'


def test_invalid_override_and_type_fail_closed():
    with pytest.raises(ValueError):
        recognize_dataset(pd.DataFrame({'Revenue': [4]}), override='Clinical verdict')
    with pytest.raises(TypeError):
        recognize_dataset([1, 2])


def test_only_schema_is_read_not_value_conversions():
    class UnsafeValue:
        def __str__(self):
            raise AssertionError('row values must not be inspected')
        def __repr__(self):
            return '<private>'
    df = pd.DataFrame({'Patient_ID': pd.Series([UnsafeValue()], dtype='object'),
                       'Diagnosis': pd.Series([UnsafeValue()], dtype='object')})
    result = recognize_dataset(df)
    assert result['detected_type'] == 'Healthcare'
    assert 'private' not in str(result).lower()
