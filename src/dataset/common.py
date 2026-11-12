"""Small offline I/O helpers. Outputs are immutable, inputs are byte checked."""
import csv
import hashlib
import io
import posixpath
import zipfile
import xml.etree.ElementTree as ET
import json
from pathlib import Path
import tempfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def csv_rows(payload):
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig'), newline=''))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Missing or repeated CSV header')
    rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('Malformed CSV row')
    return rows, reader.fieldnames


def write_csv(path, rows, fields):
    with Path(path).open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row.get(key), (dict, list))
                             else row.get(key, '') for key in fields})


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def write_jsonl(path, rows):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')


def literal_text(value):
    """Undo only the XLSX literal escape used for a leading equals sign."""
    return value[1:] if value.startswith("'=") else value


def validate_review_ids(rows, expected, count, message):
    """Shared coverage/uniqueness integrity; decision semantics belong to callers."""
    if len(rows)!=count or len({row['id'] for row in rows})!=count or {row['id'] for row in rows}!=set(expected):
        raise ValueError(message)


@contextmanager
def staged(output):
    output = Path(output).resolve()
    if output.exists(): raise FileExistsError('Immutable output exists: choose a new version')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.phase-g-', dir=output.parent) as temp:
        work = Path(temp) / 'output'; work.mkdir()
        yield work
        work.rename(output)


def seal(directory, metadata):
    metadata = dict(metadata, output_sha256={p.relative_to(directory).as_posix(): sha(p)
                    for p in sorted(directory.rglob('*')) if p.is_file()})
    save(directory/'manifest.json', metadata)
    return metadata


def verify(directory, mutable_files=()):
    directory = Path(directory).resolve(); manifest = load(directory/'manifest.json')
    for relative, checksum in manifest['output_sha256'].items():
        path = (directory/relative).resolve()
        if not path.is_relative_to(directory):raise ValueError('Invalid manifest path: '+relative)
        if relative in set(mutable_files):continue
        if not path.is_file() or sha(path) != checksum:
            raise ValueError('Manifest checksum mismatch: '+relative)
    return manifest


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
