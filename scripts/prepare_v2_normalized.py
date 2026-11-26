import argparse
import html
import html.entities
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from src.dataset.common import ROOT, csv_rows, digest, load, read_jsonl, save, seal, sha, staged, verify, write_csv, write_jsonl

OUT=ROOT/'outputs'
parser = argparse.ArgumentParser(
    description='Rebuild the V2 technical text view and join locked labels by comment ID.')
parser.add_argument('--output', required=True, type=Path,
                    help='New run directory under outputs/')
DEST = parser.parse_args().output.resolve()
if not DEST.is_relative_to(OUT.resolve()) or DEST == OUT.resolve():
    parser.error('--output must be a new directory under outputs/')
if DEST.exists():
    parser.error('--output already exists')
STEP1=OUT/'02_Du_lieu_va_nhan/04_Kiem_tra_nguon_V2'
EXP=OUT/'annotation_expansion_round_01'
T2=OUT/'cmt_v2_20261125'
SOURCE_NEW=OUT/'test_extra_crawl_20261125_final/comments_top80.csv'
LABELS={'POS','NEG','NEU','REVIEW','EXCLUDE'}
SENTIMENT={'POS','NEG','NEU'}
DIGITS=re.compile(r'[0-9]+\Z')
CONTROL=re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')
ENTITY=re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);')
TECHNICAL=re.compile(r'```[\s\S]*?```|`[^`]*`|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
RULES=('unicode_nfc','remove_control','decode_html_entity','normalize_whitespace')
hashes={}
v1=verify(STEP1)
test_manifest=verify(T2)
expansion_manifest=load(EXP/'manifest.json')

def pinned(path):
    rel=path.relative_to(ROOT).as_posix()
    hashed=sha(path)
    expected=v1['inputs_sha256'].get(rel)
    if expected is not None:assert hashed==expected,rel
    hashes[rel]=hashed
    return path
def read_csv(path):
    return csv_rows(pinned(path).read_bytes())[0]
def read_lines(path):
    return read_jsonl(pinned(path))
def by_id(rows,key='comment_id'):
    result={r[key]:r for r in rows}
    assert len(result)==len(rows)
    assert all(isinstance(cid,str) and DIGITS.fullmatch(cid) for cid in result)
    return result
def votes(paths):
    rows=[r for path in paths for r in read_csv(path)]
    result={cid:r['label'] for cid,r in by_id(rows).items()}
    assert set(result.values())<=LABELS
    return result

def decode_one(match):
    name=match[0][1:-1]
    if name.startswith('#'):
        try:
            value=int(name[2:],16) if name[1:2].lower()=='x' else int(name[1:])
        except ValueError:
            return match[0]
        if not 32<=value<=0x10ffff or 0xd800<=value<=0xdfff:
            return match[0]
    elif name+';' not in html.entities.html5:
        return match[0]
    return html.unescape(match[0])
def decode_entities(text):
    while True:
        cursor=0
        parts=[]
        for token in TECHNICAL.finditer(text):
            parts.extend((ENTITY.sub(decode_one,text[cursor:token.start()]),token[0]))
            cursor=token.end()
        parts.append(ENTITY.sub(decode_one,text[cursor:]))
        value=''.join(parts)
        if value==text:
            return value
        text=value
def normalize(text):
    applied=set()
    for name,function in (
        ('unicode_nfc',lambda s:unicodedata.normalize('NFC',s)),
        ('remove_control',lambda s:CONTROL.sub('',s)),
        ('decode_html_entity',decode_entities),
        ('unicode_nfc',lambda s:unicodedata.normalize('NFC',s)),
        ('normalize_whitespace',lambda s:' '.join(s.split())),
    ):
        updated=function(text)
        if updated!=text:
            applied.add(name)
        text=updated
    return text,[name for name in RULES if name in applied]

assert normalize('=)))  👩‍❤️‍👩\t a\u0301 &amp; \x08 b')[0]=='=))) 👩‍❤️‍👩 á & b'
assert normalize('https://x.example/?q=&amp; `&amp;`')[0]=='https://x.example/?q=&amp; `&amp;`'
assert normalize('&#0; &#xD800;')[0]=='&#0; &#xD800;'
pinned(STEP1/'manifest.json')
pinned(T2/'manifest.json')
pinned(EXP/'manifest.json')
old={}
for relative,expected in expansion_manifest['input_sha256'].items():
    path=Path(relative)
    if path.name!='comments.csv':
        continue
    rs=by_id(read_csv(path))
    assert hashes[path.relative_to(ROOT).as_posix()]==expected and not old.keys()&rs.keys()
    old.update(rs)
new=by_id(read_csv(SOURCE_NEW))
assert len(old)==12795 and len(new)==2181 and not old.keys()&new.keys()
combined={**old,**new}

audit=by_id(read_csv(STEP1/'train_candidate_checks.local.csv'))
assert len(audit)==5998
labels={}
def attach(cid,label,source):
    assert cid in combined and label in LABELS and cid not in labels
    labels[cid]=(label,source)

for cid,r in audit.items():
    assert digest(combined[cid]['text_clean'])==r['text_sha256']
    assert combined[cid]['post_id']==r['post_id']
    if r['source'] in {'E','C','U'}:
        attach(cid,r['label'],r['source'])

r2=EXP/'round_2/ai_round_2'
second=(votes([r2/'ai_chatgpt_U_recheck_01_50.csv']),
        votes([r2/'ai_claude_U_recheck_01_50.csv']),
        votes(sorted(r2.glob('ai_gemini_U_recheck_chunk_*.csv'))))
exp_status={}
for i,batch in enumerate(expansion_manifest['batches'][:50],1):
    b=by_id(read_csv(EXP/batch['file']))
    assert hashes[(EXP/batch['file']).relative_to(ROOT).as_posix()]==batch['sha256']
    first=[votes([EXP/'ai_round_1'/f'ai_{n}_U_chunk_{i:02d}.csv']) for n in ('chatgpt','claude','gemini')]
    assert all(v.keys()==b.keys() for v in first)
    for cid in b:
        a={v[cid] for v in first}
        if len(a)==1:
            attach(cid,next(iter(a)),'EXP_R1_3OF3')
        elif all(cid in v for v in second):
            c=Counter(v[cid] for v in second)
            label,n=c.most_common(1)[0]
            if n==3:
                attach(cid,label,'EXP_R2_3OF3')
            elif n==2 and label in SENTIMENT and c['REVIEW']==1:
                attach(cid,label,'EXP_R2_2_PLUS_REVIEW')
        exp_status[cid]=labels.get(cid,('','PENDING'))[1]
assert len(exp_status)==5000
assert sum(v!='PENDING' for v in exp_status.values())==4020

test_decisions=by_id(read_lines(T2/'T2_toan_bo_quyet_dinh.local.jsonl'))
test_scored=by_id(read_lines(T2/'T2_cham_3_nhan.local.jsonl'))
queue=by_id(read_csv(T2/'cmt_cho_gan_chi_muc.local.csv'))
assert len(test_decisions)==652 and len(test_scored)==613 and len(queue)==1731
assert not queue.keys()&labels.keys()
assert not queue.keys()&test_decisions.keys()
assert test_scored=={cid:r for cid,r in test_decisions.items() if r['label'] in SENTIMENT}
for cid,r in test_decisions.items():
    assert combined[cid]['text_clean']==r['text_clean']
    assert combined[cid]['post_id']==r['post_id']
    attach(cid,r['label'],r['test_source'])
assert set(labels)==set(audit)|set(test_decisions) or set(labels)<(set(audit)|set(test_decisions))

stats=defaultdict(Counter)
changes=[]
all_rows=[]
test_view=[]
train_candidate_view=[]
for cid,row in combined.items():
    source_text=row['text_clean']
    final,applied=normalize(source_text)
    assert normalize(final)==(final,[])
    assert not (source_text.startswith('=') and not final.startswith('='))
    cohort='crawl_old' if cid in old else 'crawl_new'
    label,origin=labels.get(cid,('', 'PENDING'))
    role=('T2_SCORE' if cid in test_scored else 'T2_REVIEW_OR_EXCLUDE' if cid in test_decisions else
          'PENDING_SUPPLEMENT' if cid in queue else 'TRAIN_CANDIDATE' if cid in audit else 'CORPUS')
    result=dict(comment_id=cid,post_id=row['post_id'],movie_id=row['movie_id'],post_url=row['post_url'],
                source_name=row['source_name'],source_run=row['crawl_run_id'],cohort=cohort,split_role=role,
                text_source=source_text,text_normalized=final,text_source_sha256=digest(source_text),
                technical_rules=applied,clean_status_source=row['clean_status'],label=label,label_source=origin)
    all_rows.append(result)
    if cid in test_scored:
        assert final and label==test_scored[cid]['label']
        test_view.append(result)
    if cid in audit:train_candidate_view.append(dict(result,candidate_source=audit[cid]['source'],chunk=audit[cid]['chunk']))
    slices=[cohort,'all']
    if cid in audit:slices.append('train_candidates')
    if cid in test_scored:slices.append('T2_scored')
    if cid in queue:slices.append('pending_supplement')
    for name in slices:
        c=stats[name]
        c['rows']+=1
        c['rows_changed']+=bool(applied)
        c['empty_after']+=not final
        c['rows_with_labels']+=bool(label)
        c.update(applied)
    if applied:
        changes.append(dict(comment_id=cid,cohort=cohort,split_role=role,text_source_sha256=digest(source_text),
                            text_normalized_sha256=digest(final),applied_rules=applied))
assert len(all_rows)==14976 and len(test_view)==613 and len(train_candidate_view)==5998
label_totals=Counter(r['label'] for r in all_rows if r['label'])
label_by_source=Counter(r['label_source'] for r in all_rows if r['label'])
assert label_by_source['T_original']==202 and label_by_source['T_supplement']==450
assert sum(bool(r['label']) for r in all_rows)==5670
summary=dict(cohorts={name:dict(c) for name,c in stats.items()},label_counts=dict(label_totals),
             labels_by_source=dict(label_by_source),pending_in_chunk_01_50=980,
             stage='technical_normalization_then_join_locked_labels',
             train_finalized=False,scoring_performed=False,abbreviation_mapping_applied=False)
with staged(DEST) as root:
    save(root/'thong_ke.json',summary)
    write_jsonl(root/'V2_chuan_hoa_va_giu_nhan.local.jsonl',all_rows)
    write_jsonl(root/'ung_vien_train_da_chuan_hoa.local.jsonl',train_candidate_view)
    write_jsonl(root/'T2_da_chuan_hoa.local.jsonl',test_view)
    write_csv(root/'doi_chieu_thay_doi.local.csv',changes,
              ['comment_id','cohort','split_role','text_source_sha256','text_normalized_sha256','applied_rules'])
    (root/'prepare_v2_normalized.py').write_bytes(Path(__file__).read_bytes())
    seal(root,dict(kind='V2_TECHNICAL_NORMALIZATION_AND_LABEL_JOIN',source_sha256=hashes,
                   t2_manifest_sha256=sha(T2/'manifest.json'),replaces_source_files=False))
verify(DEST)
print(summary)
