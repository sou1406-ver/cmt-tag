import unittest
from src.dataset.repetition import repetition_signals
from src.dataset.semantic_quality import assess
from src.preprocessing.emoji_aliases import normalize_aliases
from src.dataset.phase_i1 import balanced_audit


class PhaseI1Tests(unittest.TestCase):
    def test_long_repeated_block_detected(self):
        block='Một thông điệp quảng bá rất dài gồm nhiều từ được sao chép nguyên vẹn liên tục '
        result=repetition_signals(block*30)
        self.assertEqual(result['repetition_status'],'EXCLUDE_CANDIDATE')
        self.assertGreater(result['repetition_ratio'],.65)

    def test_emoji_and_emphasis_not_structural_spam(self):
        for text in ('😂'*100,'hayyyyy quáaaaa','hay quá hay quá hay quá'):
            self.assertFalse(repetition_signals(text)['repetition_risk'])

    def test_alias_preserves_negation_urls_and_identifiers(self):
        raw='không hay :rolling_on_the_floor_laughing: https://x/:red_heart: ID:red_heart: `:crying_face:`'
        clean,events=normalize_aliases(raw)
        self.assertIn('không hay 🤣',clean)
        self.assertIn('https://x/:red_heart:',clean)
        self.assertIn('ID:red_heart:',clean)
        self.assertIn('`:crying_face:`',clean)
        self.assertEqual(len(events),1)
        self.assertEqual(normalize_aliases(clean)[0],clean)
        self.assertIn(':rolling_on_the_floor_laughing:',raw)

    def test_unknown_alias_and_teencode_underscores_preserved(self):
        text='ko khum k đc j z kịch_bản :unknown_alias:'
        self.assertEqual(normalize_aliases(text),(text,[]))

    def test_film_discussion_without_phim_keyword_not_excluded(self):
        text='Diễn xuất thật tự nhiên, kịch bản chặt chẽ và nhân vật có chiều sâu.'
        row=dict(text_raw=text)
        result=assess(row,text,repetition_signals(text))
        self.assertEqual(result['domain_status'],'IN_DOMAIN_LIKELY')
        self.assertEqual(result['quality_status'],'KEEP')

    def test_script_religion_not_blacklisted(self):
        text='Nhân vật này bàn về tôn giáo và chiến tranh السلام'
        result=assess(dict(text_raw=text),text,repetition_signals(text))
        self.assertNotEqual(result['domain_status'],'OFF_TOPIC_LIKELY')
        self.assertNotEqual(result['quality_status'],'EXCLUDE')

    def test_long_review_kept_whole_and_sent_to_review(self):
        text='Diễn xuất và kịch bản có nhiều khía cạnh. '*40
        clean,_=normalize_aliases(text)
        self.assertEqual(clean,text)
        self.assertEqual(assess(dict(text_raw=text),text,repetition_signals(text))['quality_status'],'REVIEW')

    def test_audit_sampling_deterministic(self):
        rows=[dict(record_id=str(i),source_dataset='legacy',quality_status='REVIEW',repetition_status='LOW_RISK',
                   text_clean='a',alias_changes=[],domain_status='UNCERTAIN') for i in range(20)]
        for row in rows:row['bare_alias_signal']=False
        self.assertEqual(balanced_audit(rows,10,1),balanced_audit(rows,10,1))

    def test_long_period_block_detected(self):
        text=(' '.join('token'+str(i) for i in range(150))+' ')*10
        self.assertEqual(repetition_signals(text)['repetition_status'],'EXCLUDE_CANDIDATE')

if __name__=='__main__':unittest.main()
