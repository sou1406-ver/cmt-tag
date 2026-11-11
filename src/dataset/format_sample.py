"""Targeted boundary-case validation, independent of sentiment labels."""
import random
import re
from .phase_i3 import held


def select(rows,frequency,count=200,seed=20261115):
    safe=sorted((r for r in rows if not held(r)),key=lambda r:r['record_id']);rng=random.Random(seed);rng.shuffle(safe)
    predicates={
        'common_token':lambda r:any(frequency.get(e['source_token'],0)>=20 for e in r['format_evidence']),
        'rare_token':lambda r:any(0<frequency.get(e['source_token'],0)<=2 for e in r['format_evidence']),
        'multiple_underscores':lambda r:any(e['source_token'].count('_')>=2 for e in r['format_evidence']),
        'possible_name':lambda r:any(e['rule']=='PRESERVE_POSSIBLE_NAME' for e in r['format_evidence']),
        'protected_identifier_or_region':lambda r:any(e['confidence_category']=='PROTECTED_IDENTIFIER' for e in r['format_evidence']),
        'emoji_alias':lambda r:bool(r['alias_changes']),
        'negation':lambda r:bool(r['flags']['negation_present']),
        'sarcasm_emoticon_surface_cue':lambda r:bool(re.search(r':\)\)|=\)\)|hay quá nhỉ|hay quá cơ',r['text_raw'],re.I)),
        'facebook':lambda r:r['source_dataset']=='facebook',
        'legacy':lambda r:r['source_dataset']=='legacy_29k_unverified',
        'unchanged_i2':lambda r:r['text_clean_i2']==r['text_clean_i3'],
        'long_text':lambda r:len(r['text_clean'])>1000}
    chosen=[];ids=set();available={}
    for label,predicate in predicates.items():
        matches=[r for r in safe if predicate(r)];available[label]=len(matches)
        candidate=next((r for r in matches if r['record_id'] not in ids),None)
        if candidate is not None:chosen.append(candidate);ids.add(candidate['record_id'])
    # Fill from shuffled source/format/length strata instead of a sentiment score.
    from collections import defaultdict
    buckets=defaultdict(list)
    for r in safe:
        if r['record_id'] not in ids:buckets[(r['source_dataset'],r['format_status'],len(r['text_clean'])>1000)].append(r)
    while len(chosen)<count:
        progress=False
        for key in sorted(buckets):
            if buckets[key]:r=buckets[key].pop();chosen.append(r);ids.add(r['record_id']);progress=True
            if len(chosen)==count:break
        if not progress:break
    return chosen,dict(available=available,selected={name:sum(predicate(r) for r in chosen) for name,predicate in predicates.items()},
        seed=seed,method='boundary-case anchors then seeded source-format-length round robin; not population random')
