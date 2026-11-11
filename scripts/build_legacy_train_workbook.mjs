// Author from a blinded JSON array, using the bundled @oai/artifact-tool only.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const [input,outputDir]=process.argv.slice(2);
if(!input||!outputDir)throw new Error('Usage: node builder.mjs workbook_input.json NEW_OUTPUT_DIR');
const rows=JSON.parse(await fs.readFile(input,'utf8'));
const fields=['id','text_view','status','label','review_reason','reason'];
if(!Array.isArray(rows)||rows.length<200||rows.length>300||new Set(rows.map(r=>r.id)).size!==rows.length)
  throw new Error('Require 200–300 distinct annotation candidates');
for(const row of rows){
  if(Object.keys(row).sort().join(',')!==[...fields].sort().join(',')||fields.some(k=>typeof row[k]!=='string')||fields.slice(2).some(k=>row[k]!==''))
    throw new Error('Only blind fields and empty decisions permitted');
}
await fs.mkdir(outputDir,{recursive:false});
const book=Workbook.create(),sheet=book.worksheets.add('Gan nhan train'),last=rows.length+1;
const literal=s=>s.startsWith('=')?"'"+s:s;
sheet.getRange(`A1:F${last}`).values=[fields,...rows.map(r=>fields.map(k=>literal(r[k])))];
sheet.getRange(`A1:F${last}`).setNumberFormat('@');
sheet.getRange(`A1:F${last}`).format.font={name:'Arial',size:11,color:'#243247'};
sheet.getRange('A1:F1').format={fill:'#253858',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:28};
sheet.getRange(`A2:F${last}`).format.wrapText=true;
sheet.getRange(`A2:F${last}`).format.verticalAlignment='top';
sheet.getRange(`A1:A${last}`).format.columnWidth=29;
sheet.getRange(`B1:B${last}`).format.columnWidth=100;
sheet.getRange(`C1:D${last}`).format.columnWidth=16;
sheet.getRange(`E1:E${last}`).format.columnWidth=23;
sheet.getRange(`F1:F${last}`).format.columnWidth=36;
sheet.getRange(`C2:F${last}`).format.fill='#FFF9E6';
rows.forEach((r,i)=>{
  sheet.getRange(`A${i+2}:F${i+2}`).format.rowHeight=Math.min(409,Math.max(66,18*(Math.ceil(r.text_view.length/95)+r.text_view.split('\n').length)));
  if(i%2===1)sheet.getRange(`A${i+2}:B${i+2}`).format.fill='#F0F4F8';
});
sheet.getRange(`C2:C${last}`).dataValidation={rule:{type:'list',values:['LABELED','REVIEW','EXCLUDE']}};
sheet.getRange(`D2:D${last}`).dataValidation={rule:{type:'list',values:['POS','NEG','NEU','REVIEW','EXCLUDE']}};
sheet.getRange(`E2:E${last}`).dataValidation={rule:{type:'list',values:['REV_MIXED','REV_SARCASM','REV_TARGET','REV_CONTEXT','REV_OTHER']}};
sheet.freezePanes.freezeRows(1);
sheet.tables.add(`A1:F${last}`,true,'LegacyTrainAnnotations');
const preview=await book.render({sheetName:'Gan nhan train',range:'A1:F6',scale:1.1,format:'png'});
await fs.writeFile(path.join(outputDir,'preview.png'),new Uint8Array(await preview.arrayBuffer()));
const xlsx=await SpreadsheetFile.exportXlsx(book);
await xlsx.save(path.join(outputDir,'legacy_train_candidates.xlsx'));
console.log(`Exported ${rows.length} blind train candidates; labels blank.`);
