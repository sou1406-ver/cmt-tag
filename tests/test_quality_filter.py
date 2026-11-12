"""High-precision tag/link fixtures; no actual gold data opened."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.preprocessing import preprocess
from src.preprocessing.quality import strip_urls, quality_view
from src.dataset.common import save, seal, write_jsonl, read_jsonl, sha


class QualityFilterTests(unittest.TestCase):
    def row(self,text,source='facebook',human=False):
        return dict(record_id='r',source_dataset=source,text_raw=text,text_minimal=preprocess(text),
            post_id='10' if source=='facebook' else '',post_url='https://www.facebook.com/p/posts/10' if source=='facebook' else '',
            comment_id='11' if source=='facebook' else '',human_label='POS' if human else '',
            human_decisions=[dict(status='LABELED',label='POS')] if human else [],annotation_eligibility='ELIGIBLE_PROPOSED')

    def obs(self,row,dom,count=1):
        return dict(text_raw=row['text_raw'],post_id=row['post_id'],comment_id=row['comment_id'],
                    text_extraction_version='dom_text_v2',mention_count=count,text_without_mentions=dom)

    def test_urls_only_are_excluded_both_sources(self):
        for source in ['facebook','legacy_29k_unverified']:
            for text in ['https://okf168.com','http://example.com/a','www.example.com','example.com','https://a.com,']:
                v=quality_view(self.row(text,source))
                self.assertEqual(v['quality_decision'],'EXCLUDE')
                self.assertIn('EXCLUDE_LINK_ONLY',v['quality_flags'])

    def test_url_with_sentiment_keeps_remaining_words(self):
        for text,expected in [('Phim hay https://abc.com thật','Phim hay thật'),
            ('Phim dở www.abc.com','Phim dở'),('https://youtube.com/watch?v=12 phim dở','phim dở')]:
            v=quality_view(self.row(text));self.assertEqual(v['text_annotation_view'],expected)
            self.assertEqual(v['quality_decision'],'KEEP')

    def test_url_boundaries_do_not_join_words(self):
        self.assertEqual(strip_urls('hay(https://abc.com)thật'),'hay( )thật')
        self.assertEqual(strip_urls('Xem example.com. Phim hay!'),'Xem . Phim hay!')
        self.assertEqual(strip_urls('a https://abc.com b'),'a b')

    def test_email_file_decimal_and_sentence_punctuation(self):
        for text in ['a@abc.com','a+b@example.com.vn','8.5/10','8.5','report.pdf','movie.mp4','data.csv','notes.txt','setup.py','Phim hay.']:
            self.assertEqual(strip_urls(text),text)

    def test_dom_tag_only_empty_extension(self):
        row=self.row('Thúy Thúy');v=quality_view(row,self.obs(row,''))
        self.assertEqual(v['quality_decision'],'EXCLUDE');self.assertIn('EXCLUDE_TAG_ONLY',v['quality_flags'])
        self.assertEqual(v['view_method'],'DOM_RULE_MATCH')

    def test_no_dom_review_never_remove_name(self):
        row=self.row('Thúy Thúy');v=quality_view(row)
        self.assertEqual(v['quality_decision'],'REVIEW');self.assertIn('TAG_ONLY_REVIEW',v['quality_flags'])
        self.assertEqual(v['text_annotation_view'],row['text_raw'])

    def test_pinned_identity_and_deletion_validation(self):
        row=self.row('Thúy Thúy')
        for key,value in [('comment_id','bad'),('mention_count',True),('mention_count',0),('text_extraction_version','v1')]:
            obs=self.obs(row,'');obs[key]=value
            self.assertNotEqual(quality_view(row,obs)['quality_decision'],'EXCLUDE')
        row=self.row('Thúy Thúy phim hay')
        self.assertNotEqual(quality_view(row,self.obs(row,''))['quality_decision'],'EXCLUDE')

    def test_emoji_emoticon_score_and_content_not_excluded(self):
        for text,dom,decision in [('Thúy Thúy 😂','😂','REVIEW'),('Thúy Thúy :))',':))','REVIEW'),
            ('Thúy Thúy 10/10','10/10','KEEP'),('Bùi Tuấn Anh bạn nói đúng','bạn nói đúng','KEEP')]:
            row=self.row(text);v=quality_view(row,self.obs(row,dom))
            self.assertEqual(v['quality_decision'],decision)
        for text in ['Hay','Dở','10/10','😂','Không đáng tiền']:
            self.assertEqual(quality_view(self.row(text))['quality_decision'],'KEEP')

    def test_link_name_expression_and_uncertain_words_review(self):
        for text in ['https://okf168.com Phạm Đạt','https://a.com 😂','https://a.com :))','https://a.com ))','https://a.com xem đi']:
            self.assertEqual(quality_view(self.row(text))['quality_decision'],'REVIEW')
        v=quality_view(self.row('https://a.com mua ngay khuyến mãi'))
        self.assertIn('POSSIBLE_LINK_SPAM',v['quality_flags']);self.assertEqual(v['quality_decision'],'REVIEW')

    def test_overlap_priority_single_decision(self):
        row=self.row('Thúy Thúy https://a.com')
        v=quality_view(row,self.obs(row,' https://a.com'))
        self.assertEqual(v['quality_flags'],['EXCLUDE_TAG_ONLY','EXCLUDE_LINK_ONLY'])
        self.assertEqual(v['quality_reason'],'EXCLUDE_TAG_ONLY')

    def test_human_only_flag_and_no_text_or_label_mutation(self):
        row=self.row('https://a.com',human=True);original=deepcopy(row)
        v=quality_view(row)
        self.assertEqual(v['quality_decision'],'KEEP');self.assertEqual(v['proposed_decision'],'EXCLUDE')
        self.assertEqual(v['text_annotation_view'],row['text_minimal']);self.assertEqual(row,original)

    def test_idempotence(self):
        for text in ['Phim hay https://a.com !','a@b.com','8.5/10','example.com','phim  :))']:
            self.assertEqual(strip_urls(strip_urls(text)),strip_urls(text))
            row=self.row(text);self.assertEqual(quality_view(row),quality_view(dict(row,**quality_view(row))))

    def test_new_version_keeps_source_gold_and_receipt_bytes(self):
        from src.dataset.quality_filter import filter_quality
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'outputs/canonical/versions/old';source.mkdir(parents=True)
            output=root/'outputs/canonical/versions/new';review=root/'outputs/quality_filter_review'
            row=self.row('https://a.com','legacy_29k_unverified');row['source_file']='unavailable.csv';row['source_row']=1;row['source_sha256']='unavailable'
            human=self.row('https://a.com','legacy_29k_unverified',human=True);human.update(record_id='human',annotation_eligibility='INELIGIBLE')
            write_jsonl(source/'candidate.local.jsonl',[row,human]);save(source/'protected_inputs.local.json',{})
            save(source/'protection.local.json',{'protected_ids':['historic']});seal(source,dict(status='FIXTURE'))
            gold=root/'outputs/gold';gold.mkdir();(gold/'receipt.json').write_bytes(b'opaque not JSON')
            baseline={str(p):sha(p) for p in [*source.iterdir(),gold/'receipt.json']}
            result=filter_quality(source,output,review,root)
            self.assertEqual(result['pool_before'],1);self.assertEqual(result['pool_excluded'],1)
            self.assertEqual(result['excluded_unlabeled'],1)
            self.assertEqual({str(p):sha(p) for p in map(Path,baseline)},baseline)
            self.assertEqual(len(read_jsonl(output/'candidate.local.jsonl')),2)
            self.assertEqual(read_jsonl(output/'candidate.local.jsonl')[1]['human_decisions'],human['human_decisions'])
            with self.assertRaises(FileExistsError):filter_quality(source,output,review,root)


if __name__=='__main__':unittest.main()
