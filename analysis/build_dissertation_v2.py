"""Build editable English/Chinese dissertation drafts from manuscript Markdown.
Run with the bundled Codex document Python (python-docx + Pillow).
PDFs are faithful DOCX renders produced separately by render_docx.py.
"""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]/'manuscript'/'v2'


def elem(tag, **attrs):
    e=OxmlElement(tag)
    for k,v in attrs.items(): e.set(qn(k),str(v))
    return e


def field(p, instruction, display, bookmark=None):
    if bookmark:
        p._p.append(elem('w:bookmarkStart', **{'w:id':str({'ref':100,'fig':200,'tbl':300}[bookmark.split('_')[0]]+int(bookmark.split('_')[1])),'w:name':bookmark}))
    f=elem('w:fldSimple', **{'w:instr':instruction})
    r=elem('w:r');t=elem('w:t');t.text=display;r.append(t);f.append(r);p._p.append(f)
    if bookmark:
        p._p.append(elem('w:bookmarkEnd', **{'w:id':str({'ref':100,'fig':200,'tbl':300}[bookmark.split('_')[0]]+int(bookmark.split('_')[1]))}))


def hyperlink(p, text, url):
    h=elem('w:hyperlink', **{'r:id':p.part.relate_to(url,RT.HYPERLINK,is_external=True)})
    r=elem('w:r');pr=elem('w:rPr');pr.append(elem('w:color',**{'w:val':'245B70'}));r.append(pr)
    t=elem('w:t');t.text=text;r.append(t);h.append(r);p._p.append(h)


def inline(p,text):
    pattern=r'https?://[^\s]+|\[(\d+)\]|\b(Figure|Table) (\d+)|([图表])\s*(\d+)'
    last=0
    for m in re.finditer(pattern,text):
        p.add_run(text[last:m.start()]);v=m.group()
        if v.startswith('http'): hyperlink(p,v,v)
        elif m.group(1):
            p.add_run('[');field(p,f'REF ref_{m.group(1)} \\h',m.group(1));p.add_run(']')
        else:
            lab=m.group(2) or m.group(4);num=m.group(3) or m.group(5)
            p.add_run(lab+' ');field(p,f'REF {"fig" if lab in ("Figure","图") else "tbl"}_{num} \\h',num)
        last=m.end()
    p.add_run(text[last:])


def build(lang):
    text=(ROOT/f'dissertation_draft_{lang}.md').read_text()
    doc=Document();sec=doc.sections[0]
    sec.page_width=Cm(21);sec.page_height=Cm(29.7)
    sec.top_margin=Cm(2.4);sec.bottom_margin=Cm(2.3);sec.left_margin=Cm(2.5);sec.right_margin=Cm(2.5)
    sec.header_distance=Cm(1);sec.footer_distance=Cm(1)
    sec.different_first_page_header_footer=True
    normal=doc.styles['Normal'];normal.font.name='Times New Roman';normal.font.size=Pt(12)
    normal._element.get_or_add_rPr().append(elem('w:rFonts',**{'w:ascii':'Times New Roman','w:hAnsi':'Times New Roman','w:eastAsia':'Songti SC'}))
    normal.paragraph_format.space_after=Pt(6)
    normal.paragraph_format.line_spacing=1.25 if lang=='en' else Pt(20)
    for name,size in [('Title',26),('Subtitle',16),('Heading 1',17),('Heading 2',13),('Caption',10)]:
        st=doc.styles[name];st.font.name='Times New Roman';st.font.size=Pt(size);st.font.color.rgb=RGBColor(25,35,39)
        st._element.get_or_add_rPr().append(elem('w:rFonts',**{'w:ascii':'Times New Roman','w:hAnsi':'Times New Roman','w:eastAsia':'Songti SC'}))
        st.paragraph_format.space_before=Pt(14 if name.startswith('Heading') else 0)
        st.paragraph_format.space_after=Pt(6)
    doc.styles['Caption'].font.italic=False
    doc.styles['Subtitle'].font.italic=False
    doc.styles['Caption'].paragraph_format.line_spacing=Pt(12)
    for name in ('Title','Subtitle','Heading 1','Heading 2'):
        doc.styles[name].paragraph_format.line_spacing=1.05
    for st in doc.styles:
        for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER;field(footer,'PAGE','1')
    doc.core_properties.author='ZHANG YUXUAN';doc.core_properties.title='LLM-Based Report Generator' if lang=='en' else '基于大语言模型的报告生成系统'
    doc.core_properties.subject='Multi-source integration and structure, style and depth customization'
    lines=text.splitlines();i=0;cover=True;chapter=0
    while i<len(lines):
        line=lines[i].strip();i+=1
        if not line: continue
        if line.startswith('# Abstract') or line=='# 摘要':
            doc.add_page_break()
            cp=doc.add_paragraph('Contents' if lang=='en' else '目录', 'Heading 1')
            for j,title in enumerate(re.findall(r'^# (.+)$',text,re.M)[1:]):
                tp=doc.add_paragraph()
                h=elem('w:hyperlink',**{'w:anchor':f'chapter_{j}'})
                rr=elem('w:r');tt=elem('w:t');tt.text=title;rr.append(tt);h.append(rr);tp._p.append(h)
            doc.add_page_break();cover=False
        if line.startswith('# '):
            p=doc.add_paragraph(line[2:],'Title' if cover else 'Heading 1')
            if cover:p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(100)
            else:
                p._p.insert(0,elem('w:bookmarkStart',**{'w:id':str(1000+chapter),'w:name':f'chapter_{chapter}'}))
                p._p.append(elem('w:bookmarkEnd',**{'w:id':str(1000+chapter)}));chapter+=1
            continue
        if line.startswith('## '):
            p=doc.add_paragraph(line[3:],'Subtitle' if cover else 'Heading 2')
            if cover:p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(50)
            continue
        if line.startswith('!['):
            alt,path=re.match(r'!\[(.*?)\]\((.*?)\)',line).groups()
            img=ROOT/path
            w,h=Image.open(img).size
            width=min(6.25,6.7*w/h)
            p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.paragraph_format.line_spacing=1.0
            run=p.add_run();pic=run.add_picture(str(img),width=Inches(width));pic._inline.docPr.set('descr',alt)
            continue
        caption=re.match(r'^(Figure|Table|图|表)\s*(\d+)\.\s*(.*)',line)
        if caption:
            lab,num,body=caption.groups();p=doc.add_paragraph(style='Caption')
            p.paragraph_format.keep_with_next=lab in ('Table','表')
            p.add_run(lab+' ');field(p,'SEQ '+('Figure' if lab in ('Figure','图') else 'Table')+' \\* ARABIC',num,('fig_' if lab in ('Figure','图') else 'tbl_')+num)
            p.add_run('. ');inline(p,body);continue
        if line.startswith('|'):
            rows=[line]
            while i<len(lines) and lines[i].strip().startswith('|'):
                rows.append(lines[i].strip());i+=1
            rows=[r for r in rows if not re.fullmatch(r'[|:\s-]+',r)]
            cells=[[c.strip() for c in r.strip('|').split('|')] for r in rows]
            table=doc.add_table(rows=0,cols=len(cells[0]));table.style='Table Grid';table.autofit=False
            # Proportional widths for readable descriptions and compact numeric columns.
            n=len(cells[0]);weights=([.24,.38,.38] if n==3 else [.29,.25,.23,.23] if n==4 else [.27,.12,.13,.24,.24])
            if len(weights)!=n:weights=[1/n]*n
            for column,w in zip(table.columns,weights):column.width=Cm(16*w)
            for ri,values in enumerate(cells):
                row=table.add_row()
                row._tr.get_or_add_trPr().append(elem('w:cantSplit'))
                if ri==0:row._tr.get_or_add_trPr().append(elem('w:tblHeader'))
                for ci,(cell,value) in enumerate(zip(row.cells,values)):
                    cell.width=Cm(16*weights[ci]);p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4);p.paragraph_format.line_spacing=1.05
                    if ri<len(cells)-1:p.paragraph_format.keep_with_next=True
                    inline(p,value)
                    for run in p.runs:run.font.size=Pt(9.5);run.bold=ri==0
                    if ri==0:cell._tc.get_or_add_tcPr().append(elem('w:shd',**{'w:fill':'E9EEF0'}))
            doc.add_paragraph().paragraph_format.space_after=Pt(0)
            continue
        ref=re.match(r'^\[(\d+)\] (.+)',line)
        p=doc.add_paragraph(style='List Bullet' if line.startswith('- ') else 'Normal')
        if cover:
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(line);continue
        if ref:
            p.paragraph_format.keep_together=True;p.paragraph_format.left_indent=Cm(.7);p.paragraph_format.first_line_indent=Cm(-.7)
            p.add_run('[');field(p,'SEQ Reference \\* ARABIC',ref.group(1),'ref_'+ref.group(1));p.add_run('] ');inline(p,ref.group(2))
        else:inline(p,line[2:] if line.startswith('- ') else line)
    doc.settings.element.append(elem('w:updateFields',**{'w:val':'true'}))
    target=ROOT/f'dissertation_draft_{lang}.docx';doc.save(target);print(target)

if __name__=='__main__':
    for language in ('en','zh'):build(language)
