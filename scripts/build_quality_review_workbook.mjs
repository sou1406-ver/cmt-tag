// Run an isolated copy with bundled @oai/artifact-tool dependencies.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2);
const bytes=await fs.readFile(input),rows=JSON.parse(bytes.toString('utf8'));
if(rows.length!==200||new Set(rows.map(r=>r.record_id)).size!==200)throw Error('Require 200 unique IDs');
await fs.mkdir(output,{recursive:false});
const book=Workbook.create();
const review=book.worksheets.add('Review'),raw=book.worksheets.add('Raw & Changes'),instructions=book.worksheets.add('Instructions');
const literal=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const reviewValues=[['id','text_annotation','quality_status_proposed','quality_reasons','human_quality_decision','human_note'],
  ...rows.map(r=>[r.record_id,r.text_annotation,r.quality_status,r.quality_reason_code.join('; '),'',''].map(literal))];
const rawValues=[['id','text_raw','text_clean','transform_events','quality_evidence'],
 ...rows.map(r=>[r.record_id,r.text_raw,r.text_clean,JSON.stringify(r.transform_events),JSON.stringify({domain:r.domain_status,
  reasons:r.quality_reason_code,repetition_ratio:r.repetition_ratio,repeats:r.repeated_block_count,unresolved:r.unresolved_tokens})].map(literal))];
if([...reviewValues,...rawValues].some(row=>row.some(v=>v.length>32767)))throw Error('Excel cell limit exceeded; no silent truncation allowed');
review.getRange('A1:F201').values=reviewValues;
raw.getRange('A1:E201').values=rawValues;
for(const [sheet,last] of [[review,'F'],[raw,'E']]){
 sheet.getRange(`A1:${last}201`).setNumberFormat('@');
 sheet.getRange(`A1:${last}201`).format.font={name:'Arial',size:11,color:'#20324B'};
 sheet.getRange(`A1:${last}201`).format.wrapText=true;
 sheet.getRange(`A1:${last}201`).format.verticalAlignment='top';
 sheet.getRange(`A1:${last}1`).format={fill:'#203B5C',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:42};
 sheet.getRange('A1:A201').format.columnWidth=24;
 sheet.freezePanes.freezeRows(1);
 sheet.tables.add(`A1:${last}201`,true,sheet===review?'QualityReview':'RawChanges');
 rows.forEach((r,i)=>sheet.getRange(`A${i+2}:${last}${i+2}`).format.rowHeight=Math.min(260,Math.max(72,18*(Math.ceil(r.text_annotation.length/105)+1))));
}
review.getRange('B1:B201').format.columnWidth=105;
review.getRange('C1:C201').format.columnWidth=20;
review.getRange('D1:D201').format.columnWidth=31;
review.getRange('E1:E201').format.columnWidth=24;
review.getRange('F1:F201').format.columnWidth=33;
review.getRange('E2:F201').format.fill='#FFF2CC';
review.getRange('E2:E201').dataValidation={rule:{type:'list',values:['KEEP','REVIEW','EXCLUDE']}};
raw.getRange('B1:C201').format.columnWidth=90;
raw.getRange('D1:E201').format.columnWidth=65;
const guide=[['Duyệt chất lượng văn bản','Hướng dẫn'],
 ['Chỉ điền cột E và F trong Review','Không sửa ID, text hoặc các đề xuất.'],
 ['KEEP','Có thể hiểu và gán sentiment về phim; format đã hợp lý.'],
 ['REVIEW','Chưa đủ ngữ cảnh, format chưa rõ, nhiều ý hoặc nghi lặp.'],
 ['EXCLUDE','Rác/spam/ngoài phạm vi có căn cứ rõ. Không suy từ độ dài hoặc thiếu từ phim.'],
 ['Không gán POS/NEG/NEU tại đây','Đây là review chất lượng, chưa phải annotation sentiment.'],
 ['Text dài giữ đầy đủ trong ô','Chọn B, Ctrl+Shift+U mở thanh công thức hoặc F2 để đọc toàn bộ; dòng được giới hạn chiều cao hiển thị.'],
 ['Raw & Changes','Tra raw và biến đổi theo cùng ID khi nghi mất nghĩa.'],
 ['Bản pilot','Chưa duyệt; chưa gửi AI trước khi xác nhận chất lượng.']];
instructions.getRange('A1:B9').values=guide;
instructions.getRange('A1:B9').format={font:{name:'Arial',size:12,color:'#20324B'},wrapText:true,verticalAlignment:'top',rowHeight:58};
instructions.getRange('A1:A9').format.columnWidth=43;instructions.getRange('B1:B9').format.columnWidth=100;
instructions.getRange('A1:B1').format={fill:'#203B5C',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
book.recalculate();
for(const [name,range,file] of [['Review','A1:F4','review'],['Raw & Changes','A1:E3','raw'],['Instructions','A1:B9','instructions']]){
 const img=await book.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(output,file+'.png'),new Uint8Array(await img.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(book);await xlsx.save(path.join(output,'quality_review_200.xlsx'));
await fs.writeFile(path.join(output,'workbook_manifest.local.json'),JSON.stringify({input_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),rows:200,status:'PENDING_HUMAN_QUALITY_APPROVAL'}));
console.log('Created 200-row quality workbook; decision and note columns blank.');
