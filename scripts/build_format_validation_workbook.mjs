// Run isolated copy with the bundled @oai/artifact-tool runtime.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2),bytes=await fs.readFile(input),rows=JSON.parse(bytes.toString('utf8'));
if(rows.length!==200||new Set(rows.map(r=>r.record_id)).size!==200)throw Error('Require 200 unique validation rows');
await fs.mkdir(output,{recursive:false});
const book=Workbook.create(),main=book.worksheets.add('Validation'),compare=book.worksheets.add('Raw I2 I3'),guide=book.worksheets.add('Instructions');
const literal=s=>String(s??'').startsWith('=')?"'"+s:String(s??'');
const events=rows.map(r=>JSON.stringify({transform_events:r.transform_events,format_evidence:r.format_evidence}));
const chunks=Math.max(1,...events.map(s=>Math.ceil(s.length/30000)));
const col=n=>{let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s};
const evidenceHeaders=Array.from({length:chunks},(_,i)=>'transformation_evidence_'+(i+1));
const values=[['id','text_clean_i3','change_summary','format_decision','human_note'],...rows.map(r=>[
 r.record_id,r.text_clean_i3,`${r.transform_events.length} biến đổi; ${r.unresolved_tokens.length} token chưa rõ; ${r.format_status}`,'',''].map(literal))];
const rawValues=[['id','text_raw','text_clean_i2','text_clean_i3',...evidenceHeaders],...rows.map((r,i)=>[
 r.record_id,r.text_raw,r.text_clean_i2,r.text_clean_i3,...Array.from({length:chunks},(_,j)=>events[i].slice(j*30000,(j+1)*30000))].map(literal))];
if([...values,...rawValues].some(r=>r.some(v=>v.length>32767)))throw Error('Cell too long: never truncate text');
main.getRange('A1:E201').values=values;compare.getRange(`A1:${col(4+chunks)}201`).values=rawValues;
for(const [sheet,last] of [[main,'E'],[compare,col(4+chunks)]]){
 sheet.getRange(`A1:${last}201`).setNumberFormat('@');
 sheet.getRange(`A1:${last}201`).format={font:{name:'Arial',size:11,color:'#24364A'},wrapText:true,verticalAlignment:'top'};
 sheet.getRange(`A1:${last}1`).format={fill:'#214768',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:40};
 sheet.getRange('A1:A201').format.columnWidth=24;sheet.freezePanes.freezeRows(1);
 sheet.tables.add(`A1:${last}201`,true,sheet===main?'FormatValidation':'FormatComparisons');
 rows.forEach((r,i)=>sheet.getRange(`A${i+2}:${last}${i+2}`).format.rowHeight=Math.min(260,Math.max(70,18*(Math.ceil(r.text_clean_i3.length/100)+1))));
}
main.getRange('B1:B201').format.columnWidth=105;main.getRange('C1:C201').format.columnWidth=36;
main.getRange('D1:D201').format.columnWidth=21;main.getRange('E1:E201').format.columnWidth=40;
main.getRange('D2:E201').format.fill='#FFF2CC';
main.getRange('D2:D201').dataValidation={rule:{type:'list',values:['ACCEPT','REJECT','UNSURE']}};
compare.getRange('B1:D201').format.columnWidth=85;
compare.getRange(`E1:${col(4+chunks)}201`).format.columnWidth=70;
const instructions=[['Kiểm định phục hồi format','Hướng dẫn'],
 ['Chỉ điền D và E trong Validation','Giữ nguyên ID, text và tóm tắt thay đổi.'],
 ['ACCEPT','Bản I.3 giữ đúng nội dung và format đọc được.'],
 ['REJECT','Phép chuyển làm sai hoặc mất nội dung; ghi token/đoạn cần sửa vào ghi chú.'],
 ['UNSURE','Chưa đủ bằng chứng xác nhận chuyển đổi; không đoán.'],
 ['Không gán sentiment/chất lượng miền','Có thể ACCEPT format của câu spam; việc liên quan phim được đánh giá riêng.'],
 ['Raw I2 I3','Đối chiếu nguyên văn, bản I.2, I.3 và bằng chứng theo cùng ID.'],
 ['Văn bản dài vẫn giữ đủ','Chọn ô B rồi Ctrl+Shift+U mở thanh công thức, hoặc F2 để đọc hết.'],
 ['Chưa phát hành pilot','Chỉ tính transformation accuracy sau quyết định thật; chưa gửi AI.']];
guide.getRange('A1:B9').values=instructions;guide.getRange('A1:B9').format={font:{name:'Arial',size:12},wrapText:true,verticalAlignment:'top',rowHeight:56};
guide.getRange('A1:A9').format.columnWidth=42;guide.getRange('B1:B9').format.columnWidth=100;
guide.getRange('A1:B1').format={fill:'#214768',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
book.recalculate();
for(const [name,range,file] of [['Validation','A1:E4','validation'],['Raw I2 I3','A1:E2','comparison'],['Instructions','A1:B9','instructions']]){
 const png=await book.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(output,file+'.png'),new Uint8Array(await png.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(book)).save(path.join(output,'plain_text_validation_200.xlsx'));
await fs.writeFile(path.join(output,'manifest.local.json'),JSON.stringify({rows:200,input_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),status:'PENDING_HUMAN_FORMAT_APPROVAL'}));
console.log('Exported 200 format validation rows; decisions and notes blank.');
