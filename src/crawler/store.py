"""Durable append-only journals; checkpoint is a derived optimization."""
import csv
import hashlib
import json
import os
import random
import re
import textwrap
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .parser import (facebook_url, comment_identity, post_id, created_at, TEXT_FIELDS, CLEAN_FIELDS,
                     EVIDENCE_FIELDS, METADATA_FIELDS, valid_text_metadata, valid_extra_metadata, source_metadata)


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value, exclusive=False):
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if exclusive:
        with path.open('x', encoding='utf-8') as f:
            f.write(data)
    else:
        tmp = path.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)


def load_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def run_config(path):
    config = json.loads((path/'config.json').read_text(encoding='utf-8'))
    if (path/'interactive_mode.json').exists(): config['interactive']=True
    if config.get('interactive') and (path/'interactive_inputs.jsonl').exists():
        config['posts'] = config['posts'] + load_lines(path/'interactive_inputs.jsonl')
    return config


class Store:
    def __init__(self, root, config=None, resume=None, interactive=False):
        if resume and not re.fullmatch(r'[A-Za-z0-9_-]+', resume):
            raise ValueError('Invalid run ID')
        self.run_id = resume or ('fb_' + uuid4().hex)
        self.path = Path(root) / self.run_id
        if resume:
            self.config = json.loads((self.path/'config.json').read_text(encoding='utf-8'))
            if (self.path/'interactive_mode.json').exists(): self.config['interactive']=True
            checkpoint = json.loads((self.path / 'checkpoint.json').read_text(encoding='utf-8'))
            if checkpoint['status'] == 'complete' and not (self.config.get('interactive') or interactive):
                raise ValueError('Completed runs are immutable; create a new run')
        else:
            if config.get('campaign_v2'):
                for post in config['posts']:
                    cap=post.get('max_comments',config['max_comments'])
                    if type(cap) is not int or not 1<=cap<=500:raise ValueError('V2 max_comments must be 1..500')
                if type(config.get('max_comments')) is not int or not 1<=config['max_comments']<=500:
                    raise ValueError('V2 max_comments must be 1..500')
            for post in config['posts']:source_metadata(post)
            self.path.mkdir(parents=True, exist_ok=False)
            self.config = dict(config, run_id=self.run_id, created_at=now())
            self.config['source_dataset'] = self.config.get('source_dataset') or self.run_id
            write_json(self.path / 'config.json', self.config, exclusive=True)
            for name in ('raw_comments.jsonl', 'posts.jsonl', 'errors.jsonl'):
                (self.path / name).touch(exist_ok=False)
        # If a hard stop left an incomplete journal write, retain bytes in a
        # recovery file and truncate ONLY the uncommitted tail before appending.
        journals = ['raw_comments.jsonl', 'posts.jsonl', 'errors.jsonl']
        if (self.path/'interactive_inputs.jsonl').exists():
            journals.append('interactive_inputs.jsonl')
        for name in journals:
            path = self.path / name
            data = path.read_bytes()
            if data and not data.endswith(b'\n'):
                tail = data.rsplit(b'\n', 1)[-1]
                backup = self.path / (name + '.tail_' + uuid4().hex)
                backup.write_bytes(tail)
                with path.open('r+b') as f:
                    f.truncate(len(data) - len(tail))
        if interactive and not self.config.get('interactive'):
            write_json(self.path/'interactive_mode.json',{'interactive':True},exclusive=True)
            self.config['interactive']=True
        if self.config.get('interactive'):
            self.config = run_config(self.path)
        self.rows = load_lines(self.path / 'raw_comments.jsonl')
        self.post_counts = Counter(r['post_url'] for r in self.rows)
        self.posts = load_lines(self.path / 'posts.jsonl')
        self.keys = {self.key(r) for r in self.rows if self.key(r)}
        # Reuse prior raw journals as the identity index, not a second ledger.
        if self.config.get('campaign_v2'):
            for journal in sorted(self.path.parent.glob('*/raw_comments.jsonl')):
                if journal.parent==self.path:continue
                for line in journal.read_bytes().splitlines(keepends=True):
                    if not line.endswith(b'\n'):continue # uncommitted crash tail
                    item=json.loads(line)
                    key=self.key(item)
                    if key:self.keys.add(key)
        self.local_seen = set()
        self.displayed_counts={p['post_url']:p.get('displayed_count') for p in self.posts}
        self.checkpoint_every = 25
        self.checkpoint('running')

    @staticmethod
    def key(row):
        if row.get('comment_id'):
            return ('facebook', row['comment_id'])
        if row.get('comment_permalink'):
            return ('facebook_permalink', row['comment_permalink'])
        return None

    def add_post(self, post):
        if not self.config.get('interactive'):
            raise ValueError('Only interactive runs can append input posts')
        existing = next((p for p in self.config['posts'] if p['post_url']==post['post_url']),None)
        if existing:
            if existing['movie_id'] != post['movie_id']:
                raise ValueError('This post already belongs to another movie in this run')
            return
        if len(self.config['posts']) >= self.config['max_posts']:
            raise ValueError('Run reached max_posts; start a new run')
        source_metadata(post)
        cap=post.get('max_comments',self.config['max_comments'])
        if self.config.get('campaign_v2') and (type(cap) is not int or not 1<=cap<=500):
            raise ValueError('V2 max_comments must be 1..500')
        self.append('interactive_inputs.jsonl',post)
        self.config['posts'].append(post)

    def append(self, name, value):
        with (self.path / name).open('a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(value, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())

    def add(self, observation, post, page_session):
        row = {k: v for k, v in observation.items() if k != 'dom_observation_id'}
        key = self.key(row)
        local_key = (page_session, observation['dom_observation_id'], row['text_raw'], row['extraction_status'])
        if key in self.keys or local_key in self.local_seen:
            # Journaling counts makes reports reproducible after a crash.
            if key in self.keys and local_key not in self.local_seen:
                self.append('errors.jsonl', {'code':'duplicate_source_id', 'post_url':post['post_url'], 'at':now()})
            self.local_seen.add(local_key)
            return False
        self.local_seen.add(local_key)
        row.update(internal_record_id='r_' + uuid4().hex, post_url=post['post_url'],
                   movie_id=post['movie_id'], collected_at=now(),
                   source_dataset=self.config['source_dataset'], crawl_run_id=self.run_id,
                   possible_duplicate=key is None)
        row.update(source_metadata(post))
        self.append('raw_comments.jsonl', row)
        self.rows.append(row)
        self.post_counts[row['post_url']] += 1
        if key:
            self.keys.add(key)
        if len(self.rows) % self.checkpoint_every == 0:
            self.checkpoint('running')
        return True

    def finish_post(self, post, status, reason, **extra):
        extra.setdefault('displayed_count',self.displayed_counts.get(post['post_url']))
        item = dict(post, status=status, reason=reason, at=now(),**extra)
        self.append('posts.jsonl', item)
        self.posts.append(item)
        self.checkpoint('running')
        write_json(self.path/'crawl_report.json',validate(self.path))

    def checkpoint(self, status):
        write_json(self.path / 'checkpoint.json', {'status':status, 'rows':len(self.rows),
                   'updated_at':now(), 'run_id':self.run_id})

    def finish(self):
        report = validate(self.path)
        write_json(self.path / 'crawl_report.json', report)
        complete = (not report['posts_without_result'] and
                    report['post_status_counts']['success'] == report['requested_posts'])
        self.checkpoint('complete' if complete else 'interrupted')
        return report


FIELDS = ('text_raw', 'comment_id', 'post_id', 'post_url', 'parent_comment_id',
          'movie_id', 'collected_at', 'comment_created_at', 'source_dataset',
          'crawl_run_id', 'record_type', 'extraction_status', 'internal_record_id')


def validate(path):
    path = Path(path)
    config = run_config(path)
    rows, parse_errors = [], 0
    raw_errors_by_post=Counter()
    internal_ids = set()
    sources = {p['post_url']:p['movie_id'] for p in config['posts']}
    for line in (path/'raw_comments.jsonl').read_text(encoding='utf-8').splitlines():
        item_source=None
        try:
            r = json.loads(line)
            item_source=r.get('post_url') if isinstance(r,dict) and isinstance(r.get('post_url'),str) else None
            if (any(k not in r for k in FIELDS) or not isinstance(r['text_raw'], str) or
                    not valid_text_metadata(r) or not valid_extra_metadata(r)):
                raise ValueError()
            facebook_url(r['post_url'])
            if r['post_url'] not in sources or r['movie_id'] != sources[r['post_url']]:
                raise ValueError('Unknown source')
            if r['crawl_run_id'] != config['run_id'] or r['source_dataset'] != config['source_dataset']:
                raise ValueError('Provenance mismatch')
            if r['internal_record_id'] in internal_ids:
                raise ValueError('Duplicate internal ID')
            internal_ids.add(r['internal_record_id'])
            if r['post_id'] is not None and r['post_id'] != post_id(r['post_url']):
                raise ValueError('Post ID mismatch')
            if r['comment_id'] and comment_identity(r.get('comment_permalink'), r['post_url'])[0] != r['comment_id']:
                raise ValueError('Unverified comment ID')
            if r['comment_created_at'] and not created_at(r['comment_created_at']):
                raise ValueError('Invalid creation time')
            if r['record_type'] not in ('comment','reply') or r['extraction_status'] not in ('complete','truncated'):
                raise ValueError()
            if not datetime.fromisoformat(r['collected_at']).tzinfo:
                raise ValueError('Missing timestamp timezone')
            rows.append(r)
        except (ValueError, TypeError, KeyError, AttributeError):
            parse_errors += 1
            raw_errors_by_post[item_source]+=1
    posts = {p['post_url']:p for p in load_lines(path/'posts.jsonl')}
    statuses = Counter(p['status'] for p in posts.values())
    keys = [Store.key(r) for r in rows if Store.key(r)]
    duplicates = len(keys)-len(set(keys))
    errors = load_lines(path/'errors.jsonl')
    metadata = ('comment_id','post_id','parent_comment_id','movie_id','collected_at','comment_created_at','post_url',
                'source_name','source_type','reaction_count','crawl_run_id')
    present=lambda r,k:r.get(k) is not None and r.get(k)!=''
    per_post_quality={}
    for source,movie in sources.items():
        subset=[r for r in rows if r['post_url']==source]
        source_errors=[e for e in errors if e.get('post_url')==source]
        source_keys=[Store.key(r) for r in subset if Store.key(r)]
        result=posts.get(source,{})
        per_post_quality[source]={'movie_id':movie,'records':len(subset),
            'record_types':dict(Counter(r['record_type'] for r in subset)),
            'clean_status':dict(Counter(r.get('clean_status','UNKNOWN') for r in subset)),
            'missing_metadata':{k:sum(not present(r,k) for r in subset
                                     if k!='parent_comment_id' or r['record_type']=='reply') for k in metadata},
            'replies_missing_parent_id':sum(r['record_type']=='reply' and not r['parent_comment_id'] for r in subset),
            'duplicate_ids_in_raw':len(source_keys)-len(set(source_keys)),
            'duplicate_observations_skipped':sum(e['code']=='duplicate_source_id' for e in source_errors),
            'dom_parse_observations':sum(e.get('count',1) for e in source_errors if e['code']=='parse_error'),
            'raw_validation_errors':raw_errors_by_post[source],
            'truncated':sum(r['extraction_status']=='truncated' for r in subset),
            'status':result.get('status'),'reason':result.get('reason'),
            'displayed_count':result.get('displayed_count'),'coverage_verified':False}
        for key,n in per_post_quality[source]['missing_metadata'].items():
            denominator=sum(r['record_type']=='reply' for r in subset) if key=='parent_comment_id' else len(subset)
            per_post_quality[source].setdefault('missing_metadata_rate',{})[key]=n/denominator if denominator else None
    sample = random.Random(42).sample(rows, min(10,len(rows)))
    return {'run_id':config['run_id'], 'requested_posts':len(config['posts']),
            'post_status_counts':{k:statuses[k] for k in ('success','failed','partial','blocked')},
            'posts_without_result':len(config['posts'])-len(posts),
            'total_records':len(rows), 'record_types':dict(Counter(r['record_type'] for r in rows)),
            'coverage_verified':False,'record_count_cap':config.get('max_comments'),
            'collection_scope':'accessible visible comments and replies; safety budgets apply; total coverage unknown',
            'with_comment_id':sum(bool(r['comment_id']) for r in rows),
            'with_post_id':sum(bool(r['post_id']) for r in rows),
            'missing_metadata_records':sum(any(not r[k] for k in ('comment_id','post_id','comment_created_at')) for r in rows),
            'metadata_completeness_rate':{k:sum(present(r,k) for r in rows)/len(rows) if rows else 0 for k in metadata},
            'truncated':sum(r['extraction_status']=='truncated' for r in rows),
            'duplicate_source_ids_in_raw':duplicates,
            'duplicate_source_observations_skipped':sum(e['code']=='duplicate_source_id' for e in errors),
            'possible_duplicates_unresolved':sum(r.get('possible_duplicate',False) for r in rows),
            'raw_validation_errors':parse_errors,
            'dom_parse_observations':sum(e.get('count',1) for e in errors if e['code']=='parse_error'),
            'parse_errors':parse_errors+sum(e.get('count',1) for e in errors if e['code']=='parse_error'),
            'per_post':dict(Counter(r['post_url'] for r in rows)),
            'per_movie':dict(Counter(r['movie_id'] for r in rows)),
            'per_post_quality':per_post_quality,
            'posts':list(posts.values()), 'manual_review_sample':[
                {k:r[k] for k in ('internal_record_id','text_raw','post_url','comment_id','extraction_status')} for r in sample],
            'warnings':['Visible accessible comments only; total coverage cannot be verified.',
                        'Parent IDs apply only to replies; created_at is not collected_at.',
                        'Missing post metadata does not establish post-independent splits.'],
            'uncommitted_tail_backups':[p.name for p in path.glob('*.tail_*')],
            'raw_sha256':hashlib.sha256((path/'raw_comments.jsonl').read_bytes()).hexdigest()}


def _export_records(path,allow_partial,require_complete=True):
    path=Path(path)
    from .locking import run_is_busy
    if run_is_busy(path/'.browser.lock'):
        raise ValueError('Cannot export while a browser may be writing this run')
    report = validate(path)
    if report['raw_validation_errors'] or report['duplicate_source_ids_in_raw']:
        raise ValueError('Validation failed; inspect run report')
    if report['dom_parse_observations'] and not allow_partial:
        raise ValueError('Unparsed DOM observations; inspect report and use --allow-partial to export validated rows only')
    rows = load_lines(path/'raw_comments.jsonl')
    # Preserve raw. Phase B only receives complete observations. Excluded
    # truncated rows remain in the raw journal and export manifest.
    complete = [r for r in rows if r['extraction_status']=='complete']
    if not complete and require_complete:
        raise ValueError('No complete records to import')
    return report,rows,complete


def export_run(path, destination, *, allow_partial=False):
    path,destination=Path(path),Path(destination)
    report,rows,complete=_export_records(path,allow_partial)
    if destination.exists():
        if not destination.is_dir() or {p.name for p in destination.iterdir()}!={'review.xlsx'}:
            raise FileExistsError('Export directory already exists')
    else:destination.mkdir(parents=True, exist_ok=False)
    csv_path = destination/'comments.csv'
    with csv_path.open('x',encoding='utf-8-sig',newline='') as f:
        optional=list(TEXT_FIELDS) if any('text_extraction_version' in row for row in complete) else []
        if any('text_clean' in row for row in complete): optional+=list(CLEAN_FIELDS)
        if any('clean_evidence' in row for row in complete): optional+=list(EVIDENCE_FIELDS)
        optional+=list(METADATA_FIELDS)
        writer=csv.DictWriter(f,fieldnames=list(FIELDS)+['comment_permalink','possible_duplicate']+optional)
        writer.writeheader()
        writer.writerows({**row, **{key:json.dumps(row[key],ensure_ascii=False)
                                   for key in ('clean_review_reasons',)+EVIDENCE_FIELDS if key in row}}
                         for row in complete)
    config = {'schema_version':'1.0','inputs':[{'path':str(csv_path.resolve()),'format':'csv',
        'source_dataset':json.loads((path/'config.json').read_text(encoding='utf-8'))['source_dataset'],
        'post_namespace':'facebook','columns':{k:k for k in ('text_raw','comment_id','post_id','post_url',
             'parent_comment_id','movie_id','collected_at')}}],
        'quality':{'ui_strings':[],'spam_patterns':[]},
        'near_duplicate':{'threshold':0.9,'min_chars':40,'shingle_size':3},
        'split':{'seed':42,'ratios':{'train':0.7,'dev':0.15,'test':0.15}}}
    write_json(destination/'import_config.json',config,exclusive=True)
    write_json(destination/'export_manifest.json',{'run_id':report['run_id'],
        'raw_sha256':report['raw_sha256'],'exported':len(complete),
        'truncated_not_imported':len(rows)-len(complete),
        'allow_partial':allow_partial,
        'raw_validation_errors':report['raw_validation_errors'],
        'dom_parse_observations':report['dom_parse_observations'],
        'post_status_counts':report['post_status_counts'],
        'coverage_verified':False,
        'warnings':report['warnings']+(['DOM parse counts are repeated observations, not unique missing comments.']
                                      if report['dom_parse_observations'] else []),
        'note':'No labels; Phase B keeps all records but marks text duplicates as non-independent.'},exclusive=True)
    return destination


def export_review(path,destination,*,allow_partial=False):
    """One portable, filterable XLSX review view; raw/journals remain authoritative."""
    report,rows,_=_export_records(path,allow_partial,require_complete=False)
    if not rows:raise ValueError('No complete records or raw observations to review')
    destination=Path(destination)
    fields=('movie_id','post_id','post_url','source_name','source_type','comment_id','parent_comment_id',
            'record_type','comment_created_at','collected_at','run_id','reaction_count','text_raw','text_clean',
            'mention_count','url_count','non_text_media_count','clean_status','extraction_status','displayed_count')
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheet=ET.Element('worksheet',xmlns=ns)
    views=ET.SubElement(sheet,'sheetViews');view=ET.SubElement(views,'sheetView',workbookViewId='0')
    ET.SubElement(view,'pane',ySplit='1',topLeftCell='A2',activePane='bottomLeft',state='frozen')
    cols=ET.SubElement(sheet,'cols')
    for i,key in enumerate(fields,1):
        ET.SubElement(cols,'col',min=str(i),max=str(i),width=str(75 if key in ('text_raw','text_clean') else 35 if key=='post_url' else 23),customWidth='1')
    data=ET.SubElement(sheet,'sheetData')
    for index,record in enumerate([dict(zip(fields,fields)),*rows],1):
        lines=max(sum(max(1,len(textwrap.wrap(line,70))) for line in (record.get(key) or '').split('\n'))
                  for key in ('text_raw','text_clean'))
        row=ET.SubElement(data,'row',r=str(index),ht=str(28 if index==1 else min(409,max(32,lines*16+12))),customHeight='1')
        record=dict(record)
        if index>1:
            record['run_id']=record['crawl_run_id']
            record['displayed_count']=report['per_post_quality'][record['post_url']]['displayed_count']
        for col,key in enumerate(fields,1):
            value=record.get(key);text='' if value is None else str(value)
            if len(text)>32767 or any(ord(c)<32 and c not in '\t\n\r' for c in text):
                raise ValueError('Excel cannot represent cell; use CSV/JSONL; raw was not changed')
            cell=ET.SubElement(row,'c',r=chr(64+col)+str(index),s='1' if index==1 else '2')
            if type(value) is int:ET.SubElement(cell,'v').text=str(value)
            else:
                cell.set('t','inlineStr');inline=ET.SubElement(cell,'is')
                ET.SubElement(inline,'t',{'{http://www.w3.org/XML/1998/namespace}space':'preserve'}).text=text
    ET.SubElement(sheet,'autoFilter',ref=f'A1:T{len(rows)+1}')
    styles=f'''<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF203864"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0"><alignment vertical="center"/></xf><xf fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>'''
    contents='''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'''
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',contents)
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Comments" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml',styles);z.writestr('xl/worksheets/sheet1.xml',ET.tostring(sheet,encoding='utf-8',xml_declaration=True))
    return destination
