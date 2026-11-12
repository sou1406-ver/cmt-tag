"""Simple filter policy, literal text preservation and exact-only removal."""
import unittest
from copy import deepcopy
from src.dataset.master import minimal_filter_text,filter_row_reasons,strict_filter_dedup,cleaning_protection,facebook_length_review
from src.data.split import duplicate_groups
from src.data.quality import layers, verified_post
from src.dataset.blind import deny_reserved, quarantine_posts


class DatasetFilterTests(unittest.TestCase):
    def row(self,rid='a',text='phim hay',source='legacy_29k_unverified',label=''):
        return dict(record_id=rid,text_raw=text,text_normalized=minimal_filter_text(text),source_dataset=source,human_label=label,
            human_decisions=[dict(status='LABELED',label=label)] if label else [])

    def test_underscore_policy_is_raw_and_legacy_only(self):
        self.assertIn('LEGACY_RAW_UNDERSCORE',filter_row_reasons(self.row(text='kịch_bản')))
        self.assertEqual(filter_row_reasons(self.row(text='kịch_bản',source='facebook')),[])
        self.assertIn('LEGACY_RAW_UNDERSCORE',filter_row_reasons(self.row(text='https://x.test/a_b')))

    def test_800_is_exclusive_and_facebook_has_no_implicit_limit(self):
        self.assertNotIn('EXC_TOO_LONG',filter_row_reasons(self.row(text='a'*800),legacy_max_characters=800))
        self.assertIn('EXC_TOO_LONG',filter_row_reasons(self.row(text='a'*801),legacy_max_characters=800))
        self.assertNotIn('EXC_TOO_LONG',filter_row_reasons(self.row(text='a'*801,source='facebook')))
        self.assertIn('EXC_TOO_LONG',filter_row_reasons(self.row(text='a'*801,source='facebook'),facebook_max_characters=800))

    def test_updated_default_is_strictly_over_1000(self):
        self.assertNotIn('EXC_TOO_LONG',filter_row_reasons(self.row(text='a'*1000)))
        self.assertIn('EXC_TOO_LONG',filter_row_reasons(self.row(text='a'*1001)))

    def test_facebook_long_comment_is_review_not_excluded_or_relabeled(self):
        row=self.row(text='a'*1001,source='facebook',label='POS');before=deepcopy(row)
        self.assertTrue(facebook_length_review(row));self.assertEqual(filter_row_reasons(row),[]);self.assertEqual(row,before)
        self.assertFalse(facebook_length_review(self.row(text='a'*1000,source='facebook')))
        self.assertFalse(facebook_length_review(self.row(text='a'*1001,source='legacy_29k_unverified')))

    def test_empty_and_confirmed_encoding_errors(self):
        self.assertIn('EMPTY_TEXT',filter_row_reasons(self.row(text=' \n\t')))
        for text in ['abc\ufffd','abc\x00']:
            self.assertIn('INVALID_ENCODING_OR_CONTROL',filter_row_reasons(self.row(text=text)))
        self.assertEqual(filter_row_reasons(self.row(text='abc\nxyz')),[])

    def test_short_emoji_teencode_and_ui_string_not_automatically_deleted(self):
        for text in ['😭',':))',':):)','-_-','ko','hay','Xem thêm','a']:
            self.assertEqual(filter_row_reasons(self.row(text=text,source='facebook')),[])

    def test_real_human_exclude_is_preserved_as_evidence(self):
        r=self.row();r['human_decisions']=[dict(status='EXCLUDE',label='')]
        self.assertIn('HUMAN_EXCLUDE',filter_row_reasons(r))
        r['human_decisions'].append(dict(status='LABELED',label='POS'))
        self.assertNotIn('HUMAN_EXCLUDE',filter_row_reasons(r))

    def test_minimal_view_preserves_expression_and_internal_spacing(self):
        for text in ['phim ko :))',':):)',':-)', '-_-','a -  b','a\n- b','không hay lắmmmm','Trấn Thành và Mưa Đỏ','a  b']:
            self.assertEqual(minimal_filter_text(text),text)
            self.assertEqual(minimal_filter_text(minimal_filter_text(text)),text)

    def test_nfc_exact_entities_and_conservative_whitespace(self):
        self.assertEqual(minimal_filter_text('  a\u0301 &amp;amp; b\r\nc\u00a0d  '),'á & b\nc d')
        self.assertEqual(minimal_filter_text('&notareal; &not_real; &#0;'),'&notareal; &not_real; &#0;')

    def test_code_url_email_are_literal(self):
        text='https://x.test/?a=1&amp;b=2 `a &amp; b` ```a &amp; b``` a+b@x.test'
        self.assertEqual(minimal_filter_text(text),text)

    def test_strict_exact_only_and_no_label_transfer(self):
        rows=[self.row('a','phim hay',source='facebook'),self.row('b','phim hay',label='NEG'),self.row('c','Phim hay'),self.row('d','phim  hay')]
        before=deepcopy(rows);kept,removed,groups,conflicts=strict_filter_dedup(rows)
        self.assertEqual({r['record_id'] for r in kept},{'b','c','d'});self.assertEqual(removed[0][0]['record_id'],'a');self.assertEqual(removed[0][1],'b')
        self.assertEqual(rows,before);self.assertEqual(conflicts,set());self.assertEqual(kept[0]['human_label'],'NEG')

    def test_conflicting_labels_flagged_not_rewritten(self):
        rows=[self.row('a',label='POS'),self.row('b',label='NEG')]
        before=deepcopy(rows);kept,removed,groups,conflicts=strict_filter_dedup(rows)
        self.assertEqual(len(kept),1);self.assertEqual(rows,before);self.assertIn(groups['a'],conflicts)

    def test_near_link_protects_but_does_not_delete_independent_opinion(self):
        rows=[self.row('a','phim này hay'),self.row('b','phim này không hay')]
        kept,removed,_,_=strict_filter_dedup(rows);self.assertEqual(len(kept),2);self.assertEqual(removed,[])
        blocked,_=cleaning_protection(rows,{'a'},[dict(left='a',right='b')]);self.assertEqual(blocked,{'a','b'})

    def test_moved_duplicate_detector_keeps_direct_edges_and_exact_aliases(self):
        rows=[dict(record_id='a',text_clean='phim có kịch bản hay và diễn xuất rất tốt'),
              dict(record_id='b',text_clean='PHIM có kịch bản hay và diễn xuất rất tốt'),
              dict(record_id='c',text_clean='phim có kịch bản hay và diễn xuất rất tốt nhé')]
        groups,extras,near=duplicate_groups(rows,threshold=.7,min_chars=10)
        self.assertEqual(groups['a'],groups['b'])
        self.assertEqual(extras,{'b'})
        self.assertEqual(near['neighbors']['a'],{'c'})
        self.assertEqual(near['summary']['direct_near_duplicate_edges'],1)

    def test_quality_is_only_proposal_and_linked_parent_is_not_sentiment(self):
        result=layers(dict(text_normalized='cũng vậy',parent_comment_id='parent'),dict(text_normalized='phim hay'))
        self.assertEqual(result['domain_status'],'CONTEXT_REQUIRED')
        self.assertNotIn('label',result)
        self.assertIn('LINKED_PARENT_FILM_CUE_NOT_CHILD_CONFIRMATION',result['domain_evidence'])
        self.assertFalse(verified_post(dict(source_dataset='facebook',post_id='bad',comment_id='1',post_url='https://example.com/')))

    def test_whole_post_quarantine_retains_cross_platform_duplicate_protection(self):
        rows=[dict(id='a',group_id='g',source_platform='facebook',post_id='10',comment_id='11',post_url='https://www.facebook.com/p/posts/10',text_view='phim hay',text_variants=['phim hay']),
              dict(id='b',group_id='g',source_platform='momo',post_id='20',comment_id='21',post_url='',text_view='phim hay',text_variants=['phim hay'])]
        reserved=quarantine_posts(rows,{'10'})
        self.assertEqual(set(reserved['ids']),{'a','b'})
        with self.assertRaises(ValueError):deny_reserved([rows[1]],'train',reserved)
        deny_reserved([dict(source_platform='momo',comment_id='11',post_id='30')],'train',reserved)


if __name__=='__main__':unittest.main()
