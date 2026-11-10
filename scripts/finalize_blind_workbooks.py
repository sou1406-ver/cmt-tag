"""Verify workbook privacy and literal values, then seal a new ready task."""
import argparse
from pathlib import Path
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.normalize_annotations import read_input
from src.dataset.blind import BLIND_FIELDS
from src.dataset.common import load, save, seal, sha, staged, verify


def check_workbook(path, expected):
    fields, rows, _ = read_input(path, text_field='text_view')
    if fields != BLIND_FIELDS or rows != expected: raise ValueError('Workbook values differ from blinded task')
    with zipfile.ZipFile(path) as z:
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=workbook.findall('s:sheets/s:sheet',ns)
        if len(sheets)!=1 or sheets[0].get('state','visible')!='visible':raise ValueError('Only one visible blind sheet allowed')
        for name in z.namelist():
            if any(term in name for term in ('externalLinks','comments','threadedComments','customXml')):
                raise ValueError('Unexpected workbook metadata channel')
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                xml=ET.fromstring(z.read(name))
                if xml.findall('.//s:f',ns):raise ValueError('Formulas forbidden in blind annotation')
                for cell in xml.findall('.//s:sheetData/s:row/s:c',ns):
                    col=''.join(c for c in cell.get('r','') if c.isalpha())
                    if col not in 'ABCDEF' or len(col)!=1:raise ValueError('Extra columns forbidden')


def finalize(source, workbooks, output):
    source,workbooks=Path(source),Path(workbooks);manifest=verify(source)
    if manifest['status']!='RESERVED_PENDING_WORKBOOKS':raise ValueError('A full 180-item reservation required')
    payload=load(source/'workbook_input.json')
    if len(payload['a'])!=180 or len(payload['b'])!=50:raise ValueError('Expected exactly 180 A and 50 B rows')
    names={'a':'test_annotator_a.xlsx','b':'test_annotator_b_50.xlsx'}
    for key,name in names.items():check_workbook(workbooks/name,payload[key])
    with staged(output) as work:
        for name in manifest['output_sha256']:shutil.copyfile(source/name,work/name)
        for name in names.values():shutil.copyfile(workbooks/name,work/name)
        result={k:v for k,v in manifest.items() if k!='output_sha256'}
        result.update(status='BLIND_READY',parent_reservation_manifest_sha256=sha(source/'manifest.json'))
        return seal(work,result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','workbooks','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=finalize(a.source,a.workbooks,a.output);print(r['status'])


if __name__=='__main__':main()
