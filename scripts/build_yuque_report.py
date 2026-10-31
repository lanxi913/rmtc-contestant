# -*- coding: utf-8 -*-
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'TECHNICAL_REPORT.md'
IMAGE=ROOT/'docs'/'precheck-referee-2026-10-31.png'
OUTPUT=ROOT/'语雀技术报告-可发布草稿.docx'

def set_font(run, name='宋体', size=10.5, bold=None, color=None):
    run.font.name=name
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),name)
    run.font.size=Pt(size)
    if bold is not None: run.bold=bold
    if color: run.font.color.rgb=RGBColor(*color)

def add_text(doc, text, style=None):
    p=doc.add_paragraph(style=style) if style else doc.add_paragraph()
    p.paragraph_format.space_after=Pt(5)
    for part in re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', text):
        if not part: continue
        if part.startswith('`'): set_font(p.add_run(part[1:-1]),'Consolas',9)
        elif part.startswith('**'): set_font(p.add_run(part[2:-2]),bold=True)
        else: set_font(p.add_run(part))
    return p

def replace(p,text):
    p.text=text
    for r in p.runs: set_font(r)

lines=SOURCE.read_text(encoding='utf-8').splitlines()
doc=Document(); sec=doc.sections[0]
sec.top_margin=Inches(.72);sec.bottom_margin=Inches(.72);sec.left_margin=Inches(.82);sec.right_margin=Inches(.82)
for name in ('Normal','Title','Heading 1','Heading 2','Heading 3'):
    st=doc.styles[name];st.font.name='宋体';st._element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')
    if name=='Normal': st.font.size=Pt(10.5)
    if name=='Heading 1': st.font.color.rgb=RGBColor(31,78,95)
    if name=='Heading 2': st.font.color.rgb=RGBColor(42,104,115)
inserted=False;i=0
while i<len(lines):
    s=lines[i].strip()
    if not s or s=='---': i+=1;continue
    if s.startswith('```'):
        i+=1; code=[]
        while i<len(lines) and not lines[i].strip().startswith('```'): code.append(lines[i]);i+=1
        p=doc.add_paragraph();p.paragraph_format.left_indent=Inches(.18);set_font(p.add_run('\n'.join(code)),'Consolas',8.5)
        i+=1;continue
    if s.startswith('!['):
        p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(IMAGE),width=Inches(6.3));inserted=True
        cap=doc.add_paragraph('图 1：2026-10-31 自研参赛程序接入公开 Stage 1 测试端。诊断区显示接收 Tick、动作 Tick、执行 Tick 与 last_action；本图为公开练习证据，不代表正式成绩或现场检录。')
        cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
        for r in cap.runs:set_font(r,size=9,color=(80,90,100))
        i+=1;continue
    if s.startswith('|'):
        raw=[]
        while i<len(lines) and lines[i].strip().startswith('|'):raw.append(lines[i].strip());i+=1
        rows=[]
        for row in raw:
            cells=[x.strip() for x in row.strip('|').split('|')]
            if all(re.fullmatch(r':?-{3,}:?',x or '-') for x in cells):continue
            rows.append(cells)
        if rows:
            table=doc.add_table(rows=0,cols=max(map(len,rows)));table.style='Table Grid'
            for ri,row in enumerate(rows):
                cells=table.add_row().cells
                for ci,cell in enumerate(cells):
                    cell.text='';set_font(cell.paragraphs[0].add_run(row[ci] if ci<len(row) else ''),size=9,bold=(ri==0))
                    if ri==0:
                        sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'DCE9EC');cell._tc.get_or_add_tcPr().append(sh)
        continue
    if s.startswith('# '):
        p=doc.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;set_font(p.add_run(s[2:]),'黑体',20,True,(31,78,95))
    elif s.startswith('## '):doc.add_heading(s[3:],level=1)
    elif s.startswith('### '):doc.add_heading(s[4:],level=2)
    elif s.startswith('> '):add_text(doc,s[2:])
    elif re.match(r'^\d+\. ',s):add_text(doc,re.sub(r'^\d+\. ','',s),style='List Number')
    elif s.startswith('- [ ] '):add_text(doc,'□ '+s[6:],style='List Bullet')
    elif s.startswith('- [x] '):add_text(doc,'☑ '+s[6:],style='List Bullet')
    elif s.startswith('- '):add_text(doc,s[2:],style='List Bullet')
    elif s.startswith('C:\\Users\\lanxi'):add_text(doc,'原始练习材料：项目外部归档 rmtc_materials/ 中对应 JSON 与日志文件。')
    else:add_text(doc,s)
    i+=1

for p in doc.paragraphs:
    text=p.text
    if '本报告依据' in text and '官方规则 v1.2' in text:
        replace(p,text+' 本次另以 2026-10-31 提供的规则 v1.1、通信协议 v1.1 与测试端教程 v1.1 作交叉核对；v1.1 标注为初版，不能据此覆盖 v1.2 或 2026-10-30 手册，最终以主办方当前有效版本与公告为准。')
    elif text.startswith('本节不估算工时'):
        replace(p,text+' 2026-10-30 的手册核对和 2026-10-31 的公开测试截图采集为可核验材料整理阶段，不补造开发日期。')
    elif text.startswith('以上文档名用于整理项目材料'):
        replace(p,'以上文档名用于整理项目材料。原始练习 JSON 与日志保存在项目外部归档，不依赖本机绝对路径。归档只含必要证据，并在 EVIDENCE_MANIFEST.md 标注来源、SHA-256、证明范围和限制。')
    elif text.startswith('因此项目文档和归档包'):
        replace(p,'项目文档和归档包不能依赖项目外部材料路径。归档时应筛选必要证据复制到归档内，并标注其来源、SHA-256、证明范围和限制；不应整体搬运官方裁判、令牌、缓存、观赛数据或无关文件。')
    elif '首帧' in text and 'mission_text' in text:
        replace(p,text+' `mission_text` 仅提供任务上下文，不能作为随机事件或据此虚构事件事实；随机事件仍以公开 `event_text` 为依据。')

for section in doc.sections:
    footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run('RMTC 图灵对决赛技术报告｜公开测试证据版｜2026-10-31'),size=8,color=(100,100,100))
doc.core_properties.title='RMTC 图灵对决赛技术报告'
doc.core_properties.subject='参赛程序技术报告与公开测试端前置检录证据'
doc.core_properties.author='王烨'
doc.save(OUTPUT)
check=Document(OUTPUT)
all_text='\n'.join(p.text for p in check.paragraphs)+'\n'+'\n'.join(c.text for t in check.tables for row in t.rows for c in row.cells)
assert inserted and len(check.inline_shapes)==1
assert 'C:\\Users\\lanxi' not in all_text
assert '没有可确认合格的运行截图' not in all_text
assert any('mission_text' in p.text and '随机事件' in p.text for p in check.paragraphs)
print(f'file={OUTPUT}\nparagraphs={len(check.paragraphs)} tables={len(check.tables)} images={len(check.inline_shapes)} bytes={OUTPUT.stat().st_size}')
