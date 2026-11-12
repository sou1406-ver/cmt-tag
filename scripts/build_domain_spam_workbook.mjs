// Run an isolated copy with the bundled @oai/artifact-tool dependency.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2),bytes=await fs.readFile(input),c=JSON.parse(bytes.toString('utf8')),rows=c.rows;
const expected=c.kind==='holdout'?40:c.kind==='canonical'?c.review_count:200;
if(rows.length!==expected||new Set(rows.map(r=>r.record_id)).size!==expected)throw Error('Wrong fixed review IDs');
await fs.mkdir(output,{recursive:false});
const book=Workbook.create(),main=book.worksheets.add('Review'),source=book.worksheets.add('Source'),guide=book.worksheets.add('Instructions');
const literal=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const values=[['id','text_view','human_domain_decision','human_spam_decision','human_note'],...rows.map(r=>[r.record_id,r.text_view,r.human_domain_decision,r.human_spam_decision,r.human_note].map(literal))];
const evidence=[['id','text_raw','text_previous','source_view','text_sha256'],...rows.map(r=>[r.record_id,r.text_raw,r.text_previous,r.source_view,r.text_sha256].map(literal))];
if([...values,...evidence].some(r=>r.some(v=>v.length>32767)))throw Error('Text too long for Excel; no truncation');
const last=rows.length+1;main.getRange(`A1:E${last}`).values=values;source.getRange(`A1:E${last}`).values=evidence;
for(const [sheet,name] of [[main,'QualityReview'],[source,'QualitySource']]){
 sheet.showGridLines=false;sheet.getRange(`A1:E${last}`).setNumberFormat('@');
 sheet.getRange(`A1:E${last}`).format={font:{name:'Arial',size:11,color:'#24364B'},wrapText:true,verticalAlignment:'top'};
 sheet.getRange('A1:E1').format={fill:'#234B65',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:42};
 sheet.getRange(`A1:A${last}`).format.columnWidth=24;sheet.freezePanes.freezeRows(1);sheet.tables.add(`A1:E${last}`,true,name);
 rows.forEach((r,i)=>sheet.getRange(`A${i+2}:E${i+2}`).format.rowHeight=Math.min(260,Math.max(65,18*(Math.ceil(r.text_view.length/100)+1))));
}
main.getRange(`B1:B${last}`).format.columnWidth=105;main.getRange(`C1:D${last}`).format.columnWidth=25;main.getRange(`E1:E${last}`).format.columnWidth=43;
main.getRange(`C2:E${last}`).format.fill='#FFF2CC';
main.getRange(`C2:C${last}`).dataValidation={rule:{type:'list',values:['IN_DOMAIN','OFF_TOPIC','CONTEXT_REQUIRED','UNSURE']}};
main.getRange(`D2:D${last}`).dataValidation={rule:{type:'list',values:['SPAM','NOT_SPAM','SPAM_UNSURE']}};
source.getRange(`B1:C${last}`).format.columnWidth=85;source.getRange(`D1:E${last}`).format.columnWidth=48;
const instructions=[['Domain và spam v3.1','Hướng dẫn'],
 ['Chỉ điền C, D, E ở Review','Hai quyết định riêng biệt. Không sửa ID hoặc văn bản. Không điền POS/NEG/NEU.'],
 ['IN_DOMAIN','Đánh giá hoặc hỏi/cung cấp thông tin về phim, nhân vật, diễn xuất, kịch bản, hình ảnh, âm thanh, trải nghiệm do phim mang lại.'],
 ['OFF_TOPIC','Nội dung rõ ràng ngoài phim. Không suy OFF_TOPIC chỉ vì thiếu từ phim; không coi OFF_TOPIC là NEU.'],
 ['CONTEXT_REQUIRED / UNSURE','Cần parent/post thật hoặc không đủ căn cứ. Không đoán context. Source chỉ là metadata có sẵn, chưa chứng minh domain.'],
 ['SPAM / NOT_SPAM / SPAM_UNSURE','Spam độc lập domain. Quảng cáo hoặc lặp copy-paste phải có bằng chứng. Chưa rõ chọn SPAM_UNSURE.'],
 ['Đừng loại vì dài hoặc biểu cảm','Review dài, trích dẫn, emoji lặp và quan điểm tiêu cực không tự là spam. Không dùng tên, tôn giáo, ngôn ngữ làm tiêu chí.'],
 ['Đọc toàn bộ comment','F2 hoặc mở thanh công thức bằng Ctrl+Shift+U. File giữ đủ text; chiều cao dòng chỉ giới hạn hiển thị.'],
 [c.kind==='holdout'?'Quality holdout 40 ID cố định':c.kind==='canonical'?'Canonical raw rebuild, quality sample':'Cùng 200 ID semantic I.4',c.kind==='holdout'?'Không dùng để phát triển rule. Đây không phải independent sentiment test.':c.kind==='canonical'?'Mẫu theo nguồn/vùng/change; không phải test. Source chứa provenance và text trước rebuild để đối chiếu. Không có block nguồn đã loại.':'Bản làm việc v3.1; chỉ giữ quyết định cũ khi text giống hệt. File I.4 cũ được bảo toàn.'],
 ['Chưa phát hành corpus/pilot','Quyết định được import vào ledger. Không tự duyệt toàn corpus hoặc chuyển annotation pointer.']];
guide.getRange('A1:B10').values=instructions;guide.getRange('A1:B10').format={font:{name:'Arial',size:12},wrapText:true,verticalAlignment:'top',rowHeight:65};
guide.getRange('A1:A10').format.columnWidth=43;guide.getRange('B1:B10').format.columnWidth=105;guide.showGridLines=false;
guide.getRange('A1:B1').format={fill:'#234B65',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
book.recalculate();
const scan=await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:5},maxChars:500});
await fs.writeFile(path.join(output,'formula_scan.local.ndjson'),scan.ndjson);
for(const [sheet,range,file] of [['Review','A1:E4','review'],['Source','A1:E2','source'],['Instructions','A1:B10','instructions']]){
 const png=await book.render({sheetName:sheet,range,scale:1,format:'png'});await fs.writeFile(path.join(output,file+'.png'),new Uint8Array(await png.arrayBuffer()));
}
const filename=c.kind==='holdout'?'quality_holdout_40.xlsx':c.kind==='canonical'?'canonical_quality_review.xlsx':'semantic_quality_review_v31_200.xlsx';
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(output,filename));
await fs.writeFile(path.join(output,'manifest.local.json'),JSON.stringify({rows:rows.length,kind:c.kind,input_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),status:c.status}));
console.log(`Created ${rows.length} fixed-ID ${c.kind} review rows.`);
