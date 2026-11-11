"""Fixed basic normalization; no learned dictionaries, sentiment edits or segmentation."""
import argparse
from collections import Counter
import html
from pathlib import Path
import re
import unicodedata

BASIC = dict(version='basic_v1',unicode='NFC',whitespace='collapse',html_entities='semicolon_fixed_point_outside_urls',
             urls='preserve',mentions='preserve',underscores='preserve',teencode='preserve',
             repetitions='preserve',emoji_aliases='preserve',case='preserve')
ENTITY=re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);')
URL=re.compile(r'https?://\S+|www\.\S+',re.I)
MENTION=re.compile(r'(?<!\w)[@#][\w.]+')
UNDERSCORE=re.compile(r'\S*_\S*')
EMOJI=re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\u200d\ufe0f]')
ALIAS=re.compile(r':[a-z_]{3,}:|\b(?:[a-z]+_)*(?:face|heart)(?:_[a-z]+)*\b')
NEGATION=re.compile(r'(?<![^\W_])(?:không|chẳng|chưa|đừng)(?![^\W_])',re.I)


def normalize(text,config=None):
    config=BASIC if config is None else config
    if config!=BASIC:raise ValueError('Only the predeclared basic_v1 normalization is supported')
    if not isinstance(text,str):raise TypeError('Literal string required')
    # Decode complete entities only. Fixed point prevents repeated runs changing
    # nested encodings; no partial "&not..." or guessed emoji reconstruction.
    while True:
        pieces=[];start=0
        for match in URL.finditer(text):
            pieces.extend([ENTITY.sub(lambda m:html.unescape(m[0]),text[start:match.start()]),match[0]])
            start=match.end()
        pieces.append(ENTITY.sub(lambda m:html.unescape(m[0]),text[start:]));decoded=''.join(pieces)
        if decoded==text:break
        text=decoded
    return ' '.join(unicodedata.normalize('NFC',text).split())


def signals(text):
    tokens=UNDERSCORE.findall(text);kinds=Counter()
    for token in tokens:
        if URL.fullmatch(token):kind='url_preserved'
        elif token.startswith(('@','#')):kind='mention_or_hashtag_preserved'
        elif any(c.isdigit() for c in token):kind='identifier_or_numeric_risk'
        elif re.fullmatch(r'[^\W\d_]+(?:_[^\W\d_]+)+',token):kind='joined_letters_candidate_not_proven_segmentation'
        else:kind='other_underscore_risk'
        kinds[kind]+=1
    return dict(characters=len(text),tokens=len(text.split()),urls=len(URL.findall(text)),mentions=len(MENTION.findall(text)),
        underscore_tokens=len(tokens),underscore_kinds=dict(kinds),emoji_codepoints=len(EMOJI.findall(text)),
        emoji_aliases=len(ALIAS.findall(text)),html_entities=len(ENTITY.findall(text)))


def inspect(before,after):
    old=unicodedata.normalize('NFC',before)
    losses=[]
    if len(EMOJI.findall(after))<len(EMOJI.findall(old)):losses.append('EMOJI_CODEPOINT_LOSS')
    if any(after.count(c)<old.count(c) for c in '!?'):losses.append('EXCLAMATION_OR_QUESTION_LOSS')
    if Counter(NEGATION.findall(old.casefold()))-Counter(NEGATION.findall(after.casefold())):losses.append('NEGATION_LOSS')
    return dict(changed=before!=after,before=signals(before),after=signals(after),empty_after=not after,
                sentiment_information_risks=losses)


def main():
    from src.dataset.common import csv_rows,load,seal,staged,write_csv,save
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--text-column',default='text_view')
    p.add_argument('--config',type=Path,default=Path('configs/unified_dataset.json'));a=p.parse_args()
    cfg=load(a.config)['normalization'];rows,fields=csv_rows(a.input.read_bytes())
    if a.text_column not in fields:raise ValueError('Input text column missing')
    if 'text_normalized' in fields:raise ValueError('Normalized field already exists; use the original source')
    audits=[]
    for i,row in enumerate(rows):
        row['text_normalized']=normalize(row[a.text_column],cfg)
        audits.append(dict(row=i+1,**inspect(row[a.text_column],row['text_normalized'])))
    with staged(a.output) as work:
        write_csv(work/'normalized.csv',rows,[*fields,'text_normalized']);save(work/'audit.json',audits)
        seal(work,dict(status='NORMALIZED_VIEW_CREATED',rows=len(rows),changed=sum(x['changed'] for x in audits),source_unchanged=True))


if __name__=='__main__':main()
