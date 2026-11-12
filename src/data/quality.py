"""Conservative quality decisions: retain short comments, spelling, emoji and raw."""

import re
from collections import Counter, defaultdict

from .schema import effective_human


def assess_quality(records, config):
    ui = {value.casefold() for value in config.get("ui_strings", [])}
    spam = [re.compile(pattern, re.IGNORECASE) for pattern in config.get("spam_patterns", [])]
    for record in records:
        text = record["text"]
        reasons = []
        if not text:
            reasons.append("EMPTY")
        elif text.casefold() in ui:
            reasons.append("UI_STRING")
        if text and re.search(r"(?:…|\.{3})\s*(?:xem thêm|see more)\s*$", text, re.IGNORECASE):
            reasons.append("TRUNCATED_UI_SUFFIX")
        if text and any(pattern.search(text) for pattern in spam):
            reasons.append("SPAM_RULE")
        record["quality"] = {
            "status": "EXCLUDE" if reasons else "KEEP",
            "reasons": reasons, "duplicate_of": None, "label_conflict": False,
        }


def mark_exact_duplicates(records):
    """Retain every row and its provenance; only one representative is eligible."""
    buckets = defaultdict(list)
    for record in records:
        if record["quality"]["status"] == "KEEP":
            buckets[record["text_hash"]].append(record)
    for bucket in buckets.values():
        representative = min(bucket, key=lambda r: r["id"])
        human_decisions = [effective_human(r) for r in bucket]
        signatures = {(d["status"], d["label"]) for d in human_decisions if d is not None}
        conflict = len(signatures) > 1
        for record in bucket:
            record["quality"]["label_conflict"] = conflict
            if conflict:
                record["quality"]["reasons"].append("DUPLICATE_HUMAN_CONFLICT")
            if record is not representative:
                record["quality"]["duplicate_of"] = representative["id"]
                record["quality"]["reasons"].append("EXACT_DUPLICATE")


def near_duplicate_candidates(records, config):
    """Token-shingle Jaccard candidates, never automatic deletion or sentiment rules.

    Inverted postings enumerate pairs sharing a shingle. Every threshold match is
    kept for inspection and connected for conservative split isolation.
    """
    threshold = config.get("threshold", 0.9)
    minimum = config.get("min_chars", 40)
    width = config.get("shingle_size", 3)
    if not 0 < threshold <= 1 or minimum < 1 or width < 1:
        raise ValueError("Invalid near-duplicate configuration")
    representatives = sorted(
        (r for r in records if r["quality"]["status"] == "KEEP" and not r["quality"]["duplicate_of"]),
        key=lambda r: r["id"],
    )
    postings, sizes, candidates = defaultdict(list), {}, []
    for record in representatives:
        text = record["text"].casefold()
        if len(text) < minimum:
            continue
        tokens = re.findall(r"\w+|[^\w\s]", text)
        shingles = {tuple(tokens[i:i + width]) for i in range(len(tokens) - width + 1)}
        if not shingles:
            continue
        overlaps = Counter()
        for shingle in shingles:
            overlaps.update(postings[shingle])
        current = record["id"]
        for previous, intersection in sorted(overlaps.items()):
            union = len(shingles) + sizes[previous] - intersection
            score = intersection / union
            if score >= threshold:
                candidates.append({
                    "left": previous, "right": current, "score": round(score, 8),
                    "method": f"token_{width}gram_jaccard",
                    "decision": "pending_review", "policy": "keep_and_group",
                })
        sizes[current] = len(shingles)
        for shingle in shingles:
            postings[shingle].append(current)
    return candidates

from src.dataset.common import ROOT, load
from src.dataset.repetition import repetition_signals
from src.crawler.parser import post_id as parsed_post_id

FILM=re.compile(r'(?<!\w)(?:phim|kịch[ _]bản|diễn[ _]xuất|đạo[ _]diễn|nhân[ _]vật|cảnh[ _]quay|cinema|movie|âm[ _]nhạc|nhịp[ _]phim)(?!\w)',re.I)

AD=re.compile(r'(?<!\w)(?:mua ngay|đặt hàng|liên hệ|inbox|khuyến mãi|giảm giá|hotline|freeship)(?!\w)',re.I)

UI={s.casefold() for s in load(ROOT/'configs/phase_i.json')['exact_ui_strings']}

def verified_post(row):
    # Available metadata is an identity link, not an unused-source attestation.
    if row.get('source_dataset')!='facebook' or not all(row.get(k) for k in ('post_id','post_url','comment_id')):return ''
    try:return str(row['post_id']) if parsed_post_id(row['post_url'])==str(row['post_id']) else ''
    except ValueError:return ''

def layers(row,parent=None):
    text=row['text_normalized'];technical='VALID';reasons=[]
    if not text.strip():technical='EXCLUDE_EMPTY';reasons.append('EMPTY_TEXT')
    elif text.strip().casefold() in UI:technical='EXCLUDE_EXACT_UI';reasons.append('EXACT_KNOWN_UI')
    elif '\ufffd' in text:technical='REVIEW_ENCODING';reasons.append('REPLACEMENT_CHARACTER')
    elif any('TRUNCAT' in x or 'CORRUPT' in x for x in row.get('quality_reasons',[]) if isinstance(x,str)):
        technical='REVIEW_CORRUPTION';reasons.append('SOURCE_CORRUPTION_FLAG')
    elif not re.search(r'\w',text):technical='REVIEW_NON_TEXT';reasons.append('NON_TEXT_CONTEXT_REQUIRED')
    rep=repetition_signals(text)
    advertising=len(AD.findall(text))>=2
    spam='SPAM_CANDIDATE' if rep['repetition_risk'] or advertising else 'NOT_FLAGGED_UNVALIDATED'
    evidence=[]
    if FILM.search(text):domain='IN_DOMAIN_CANDIDATE';evidence.append('FILM_CONTENT_CUE')
    elif row.get('parent_comment_id') and len(text)<=80:
        domain='CONTEXT_REQUIRED';evidence.append('SHORT_REPLY')
        if parent is not None and FILM.search(parent['text_normalized']):evidence.append('LINKED_PARENT_FILM_CUE_NOT_CHILD_CONFIRMATION')
    elif advertising:domain='OFF_TOPIC_CANDIDATE';evidence.append('MULTIPLE_AD_CUES_UNVALIDATED')
    else:domain='UNCERTAIN';evidence.append('INSUFFICIENT_COMMENT_EVIDENCE')
    if verified_post(row):evidence.append('POST_IDENTITY_PRESENT_NOT_DOMAIN_PROOF')
    return dict(technical_status=technical,domain_status=domain,domain_evidence=evidence,spam_status=spam,
        technical_reasons=reasons,structural_spam_reasons=(['REPETITION_SIGNAL'] if rep['repetition_risk'] else [])+(['ADVERTISING_CUES'] if advertising else []),
        repetition_diagnostics=rep,final_quality_decision='EXCLUDE_TECHNICAL' if technical.startswith('EXCLUDE_') else 'KEEP_PROPOSED' if technical=='VALID' and domain=='IN_DOMAIN_CANDIDATE' and spam=='NOT_FLAGGED_UNVALIDATED' else 'REVIEW_PROPOSED')
