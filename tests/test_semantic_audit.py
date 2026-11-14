import copy
import csv
import json
from pathlib import Path
import random
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape

from scripts.sample_audit import (FIELDS, EDITABLE, IMMUTABLE, estimate, load_source, read_csv, read_audit, row_hash,
                                 select_sample, sha, validate_audit, write_report)


def frame():
    rows = []
    for post in range(20):
        for item in range(30):
            rows.append(dict(comment_id=str(10000 + post * 30 + item), post_id=str(1000 + post),
                post_url=f'https://www.facebook.com/groups/fixture/posts/{1000 + post}',
                source_name='Fixture ' + str(post % 3), source_type='group', movie_id='film_' + str(post % 8),
                record_type='comment' if item % 2 == 0 else 'reply', parent_comment_id='999',
                text_raw=f'Fixture raw {post} {item}? :))', text_clean=f'Fixture {post} {item}? :))',
                clean_status='KEEP'))
    return rows


class SemanticAuditTests(unittest.TestCase):
    def test_excel_import_preserves_source_and_rejects_edits(self):
        rows, _ = select_sample(frame())
        manifest = {'selected': [dict(comment_id=r['comment_id'], immutable_sha256=row_hash(r)) for r in rows]}
        def write_book(path, items, reference, formula=False):
            ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
            def sheet(headers, data):
                xml = []
                for idx, values in enumerate([headers, *[[r[k] for k in headers] for r in data]], 1):
                    cells = []
                    for col, value in enumerate(values, 1):
                        name = ''; n = col
                        while n: n, rem = divmod(n-1, 26); name = chr(65+rem) + name
                        extra = '<f>1+1</f>' if formula and idx == 2 and col == 1 else ''
                        cells.append(f'<c r="{name}{idx}" t="inlineStr">{extra}<is><t>{escape(str(value))}</t></is></c>')
                    xml.append(f'<row r="{idx}">{"".join(cells)}</row>')
                return f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml)}</sheetData></worksheet>'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Gán nhãn" sheetId="1" r:id="r1"/><sheet name="Đối chiếu" sheetId="2" r:id="r2"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet1.xml', sheet(['comment_id', 'text_clean', *EDITABLE], items))
                z.writestr('xl/worksheets/sheet2.xml', sheet(list(IMMUTABLE), reference))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); csv_path = directory / 'audit_sample.csv'
            with csv_path.open('w', encoding='utf8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
            original_bytes = csv_path.read_bytes()
            book = directory / 'audit_sample.xlsx'; annotated = copy.deepcopy(rows)
            annotated[0].update(semantic_relevance='RELEVANT', needs_context='NO', confidence='HIGH')
            write_book(book, annotated, rows)
            actual = read_audit(directory, manifest)
            self.assertEqual(actual[0]['semantic_relevance'], 'RELEVANT')
            self.assertEqual(csv_path.read_bytes(), original_bytes)
            for kind in ('text', 'id', 'label', 'reference', 'formula'):
                changed = copy.deepcopy(annotated); ref = copy.deepcopy(rows)
                if kind == 'text': changed[0]['text_clean'] += ' edited'
                if kind == 'id': changed[0]['comment_id'] = changed[1]['comment_id']
                if kind == 'label': changed[0]['semantic_relevance'] = 'POS'
                if kind == 'reference': ref[0]['text_raw'] += ' edited'
                write_book(book, changed, ref, formula=kind == 'formula')
                with self.subTest(kind=kind), self.assertRaises(ValueError): read_audit(directory, manifest)
            with self.assertRaises(FileNotFoundError): read_audit(directory, manifest, directory / 'missing.xlsx')

    def test_reproducible_unique_stratified_and_immutable(self):
        original = frame(); before = copy.deepcopy(original)
        rows, strata = select_sample(original)
        shuffled = copy.deepcopy(original); random.Random(999).shuffle(shuffled)
        self.assertEqual((rows, strata), select_sample(shuffled))
        self.assertEqual(original, before)
        self.assertEqual(len(rows), 300); self.assertEqual(len({r['comment_id'] for r in rows}), 300)
        self.assertEqual(len({r['post_id'] for r in rows}), 20)
        self.assertEqual(len({r['source'] for r in rows}), 3)
        self.assertEqual(sum(r['sample_type'] == 'random' for r in rows), 240)
        self.assertEqual(sum(r['sample_type'] == 'hard' for r in rows), 60)
        for typ, cap in (('random', 14), ('hard', 6)):
            for post in {r['post_id'] for r in rows}:
                self.assertLessEqual(sum(r['sample_type'] == typ and r['post_id'] == post for r in rows), cap)
        for r in rows:
            if r['sample_type'] == 'random':
                self.assertAlmostEqual(float(r['inclusion_probability']), int(r['random_stratum_n']) / int(r['population_stratum_size']))
            else: self.assertEqual(r['inclusion_probability'], '')
            self.assertTrue(all(r[key] == '' for key in ('semantic_relevance', 'audit_reason', 'needs_context', 'confidence')))
        self.assertTrue(all(h['n'] >= 2 or h['n'] == h['N'] for h in strata))

    def test_random_selection_does_not_use_sentiment_cues(self):
        original = frame(); altered = copy.deepcopy(original)
        for r in altered: r['text_clean'] += ' khen chê bất kỳ?'
        a, _ = select_sample(original); b, _ = select_sample(altered)
        self.assertEqual({r['comment_id'] for r in a if r['sample_type'] == 'random'},
                         {r['comment_id'] for r in b if r['sample_type'] == 'random'})

    def test_keep_frame_validation_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.csv'; rows = frame()
            rows[0]['clean_status'] = 'REVIEW'; rows[1]['clean_status'] = 'EXCLUDE'
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            before = path.read_bytes(); all_rows, eligible = load_source(path)
            self.assertEqual(len(all_rows), 600); self.assertEqual(len(eligible), 598)
            sample, _ = select_sample(eligible)
            self.assertTrue(all(r['clean_status'] == 'KEEP' for r in sample))
            self.assertEqual(path.read_bytes(), before)
            rows[2]['comment_id'] = rows[3]['comment_id']
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, 'Duplicate'): load_source(path)

    def test_annotation_integrity_and_label_validation(self):
        rows, _ = select_sample(frame())
        manifest = {'selected': [{'comment_id': r['comment_id'], 'immutable_sha256': row_hash(r)} for r in rows]}
        validate_audit(rows, manifest)
        bad = copy.deepcopy(rows); bad[0]['text_clean'] += ' edited'
        with self.assertRaisesRegex(ValueError, 'edited'): validate_audit(bad, manifest)
        with self.assertRaises(ValueError): validate_audit(rows[:-1], manifest)
        with self.assertRaises(ValueError): validate_audit([rows[0], *rows[0:-1]], manifest)
        bad = copy.deepcopy(rows); bad[0]['semantic_relevance'] = 'POS'
        with self.assertRaisesRegex(ValueError, 'Invalid relevance'): validate_audit(bad, manifest)
        good = copy.deepcopy(rows)
        good[0].update(semantic_relevance='UNCERTAIN', audit_reason='CONTEXT_MISSING', needs_context='YES', confidence='LOW')
        validate_audit(good, manifest)

    def test_weighted_srs_variance_matches_hand_calculation_and_ignores_hard(self):
        strata = [{'key': 'a', 'N': 4, 'n': 2}, {'key': 'b', 'N': 2, 'n': 2}]
        rows = [dict(sample_type='random', sample_stratum=h, semantic_relevance=label)
                for h, label in [('a', 'RELEVANT'), ('a', 'IRRELEVANT'), ('b', 'IRRELEVANT'), ('b', 'IRRELEVANT')]]
        rows.append(dict(sample_type='hard', sample_stratum='a', semantic_relevance='RELEVANT'))
        actual = estimate(rows, strata, 'RELEVANT')
        self.assertAlmostEqual(actual['rate'], 1 / 3); self.assertAlmostEqual(actual['variance'], 1 / 18)
        rows[-1]['semantic_relevance'] = 'UNCERTAIN'
        self.assertEqual(estimate(rows, strata, 'RELEVANT'), actual)
        rows[0]['semantic_relevance'] = ''
        self.assertIsNone(estimate(rows, strata, 'RELEVANT'))

    def test_no_false_zero_uncertainty_and_census(self):
        rows = [dict(sample_type='random', sample_stratum='a', semantic_relevance='RELEVANT') for _ in range(2)]
        self.assertIsNone(estimate(rows, [{'key': 'a', 'N': 4, 'n': 2}], 'RELEVANT')['ci95'])
        self.assertEqual(estimate(rows, [{'key': 'a', 'N': 2, 'n': 2}], 'RELEVANT')['ci95'], [1., 1.])

    def test_report_waits_for_humans_and_checks_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.csv'; source.write_text('fixture', encoding='utf8')
            guideline = root / 'guide.md'; guideline.write_text('fixture', encoding='utf8')
            rows, strata = select_sample(frame())
            with (root / 'audit_sample.csv').open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
            manifest = dict(source_file=str(source), source_sha256=sha(source), guideline_file=str(guideline),
                guideline_sha256=sha(guideline), source_records=600, eligible_records=600, seed=20261114,
                random_count=240, hard_count=60, strata=strata,
                selected=[{'comment_id': r['comment_id'], 'immutable_sha256': row_hash(r)} for r in rows])
            (root / 'sampling_manifest.json').write_text(json.dumps(manifest), encoding='utf8')
            result = write_report(root); self.assertEqual(result['labelled'], 0)
            report = (root / 'audit_report.md').read_text(encoding='utf8')
            self.assertIn('Chờ người gán', report); self.assertIn('Chờ nhãn random', report)
            self.assertEqual(len(read_csv(root / 'audit_sample.csv')), 300)
            source.write_text('changed', encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'checksum'): write_report(root)


if __name__ == '__main__': unittest.main()
