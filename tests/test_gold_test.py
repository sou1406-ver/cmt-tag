"""Gold protocol fixtures: no Facebook, external API, real train or real gold evaluation."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from src.annotation import gold
from src.annotation.core import pair_metrics
from src.crawler.store import Store, export_run
from src.crawler.parser import observations
from src.dataset.common import load,save,seal,write_csv,write_jsonl,read_jsonl,read_sheet,sha
from src.dataset.blind import assert_intakes_allowed
from test_crawler import CONFIG


class GoldTestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.directory=self.root/'outputs/gold';self.directory.mkdir(parents=True)
        self.old_text=' '.join('unique'+str(i) for i in range(60))
        old=dict(record_id='old',id='old',post_id='2051192968820637',comment_id='777',movie_id='old_movie',text_raw=self.old_text,text_minimal=self.old_text)
        for relative,name,status in [('outputs/phase_g/master','master.jsonl','MASTER_CREATED'),('outputs/canonical/versions/filtered_20261112_final','candidate.local.jsonl','FILTERED_CANDIDATE_QUALITY_REVIEW_PENDING')]:
            path=self.root/relative;path.mkdir(parents=True);write_jsonl(path/name,[old]);seal(path,dict(status=status,records=1))
        self.posts=[dict(movie_id='film_'+str(i%12),post_url='https://www.facebook.com/groups/group'+str(i%3)+'/permalink/'+str(100000+i)) for i in range(30)]
        self.write_posts()

    def write_posts(self):
        p=self.directory/'posts.csv'
        if p.exists():p.unlink()
        write_csv(p,self.posts,['movie_id','post_url'])

    def source(self,count=13,overrides=None,max_comments=60):
        overrides=overrides or {}
        with patch('src.crawler.store.now',return_value='2026-11-14T10:00:00+07:00'):
            store=Store(self.root/'data/crawl_runs',dict(CONFIG,posts=self.posts,max_comments=max_comments,max_posts=100,interactive=False))
            for pi,post in enumerate(self.posts):
                for ci in range(count):
                    cid=str(400000+pi*100+ci)
                    item=dict(text_raw='fixture '+__import__('hashlib').sha256((str(pi)+':'+str(ci)).encode()).hexdigest(),permalink=post['post_url']+'?comment_id='+cid,observation_id=cid)
                    if ci%2:item['permalink']=post['post_url']+'?comment_id='+str(400000+pi*100)+'&reply_comment_id='+cid
                    item.update(overrides.get((pi,ci),{}));rows,errors=observations([item],post['post_url']);self.assertEqual(errors,0)
                    store.add(rows[0],post,'fixture')
                store.finish_post(post,'partial','comment_limit')
            store.finish()
        export=self.directory/'input_export';export_run(store.path,export)
        return export,store.path

    def sampled(self,count=13,overrides=None):
        export,run=self.source(count,overrides);summary=gold.sample(export,directory=self.directory,root=self.root)
        return summary,run

    def fill(self,name,expected,labels=None,fields=gold.FIELDS,label_field='label'):
        labels=labels or {};path=self.directory/name
        rows=[dict(r,**{label_field:labels.get(r['id'],'POS')},note='') for r in expected]
        if path.exists():path.unlink()
        gold.workbook(path,rows,fields,label_column=5 if label_field=='label_final' else 3)
        return rows

    def rounds(self,changes=None):
        self.sampled();task=load(self.directory/'coordinator.json')
        self.fill('gold_test.xlsx',task['rows']);gold.recheck(self.directory,'user',self.root)
        repeat=load(self.directory/'recheck_coordinator.json')
        self.fill('gold_recheck.xlsx',repeat['rows'],changes)
        return task,repeat

    def lock(self):
        task,repeat=self.rounds();result=gold.agreement(self.directory,root=self.root)
        self.assertEqual(result['status'],'LOCKED_SINGLE_ANNOTATOR_TEST')
        return task

    def train_fixture(self,extra=None):
        path=self.root/'train';path.mkdir()
        rows=[]
        for i,label in enumerate(['POS','NEG','NEU']*8):
            text=label+' independent '+__import__('hashlib').sha256(str(i).encode()).hexdigest()
            rows.append(dict(record_id='train_'+str(i),post_id='old_train_'+str(i),comment_id='train_comment_'+str(i),text_raw=text,text_minimal=text,human_label=label,human_decisions=[dict(status='LABELED',label=label)]))
        rows.extend(extra or []);write_jsonl(path/'candidate.local.jsonl',rows);seal(path,dict(status='fixture'))
        return path/'candidate.local.jsonl'

    def test_group_profile_and_unknown_are_url_only(self):
        self.assertEqual(gold.group_identity('https://www.facebook.com/groups/cinema/permalink/1'),'GROUP:cinema')
        self.assertEqual(gold.group_identity('https://www.facebook.com/ReviewPage/posts/1'),'PROFILE:ReviewPage')
        self.assertEqual(gold.group_identity('https://www.facebook.com/story.php?story_fbid=1&id=2'),'UNKNOWN')

    def test_dom_accepts_only_bounded_contiguous_names(self):
        self.assertEqual(gold.display_text('Nguyễn Văn A phim hay','phim hay',1),'phim hay')
        self.assertEqual(gold.display_text('张三 phim hay','phim hay',1),'phim hay')
        for raw,dom,count in [('Mong đạo diễn làm tiếp','làm tiếp',1),('Nguyễn 123 phim hay','phim hay',1),('Nguyễn @An phim hay','phim hay',1),('Nguyễn #An phim hay','phim hay',1),('https://a.test phim hay','phim hay',1),('A B C D E F G phim hay','phim hay',1),('A phim hay B','phim hay',1),('Nguyễn Văn A phim hay','',1),('Nguyễn Văn A phim hay','phim dở',1)]:
            with self.subTest(raw=raw):self.assertEqual(gold.display_text(raw,dom,count),raw)

    def test_caps_seed_reply_and_no_labels_in_primary_workbook(self):
        summary,_=self.sampled();self.assertEqual(summary['selected'],300)
        self.assertTrue(all(n<=12 for n in summary['by_post'].values()));self.assertTrue(all(n<=100 for n in summary['by_group'].values()))
        self.assertTrue(all(n<=36 for n in summary['by_movie'].values()));self.assertGreater(summary['replies'],0)
        headers,rows,_=read_sheet(self.directory/'gold_test.xlsx','Annotation');self.assertEqual(headers,gold.FIELDS)
        self.assertTrue(all(not r['label'] and not r['note'] for r in rows))
        candidates=read_jsonl(self.directory/'imported.local.jsonl')
        a=gold.quota_sample(candidates)[0];b=gold.quota_sample(list(reversed(candidates)))[0]
        self.assertEqual([r['id'] for r in a],[r['id'] for r in b])
        self.assertEqual(load(self.directory/'manifest.json')['posts_csv_sha256'],sha(self.directory/'posts.csv'))

    def test_collection_cap_60_is_recorded_consistently(self):
        summary,_=self.sampled(1)
        self.assertEqual(summary['max_comments'],60)
        for name in ('manifest.json','coordinator.json','sample_receipt.json'):
            self.assertEqual(load(self.directory/name)['max_comments'],60)
        self.assertIn('up to 60',summary['sampling'])
        self.assertFalse(load(self.directory/'manifest.json')['pre_crawl_lock_claimed'])

    def test_collection_cap_200_flows_through_agreement_and_evaluation_receipt(self):
        export,_=self.source(max_comments=200)
        summary=gold.sample(export,directory=self.directory,root=self.root)
        self.assertEqual(summary['max_comments'],200);self.assertIn('up to 200',summary['sampling'])
        for name in ('manifest.json','coordinator.json','sample_receipt.json'):
            self.assertEqual(load(self.directory/name)['max_comments'],200)
        task=load(self.directory/'coordinator.json');self.fill('gold_test.xlsx',task['rows'])
        gold.recheck(self.directory,'user',self.root)
        repeat=load(self.directory/'recheck_coordinator.json');self.fill('gold_recheck.xlsx',repeat['rows'])
        report=gold.agreement(self.directory,root=self.root)
        self.assertEqual(report['max_comments'],200);self.assertIn('up to 200',report['sampling_note'])
        from src.models.core import evaluate_gold
        evaluate_gold(self.directory,self.train_fixture(),self.root)
        receipt=load(self.directory/'results/receipt.json')
        self.assertEqual(receipt['max_comments'],200);self.assertIn('up to 200',receipt['annotation_protocol'])
        self.assertEqual(load(self.directory/'results/metrics.json')['max_comments'],200)

    def test_collection_cap_is_integer_1_to_200(self):
        for value in (1,60,100,200):
            self.assertEqual(gold.collection_cap(dict(max_comments=value)),value)
        for value in (0,201,None,True,60.0,'100'):
            with self.subTest(value=value),self.assertRaises(ValueError):gold.collection_cap(dict(max_comments=value))

    def test_cap_counts_truncated_records_still_present_in_journal(self):
        self.posts=self.posts[:1];self.write_posts()
        export,_=self.source(count=2,max_comments=1,overrides={(0,1):dict(truncated=True)})
        self.assertEqual(load(export/'export_manifest.json')['exported'],1)
        with self.assertRaisesRegex(ValueError,'configured max_comments=1'):
            gold.sample(export,directory=self.directory,root=self.root)

    def test_movie_cap_shortfall_is_reported_without_relaxation(self):
        self.posts=[dict(p,movie_id='one_movie') for p in self.posts];self.write_posts()
        summary,_=self.sampled();self.assertEqual(summary['selected'],36)
        self.assertEqual(summary['shortfall'],264);self.assertGreater(summary['limits_blocking']['movie'],0)

    def test_old_post_and_comment_are_rejected_and_listed(self):
        self.posts[0]=dict(movie_id='old_movie',post_url='https://www.facebook.com/x/posts/2051192968820637');self.write_posts()
        summary,_=self.sampled(1,{(1,0):dict(permalink=self.posts[1]['post_url']+'?comment_id=777')})
        rejected=load(self.directory/'rejections.json')
        self.assertTrue(any(r.get('post_id')=='2051192968820637' and r['reason']=='POST_ALREADY_IN_HISTORY' for r in rejected))
        self.assertTrue(any(r['reason']=='COMMENT_ALREADY_IN_HISTORY' for r in rejected));self.assertEqual(summary['selected'],28)

    def test_development_only_post_is_also_rejected(self):
        development=self.root/'outputs/development/reviewed';development.mkdir(parents=True)
        write_csv(development/'annotations.csv',[dict(post_id='100000',comment_id='history_only')],['post_id','comment_id'])
        summary,_=self.sampled(1)
        self.assertEqual(summary['selected'],29)
        self.assertTrue(any(r.get('post_id')=='100000' and r['reason']=='POST_ALREADY_IN_HISTORY' for r in load(self.directory/'rejections.json')))

    def test_empty_and_batch_exact_only_long_and_near_old_are_kept(self):
        summary,_=self.sampled(1,{(0,0):dict(text_raw='x'*1201),(1,0):dict(text_raw=''),(2,0):dict(text_raw='same duplicate'),(3,0):dict(text_raw='same duplicate'),(4,0):dict(text_raw=self.old_text+' extra'),(5,0):dict(text_raw=':):)')})
        self.assertEqual(summary['selected'],28);self.assertGreaterEqual(summary['near_old'],1)
        rows=load(self.directory/'coordinator.json')['rows'];self.assertTrue(any(len(r['text'])==1201 for r in rows));self.assertTrue(any(r['text']==':):)' for r in rows))

    def test_all_new_post_records_are_reserved_before_workbook_export(self):
        export,_=self.source()
        with patch('src.annotation.gold.workbook',side_effect=RuntimeError('fixture export failure')):
            with self.assertRaises(RuntimeError):gold.sample(export,directory=self.directory,root=self.root)
        with self.assertRaises(ValueError):assert_intakes_allowed([dict(post_id='100000')],'train',self.root/'data/test_reservations')

    def test_workbook_id_text_and_label_validation(self):
        self.sampled(1);task=load(self.directory/'coordinator.json');rows=task['rows']
        with self.assertRaisesRegex(ValueError,'Every row'):gold.recheck(self.directory,'user',self.root)
        self.fill('gold_test.xlsx',rows);headers,values,_=read_sheet(self.directory/'gold_test.xlsx','Annotation')
        values[0]['text']='edited';self.fill('bad_text.xlsx',values)
        with self.assertRaisesRegex(ValueError,'text edited'):gold._labels(self.directory/'bad_text.xlsx',rows)
        values[0]=dict(values[1]);self.fill('bad_ids.xlsx',values)
        with self.assertRaisesRegex(ValueError,'IDs'):gold._labels(self.directory/'bad_ids.xlsx',rows)
        self.fill('bad_label.xlsx',rows,{rows[0]['id']:'OTHER'})
        with self.assertRaisesRegex(ValueError,'Every row'):gold._labels(self.directory/'bad_label.xlsx',rows)

    def test_recheck_100_has_no_old_labels_and_preserves_first_round(self):
        self.sampled();task=load(self.directory/'coordinator.json');self.fill('gold_test.xlsx',task['rows'])
        result=gold.recheck(self.directory,'user',self.root);self.assertEqual(result['selected'],100)
        headers,rows,_=read_sheet(self.directory/'gold_recheck.xlsx','Annotation')
        self.assertEqual(headers,gold.FIELDS);self.assertEqual(len({r['id'] for r in rows}),100)
        self.assertTrue(all(not r['label'] and not r['note'] for r in rows));self.assertEqual(len(read_jsonl(self.directory/'round_1.local.jsonl')),300)
        self.assertNotEqual([r['id'] for r in rows],[r['id'] for r in task['rows']][:100])

    def test_source_export_cannot_change_after_sample(self):
        self.sampled(1)
        source=self.directory/'input_export/comments.csv'
        source.write_bytes(source.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'Source export/journal changed'):
            gold.recheck(self.directory,'user',self.root)

    def test_kappa_hand_calculation(self):
        x=['POS']*20+['NEG']*20;y=['POS']*18+['NEG']*2+['POS']*4+['NEG']*16
        report=pair_metrics(x,y);self.assertAlmostEqual(report['agreement'],.85);self.assertAlmostEqual(report['kappa'],.7)
        self.assertEqual(report['confusion_matrix'][0][1],2);self.assertEqual(report['confusion_matrix'][1][0],4)

    def test_disagreements_final_lock_and_both_labels_kept(self):
        task,repeat=self.rounds();rid=repeat['rows'][0]['id'];self.fill('gold_recheck.xlsx',repeat['rows'],{rid:'NEG'})
        report=gold.agreement(self.directory,root=self.root);self.assertEqual(report['agreement_type'],'intra_annotator')
        self.assertEqual(report['status'],'AWAITING_USER_FINAL_LABELS');self.assertFalse((self.directory/'locked_gold.json').exists())
        rows=load(self.directory/'disagreement_coordinator.json')['rows'];fields=['id','text','label_1','label_2','label_final','note']
        self.fill('gold_disagreements.xlsx',rows,{rid:'NEU'},fields,'label_final')
        gold.agreement(self.directory,True,self.root)
        locked={r['id']:r for r in read_jsonl(self.directory/'locked_gold.local.jsonl')}
        self.assertEqual(locked[rid]['label_1'],'POS');self.assertEqual(locked[rid]['label_2'],'NEG');self.assertEqual(locked[rid]['label'],'NEU')

    def test_review_exclude_are_not_neutral(self):
        self.sampled(1);task=load(self.directory/'coordinator.json');labels={r['id']:'REVIEW' if i%2 else 'EXCLUDE' for i,r in enumerate(task['rows'])}
        self.fill('gold_test.xlsx',task['rows'],labels);gold.recheck(self.directory,'user',self.root)
        repeat=load(self.directory/'recheck_coordinator.json');self.fill('gold_recheck.xlsx',repeat['rows'],labels)
        report=gold.agreement(self.directory,root=self.root);self.assertEqual(report['sentiment_pair_count'],0)
        self.assertTrue(all(r['label'] is None for r in read_jsonl(self.directory/'locked_gold.local.jsonl')))

    def test_evaluate_rejects_unlocked_gold(self):
        from src.models.core import evaluate_gold
        with self.assertRaisesRegex(ValueError,'locked'):evaluate_gold(self.directory,self.root/'missing.jsonl',self.root)
        self.assertFalse((self.directory/'results/receipt.json').exists())

    def test_nb_has_no_class_weight_and_fixed_svm_parameters(self):
        from src.models.core import GOLD_CONFIG,gold_model
        for name in GOLD_CONFIG:
            estimator=gold_model(name).named_steps['model']
            if 'nb' in name:self.assertNotIn('class_weight',estimator.get_params())
            else:self.assertEqual(estimator.class_weight,'balanced')
        self.assertEqual(gold_model('tfidf_char_svm').named_steps['vectorizer'].ngram_range,(3,5))

    def test_train_leakage_removes_exact_near_and_reserved_post(self):
        from src.models.core import gold_train_rows
        self.lock();test=read_jsonl(self.directory/'locked_gold.local.jsonl');text=self.old_text
        # Add a controlled long gold text to the isolated leakage-function fixture.
        probe=[dict(test[0],text=text)]
        extras=[dict(record_id='exact',post_id='p_exact',comment_id='',text_raw=text,text_minimal=text,human_label='NEG',human_decisions=[dict(status='LABELED',label='NEG')]),
                dict(record_id='near',post_id='p_near',comment_id='',text_raw=text+' extra',text_minimal=text+' extra',human_label='POS',human_decisions=[dict(status='LABELED',label='POS')]),
                dict(record_id='post',post_id=test[0]['post_id'],comment_id='',text_raw='completely distinct reserved text',human_label='NEU',human_decisions=[dict(status='LABELED',label='NEU')])]
        path=self.train_fixture(extras);used,removed,summary=gold_train_rows(probe,path,self.root)
        self.assertTrue({'exact','near','post'}<={r['id'] for r in removed});self.assertEqual(summary['used'],24)

    def test_train_near_leakage_check_does_not_skip_high_frequency_shingles(self):
        from src.models.core import gold_train_rows
        self.lock();test=read_jsonl(self.directory/'locked_gold.local.jsonl')
        probe=[dict(test[0],text=self.old_text)]
        extras=[dict(record_id='near_'+str(i),post_id='post_'+str(i),comment_id='',text_raw=self.old_text+' suffix'+str(i),human_label='NEG',human_decisions=[dict(status='LABELED',label='NEG')]) for i in range(300)]
        path=self.train_fixture(extras);used,removed,summary=gold_train_rows(probe,path,self.root)
        self.assertEqual(len(removed),300);self.assertEqual(len(used),24)
        self.assertEqual(summary['near_detector']['high_document_frequency_shingles_skipped'],0)

    def test_fixture_evaluate_exactly_once_receipt_and_four_pngs(self):
        from src.models.core import evaluate_gold
        self.lock();train=self.train_fixture();result=evaluate_gold(self.directory,train,self.root)
        self.assertEqual(len(result['models']),4);self.assertEqual(result['train']['used'],24)
        self.assertEqual(len(list((self.directory/'results').glob('*_confusion.png'))),4)
        self.assertTrue(all(p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') for p in (self.directory/'results').glob('*.png')))
        with self.assertRaises(FileExistsError):evaluate_gold(self.directory,train,self.root)
        (self.directory/'results/receipt.json').unlink()
        with self.assertRaises(FileExistsError):evaluate_gold(self.directory,train,self.root)

    def test_failed_fixture_fit_still_consumes_evaluation_receipt(self):
        from src.models.core import evaluate_gold
        self.lock();train=self.train_fixture()
        class Broken:
            def fit(self,*args):raise RuntimeError('synthetic fitting failure')
        with patch('src.models.core.gold_model',return_value=Broken()):
            with self.assertRaises(RuntimeError):evaluate_gold(self.directory,train,self.root)
        self.assertTrue((self.directory/'results/receipt.json').is_file())
        with self.assertRaises(FileExistsError):evaluate_gold(self.directory,train,self.root)


if __name__=='__main__':unittest.main()
