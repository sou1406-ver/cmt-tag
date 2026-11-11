"""Read-only quality workbook validation/import; immutable text joined by ID."""
import json
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from .common import load,sha,save,write_csv,staged,seal
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_sheet(path,name):
    with zipfile.ZipFile(path) as z:
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        sheet=next(s for s in wb.findall('s:sheets/s:sheet',NS) if s.get('name')==name)
        rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rel=next(r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if r.get('Id')==rid)
        target=rel.get('Target');target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        if not target.startswith('xl/worksheets/'):raise ValueError('External/invalid sheet')
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(t.text or '' for t in s.iter('{'+NS['s']+'}t')) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        tree=ET.fromstring(z.read(target));grid=[]
        for row in tree.findall('s:sheetData/s:row',NS):
            cells={}
            for cell in row.findall('s:c',NS):
                if cell.find('s:f',NS) is not None:raise ValueError('Formulas not allowed in manual quality data')
                address=cell.get('r');col=''.join(c for c in address if c.isalpha());n=0
                for c in col:n=n*26+ord(c)-64
                value=cell.findtext('s:v','',NS)
                if cell.get('t')=='s':value=strings[int(value)]
                elif cell.get('t')=='inlineStr':value=''.join(t.text or '' for t in cell.findall('.//s:t',NS))
                cells[n]=value
            if cells:grid.append(cells)
        headers=[grid[0].get(i,'') for i in range(1,max(grid[0])+1)]
        if len(set(headers))!=len(headers):raise ValueError('Duplicate headers')
        rows=[{header:r.get(i,'') for i,header in enumerate(headers,1)} for r in grid[1:] if r.get(1)]
        return headers,rows,tree


def validate(path,input_json,require_complete=False):
    expected={r['record_id']:r for r in load(input_json)}
    headers,rows,tree=read_sheet(path,'Review');_,raw_rows,_=read_sheet(path,'Raw & Changes')
    if headers!=['id','text_annotation','quality_status_proposed','quality_reasons','human_quality_decision','human_note']:raise ValueError('Wrong review schema')
    for data in (rows,raw_rows):
        if len(data)!=200 or len({r['id'] for r in data})!=200 or {r['id'] for r in data}!=set(expected):raise ValueError('Workbook IDs differ')
    for r in rows:
        e=expected[r['id']]
        text=r['text_annotation'];text=text[1:] if text.startswith("'=") else text
        if text!=e['text_annotation'] or r['quality_status_proposed']!=e['quality_status'] or r['quality_reasons']!='; '.join(e['quality_reason_code']):raise ValueError('Source text/proposals edited')
        if r['human_quality_decision'] not in ('','KEEP','REVIEW','EXCLUDE'):raise ValueError('Invalid human decision')
        if require_complete and not r['human_quality_decision']:raise ValueError('Incomplete human quality review')
    for r in raw_rows:
        e=expected[r['id']]
        for key in ('text_raw','text_clean'):
            val=r[key][1:] if r[key].startswith("'=") else r[key]
            if val!=e[key]:raise ValueError('Raw/clean sheet text edited or truncated')
        if json.loads(r['transform_events'])!=e['transform_events']:raise ValueError('Transform evidence changed')
    if tree.find('s:sheetViews/s:sheetView/s:pane',NS) is None or tree.find('s:dataValidations',NS) is None:raise ValueError('Missing freeze/dropdown')
    return rows


def import_review(path,input_json,output):
    rows=validate(path,input_json,require_complete=True)
    with staged(output) as work:
        write_csv(work/'human_quality_decisions.local.csv',rows,['id','human_quality_decision','human_note'])
        seal(work,dict(status='HUMAN_QUALITY_REVIEW_IMPORTED',rows=len(rows),input_sha256=sha(path),coordinator_sha256=sha(input_json),sentiment_labels_changed=False,pilot_release_approved=False))
    return len(rows)
