import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.dataset.phase_i4 import proposal,sample,domain_metrics,require_release,source_description
from src.dataset.common import save
from src.dataset.repetition import repetition_signals


class PhaseI4Tests(unittest.TestCase):
    def row(self,**kwargs):
        row=dict(record_id='a',domain_status='IN_DOMAIN_LIKELY',domain_evidence=['FILM_CUE'],
            quality_reason_code=[],format_status='PLAIN_OR_PROTECTED',technical_quality_status='KEEP',repetition_risk=False,
            source_dataset='facebook',quality_status='KEEP',movie_id='film',post_id='post',text_clean='phim hay',text_raw='phim hay')
        row.update(kwargs);return row

    def test_metadata_alone_is_uncertain_not_human_truth(self):
        result=proposal(self.row(domain_evidence=['VERIFIED_FILM_POST_METADATA']))
        self.assertEqual(result['proposed_domain_status'],'UNCERTAIN')
        self.assertEqual(result['proposal_status'],'PROPOSED_UNVALIDATED')

    def test_partial_provenance_not_asserted_as_verified_identity(self):
        result=source_description(self.row(comment_id='',post_url=''))
        self.assertIn('incomplete',result)
        self.assertIn('unverified',source_description(self.row(source_dataset='legacy_29k_unverified')))

    def test_context_never_becomes_exclusion_or_sentiment(self):
        result=proposal(self.row(domain_status='CONTEXT_NEEDED'))
        self.assertEqual(result['proposed_domain_status'],'CONTEXT_REQUIRED')
        self.assertNotIn('NEU',result.values())

    def test_blank_or_sentiment_decisions_cannot_produce_metrics(self):
        for value in ('','POS','NEG','NEU'):
            with self.assertRaises(ValueError):domain_metrics([self.row(proposed_domain_status='IN_DOMAIN',human_domain_decision=value)])

    def test_real_sample_metrics_with_abstentions(self):
        rows=[self.row(proposed_domain_status='OFF_TOPIC',human_domain_decision='OFF_TOPIC'),
              self.row(proposed_domain_status='IN_DOMAIN',human_domain_decision='OFF_TOPIC'),
              self.row(proposed_domain_status='OFF_TOPIC',human_domain_decision='UNSURE')]
        result=domain_metrics(rows)
        self.assertEqual(result['off_topic_precision'],1);self.assertEqual(result['off_topic_recall'],.5)
        self.assertEqual(result['context_and_unsure_abstained'],1)

    def test_sampling_keep_random_and_exact_probabilities(self):
        rows=[self.row(record_id=str(i),quality_status='KEEP' if i<80 else 'REVIEW',proposed_domain_status='UNCERTAIN') for i in range(250)]
        selected,design=sample(rows,7)
        self.assertEqual(len(selected),200);self.assertEqual(sum(r['sampling_stratum']=='KEEP_RANDOM' for r in selected),50)
        self.assertEqual(len({r['record_id'] for r in selected}),200)
        self.assertTrue(all(r['inclusion_probability']==r['selected']/r['frame'] for r in design))
        self.assertEqual(selected,sample(rows,7)[0])

    def test_emoji_emphasis_not_repetition_spam(self):
        self.assertFalse(repetition_signals('😂'*100)['repetition_risk'])

    def test_off_topic_decision_remains_domain_only(self):
        result=domain_metrics([self.row(proposed_domain_status='IN_DOMAIN',human_domain_decision='OFF_TOPIC')])
        self.assertEqual(result['off_topic_in_keep'],1);self.assertNotIn('NEU',str(result))

    def test_release_requires_real_approval_and_imports(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);approval=root/'approval.json';save(approval,dict(approved='false'))
            with self.assertRaisesRegex(ValueError,'Explicit human'):require_release(root,root,root,approval,root/'manifest.json')

if __name__=='__main__':unittest.main()
