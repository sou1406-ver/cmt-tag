// Run from an isolated authoring directory linked to the bundled artifact-tool.
// Input is already blinded; this builder refuses coordinator metadata.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [inputPath, outputDir] = process.argv.slice(2);
if (!inputPath || !outputDir) throw new Error('Usage: node build_blind_workbooks.mjs workbook_input.json NEW_OUTPUT_DIR');
const fields = ['id','text_view','status','label','review_reason','reason'];
const payload = JSON.parse(await fs.readFile(inputPath, 'utf8'));
if (Object.keys(payload).sort().join(',') !== 'a,b') throw new Error('Only blind A/B input is permitted');
for (const key of ['a','b']) {
  if (payload[key].length !== (key==='a' ? 180 : 50)) throw new Error('Require exactly 180 A and 50 B rows');
  for (const row of payload[key]) {
    if (Object.keys(row).sort().join(',') !== [...fields].sort().join(',') ||
        fields.some(f => typeof row[f] !== 'string') || fields.slice(2).some(f => row[f] !== ''))
      throw new Error('Unexpected metadata or pre-filled decisions');
  }
}
if (new Set(payload.a.map(r=>r.id)).size!==180 || new Set(payload.b.map(r=>r.id)).size!==50 ||
    payload.b.some(r=>!payload.a.some(a=>a.id===r.id && a.text_view===r.text_view)))
  throw new Error('B must be a distinct subset of A with identical literal text');
await fs.mkdir(outputDir, {recursive:false});
for (const key of ['a','b']) {
  const rows = payload[key], book = Workbook.create(), sheet = book.worksheets.add('Gan nhan mu');
  const last = rows.length+1;
  const safeText = s => s.startsWith('=') ? "'"+s : s;
  sheet.getRange(`A1:F${last}`).values = [fields,...rows.map(r=>fields.map(f=>safeText(r[f])))];
  sheet.getRange(`A1:F${last}`).format.font = {name:'Arial',size:11,color:'#243247'};
  sheet.getRange(`A1:F${last}`).setNumberFormat('@');
  sheet.getRange('A1:F1').format = {fill:'#253858',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:28};
  sheet.getRange(`A2:F${last}`).format.wrapText = true;
  sheet.getRange(`A2:F${last}`).format.verticalAlignment = 'top';
  sheet.getRange(`A1:A${last}`).format.columnWidth = 28;
  sheet.getRange(`B1:B${last}`).format.columnWidth = 100;
  sheet.getRange(`C1:D${last}`).format.columnWidth = 16;
  sheet.getRange(`E1:E${last}`).format.columnWidth = 22;
  sheet.getRange(`F1:F${last}`).format.columnWidth = 38;
  sheet.getRange(`C2:F${last}`).format.fill = '#FFF9E6';
  sheet.getRange(`C2:F${last}`).format.font = {name:'Arial',size:11,color:'#1756A9'};
  rows.forEach((row,i)=>{
    sheet.getRange(`A${i+2}:F${i+2}`).format.rowHeight = Math.min(409,Math.max(62,18*(Math.ceil(row.text_view.length/100)+row.text_view.split('\n').length)));
    if (i%2===1) sheet.getRange(`A${i+2}:B${i+2}`).format.fill='#F0F4F8';
  });
  sheet.getRange(`C2:C${last}`).dataValidation={rule:{type:'list',values:['LABELED','REVIEW','EXCLUDE']}};
  sheet.getRange(`D2:D${last}`).dataValidation={rule:{type:'list',values:['POS','NEG','NEU','REVIEW','EXCLUDE']}};
  sheet.getRange(`E2:E${last}`).dataValidation={rule:{type:'list',values:['REV_MIXED','REV_SARCASM','REV_TARGET','REV_CONTEXT','REV_OTHER']}};
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add(`A1:F${last}`,true,'BlindAnnotations');
  const preview=await book.render({sheetName:'Gan nhan mu',range:'A1:F6',scale:1.3,format:'png'});
  await fs.writeFile(path.join(outputDir,`preview_${key}.png`),new Uint8Array(await preview.arrayBuffer()));
  const xlsx=await SpreadsheetFile.exportXlsx(book);
  await xlsx.save(path.join(outputDir,key==='a'?'test_annotator_a.xlsx':'test_annotator_b_50.xlsx'));
}
console.log('Created two blind workbooks; no coordinator metadata included.');
// All exports/renders are awaited. Shut down artifact rendering workers cleanly.
process.exit(0);
