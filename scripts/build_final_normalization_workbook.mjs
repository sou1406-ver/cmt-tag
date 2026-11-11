// Run isolated copy with bundled @oai/artifact-tool only.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2),bytes=await fs.readFile(input),rows=JSON.parse(bytes.toString('utf8'));
if(rows.length!==150||new Set(rows.map(r=>r.record_id)).size!==150)throw Error('Require 150 unique normalization IDs');
await fs.mkdir(output,{recursive:false});
const book=Workbook.create(),main=book.worksheets.add('Review'),compare=book.worksheets.add('Raw I3 Normalized'),guide=book.worksheets.add('Instructions');
const literal=s=>String(s??'').startsWith('=')?"'"+s:String(s??'');
const events=rows.map(r=>JSON.stringify({events:r.normalization_events,flags:r.normalization_flags}));
const chunks=Math.max(1,...events.map(v=>Math.ceil(v.length/30000)));
const col=n=>{let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s};
const values=[['id','text_normalized','change_categories','human_decision','human_note'],...rows.map(r=>[
 r.record_id,r.text_normalized,r.change_categories.join('; ')||(r.changed_vs_i3?'PROTECTION_OR_INHERITED_FORMAT':'UNCHANGED_CONTROL'),'',''].map(literal))];
const comparison=[['id','text_raw','text_clean_i3','text_normalized',...Array.from({length:chunks},(_,i)=>'transform_events_'+(i+1))],
 ...rows.map((r,i)=>[r.record_id,r.text_raw,r.text_clean_i3,r.text_normalized,...Array.from({length:chunks},(_,j)=>events[i].slice(j*30000,(j+1)*30000))].map(literal))];
if([...values,...comparison].some(r=>r.some(v=>v.length>32767)))throw Error('Cell length exceeded; no truncation allowed');
main.getRange('A1:E151').values=values;compare.getRange(`A1:${col(4+chunks)}151`).values=comparison;
for(const [sheet,last] of [[main,'E'],[compare,col(4+chunks)]]){
 sheet.getRange(`A1:${last}151`).setNumberFormat('@');sheet.getRange(`A1:${last}151`).format={font:{name:'Arial',size:11,color:'#24364B'},wrapText:true,verticalAlignment:'top'};
 sheet.getRange(`A1:${last}1`).format={fill:'#234B65',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:40};
 sheet.getRange('A1:A151').format.columnWidth=24;sheet.freezePanes.freezeRows(1);
 sheet.tables.add(`A1:${last}151`,true,sheet===main?'FinalNormalizationReview':'NormalizationComparison');
 rows.forEach((r,i)=>sheet.getRange(`A${i+2}:${last}${i+2}`).format.rowHeight=Math.min(260,Math.max(70,18*(Math.ceil(r.text_normalized.length/100)+1))));
}
main.getRange('B1:B151').format.columnWidth=105;main.getRange('C1:C151').format.columnWidth=35;
main.getRange('D1:D151').format.columnWidth=21;main.getRange('E1:E151').format.columnWidth=43;
main.getRange('D2:E151').format.fill='#FFF2CC';main.getRange('D2:D151').dataValidation={rule:{type:'list',values:['ACCEPT','REJECT','UNSURE']}};
compare.getRange('B1:D151').format.columnWidth=85;compare.getRange(`E1:${col(4+chunks)}151`).format.columnWidth=70;
const instructions=[['Duyệt patch normalization v3.1','Hướng dẫn'],
 ['Chỉ điền D và E trong Review','Giữ nguyên ID, text và nhóm thay đổi.'],
 ['ACCEPT','Phép chuẩn hóa giữ đúng nội dung, thái độ và giọng điệu; text đọc tự nhiên hơn.'],
 ['REJECT','Có từ/đoạn bị đổi sai nghĩa, sai tên/identifier, mất phủ định hoặc biểu cảm. Ghi rõ đoạn lỗi.'],
 ['UNSURE','Không đủ bằng chứng xác nhận; không ép chấp nhận.'],
 ['Raw I3 Normalized','Đối chiếu raw, clean I.3, bản normalized và đầy đủ events theo cùng ID.'],
 ['Không gán sentiment/domain ở đây','Đây là kiểm tra phép biến đổi, không sửa POS/NEG/NEU hay quyết định domain.'],
 ['Dòng không đổi là đối chứng','Mẫu có 10 dòng không đổi; vẫn kiểm tra nội dung được giữ đủ.'],
 ['Text dài vẫn giữ đầy đủ','Chọn ô B rồi Ctrl+Shift+U mở thanh công thức hoặc F2 để đọc toàn bộ.'],
 ['Chưa đổi text_annotation','Bản mới vẫn chờ duyệt riêng; quyết định cũ không tự chuyển sang version mới.']];
guide.getRange('A1:B10').values=instructions;guide.getRange('A1:B10').format={font:{name:'Arial',size:12},wrapText:true,verticalAlignment:'top',rowHeight:60};
guide.getRange('A1:A10').format.columnWidth=43;guide.getRange('B1:B10').format.columnWidth=105;
guide.getRange('A1:B1').format={fill:'#234B65',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
book.recalculate();
for(const [name,range,file] of [['Review','A1:E4','review'],['Raw I3 Normalized','A1:E2','comparison'],['Instructions','A1:B10','instructions']]){
 const png=await book.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(path.join(output,file+'.png'),new Uint8Array(await png.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(output,'final_normalization_review_150.xlsx'));
await fs.writeFile(path.join(output,'manifest.local.json'),JSON.stringify({rows:150,input_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),status:'PENDING_HUMAN_NORMALIZATION_APPROVAL'}));
console.log('Created 150 normalization review rows; human fields blank.');
