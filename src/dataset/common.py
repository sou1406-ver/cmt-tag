"""Small offline I/O helpers. Outputs are immutable, inputs are byte checked."""
import csv
import hashlib
import io
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
