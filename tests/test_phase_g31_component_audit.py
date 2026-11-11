import unittest

from src.dataset.component_audit import _components, direct_gate_passes


def fold_row(**updates):
    row = dict(identity_overlap=dict(post_id=0, comment_id=0),
        exact_text_hash_overlap=dict(original=0, basic=0),
        near_duplicate_pairs=dict(original=dict(selected_alias_pairs=0, full_master_alias_pairs=0),
                                  basic=dict(selected_alias_pairs=0, full_master_alias_pairs=0)),
        legacy_exact_overlap_rows=dict(original=0, basic=0),
        legacy_near_duplicate_pairs=dict(original=dict(selected_alias_pairs=0, full_master_alias_pairs=0),
                                         basic=dict(selected_alias_pairs=0, full_master_alias_pairs=0)),
        frozen_group_overlap=0)
    row.update(updates)
    return row


class ComponentAuditTests(unittest.TestCase):
    def test_components_measure_transitive_size(self):
        result = _components(['a', 'b', 'c', 'd'], [('a', 'b'), ('b', 'c')])
        self.assertEqual(result, dict(component_count=2, largest_component=3, components_over_1000=0))

    def test_direct_gate_passes_clear_folds(self):
        self.assertTrue(direct_gate_passes([fold_row() for _ in range(3)]))

    def test_direct_gate_blocks_identity_or_similarity_overlap(self):
        bad = fold_row(identity_overlap=dict(post_id=1, comment_id=0))
        self.assertFalse(direct_gate_passes([fold_row(), bad, fold_row()]))
        bad = fold_row(legacy_near_duplicate_pairs=dict(
            original=dict(selected_alias_pairs=1, full_master_alias_pairs=0),
            basic=dict(selected_alias_pairs=0, full_master_alias_pairs=0)))
        self.assertFalse(direct_gate_passes([bad]))


if __name__ == '__main__':
    unittest.main()
