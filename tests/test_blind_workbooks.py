"""Minimal OOXML parser/privacy fixtures, not authored user workbooks."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from scripts.finalize_blind_workbooks import check_workbook
from src.dataset.blind import BLIND_FIELDS


def fixture(path, extra_column=False, hidden=False, formula=False):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    fields=BLIND_FIELDS+(['movie_id'] if extra_column else [])
    values=['fixture','=Literal comment 🙂','','','','']+(['SECRET_FILM'] if extra_column else [])
    sheet=ET.Element('worksheet',xmlns=ns);data=ET.SubElement(sheet,'sheetData')
    for i,row in enumerate([fields,values],1):
        element=ET.SubElement(data,'row',r=str(i))
        for j,value in enumerate(row):
            cell=ET.SubElement(element,'c',r=chr(65+j)+str(i),t='inlineStr')
            ET.SubElement(ET.SubElement(cell,'is'),'t').text=value
            if formula and i==2 and j==1:ET.SubElement(cell,'f').text='1+1'
    hidden_sheet='<sheet name="secret" sheetId="2" state="hidden" r:id="r2"/>' if hidden else ''
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Blind" sheetId="1" r:id="r1"/>{hidden_sheet}</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',ET.tostring(sheet,encoding='utf-8'))
    return [dict(zip(BLIND_FIELDS,values))]


class WorkbookPrivacyTests(unittest.TestCase):
    def test_literal_text_preserved_with_only_six_blind_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.xlsx';expected=fixture(path);check_workbook(path,expected)

    def test_hidden_coordinator_sheet_or_extra_source_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for option in ('hidden','extra_column'):
                path=Path(temp)/(option+'.xlsx');expected=fixture(path,**{option:True})
                with self.assertRaises(ValueError):check_workbook(path,expected)

    def test_formula_cells_cannot_be_read_as_manual_annotation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'formula.xlsx';expected=fixture(path,formula=True)
            with self.assertRaises(ValueError):check_workbook(path,expected)

    def test_development_model_boundary_actually_invokes_reservation_guard(self):
        from scripts.development_baseline import plan,execute
        with patch('src.dataset.blind.assert_allowed',side_effect=ValueError('reserved')) as guard:
            with self.assertRaisesRegex(ValueError,'reserved'):plan([],dict(folds=3,seed=42))
            with self.assertRaisesRegex(ValueError,'reserved'):execute([],{}, {}, [])
            self.assertEqual([call.args[1] for call in guard.call_args_list],['validation','train'])


if __name__=='__main__':unittest.main()
