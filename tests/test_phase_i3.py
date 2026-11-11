import unittest
from src.preprocessing.plain_text_v3 import preprocess,shape
from src.dataset.phase_i3 import source_sample,funnel
from src.dataset.format_sample import select

class PhaseI3Tests(unittest.TestCase):
    def test_model_supported_token_not_in_small_dictionary(self):
        raw='Tôi có cảm_nhận rất khác, không buồn :))) 😭'
        result=preprocess(raw,{'cảm_nhận'})
        self.assertIn('cảm nhận',result['text_clean']);self.assertIn('không',result['text_clean'])
        self.assertIn(':))) 😭',result['text_clean'])
        self.assertEqual(preprocess(result['text_clean'],{'cảm_nhận'})['text_clean'],result['text_clean'])

    def test_verified_source_bound_to_hash_and_namespace(self):
        proof=[dict(source_key='synthetic',sha256='abc',format='word_segmentation',evidence='fixture attestation')]
        self.assertEqual(preprocess('thuong_thuc',source_key='synthetic',source_sha='abc',verified_sources=proof)['text_clean'],'thuong thuc')
        self.assertEqual(preprocess('thuong_thuc',source_key='other',source_sha='abc',verified_sources=proof)['text_clean'],'thuong_thuc')
        self.assertEqual(preprocess('thuong_thuc',source_key='synthetic',source_sha='wrong',verified_sources=proof)['text_clean'],'thuong_thuc')

    def test_protected_names_ids_code_and_urls(self):
        raw='Trấn_Thành user_name123 #cảm_nhận @cảm_nhận `cảm_nhận` https://x/cảm_nhận'
        self.assertEqual(preprocess(raw,{'cảm_nhận'})['text_clean'],raw)
        self.assertEqual(preprocess('السلام_عليكم',{'السلام_عليكم'})['text_clean'],'السلام_عليكم')

    def test_alias_punctuation_and_ambiguous_bare(self):
        self.assertEqual(preprocess('phim hay thinking_face :red_heart: : :')['text_clean'],'phim hay 🤔 ❤️ : :')
        self.assertEqual(preprocess('variable thinking_face')['text_clean'],'variable thinking_face')

    def test_rare_unknown_and_long_sarcasm_preserved(self):
        raw='Hay quá cơ :))) xyz_abc không '+('câu dài '*1000)
        result=preprocess(raw)
        self.assertEqual(result['text_clean'],raw.strip());self.assertEqual(result['format_status'],'NEEDS_REVIEW')

    def test_source_sampler_never_reintroduces_filtered_rows(self):
        rows=[dict(record_id=str(i),source_dataset='facebook' if i<2 else 'legacy',post_id=str(i)) for i in range(10)]
        selected=source_sample(rows,{'0':{'1'},'1':{'0'}},5,1,4)
        ids={r['record_id'] for r in selected}
        self.assertEqual(len(selected),5);self.assertFalse({'0','1'}<=ids)
        self.assertTrue(ids<={r['record_id'] for r in rows})

    def test_funnel_counts_overlap_without_double_counting(self):
        rows=[dict(eligibility_reasons=['human','same_development_post']),dict(eligibility_reasons=[])]
        result=funnel(rows)
        self.assertEqual(result['nonexclusive']['human'],1)
        self.assertEqual(result['pairwise_overlap']['human']['same_development_post'],1)
        self.assertEqual(result['eligible'],1)

    def test_format_sample_keeps_name_boundary_and_excludes_test(self):
        rows=[]
        for i in range(30):
            rows.append(dict(record_id=str(i),test_reserved=i==0,annotation_pool_reasons=[],source_dataset='facebook',
                text_raw='không',text_clean='không',text_clean_i2='không',text_clean_i3='không',format_status='NEEDS_REVIEW',
                alias_changes=[],flags={'negation_present':True},format_evidence=[dict(source_token='Tên_Riêng',rule='PRESERVE_POSSIBLE_NAME',confidence_category='AMBIGUOUS_NEEDS_REVIEW')]))
        selected,summary=select(rows,{},count=20)
        self.assertEqual(len(selected),20);self.assertFalse(any(r['test_reserved'] for r in selected))
        self.assertGreater(summary['selected']['possible_name'],0)

if __name__=='__main__':unittest.main()
