"""Bounded token block repetition diagnostics; no sentiment inference."""
from collections import Counter
import re
import zlib


def repetition_signals(text, widths=tuple(range(10,31))+(50,100)):
    tokens=re.findall(r'\w+',text.casefold()); n=len(tokens)
    # Infer periods from repeated anchors to cover long blocks beyond fixed widths.
    last={}; periods=Counter()
    for i in range(max(0,n-9)):
        anchor=tuple(tokens[i:i+10])
        if anchor in last:
            distance=i-last[anchor]
            if 10<=distance<=512:periods[distance]+=1
        last[anchor]=i
    widths=sorted(set(widths)|{width for width,count in periods.most_common(8) if count>=3})
    best_coverage=0; best_width=0; best_count=0; strong=False
    for width in widths:
        if n < width*3: continue
        positions={}
        for i in range(n-width+1):
            block=tuple(tokens[i:i+width])
            values=positions.setdefault(block,[])
            if not values or i>=values[-1]+width:values.append(i)
        for values in positions.values():
            if len(values)<3:continue
            coverage=len(values)*width/n
            strong=strong or (coverage>=.65 and len(values)>=8 and n>=100)
            if coverage>best_coverage or (coverage==best_coverage and width>best_width):
                best_coverage,best_width,best_count=coverage,width,len(values)
    sentences=[s.strip().casefold() for s in re.split(r'[.!?\n]+',text) if len(s.split())>=10]
    counts=Counter(sentences)
    risk=strong or (best_coverage>=.4 and best_count>=3)
    return dict(repetition_ratio=round(best_coverage,4),longest_repeated_span_tokens=best_width,
        repeated_block_count=best_count,repetition_risk=risk,
        repetition_status='EXCLUDE_CANDIDATE' if strong else 'REVIEW' if risk else 'LOW_RISK',
        compression_ratio=round(len(zlib.compress(text.encode()))/max(1,len(text.encode())),4),
        unique_token_ratio=round(len(set(tokens))/max(1,n),4),
        repeated_sentence_count=max(counts.values(),default=0),token_count=n,
        detector_limit='fixed blocks 10..30/50/100 plus up to 8 inferred periods <=512 tokens; no semantic classifier')
