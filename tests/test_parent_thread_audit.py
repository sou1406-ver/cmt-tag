import unittest
from unittest.mock import patch

from src.dataset.parent_thread_audit import verified_parent, _fold_thread_overlaps


def master_record(parent='p1'):
    return dict(id='m1', source_platform='facebook', comment_id='c2', post_id='post1',
        parent_comment_id=parent, source_file='source.csv', source_row=4, observations=[dict(
            source_file='source.csv', source_row=4, source_platform='facebook', comment_id='c2',
            post_id='post1', parent_comment_id=parent)])


class ParentThreadAuditTests(unittest.TestCase):
    def test_parent_requires_verified_master_link_and_source_record(self):
        row=dict(master_id='m1', comment_id='c2', post_id='post1')
        with patch('src.dataset.parent_thread_audit._selected_source_record', return_value=(
                dict(comment_id='c2',post_id='post1',parent_comment_id='p1',record_type='reply'),'FOUND')):
            self.assertEqual(verified_parent(row,master_record()), ('p1','VERIFIED','reply'))

    def test_absent_parent_field_is_unverifiable_not_zero_overlap(self):
        row=dict(master_id='m1', comment_id='c2', post_id='post1')
        with patch('src.dataset.parent_thread_audit._selected_source_record', return_value=(
                dict(comment_id='c2',post_id='post1',record_type='reply'),'FOUND')):
            self.assertEqual(verified_parent(row,master_record())[:2], (None,'UNVERIFIABLE_MISSING_METADATA'))

    def test_reply_without_parent_id_is_unverifiable(self):
        row=dict(master_id='m1', comment_id='c2', post_id='post1')
        record=master_record(parent='')
        record['observations'][0]['parent_comment_id']=''
        with patch('src.dataset.parent_thread_audit._selected_source_record', return_value=(
                dict(comment_id='c2',post_id='post1',parent_comment_id='',record_type='reply'),'FOUND')):
            self.assertEqual(verified_parent(row,record)[:2], (None,'UNVERIFIABLE_REPLY_PARENT_MISSING'))

    def test_namespace_prevents_cross_platform_parent_false_overlap(self):
        train=[dict(source_platform='facebook',post_id='p1',comment_id='parent',verified_parent_comment_id='')]
        valid=[dict(source_platform='momo',post_id='p1',comment_id='reply',verified_parent_comment_id='parent')]
        result=_fold_thread_overlaps(train,valid)
        self.assertEqual(result['parent_child_edges_crossing'],0)
        self.assertEqual(result['sibling_parent_groups_crossing'],0)

    def test_detects_parent_child_and_shared_sibling_parent(self):
        train=[dict(source_platform='facebook',post_id='p1',comment_id='parent',verified_parent_comment_id=''),
               dict(source_platform='facebook',post_id='p1',comment_id='reply_a',verified_parent_comment_id='parent')]
        valid=[dict(source_platform='facebook',post_id='p1',comment_id='reply_b',verified_parent_comment_id='parent')]
        result=_fold_thread_overlaps(train,valid)
        self.assertEqual(result['parent_child_edges_crossing'],1)
        self.assertEqual(result['sibling_parent_groups_crossing'],1)
        self.assertEqual(result['shared_parent_ids'],1)


if __name__ == '__main__':
    unittest.main()
