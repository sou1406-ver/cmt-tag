import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from src.preprocessing.plain_text import preprocess
from src.dataset.phase_i2 import release_inputs
from src.dataset.quality_workbook import read_sheet

class PhaseI2Tests(unittest.TestCase):
    def test_reviewed_compounds_plain_and_negation_preserved(self):
        raw='Tôi không thật_sự đồng_ý với quan_điểm đánh_giá kịch_bản này.'
        result=preprocess(raw)
        self.assertEqual(result['text_clean'],'Tôi không thật sự đồng ý với quan điểm đánh giá kịch bản này.')
        self.assertEqual(raw,'Tôi không thật_sự đồng_ý với quan_điểm đánh_giá kịch_bản này.')
        self.assertEqual(preprocess(result['text_clean'])['text_clean'],result['text_clean'])

    def test_protected_regions(self):
        raw='https://x/kịch_bản #kịch_bản @crying_face user_name123 `kịch_bản crying_face` a_b@example.com'
        self.assertEqual(preprocess(raw)['text_clean'],raw)

    def test_bare_alias_and_wrapped_alias(self):
        self.assertEqual(preprocess('phim hay crying_face :red_heart:')['text_clean'],'phim hay 😢 ❤️')
        self.assertEqual(preprocess('variable crying_face')['text_clean'],'variable crying_face')
        self.assertTrue(preprocess('variable crying_face')['unresolved_tokens'])

    def test_ambiguous_format_preserved(self):
        raw='ko khum k đc j z my_unknown_token :unverified_alias:'
        result=preprocess(raw)
        self.assertEqual(result['text_clean'],raw)
        self.assertIn('my_unknown_token',result['unresolved_tokens'])

    def test_sarcasm_long_text_no_semantic_edit(self):
        raw='Hay quá nhỉ :))) không còn gì để nói! '+('Đánh giá dài. '*300)
        clean=preprocess(raw)['text_clean']
        self.assertEqual(clean,raw.strip())
        self.assertEqual(preprocess(raw)['text_clean'],clean)

    def test_no_release_without_bound_approval(self):
        with TemporaryDirectory() as tmp:
            approval=Path(tmp)/'approval.json';approval.write_text('{"approved": false}')
            with self.assertRaises(ValueError):release_inputs(Path(tmp)/'pilot.csv',approval,Path(tmp)/'release')

    def test_manual_workbook_formula_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'fixture.xlsx'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Review" sheetId="1" r:id="rId1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
            with self.assertRaisesRegex(ValueError,'Formulas'):read_sheet(path,'Review')

if __name__=='__main__':unittest.main()
