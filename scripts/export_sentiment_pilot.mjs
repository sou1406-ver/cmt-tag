// Run with the bundled @oai/artifact-tool runtime; output corpus stays local.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const directory = path.resolve(process.argv[2] || 'outputs/sentiment_pilot_v3_1');
const rows=JSON.parse(await fs.readFile(path.join(directory,'workbook_input.local.json'),'utf8'));
const manifest=JSON.parse(await fs.readFile(path.join(directory,'sampling_manifest.json'),'utf8'));
const hash=text=>createHash('sha256').update(text).digest('hex');
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
    `PILOT — NGƯỜI GÁN ${annotator} — DRAFT, CHƯA ĐỐI CHIẾU V3 GỐC`,
    'Chỉ đọc text_clean của chính bình luận. Không đọc bài viết/comment cha; không xem nhãn của người còn lại.',
    'Cột C: POS / NEG / NEU / REVIEW / EXCLUDE. Nhãn để trống; không có dự đoán hoặc gợi ý.',
    'Cột D: note bắt buộc nếu REVIEW. Viết ngắn: thiếu ngữ cảnh / không hiểu tiếng lóng / hỗn hợp chưa rõ chiều.',
    'Cột F: báo lỗi cleaning nếu có. Không sửa ID, text_clean hoặc annotator_id. Không cần confidence.',
    'Đồng tình thuần túy → NEU; không hiểu câu → REVIEW, không đoán ngữ cảnh. Cảm xúc có thể hướng đến đối tượng bất kỳ.',
    'Nguồn: run Facebook fb_54e6c18b6c514f9ab822354611ab3316; coordinator và seed nằm trong sampling_manifest.json local.',
    'Bổ sung đề xuất: docs/guidelines/SENTIMENT_GUIDELINE_V3_1_PROPOSED.md. Cần đối chiếu V3 trước khi bắt đầu gán.',
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
