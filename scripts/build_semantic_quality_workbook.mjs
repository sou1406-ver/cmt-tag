// Author using an isolated copy with bundled @oai/artifact-tool only.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2),bytes=await fs.readFile(input),contract=JSON.parse(bytes.toString('utf8')),rows=contract.rows;
if(rows.length!==200||new Set(rows.map(r=>r.record_id)).size!==200)throw Error('Require 200 unique semantic-review IDs');
await fs.mkdir(output,{recursive:false});
const book=Workbook.create(),main=book.worksheets.add('Review'),evidence=book.worksheets.add('Raw & Evidence'),guide=book.worksheets.add('Instructions');
const literal=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const mainValues=[['id','text_annotation','proposed_domain_status','proposed_quality_reason','human_domain_decision','human_note'],
 ...rows.map(r=>[r.record_id,r.text_annotation,r.proposed_domain_status,r.proposed_quality_reason,'',''].map(literal))];
const rawValues=[['id','text_raw','text_clean','source_view','evidence'],...rows.map(r=>[r.record_id,r.text_raw,r.text_clean,r.source_view,r.evidence].map(literal))];
if([...mainValues,...rawValues].some(r=>r.some(v=>v.length>32767)))throw Error('Excel cell limit exceeded: no silent truncation');
main.getRange('A1:F201').values=mainValues;evidence.getRange('A1:E201').values=rawValues;
for(const [sheet,last] of [[main,'F'],[evidence,'E']]){
 sheet.getRange(`A1:${last}201`).setNumberFormat('@');
 sheet.getRange(`A1:${last}201`).format={font:{name:'Arial',size:11,color:'#213B50'},wrapText:true,verticalAlignment:'top'};
 sheet.getRange(`A1:${last}1`).format={fill:'#1F4D60',font:{name:'Arial',bold:true,color:'#FFFFFF'},rowHeight:44};
 sheet.getRange('A1:A201').format.columnWidth=24;sheet.freezePanes.freezeRows(1);
 sheet.tables.add(`A1:${last}201`,true,sheet===main?'SemanticQualityReview':'SemanticQualityEvidence');
 rows.forEach((r,i)=>sheet.getRange(`A${i+2}:${last}${i+2}`).format.rowHeight=Math.min(260,Math.max(70,18*(Math.ceil(r.text_annotation.length/100)+1))));
}
main.getRange('B1:B201').format.columnWidth=105;main.getRange('C1:C201').format.columnWidth=25;
main.getRange('D1:D201').format.columnWidth=36;main.getRange('E1:E201').format.columnWidth=26;main.getRange('F1:F201').format.columnWidth=43;
main.getRange('E2:F201').format.fill='#FFF2CC';
main.getRange('E2:E201').dataValidation={rule:{type:'list',values:['IN_DOMAIN','OFF_TOPIC','CONTEXT_REQUIRED','UNSURE']}};
evidence.getRange('B1:C201').format.columnWidth=85;evidence.getRange('D1:D201').format.columnWidth=40;evidence.getRange('E1:E201').format.columnWidth=70;
const instructions=[['Duyệt domain và spam','Hướng dẫn'],
 ['Chỉ điền E và F trong Review','Không sửa ID, text hoặc đề xuất; đề xuất của hệ thống CHƯA được kiểm định.'],
 ['IN_DOMAIN','Có nội dung về phim/nhân vật/kịch bản/diễn xuất/kỹ thuật hoặc hỏi thông tin phim; không cần khen/chê.'],
 ['OFF_TOPIC','Có bằng chứng rõ nội dung nằm ngoài phim: chuyện cá nhân, giá đồ ăn hoặc quảng cáo không bàn về phim.'],
 ['CONTEXT_REQUIRED','Cần parent/post thật để biết tác giả đang nói về phim hay việc khác; không tự đoán.'],
 ['UNSURE','Đã đọc nhưng không đủ căn cứ kết luận domain.'],
 ['OFF_TOPIC không phải NEU','NEU là sentiment trung tính trong miền phim. Không điền POS/NEG/NEU ở đây và không sửa nhãn sentiment cũ.'],
 ['Spam tách khỏi domain','Nếu xác nhận spam, bắt đầu ghi chú bằng [SPAM]; nếu đã kiểm tra và không spam dùng [NOT_SPAM]; chưa rõ dùng [SPAM_UNSURE]. Không suy spam chỉ từ OFF_TOPIC.'],
 ['Review dài, trích dẫn và emoji','Không loại vì dài hoặc 😂😂😂. Lặp trích dẫn hợp lệ vẫn có thể IN_DOMAIN; đoạn copy hàng chục lần cần ghi chú nghi spam.'],
 ['Thiếu ngữ cảnh không phải EXCLUDE','Dùng CONTEXT_REQUIRED; chưa có parent không lấy thái độ bài đăng áp cho bình luận.'],
 ['Một bản text trên sheet chính','Raw & Evidence dùng để tra khi cần. Text dài giữ đầy đủ: chọn B rồi Ctrl+Shift+U hoặc F2.'],
 ['Mẫu kiểm tra có chủ đích','Gồm random KEEP và REVIEW theo tầng; chưa đại diện phân phối corpus. Pilot AI chưa được phát hành.']];
guide.getRange('A1:B12').values=instructions;guide.getRange('A1:B12').format={font:{name:'Arial',size:12},wrapText:true,verticalAlignment:'top',rowHeight:62};
guide.getRange('A1:A12').format.columnWidth=42;guide.getRange('B1:B12').format.columnWidth=105;
guide.getRange('A1:B1').format={fill:'#1F4D60',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
book.recalculate();
for(const [name,range,file] of [['Review','A1:F4','review'],['Raw & Evidence','A1:E2','evidence'],['Instructions','A1:B12','instructions']]){
 const png=await book.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(path.join(output,file+'.png'),new Uint8Array(await png.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(output,'semantic_quality_review_200.xlsx'));
await fs.writeFile(path.join(output,'manifest.local.json'),JSON.stringify({rows:200,input_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),source_manifest_sha256:contract.source_manifest_sha256,status:'PENDING_HUMAN_REVIEW'}));
console.log('Created 200-row semantic quality workbook; human decisions and notes blank.');
