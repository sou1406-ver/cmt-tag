"""Create a new immutable Phase G master from accessible sources only."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.master import build,rebuild_canonical,promote_canonical,rebuild_cleaning


def publish_review_data(version,workbook,output):
    """Explicit user-requested review snapshot, never an approved AI release."""
    import shutil
    from collections import Counter
    from src.dataset.common import load,read_jsonl,verify,staged,write_csv,save,seal,sha,csv_rows
    from src.dataset.quality_review import validate
    manifest=verify(version);summary=load(version/'summary.json')
    if manifest.get('status')!='REBUILD_VERIFIED':raise ValueError('Verified rebuild required for review publication')
    validate(workbook,version/'workbook_input.local.json')
    rows=read_jsonl(version/'normalized_annotation_view.local.jsonl');excluded=read_jsonl(version/'exclusion_ledger.local.jsonl')
    if {r['record_id'] for r in rows}&{r['record_id'] for r in excluded}:raise ValueError('Excluded records in review snapshot')
    reviews={r['record_id']:r for r in csv_rows((version/'normalization_review_carryover.local.csv').read_bytes())[0]}
    fields=['record_id','source_dataset','source_file','source_row','source_sha256','original_id','movie_id','post_id','post_url','comment_id','parent_comment_id',
        'text_raw','text_normalized','normalization_version','format_status','technical_status','domain_status','spam_status','quality_status','annotation_eligibility',
        'human_status','human_label','normalization_review','contamination_status','raw_sha256']
    with staged(output) as out:
        write_csv(out/'comments.csv',[dict(r,human_status=';'.join(sorted({d['status'] for d in r['human_decisions']})),normalization_review=reviews.get(r['record_id'],{}).get('human_decision','')) for r in rows],fields)
        write_csv(out/'exclusions.csv',[dict(r,human_status=';'.join(sorted({d['status'] for d in r['human_decisions']})),historical_human_label=';'.join(sorted({d['label'] for d in r['human_decisions'] if d['status']=='LABELED'}))) for r in excluded],
            ['record_id','source_dataset','source_file','source_row','source_sha256','original_id','raw_sha256','status','reason','human_status','historical_human_label'])
        shutil.copyfile(workbook,out/'canonical_quality_review.xlsx')
        save(out/'source_regions.json',load(version/'source_region_quality_audit.local.json'))
        (out/'README.md').write_text('# Canonical dataset: public review snapshot\n\n'
            'Explicitly published at the repository owner\'s request for inspection.\n'
            'REBUILD_VERIFIED; QUALITY_REVIEW_PENDING; not an approved annotation/training release.\n\n'
            f"comments.csv contains {len(rows)} retained records with separate raw/normalized columns, source identity, and {summary['retained_sentiment_labels']} retained single-annotator development sentiment labels.\n"
            'Labels are existing human decisions, not independent test gold. No legacy overall is used as a target.\n'
            'exclusions.csv records the exact excluded source block without reintroducing its comments into the corpus. Historical decisions remain local.\n'
            'The workbook is a blank domain/spam review on 200 retained IDs; no ACCEPT or sentiment is prefilled.\n'
            'Original platform/post provenance for the legacy source remains unverified. This repository does not establish a data license or API annotation permission.\n'
            'Original source files and full event/provenance ledgers are local; their hashes are recorded below. Do not change IDs or raw text.\n',encoding='utf-8')
        return seal(out,dict(status='PUBLIC_REVIEW_SNAPSHOT_NOT_ANNOTATION_RELEASE',dataset_version=manifest['dataset_version'],records=len(rows),excluded_records=len(excluded),
            quality_status='QUALITY_REVIEW_PENDING',canonical_approved=False,active_pointer_updated=False,
            human_decisions_historical=summary['human_decisions_historical'],human_decisions_retained=summary['human_decisions_retained'],retained_sentiment_labels=summary['retained_sentiment_labels'],
            sources=summary['sources'],canonical_content_sha256=manifest['canonical_content_sha256'],local_rebuild_manifest_sha256=sha(version/'manifest.json'),
            legacy_source_sha256=summary['original_source_sha256'],normalization_version=summary['normalization_version'],
            original_sources=[{k:r[k] for k in ('source_file','source_sha256','container_sha256','archive_member','rows','encoding')} for r in load(version/'original_sources.local.json')]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('configs/master_dataset.json'))
    p.add_argument('--output', type=Path, default=Path('outputs/phase_g/master'))
    p.add_argument('--canonical',action='store_true',help='Raw-derived curated rebuild; never auto-promotes')
    p.add_argument('--cleaning-v3-2',type=Path,help='Verified local canonical source to derive a v3.2 candidate')
    p.add_argument('--promote',type=Path,help='Verified canonical version to promote, only with explicit approval')
    p.add_argument('--approval',type=Path)
    p.add_argument('--pointer',type=Path,default=Path('outputs/canonical/active.json'))
    p.add_argument('--publish-data',type=Path,help='Explicit review-only publication of a verified canonical version')
    p.add_argument('--workbook',type=Path)
    args = p.parse_args()
    if args.cleaning_v3_2:
        if args.canonical or args.promote or args.publish_data:p.error('Cleaning cannot publish, promote or rebuild old canonical')
        if args.output==Path('outputs/phase_g/master'):args.output=Path('outputs/canonical/versions/cleaning_v3_2')
        result=rebuild_cleaning(args.cleaning_v3_2,args.output)
        print(json.dumps({k:result[k] for k in ('status','records','changed_records','proposed_annotation_pool')}));return
    if args.publish_data:
        if args.canonical or args.promote or not args.workbook or args.output==Path('outputs/phase_g/master'):p.error('--publish-data requires --workbook and explicit new --output; cannot rebuild/promote')
        result=publish_review_data(args.publish_data,args.workbook,args.output)
        print(json.dumps({k:result[k] for k in ('status','dataset_version','records','excluded_records')}));return
    if args.promote:
        if args.canonical or not args.approval:p.error('--promote requires --approval and cannot rebuild')
        print(promote_canonical(args.promote,args.approval,args.pointer));return
    if args.canonical:
        if args.config==Path('configs/master_dataset.json'):args.config=Path('configs/canonical_dataset.json')
        if args.output==Path('outputs/phase_g/master'):args.output=Path('outputs/canonical/versions/rebuild_20261112')
        result=rebuild_canonical(args.config,args.output);keys=('status','dataset_version','records','removed_records','human_decisions_retained','retained_sentiment_labels')
    else:result=build(args.config,args.output);keys=('status','dataset_version','observations','records','human_decisions','movies','posts')
    print(json.dumps({k: result[k] for k in keys}))


if __name__ == '__main__': main()
