"""Single-annotator new-Facebook gold protocol. No network or browser actions."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from urllib.parse import urlsplit
import json
import random
import re
import textwrap
import unicodedata
import zipfile
from xml.etree import ElementTree as ET
from src.dataset.common import (ROOT, csv_rows, digest, load, normal, read_jsonl, read_sheet,
    save, seal, sha, staged, verify, write_csv, write_jsonl)
from src.dataset.master import post_url
from src.crawler.parser import post_id
from src.crawler.store import run_config, validate as validate_run, export_run
from src.preprocessing import preprocess
from .guidelines import GUIDELINE, GUIDELINE_VERSION, validate_guideline

CATEGORIES=['POS','NEG','NEU','REVIEW','EXCLUDE']
FIELDS=['id','text','label','note']
SEED=20261113
CAPS=dict(total=300,post=12,group=100,movie=36)

def now():
    return datetime.now(timezone.utc).isoformat()

def history_files(root):
    """Explicit data scopes; never visit profiles, credentials or model caches."""
    root = Path(root)
    paths = set()
    for directory in sorted((root/'data/crawl_runs').glob('*')):
        for name in ('config.json', 'interactive_inputs.jsonl', 'raw_comments.jsonl', 'posts.jsonl'):
            if (directory/name).is_file(): paths.add(directory/name)
    for directory in (root/'data/imports', root/'data/raw'):
        if directory.exists():
            for path in directory.rglob('*'):
                if path.is_file() and (path.suffix in {'.csv', '.jsonl'} or
                        path.name in {'comments.json','reviews.json','export_manifest.json'} or
                        directory.name=='raw' and path.suffix=='.json'):
                    paths.add(path)
    for directory in sorted((root/'outputs/canonical/versions').glob('*')):
        for name in ('candidate.local.jsonl', 'normalized_annotation_view.local.jsonl', 'exclusion_ledger.local.jsonl'):
            if (directory/name).is_file(): paths.add(directory/name)
    for relative in ('outputs/phase_g/master/master.jsonl',
                     'outputs/phase_g/master/exposure_ledger.json',
                     'outputs/phase_g/blind_test/availability.json',
                     'outputs/phase_g/blind_test/reservation.json'):
        if (root/relative).is_file(): paths.add(root/relative)
    historical_names={'annotations.csv','records.jsonl','predictions.csv','selection.json','reservation.json',
        'post_quarantine.json','candidate_quarantine.json','task.json','coordinator.json'}
    for relative in ('outputs/development','outputs/phase_g1','outputs/phase_g2','outputs/phase_g/blind_test','data/processed','data/splits'):
        directory=root/relative
        if directory.exists():
            paths.update(p for p in directory.rglob('*') if p.is_file() and p.name in historical_names)
    for path in (root/'data/test_reservations').glob('*.json'):
        paths.add(path)
        entry = load(path)
        for key in ('plan_root', 'collection_root', 'reservation_root'):
            if entry.get(key):
                for name in ('candidate_quarantine.json', 'post_quarantine.json', 'reservation.json'):
                    ref = Path(entry[key])/name
                    if ref.is_file(): paths.add(ref)
    return sorted(path.resolve() for path in paths)

def objects(path):
    if path.suffix == '.csv':
        return csv_rows(path.read_bytes())[0]
    if path.suffix == '.jsonl':
        return read_jsonl(path)
    obj = load(path)
    return obj if isinstance(obj, list) else [obj]

def metadata_posts(value):
    """Only structured identity fields, never infer IDs/movies from comment text."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'post_id'} and item: found.add(str(item))
            elif key in {'post_url'} and item:
                try:
                    pid = post_id(item)
                    if pid: found.add(pid)
                except (TypeError, ValueError): pass
            elif key in {'post_ids', 'known_exposed_post_ids', 'source_candidates_requiring_exposure_audit'}:
                found.update(str(x) for x in item)
            elif key=='post_urls':
                for url in item:
                    try:
                        pid=post_id(url)
                        if pid: found.add(pid)
                    except (TypeError,ValueError): pass
            elif isinstance(item, (dict, list)) and key not in {'human_decisions', 'annotations', 'original_labels'}:
                found.update(metadata_posts(item))
    elif isinstance(value, list):
        for item in value: found.update(metadata_posts(item))
    return found

def old_references(snapshot):
    refs = {}
    text_fields=('text_raw','text_view','text_minimal','text_normalized','text_without_mentions','text','comment','body','content')
    def text_rows(value,parent_post=''):
        if isinstance(value,dict):
            pid=str(value.get('post_id') or parent_post)
            if any(isinstance(value.get(k),str) and value[k] for k in text_fields): yield value,pid
            for item in value.values():
                if isinstance(item,(dict,list)): yield from text_rows(item,pid)
        elif isinstance(value,list):
            for item in value: yield from text_rows(item,parent_post)
    for filename, expected in snapshot.items():
        path = Path(filename)
        if sha(path) != expected: raise ValueError('Pre-crawl historical input changed: '+filename)
        for row,pid in text_rows(objects(path)):
            texts = [row.get(k, '') for k in text_fields]
            for field in ('text_variants','source_text_variants'):
                variants=row.get(field) or []
                if isinstance(variants,str): variants=json.loads(variants)
                if not isinstance(variants,list): raise ValueError('Malformed historical text variants')
                texts.extend(variants)
            for text in texts:
                if not isinstance(text, str) or not text: continue
                view = preprocess(text)
                key = 'old_'+digest(pid+'\n'+view)
                refs[key] = dict(record_id=key, text_clean=view, text_raw=view, text_normalized=view,
                    post_id=pid, comment_id=str(row.get('comment_id') or ''), source_dataset='historical',
                    original_id=row.get('record_id') or row.get('id') or row.get('internal_record_id') or '')
    return list(refs.values())

def workbook(path, rows, fields=FIELDS, label_column=3):
    """Small dependency-free OOXML writer; literal strings, no formula inference."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheet = ET.Element('worksheet', xmlns=ns)
    views = ET.SubElement(sheet, 'sheetViews'); view = ET.SubElement(views, 'sheetView', workbookViewId='0')
    ET.SubElement(view, 'pane', ySplit='1', topLeftCell='A2', activePane='bottomLeft', state='frozen')
    cols = ET.SubElement(sheet, 'cols')
    for i, field in enumerate(fields, 1):
        ET.SubElement(cols, 'col', min=str(i), max=str(i), width=str(110 if field=='text' else 38 if field=='note' else 25 if field=='id' else 16), customWidth='1')
    data = ET.SubElement(sheet, 'sheetData')
    values = [dict(zip(fields, fields)), *rows]
    for index, record in enumerate(values, 1):
        lines = sum(max(1, len(textwrap.wrap(line, 105))) for line in str(record.get('text', '')).split('\n'))
        row = ET.SubElement(data, 'row', r=str(index), ht=str(26 if index==1 else min(409, max(48, lines*16+12))), customHeight='1')
        for col, field in enumerate(fields, 1):
            value = str(record.get(field, ''))
            if len(value)>32767: raise ValueError('Excel cell limit exceeded; text was NOT truncated or filtered')
            cell = ET.SubElement(row, 'c', r=chr(64+col)+str(index), t='inlineStr', s='1' if index==1 else '2')
            inline = ET.SubElement(cell, 'is'); node = ET.SubElement(inline, 't', {'{http://www.w3.org/XML/1998/namespace}space':'preserve'}); node.text=value
    ET.SubElement(sheet, 'autoFilter', ref=f'A1:{chr(64+len(fields))}{max(1,len(values))}')
    if rows:
        validations=ET.SubElement(sheet, 'dataValidations', count='1')
        validation=ET.SubElement(validations, 'dataValidation', type='list', allowBlank='1', showErrorMessage='1', errorStyle='stop', sqref=f'{chr(64+label_column)}2:{chr(64+label_column)}{len(values)}')
        ET.SubElement(validation, 'formula1').text='"'+','.join(CATEGORIES)+'"'
    styles=f'''<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF203864"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>'''
    contents='''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'''
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED) as z:
        def part(name,payload):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,payload)
        part('[Content_Types].xml', contents)
        part('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        part('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Annotation" sheetId="1" r:id="rId1"/></sheets></workbook>')
        part('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        part('xl/styles.xml', styles)
        part('xl/worksheets/sheet1.xml', ET.tostring(sheet, encoding='utf-8', xml_declaration=True))


def group_identity(url):
    parts=urlsplit(url);segments=parts.path.strip('/').split('/')
    if len(segments)>1 and segments[0]=='groups' and segments[1]: return 'GROUP:'+segments[1]
    if len(segments)>1 and segments[0] not in {'posts','permalink','reel','watch','videos','share'} and not segments[0].endswith('.php'):
        return 'PROFILE:'+segments[0]
    return 'UNKNOWN'


def display_text(raw,dom=None,mention_count=0):
    """Accept DOM only when it deleted <=mention_count contiguous name segments."""
    if not isinstance(dom,str) or not dom.strip() or type(mention_count) is not int or mention_count<=0: return raw
    if dom==raw:return raw
    deleted=[]
    for tag,a,b,c,d in SequenceMatcher(None,raw,dom,autojunk=False).get_opcodes():
        if tag=='equal':continue
        if tag!='delete':return raw
        words=raw[a:b].strip().split()
        if not 1<=len(words)<=6:return raw
        for word in words:
            if not word.isalpha() or not (word[0].isupper() or all('LATIN' not in unicodedata.name(ch,'') for ch in word)):
                return raw
        deleted.append(words)
    return dom if 0<len(deleted)<=mention_count else raw


def _directory(directory,root):
    root=Path(root).resolve();directory=Path(directory).resolve()
    if not directory.is_relative_to(root/'outputs/gold'):raise ValueError('Gold files must stay under outputs/gold/')
    directory.mkdir(parents=True,exist_ok=True)
    return directory


def _manifest(directory,posts):
    checksum=sha(posts)  # The first input operation: seal the link file before inspecting comments.
    path=directory/'manifest.json'
    declaration=dict(kind='GOLD_TEST_SINGLE_ANNOTATOR',created_at=now(),posts_csv_sha256=checksum,
        seed=SEED,caps=CAPS,source_policy='New Facebook post/comment identities only; first up to 60 accessible records/post',
        annotation_protocol='one person; blind 100-item intra-annotator recheck within less than one day',
        output_sha256={'posts.sealed.csv':checksum})
    if path.exists():
        existing=load(path)
        if existing['posts_csv_sha256']!=checksum or existing['caps']!=CAPS or existing['seed']!=SEED:
            raise ValueError('Existing gold manifest belongs to another post list/protocol')
    else:save(path,declaration)
    snapshot=directory/'posts.sealed.csv'
    if not snapshot.exists():snapshot.write_bytes(Path(posts).read_bytes())
    verify(directory)


def _source(export,run_id,directory,root):
    if run_id:
        export=directory/'input_export'
        if not export.exists():export_run(Path(root)/'data/crawl_runs'/run_id,export)
    export=Path(export).resolve();receipt=load(export/'export_manifest.json')
    if run_id and receipt['run_id']!=run_id:raise ValueError('Existing local export belongs to a different run')
    run=Path(root)/'data/crawl_runs'/receipt['run_id']
    cfg=run_config(run);report=validate_run(run)
    if cfg.get('max_comments')!=60:raise ValueError('Expected the requested --max-comments 60 crawl')
    if report['raw_validation_errors'] or receipt['raw_sha256']!=sha(run/'raw_comments.jsonl'):
        raise ValueError('Invalid or changed source journal')
    rows,fields=csv_rows((export/'comments.csv').read_bytes())
    raw={r['internal_record_id']:r for r in read_jsonl(run/'raw_comments.jsonl') if r['extraction_status']=='complete'}
    if len(rows)!=len(raw) or len(rows)!=receipt['exported'] or len({r.get('internal_record_id') for r in rows})!=len(rows):
        raise ValueError('Export row coverage/IDs differ from journal')
    for row in rows:
        ref=raw.get(row['internal_record_id'])
        if not ref or any(row[k] != (str(ref.get(k)) if ref.get(k) is not None else '') for k in fields):
            raise ValueError('Export differs from original journal')
    if any(n>60 for n in Counter(r['post_id'] for r in rows).values()):raise ValueError('Source exceeds 60 records per post')
    source_hashes={str(p.resolve()):sha(p) for p in [export/'comments.csv',export/'export_manifest.json',run/'config.json',run/'raw_comments.jsonl']}
    return list(raw.values()),export,run,cfg,source_hashes


def _register(directory,posts,rows,root):
    quarantine=dict(ids=sorted({r['id'] for r in rows}|{r['source_id'] for r in rows}),groups=[],
        comment_ids=sorted({r['comment_id'] for r in rows if r['comment_id']}),
        post_ids=sorted(posts),post_urls=sorted(p['post_url'] for p in posts.values()),
        text_hashes=sorted({digest(normal(r[k])) for r in rows for k in ('text','text_raw') if r[k]}),platform='facebook')
    candidate=dict(post_ids=quarantine['post_ids'],post_urls=quarantine['post_urls'])
    save(directory/'candidate_quarantine.json',candidate)
    reservation=directory/'reservation'
    with staged(reservation) as out:
        save(out/'post_quarantine.json',quarantine);seal(out,dict(kind='GOLD_TEST_WHOLE_POST_RESERVATION'))
    registry=Path(root)/'data/test_reservations';registry.mkdir(parents=True,exist_ok=True)
    entry=dict(kind='GOLD_TEST',plan_root=str(directory),plan_manifest_sha256=sha(directory/'manifest.json'),
        collection_root=str(reservation),collection_manifest_sha256=sha(reservation/'manifest.json'),post_ids=quarantine['post_ids'],
        candidate_quarantine_sha256=sha(directory/'candidate_quarantine.json'))
    save(registry/('gold_'+digest(str(directory)+sha(directory/'manifest.json'))+'.json'),entry)


def _near(rows,old):
    from src.data.split import duplicate_groups
    new=[dict(record_id=r['id'],text_clean=preprocess(r['text'])) for r in rows]
    groups,_,near=duplicate_groups([*old,*new],threshold=.9,min_chars=40)
    owners=defaultdict(set)
    for r in [*old,*new]:owners[groups[r['record_id']]].add(r['record_id'])
    old_ids={r['record_id'] for r in old}
    flags={r['id']:sorted((near['neighbors'].get(r['id'],set())|owners[groups[r['id']]])&old_ids) for r in rows}
    return flags,near['summary']


def sample(export=None,posts=None,directory=ROOT/'outputs/gold',root=ROOT,run_id=None):
    root=Path(root).resolve();directory=_directory(directory,root);posts=Path(posts) if posts else directory/'posts.csv'
    _manifest(directory,posts)
    if (directory/'coordinator.json').exists() or (directory/'reservation').exists():raise FileExistsError('Gold sample/reservation already exists; never resample after inspection')
    if bool(export)==bool(run_id):raise ValueError('Provide exactly one --export or --run')
    validate_guideline(GUIDELINE_VERSION,sha(GUIDELINE))
    listed,fields=csv_rows((directory/'posts.sealed.csv').read_bytes())
    if fields!=['movie_id','post_url']:raise ValueError('posts.csv must contain movie_id,post_url')
    rows,export,run,cfg,source_hashes=_source(export,run_id,directory,root)
    filtered=root/'outputs/canonical/versions/filtered_20261112_final';verify(filtered)
    verify(root/'outputs/phase_g/master')
    history={};seen_posts=set();seen_comments=set()
    def ids(obj):
        if isinstance(obj,dict):
            if obj.get('comment_id'):seen_comments.add(str(obj['comment_id']))
            for value in obj.values():
                if isinstance(value,(dict,list)):ids(value)
        elif isinstance(obj,list):
            for value in obj:ids(value)
    for path in history_files(root):
        if path.is_relative_to(run.resolve()) or path.is_relative_to(export) or path.is_relative_to(directory):continue
        history[str(path)]=sha(path)
        for obj in objects(path):seen_posts.update(metadata_posts(obj));ids(obj)
    # A source already pinned in the baseline cannot become new by re-exporting it.
    baseline=load(root/'outputs/phase_g/master/manifest.json')
    if str((run/'raw_comments.jsonl').resolve()) in baseline.get('input_sha256',{}):
        raise ValueError('Source run already belongs to historical baseline')
    accepted={};rejections=[]
    for item in listed:
        url=post_url(item['post_url']);pid=post_id(url) if url else None;movie=item['movie_id'].strip()
        reason='MISSING_POST_OR_MOVIE' if not pid or not movie else 'POST_ALREADY_IN_HISTORY' if pid in seen_posts else 'REPEATED_POST' if pid in accepted else None
        if reason:rejections.append(dict(post_id=pid or '',reason=reason));continue
        accepted[pid]=dict(post_id=pid,post_url=url,movie_id=movie,group=group_identity(url))
    imported=[]
    for row in rows:
        pid=row['post_id'] or post_id(row['post_url'])
        if pid not in accepted:
            rejections.append(dict(post_id=pid or '',comment_id=row['comment_id'],reason='POST_NOT_ACCEPTED'));continue
        ref=accepted[pid]
        if row['movie_id']!=ref['movie_id']:raise ValueError('Movie metadata differs from the chosen post list')
        text=display_text(row['text_raw'],row.get('text_without_mentions') if row.get('text_extraction_version')=='dom_text_v2' else None,row.get('mention_count',0))
        imported.append(dict(id='gold_'+digest(pid+'\n'+str(row['comment_id'] or row['internal_record_id'])),text=text,text_raw=row['text_raw'],
            source_id=row['internal_record_id'],post_id=pid,post_url=ref['post_url'],movie_id=ref['movie_id'],group=ref['group'],
            comment_id=row['comment_id'] or '',parent_comment_id=row['parent_comment_id'] or '',record_type=row['record_type']))
    _register(directory,accepted,imported,root)  # Reserve EVERY accepted post/observation before filtering.
    write_jsonl(directory/'imported.local.jsonl',imported)
    old=old_references(history);eligible=[];seen_text=set()
    for row in imported:
        reason='COMMENT_ALREADY_IN_HISTORY' if row['comment_id'] and row['comment_id'] in seen_comments else 'EMPTY_TEXT' if not row['text'].strip() else 'EXACT_DUPLICATE_BATCH' if preprocess(row['text']) in seen_text else None
        if reason:rejections.append(dict(id=row['id'],post_id=row['post_id'],comment_id=row['comment_id'],reason=reason));continue
        seen_text.add(preprocess(row['text']));eligible.append(row)
    selected,pc,gc,mc,blocked=quota_sample(eligible)
    flags,near_info=_near(selected,old)
    for row in selected:row['near_old_ids']=flags[row['id']];row['text_sha256']=digest(row['text'])
    save(directory/'coordinator.json',dict(kind='GOLD_TEST_COORDINATOR',seed=SEED,rows=selected,guideline_sha256=sha(GUIDELINE)))
    workbook(directory/'gold_test.xlsx',[dict(id=r['id'],text=r['text'],label='',note='') for r in selected])
    summary=dict(status='AWAITING_SINGLE_ANNOTATOR',selected=len(selected),shortfall=300-len(selected),seed=SEED,caps=CAPS,
        by_post=dict(pc),by_group=dict(gc),by_movie=dict(mc),limits_blocking=dict(blocked),eligible=len(eligible),
        rejections=dict(Counter(r['reason'] for r in rejections)),near_old=sum(bool(r['near_old_ids']) for r in selected),
        near_detector=near_info,missing_comment_id=sum(not r['comment_id'] for r in imported),unknown_group_posts=sum(p['group']=='UNKNOWN' for p in accepted.values()),
        missing_post_or_movie=sum(r['reason']=='MISSING_POST_OR_MOVIE' for r in rejections),replies=sum(r['record_type']=='reply' for r in selected),
        sampling='quota random sample from first up to 60 accessible Facebook-ordered records/post; not a population-random sample')
    save(directory/'summary.json',summary);save(directory/'rejections.json',rejections)
    if any(sha(p)!=h for p,h in {**history,**source_hashes}.items()):raise ValueError('Historical/source input changed during sample')
    save(directory/'sample_receipt.json',dict(coordinator_sha256=sha(directory/'coordinator.json'),manifest_sha256=sha(directory/'manifest.json'),
        source_sha256=source_hashes,history_sha256=history,summary_sha256=sha(directory/'summary.json')))
    return summary


def _task(directory):
    verify(directory);receipt=load(directory/'sample_receipt.json')
    if receipt['coordinator_sha256']!=sha(directory/'coordinator.json') or receipt['manifest_sha256']!=sha(directory/'manifest.json'):
        raise ValueError('Gold coordinator/source changed')
    if any(sha(p)!=h for p,h in receipt['source_sha256'].items()):raise ValueError('Source export/journal changed after gold sampling')
    task=load(directory/'coordinator.json')
    if task['guideline_sha256']!=sha(GUIDELINE):raise ValueError('Gold guideline changed')
    return task


def _labels(path,expected,fields=FIELDS,label_field='label'):
    headers,rows,_=read_sheet(path,'Annotation');refs={r['id']:r for r in expected}
    if headers!=fields or len(rows)!=len(refs) or {r['id'] for r in rows}!=set(refs):raise ValueError('Missing/repeated/unexpected workbook IDs or columns')
    for row in rows:
        if row['text']!=refs[row['id']]['text'] or digest(row['text'])!=refs[row['id']]['text_sha256']:raise ValueError('Workbook text edited')
        if row[label_field] not in CATEGORIES:raise ValueError('Every row needs POS/NEG/NEU/REVIEW/EXCLUDE')
    return {r['id']:r for r in rows}


def recheck(directory=ROOT/'outputs/gold',annotator='user',root=ROOT):
    directory=_directory(directory,root);task=_task(directory)
    if not annotator.strip():raise ValueError('Annotator ID required')
    first=_labels(directory/'gold_test.xlsx',task['rows'])
    if not first:raise ValueError('No primary annotations to recheck')
    sample_ids=random.Random(SEED).sample(sorted(first),min(100,len(first)))
    lookup={r['id']:r for r in task['rows']};rows=[lookup[rid] for rid in sample_ids]
    order=rows.copy();random.Random(SEED+1).shuffle(order)
    # Snapshot round 1 before showing the blind second workbook.
    write_jsonl(directory/'round_1.local.jsonl',[first[rid] for rid in sorted(first)])
    workbook(directory/'gold_recheck.xlsx',[dict(id=r['id'],text=r['text'],label='',note='') for r in order])
    save(directory/'recheck_coordinator.json',dict(rows=rows,seed=SEED,annotator=annotator,created_at=now(),
        primary_workbook_sha256=sha(directory/'gold_test.xlsx'),round_1_sha256=sha(directory/'round_1.local.jsonl'),coordinator_sha256=sha(directory/'coordinator.json')))
    return dict(selected=len(rows),shortfall=100-len(rows),annotator=annotator)


def _rounds(directory):
    task=_task(directory);repeat=load(directory/'recheck_coordinator.json')
    if repeat['primary_workbook_sha256']!=sha(directory/'gold_test.xlsx') or repeat['round_1_sha256']!=sha(directory/'round_1.local.jsonl') or repeat['coordinator_sha256']!=sha(directory/'coordinator.json'):
        raise ValueError('First annotation round changed after blind recheck was exported')
    first=_labels(directory/'gold_test.xlsx',task['rows']);second=_labels(directory/'gold_recheck.xlsx',repeat['rows'])
    expected=random.Random(SEED).sample(sorted(first),min(100,len(first)))
    if set(second)!=set(expected):raise ValueError('Recheck differs from the fixed random sample')
    return task,repeat,first,second


def agreement(directory=ROOT/'outputs/gold',final=False,root=ROOT):
    directory=_directory(directory,root)
    if (directory/'locked_gold.json').exists():raise FileExistsError('Gold is already locked')
    task,repeat,first,second=_rounds(directory)
    from .core import pair_metrics
    ids=sorted(second);report=pair_metrics([first[r]['label'] for r in ids],[second[r]['label'] for r in ids])
    report.update(agreement_type='intra_annotator',annotator=repeat['annotator'],round_1_count=len(first),round_2_count=len(second),
        created_at=now(),recheck_interval_hours=(datetime.fromisoformat(now())-datetime.fromisoformat(repeat['created_at'])).total_seconds()/3600,
        sampling_note='one annotator; planned blind recheck <1 day; first 60 Facebook-ordered records/post; not inter-annotator agreement')
    report['within_one_day']=0<=report['recheck_interval_hours']<24
    differences=[dict(id=rid,text=first[rid]['text'],text_sha256=digest(first[rid]['text']),label_1=first[rid]['label'],label_2=second[rid]['label'],label_final='',note='') for rid in ids if first[rid]['label']!=second[rid]['label']]
    fields=['id','text','label_1','label_2','label_final','note']
    final_labels={}
    if differences:
        if not final:
            save(directory/'agreement.json',report)
            save(directory/'disagreement_coordinator.json',dict(rows=differences,first_sha256=sha(directory/'gold_test.xlsx'),second_sha256=sha(directory/'gold_recheck.xlsx')))
            workbook(directory/'gold_disagreements.xlsx',differences,fields,label_column=5)
            return dict(report,status='AWAITING_USER_FINAL_LABELS',inconsistent=len(differences))
        bound=load(directory/'disagreement_coordinator.json')
        if bound['rows']!=differences or bound['first_sha256']!=sha(directory/'gold_test.xlsx') or bound['second_sha256']!=sha(directory/'gold_recheck.xlsx'):raise ValueError('Annotation rounds changed since disagreement export')
        final_labels=_labels(directory/'gold_disagreements.xlsx',differences,fields,'label_final')
        for rid,row in final_labels.items():
            if row['label_1']!=first[rid]['label'] or row['label_2']!=second[rid]['label']:raise ValueError('Original labels edited in disagreement workbook')
    elif final:raise ValueError('No disagreements; omit --final')
    records=[]
    for row in task['rows']:
        rid=row['id'];label=final_labels[rid]['label_final'] if rid in final_labels else first[rid]['label']
        records.append(dict(row,label=label if label in CATEGORIES[:3] else None,status='LABELED' if label in CATEGORIES[:3] else label,
            label_1=first[rid]['label'],label_2=second[rid]['label'] if rid in second else None,
            label_final=label,note=final_labels[rid]['note'] if rid in final_labels else first[rid]['note']))
    write_jsonl(directory/'locked_gold.local.jsonl',records)
    save(directory/'locked_gold.json',dict(status='LOCKED_SINGLE_ANNOTATOR_TEST',records_sha256=sha(directory/'locked_gold.local.jsonl'),
        coordinator_sha256=sha(directory/'coordinator.json'),annotator=repeat['annotator'],seed=SEED,
        annotation_protocol='single_annotator_with_intra_annotator_recheck',locked_at=now(),agreement=report,
        source_sha256={p.name:sha(p) for p in [directory/'gold_test.xlsx',directory/'gold_recheck.xlsx',*([directory/'gold_disagreements.xlsx'] if differences else [])]}))
    if not (directory/'agreement.json').exists():save(directory/'agreement.json',report)
    return dict(report,status='LOCKED_SINGLE_ANNOTATOR_TEST',inconsistent=len(differences))


def quota_sample(eligible):
    shuffled=sorted(eligible,key=lambda r:r['id']);random.Random(SEED).shuffle(shuffled)
    selected=[];pc,gc,mc=Counter(),Counter(),Counter();blocked=Counter()
    for row in shuffled:
        limits=[name for name,key,counter in [('post',row['post_id'],pc),('group',row['group'],gc),('movie',row['movie_id'],mc)] if counter[key]>=CAPS[name]]
        if len(selected)>=300:limits.append('total')
        if limits:blocked.update(limits);continue
        selected.append(row);pc[row['post_id']]+=1;gc[row['group']]+=1;mc[row['movie_id']]+=1
    return selected,pc,gc,mc,blocked
