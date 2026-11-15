// Run with the bundled @oai/artifact-tool runtime; output corpus stays local.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const directory = path.resolve(process.argv[2] || 'outputs/sentiment_pilot');
if(process.argv.includes('--adjudication')) {
  await exportAdjudication(directory);
} else {
const rows=JSON.parse(await fs.readFile(path.join(directory,'workbook_input.local.json'),'utf8'));
const manifest=JSON.parse(await fs.readFile(path.join(directory,'sampling_manifest.json'),'utf8'));
const hash=text=>createHash('sha256').update(text).digest('hex');
if(hash(await fs.readFile(path.join(directory,'sampling_manifest.json')))!==(await fs.readFile(path.join(directory,'sampling_manifest.sha256'),'utf8')).trim())throw Error('Manifest checksum changed');
let guidelinePath=manifest.guideline_file;
try {await fs.access(guidelinePath);} catch(error) {
  if(error.code!=='ENOENT')throw error;
  const expectedDirectory=path.resolve('docs/guidelines');
  if(path.dirname(path.resolve(guidelinePath))!==expectedDirectory || path.basename(guidelinePath)==='SENTIMENT_GUIDELINE.md')throw error;
  guidelinePath=path.join(expectedDirectory,'history',path.basename(guidelinePath));
}
if(hash(await fs.readFile(guidelinePath))!==manifest.guideline_sha256)throw Error('Guideline checksum changed');
const approved=manifest.status==='READY' && manifest.guideline_status==='APPROVED_FOR_PILOT';
if(rows.length!==200 || new Set(rows.map(r=>r.comment_id)).size!==200 || rows.some((r,i)=>r.comment_id!==manifest.selected_rows[i].comment_id || hash(r.text_clean)!==manifest.selected_rows[i].text_sha256)) throw Error('Invalid workbook input ID/text hash');
const names=['A','B'].map(a=>path.join(directory,`pilot_sentiment_annotator_${a}.xlsx`));
for(const name of names) {try {await fs.access(name);throw Error('Refusing to overwrite workbook: '+name);} catch(e) {if(e.code!=='ENOENT')throw e;}}
const literal=v=>v.startsWith('=')?"'"+v:v;
for(const [index,annotator] of ['A','B'].entries()) {
  const wb=Workbook.create(); const s=wb.worksheets.add('Gán nhãn'); const guide=wb.worksheets.add('Hướng dẫn');
  s.showGridLines=false;
  const fields=['comment_id','text_clean','sentiment_label','note','annotator_id','cleaning_issue'];
  s.getRange('A1:F201').format.font={name:'Arial',size:11};
  s.getRange('A1:F201').format.wrapText=true;s.getRange('A1:F201').format.verticalAlignment='top';
  s.getRange('A1:F201').values=[fields,...rows.map(r=>[r.comment_id,literal(r.text_clean),'','',annotator,''])];
  s.getRange('A1:F1').format={fill:'#17324D',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:32};
  s.getRange('A2:A201').format.numberFormat='@';
  s.getRange('C2:D201').format.fill='#FFF2CC';s.getRange('F2:F201').format.fill='#FFF2CC';
  s.getRange('C2:C201').dataValidation={rule:{type:'list',values:['POS','NEG','NEU','REVIEW','EXCLUDE']}};
  for(const [col,width] of [['A',27],['B',105],['C',22],['D',35],['E',14],['F',28]])s.getRange(`${col}:${col}`).format.columnWidth=width;
  const longParts=[];
  for(const [i,r] of rows.entries()) {
    const lines=r.text_clean.split('\n').reduce((n,t)=>n+Math.max(1,Math.ceil([...t].length/90)),0);
    s.getRange(`A${i+2}:F${i+2}`).format.rowHeight=Math.min(390,Math.max(70,lines*17+18));
    s.getRange(`A${i+2}:B${i+2}`).format.fill=i%2?'#EDF3F8':'#FFFFFF';
    if(lines>21) {
      let chunk='',breaks=0,part=1;
      for(const ch of r.text_clean) {chunk+=ch;if(ch==='\n')breaks++;if([...chunk].length>=550||breaks>=10){longParts.push([r.comment_id,part++,literal(chunk)]);chunk='';breaks=0;}}
      if(chunk)longParts.push([r.comment_id,part,literal(chunk)]);
    }
  }
  s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(2);s.tables.add('A1:F201',true,'SentimentInput');
  const instructions=[
    `PILOT — NGƯỜI GÁN ${annotator} — ${approved?'READY / APPROVED_FOR_PILOT':'DRAFT — CHỜ XÁC MINH GUIDELINE'}`,
    'Chỉ đọc text_clean của chính bình luận. Không đọc bài viết/comment cha; không xem nhãn của người còn lại.',
    'Cột C: POS / NEG / NEU / REVIEW / EXCLUDE. Nhãn để trống; không có dự đoán hoặc gợi ý.',
    'Cột D: note bắt buộc nếu REVIEW. Viết ngắn: thiếu ngữ cảnh / không hiểu tiếng lóng / hỗn hợp chưa rõ chiều.',
    'Cột F: báo lỗi cleaning nếu có. Không sửa ID, text_clean hoặc annotator_id. Không cần confidence.',
    'Đồng tình thuần túy → NEU; không hiểu câu → REVIEW, không đoán ngữ cảnh. Cảm xúc có thể hướng đến đối tượng bất kỳ.',
    'Nguồn: run Facebook fb_54e6c18b6c514f9ab822354611ab3316; coordinator và seed nằm trong sampling_manifest.json local.',
    approved?`Guideline chính thức: ${manifest.guideline_file}; SHA256 ${manifest.guideline_sha256}`:`Guideline chưa duyệt: ${manifest.guideline_file}. Cần xác minh bản chính thức trước khi giao gán.`,
    'Câu dài: xem thêm tab Đọc dài nếu có, gán nhãn một lần ở Gán nhãn. Giữ nguyên toàn bộ text.',
  ];
  guide.showGridLines=false;guide.getRange('A:A').format.columnWidth=145;
  guide.getRange('A1:A9').values=instructions.map(t=>[t]);guide.getRange('A1:A9').format={font:{name:'Arial',size:12},wrapText:true,rowHeight:50,verticalAlignment:'top'};
  guide.getRange('A1').format.fill='#FFF2CC';guide.getRange('A1').format.font.bold=true;
  if(longParts.length) {
    const l=wb.worksheets.add('Đọc dài');l.showGridLines=false;
    l.getRange(`A1:C${longParts.length+1}`).values=[['comment_id','Phần','text_clean — chỉ đọc, gán ở tab Gán nhãn'],...longParts];
    l.getRange(`A1:C${longParts.length+1}`).format={font:{name:'Arial',size:11},wrapText:true,verticalAlignment:'top'};
    l.getRange('A:A').format.columnWidth=28;l.getRange('A:A').format.numberFormat='@';l.getRange('B:B').format.columnWidth=7;l.getRange('C:C').format.columnWidth=110;
    l.getRange('A1:C1').format={fill:'#17324D',font:{color:'#FFFFFF',bold:true},rowHeight:30};
    for(const [i,r] of longParts.entries()) {const lines=String(r[2]).split('\n').reduce((n,t)=>n+Math.max(1,Math.ceil([...t].length/95)),0);l.getRange(`A${i+2}:C${i+2}`).format.rowHeight=Math.min(390,Math.max(80,lines*18+20));}
    l.freezePanes.freezeRows(1);
  }
  wb.recalculate();
  await (await SpreadsheetFile.exportXlsx(wb)).save(names[index]);
  // Inspect structure, then render both independent workbooks for visual QA.
  await wb.inspect({kind:'sheet',include:'id,name',maxChars:500});
  const blob=await wb.render({sheetName:s.name,range:'A1:E5',scale:1,format:'png'});
  await fs.writeFile(path.join(directory,`preview_${annotator}.png`),new Uint8Array(await blob.arrayBuffer()));
}
console.log(JSON.stringify({workbooks:2,rows:rows.length,labelsFilled:0}));
}

async function exportAdjudication(directory) {
  const hash=v=>createHash('sha256').update(v).digest('hex');
  const receipt=JSON.parse(await fs.readFile(path.join(directory,'receipt.json'),'utf8'));
  const raw=await fs.readFile(path.join(directory,'adjudication_manifest.local.json'));
  if(hash(raw)!==receipt.adjudication_manifest_sha256)throw Error('Adjudication coordinator changed');
  if(hash(await fs.readFile(path.join(directory,'agreement.json')))!==receipt.agreement_sha256)throw Error('Original A/B metrics changed');
  for(const [file,h] of Object.entries(receipt.workbook_sha256))if(hash(await fs.readFile(file))!==h)throw Error('Original A/B workbook changed');
  const manifest=JSON.parse(raw);const entries=manifest.rows;
  if(!entries.length)throw Error('No rows selected for adjudication');
  if(new Set(entries.map(r=>r.data.comment_id)).size!==entries.length || entries.some(r=>r.data.final_label||r.data.adjudication_note))throw Error('Expected unique IDs and blank final decisions');
  const file=path.join(directory,'adjudication.xlsx');
  try{await fs.access(file);throw Error('Refusing to overwrite adjudication workbook');}catch(e){if(e.code!=='ENOENT')throw e;}
  const fields=['comment_id','text_clean','label_A','label_B','note_A','note_B','final_label','adjudication_note'];
  const literal=v=>v.startsWith('=')?"'"+v:v;
  const wb=Workbook.create();const s=wb.worksheets.add('Đối soát');const guide=wb.worksheets.add('Hướng dẫn');const end=entries.length+1;
  s.showGridLines=false;
  s.getRange(`A1:H${end}`).values=[fields,...entries.map(r=>fields.map(k=>literal(r.data[k])))];
  s.getRange(`A1:H${end}`).format={font:{name:'Arial',size:11},wrapText:true,verticalAlignment:'top'};
  s.getRange('A1:H1').format={fill:'#17324D',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:34};
  s.getRange('A:A').format.numberFormat='@';
  for(const [col,width] of [['A',27],['B',90],['C',12],['D',12],['E',24],['F',24],['G',16],['H',32]])s.getRange(`${col}:${col}`).format.columnWidth=width;
  const longParts=[];
  entries.forEach((r,i)=>{
    const row=i+2;const lines=r.data.text_clean.split('\n').reduce((n,t)=>n+Math.max(1,Math.ceil([...t].length/78)),0);
    s.getRange(`A${row}:H${row}`).format.fill=r.review_type==='DISAGREEMENT'?'#FCE4D6':'#E8F2FB';
    s.getRange(`G${row}:H${row}`).format.fill='#FFF2CC';
    if(r.review_type==='DISAGREEMENT')s.getRange(`C${row}:D${row}`).format.font.bold=true;
    s.getRange(`A${row}:H${row}`).format.rowHeight=Math.min(390,Math.max(70,lines*17+20));
    if(lines>21){let chunk='',breaks=0,part=1;for(const ch of r.data.text_clean){chunk+=ch;if(ch==='\n')breaks++;if([...chunk].length>=500||breaks>=10){longParts.push([r.data.comment_id,part++,literal(chunk)]);chunk='';breaks=0;}}if(chunk)longParts.push([r.data.comment_id,part,literal(chunk)]);}
  });
  s.getRange(`G2:G${end}`).dataValidation={rule:{type:'list',values:['POS','NEG','NEU','REVIEW','EXCLUDE']}};
  s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(2);s.tables.add(`A1:H${end}`,true,'Adjudication');
  guide.showGridLines=false;guide.getRange('A:A').format.columnWidth=140;
  const notes=[
    'NGƯỜI DÙNG LÀ ADJUDICATOR — A/B VẪN LÀ HAI NGƯỜI GÁN ĐỘC LẬP',
    `Cam = toàn bộ ${manifest.disagreements} câu bất đồng; xanh = ${manifest.agreement_audit_selected}/${manifest.agreement_available} câu đồng thuận được chọn ngẫu nhiên, seed ${manifest.seed}.`,
    'Chỉ điền G/H màu vàng. final_label để trống ở mọi dòng; m tự quyết theo guideline đã pin. REVIEW cần note ngắn.',
    'Được xem label_A, label_B và note_A/note_B. Chỉ dùng text_clean, không tra parent/post để suy cảm xúc.',
    'Không sửa ID, text hoặc nhãn/ghi chú gốc của A/B. Cần đọc câu dài thì xem thêm Đọc dài nếu có.',
    'Kappa nằm ở agreement.json, đã tính trên toàn bộ nhãn gốc A/B TRƯỚC đối soát. Không tính lại từ final_label.',
    'Import xuất đủ 200 quyết định: đồng thuận ngoài mẫu kiểm tra → AB_AGREE; câu đã chọn kiểm tra còn trống → PENDING_REVIEW. Không tự tạo Gold.'
  ];
  guide.getRange(`A1:A${notes.length}`).values=notes.map(v=>[v]);guide.getRange(`A1:A${notes.length}`).format={font:{name:'Arial',size:12},wrapText:true,rowHeight:55,verticalAlignment:'top'};
  if(longParts.length){const l=wb.worksheets.add('Đọc dài');l.showGridLines=false;l.getRange(`A1:C${longParts.length+1}`).values=[['comment_id','Phần','text_clean — chỉ để đọc'],...longParts];l.getRange(`A1:C${longParts.length+1}`).format={font:{name:'Arial',size:11},wrapText:true,verticalAlignment:'top'};l.getRange('A:A').format.columnWidth=28;l.getRange('A:A').format.numberFormat='@';l.getRange('B:B').format.columnWidth=7;l.getRange('C:C').format.columnWidth=100;for(const [i,r] of longParts.entries()){const lines=String(r[2]).split('\n').reduce((n,t)=>n+Math.max(1,Math.ceil([...t].length/86)),0);l.getRange(`A${i+2}:C${i+2}`).format.rowHeight=Math.min(390,Math.max(80,lines*18+20));}l.freezePanes.freezeRows(1);}
  wb.recalculate();await(await SpreadsheetFile.exportXlsx(wb)).save(file);
  const blob=await wb.render({sheetName:s.name,range:`A1:H${Math.min(end,5)}`,scale:1,format:'png'});
  await fs.writeFile(path.join(directory,'adjudication_preview.png'),new Uint8Array(await blob.arrayBuffer()));
  console.log(JSON.stringify({rows:entries.length,disagreements:manifest.disagreements,agreementAudit:manifest.agreement_audit_selected,finalLabelsFilled:0}));
}
