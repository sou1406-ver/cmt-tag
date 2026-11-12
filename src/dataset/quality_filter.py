"""Derived tag/link filter using the existing immutable build/seal helpers."""
from collections import Counter
from pathlib import Path
import random

from .common import ROOT, load, read_jsonl, save, seal, sha, staged, verify, write_csv, write_jsonl
from .blind import assert_allowed, ReservedDataError
from src.preprocessing.quality import quality_view, PRIORITY


def filter_quality(source, output, review=ROOT/'outputs/quality_filter_review', root=ROOT):
    # Reuse source resolution and byte-only protection snapshot from development CV.
    from src.models.preprocessing_cv import source_observations, snapshot
    source, output, review, root = map(lambda p:Path(p).resolve(), (source,output,review,root))
    if output.exists() or review.exists(): raise FileExistsError('Version/review directory exists; never overwrite')
    if not output.is_relative_to(root/'outputs/canonical/versions') or not review.is_relative_to(root/'outputs/quality_filter_review'):
        raise ValueError('Use local canonical versions and quality_filter_review paths')
    verify(source); before = snapshot(root, source)
    pointer = root/'outputs/canonical/active.json'
    pointer_before = sha(pointer) if pointer.exists() else None
    rows = read_jsonl(source/'candidate.local.jsonl')
    observations, source_hashes = source_observations(rows, root)
    derived=[]; pool=[]; pending=[]; exclusions=[]; examples=[]
    for row in rows:
        v = quality_view(row, observations.get(row['record_id']))
        r = dict(row, **{k:value for k,value in v.items() if k not in ('audit_dom_view','audit_after_urls')})
        # Human decisions are flagged only; old raw/minimal/labels remain byte-identical values.
        assert all(r[k]==row[k] for k in row)
        eligible = row.get('annotation_eligibility')=='ELIGIBLE_PROPOSED' and not row.get('human_decisions')
        if eligible and r['quality_decision']=='KEEP':
            try:
                assert_allowed([dict(r,id=r['record_id'],text_view=r['text_annotation_view'])], 'pseudo_labeling',
                    reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
            except ReservedDataError:
                r['quality_decision']='REVIEW';r['quality_flags'] += ['RESERVED_DERIVED_VIEW']
                r['quality_reason']='RESERVED_DERIVED_VIEW'
        if eligible:
            if r['quality_decision']=='KEEP': pool.append(r)
            elif r['quality_decision']=='REVIEW': pending.append(r)
            else: exclusions.append(r)
        derived.append(r)
        examples.append(dict(record_id=r['record_id'],source=r['source_dataset'],text_raw=r['text_raw'],
            dom_view=v['audit_dom_view'] if observations.get(r['record_id']) else None,
            text_after_urls=v['audit_after_urls'],text_annotation_view=r['text_annotation_view'],
            flags=r['quality_flags'],decision=r['quality_decision'],proposed_decision=v['proposed_decision'],
            reason=r['quality_reason'],view_method=r['view_method'],human_label=r.get('human_label'),
            human_decision_present=bool(r.get('human_decisions'))))
    audits=[]
    for src in sorted({r['source_dataset'] for r in rows}):
        rs=[r for r in derived if r['source_dataset']==src]
        was=[r for r in rs if r['annotation_eligibility']=='ELIGIBLE_PROPOSED' and not r['human_decisions']]
        audits.append(dict(source=src,records=len(rs),flag_matches=dict(Counter(f for r in rs for f in r['quality_flags'])),
            rule_excluded_unlabeled=sum(r['quality_decision']=='EXCLUDE' for r in rs),
            primary_exclusion_reasons=dict(Counter(r['quality_reason'] for r in rs if r['quality_decision']=='EXCLUDE')),
            review_records=sum(r['quality_decision']=='REVIEW' for r in rs),
            stripped_url_keep=sum(r['has_url'] and r['quality_decision']=='KEEP' and not r['human_decisions'] for r in rs),
            human_url_flag_only=sum(r['has_url'] and bool(r['human_decisions']) for r in rs),
            stripped_urls=sum(r['url_count'] for r in rs if not r['human_decisions']),
            multiple_rule_matches=sum(len(r['quality_flags'])>1 for r in rs),
            human_matches_by_label=dict(Counter(r['human_label'] or 'NON_SENTIMENT_DECISION' for r in rs if r['human_decisions'] and r['quality_flags'])),
            human_url_by_label=dict(Counter(r['human_label'] or 'NON_SENTIMENT_DECISION' for r in rs if r['human_decisions'] and r['has_url'])),
            pool_before=len(was),pool_after=sum(r['quality_decision']=='KEEP' for r in was),
            pool_review=sum(r['quality_decision']=='REVIEW' for r in was),pool_excluded=sum(r['quality_decision']=='EXCLUDE' for r in was)))
    eligible_before=sum(a['pool_before'] for a in audits)
    assert len(pool)+len(pending)+len(exclusions)==eligible_before
    summary=dict(status='REVIEW_REQUIRED',records=len(derived),human_sentiment_retained=sum(bool(r['human_label']) for r in derived),
        human_decision_records_retained=sum(bool(r['human_decisions']) for r in derived),
        excluded_unlabeled=sum(a['rule_excluded_unlabeled'] for a in audits),review_records=sum(a['review_records'] for a in audits),
        pool_before=eligible_before,pool_after=len(pool),pool_review=len(pending),pool_excluded=len(exclusions),
        unique_exclusions_not_flag_sum=True,sources=audits,approved=False,active_pointer_updated=False,
        note='All source records retained with flags; only unlabeled eligible pool is partitioned. No false-positive rate established.')
    derived_by_id={r['record_id']:r for r in derived}
    human_matched=[e for e in examples if e['human_decision_present'] and (e['flags'] or derived_by_id[e['record_id']]['has_url'])]
    rng=random.Random(20261113);selected=[]
    for flag in (*PRIORITY,'RESERVED_DERIVED_VIEW'):
        for src in sorted({r['source_dataset'] for r in rows}):
            matches=sorted([e for e in examples if e['source']==src and flag in e['flags']],key=lambda e:e['record_id'])
            selected += [dict(e,example_rule=flag) for e in rng.sample(matches,min(20,len(matches)))]
    # Separate URL-stripped-KEEP examples, even when no exclusion/review flag matches.
    keep_ids={r['record_id'] for r in derived if r['has_url'] and r['quality_decision']=='KEEP' and not r['human_decisions']}
    matches=[e for e in examples if e['record_id'] in keep_ids]
    selected += [dict(e,example_rule='URL_STRIPPED_KEEP') for e in rng.sample(matches,min(20,len(matches)))]
    summary['review_examples']=len(selected)
    with staged(output) as out:
        write_jsonl(out/'candidate.local.jsonl',derived)
        write_csv(out/'comments.csv',derived,['record_id','source_dataset','movie_id','post_id','comment_id','text_raw','text_minimal',
            'text_annotation_view','human_label','quality_flags','quality_decision','quality_reason','view_method','view_reason'])
        write_csv(out/'annotation_candidates.local.csv',pool,['record_id','text_annotation_view'])
        write_jsonl(out/'review_candidates.local.jsonl',pending)
        write_csv(out/'pool_exclusions.local.csv',exclusions,['record_id','quality_flags','quality_reason'])
        save(out/'summary.json',summary)
        save(out/'config.json',dict(source=str(source),source_manifest_sha256=sha(source/'manifest.json'),
            original_candidate_sha256=sha(source/'candidate.local.jsonl'),seed=20261113,priority=PRIORITY,
            model_input='text_model(text_annotation_view); opt-in, no precomputed duplicate column',
            parent_pool='ELIGIBLE_PROPOSED only; no promotion of previously ineligible rows',
            source_observation_hashes=source_hashes,implementation_sha256={str(p.relative_to(ROOT)):sha(p) for p in
                [ROOT/'src/preprocessing/quality.py',Path(__file__),ROOT/'src/preprocessing/model.py',ROOT/'src/annotation/gold.py']}))
        # Protections are inherited, not resampled. New views also pass the existing registry guard.
        (out/'protection.local.json').write_bytes((source/'protection.local.json').read_bytes())
        save(out/'protected_inputs.local.json',dict(before,**source_hashes))
        if snapshot(root,source)!=before or (sha(pointer) if pointer.exists() else None)!=pointer_before:
            raise ValueError('Immutable data or active pointer changed')
        if any(sha(p)!=h for p,h in source_hashes.items()):raise ValueError('Pinned DOM source changed')
        seal(out,dict(status='QUALITY_FILTER_CANDIDATE_REVIEW_PENDING',records=len(derived),source_manifest_sha256=sha(source/'manifest.json'),
                      canonical_approved=False,active_pointer_updated=False))
    with staged(review) as out:
        write_jsonl(out/'examples.local.jsonl',selected)
        write_jsonl(out/'human_matches.local.jsonl',human_matched)
        write_csv(out/'rule_counts.csv',audits,list(audits[0]))
        save(out/'summary.json',summary)
        save(out/'immutability.json',dict(verified=True,checked_files=len(before),sha256=before))
        lines=['# Tag-only / URL quality review','', '**REVIEW_REQUIRED** — candidate only; chưa duyệt pool, chưa AI labeling.','',
            f'Nguồn: `{source}`; version mới: `{output}`. Tất cả {len(derived):,} record vẫn được giữ kèm flags; không xóa raw/minimal/human decisions.', '',
            '| Nguồn | Tag-only matches | Link-only matches | Tag review | Link review | Spam review | EXCLUDE duy nhất (unlabeled) | REVIEW | URL strip + KEEP | Pool trước → sau | Pool REVIEW / EXCLUDE |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
        for a in audits:
            c=a['flag_matches'];lines.append(f"| {a['source']} | {c.get('EXCLUDE_TAG_ONLY',0)} | {c.get('EXCLUDE_LINK_ONLY',0)} | {c.get('TAG_ONLY_REVIEW',0)} | {c.get('LINK_REVIEW',0)} | {c.get('POSSIBLE_LINK_SPAM',0)} | {a['rule_excluded_unlabeled']} | {a['review_records']} | {a['stripped_url_keep']} | {a['pool_before']} → {a['pool_after']} | {a['pool_review']} / {a['pool_excluded']} |")
        lines += ['', 'Flags có thể giao nhau, tổng EXCLUDE chỉ đếm ID duy nhất. Thứ tự ưu tiên: '+', '.join(PRIORITY)+'.', '',
            f"Pool gốc {eligible_before}; còn {len(pool)} KEEP, {len(pending)} REVIEW, {len(exclusions)} EXCLUDE. Không nới eligibility cũ. "
            'Những EXCLUDE toàn corpus vốn ngoài pool không được tính thêm thành giảm pool lần nữa.', '',
            'dom_text_v2 chỉ có aggregate account-link count; kể cả source/raw/ID/checksum và deletion-rule khớp chỉ gọi DOM_RULE_MATCH, '
            'không gọi VERIFIED_DOM_VIEW. Empty DOM chỉ được chấp nhận nếu raw là toàn bộ 1–6 name-like words và deletion count >=1; '
            'không suy đoán/xóa tên từ text khi thiếu metadata. Tên title-case 1–4 từ chỉ là review cue, có thể nhầm tên phim/cụm đầu câu.', '',
            'URL explicit http(s)/www và domain trần TLD allowlist; không dùng URL+≤3 từ để EXCLUDE. '
            'Email, file extension thông thường, decimal/điểm và dấu câu quanh URL giữ nguyên. '
            'Không resolve domain hoặc biết mọi TLD; file tên .com/.app/.dev và domain cùng dạng không phân biệt tuyệt đối được. '
            'Biên URL dính văn bản/path có thể mơ hồ; không tuyên bố phát hiện toàn bộ URL.', '',
            'Human decision: giữ nguyên text_annotation_view=text_minimal và KEEP/flag-only, không tự loại hay sửa nhãn; '
            'proposed_decision và after-URL chỉ ở audit để người duyệt kiểm tra. human_matches.local.jsonl chứa đầy đủ record bị ảnh hưởng để rà false positive.', '',
            'Có sentiment cue thì URL-stripped text được KEEP theo hai rule này, không đồng nghĩa nội dung/nhãn đã được xác minh. '
            'Emoji/emoticon hoặc nội dung URL chưa rõ → REVIEW. Không có human validation thì **chưa đo false-positive rate**.', '',
            f'Ví dụ: {len(selected)} lượt, seed 20261113; tối đa 20 mỗi rule/nguồn, ít hơn thì xuất toàn bộ. '
            'Raw/DOM/after-URL/flags/decision/reason trong examples.local.jsonl; không tạo mẫu giả.', '',
            f'Giữ {summary["human_sentiment_retained"]} nhãn sentiment, {summary["human_decision_records_retained"]} record có quyết định người. '
            f'Hash trước/sau {len(before)} file bất biến khớp; protection sidecar sao nguyên bytes. '
            'Không đọc nội dung/nhãn gold, không đổi receipt/reservation/split/active pointer; không train/crawl/API.', '',
            'Reproduce bằng CLI build/filter --quality-filter SOURCE --output NEW_VERSION --quality-review NEW_REVIEW. '
            'Dùng text_annotation_view cho future annotation và text_model(text_annotation_view) khi thử model; không sửa Gold path cũ.']
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        seal(out,dict(status='REVIEW_REQUIRED',candidate_manifest_sha256=sha(output/'manifest.json')))
    return summary
