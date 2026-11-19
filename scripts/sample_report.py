"""Generate a report from the bundled fictional sample; never reads private uploads."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.data_loader import load_data
from core.report_generator import pdf_bytes

root = Path(__file__).resolve().parents[1]
source = root / 'sample_data' / 'sales.csv'
data = load_data(source.read_bytes(), source.name)
output = root / 'docs' / 'sample_report.pdf'
output.write_bytes(pdf_bytes(data, 'Original fictional sales sample', {'Scope':'All records','Currency':'NGN'},
                             metric='Revenue_NGN', group='Product'))
print(f'Created {output.name}')
