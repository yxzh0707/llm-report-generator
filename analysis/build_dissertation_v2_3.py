"""Build the Chinese v2.3 working draft with the established dissertation layout."""
from pathlib import Path
import runpy
import json
from docx import Document
from docx.shared import RGBColor, Inches, Cm, Pt
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
module = runpy.run_path(str(ROOT / 'analysis/build_dissertation_v2.py'))
build = module['build']
build.__globals__['ROOT'] = ROOT / 'manuscript/v2_3'
build('zh')
# Preserve the previous layout while making heading colors explicit.
target = ROOT / 'manuscript/v2_3/dissertation_draft_zh.docx'
doc = Document(target)
for name in ('Title', 'Subtitle', 'Heading 1', 'Heading 2'):
    doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
# Keep the interface screenshot with its introduction without a half-page gap.
for shape in doc.inline_shapes:
    if shape._inline.docPr.get('descr') == '报告主 Agent 执行结构':
        ratio = Inches(5.1) / shape.width
        shape.width = Inches(5.1)
        shape.height = int(shape.height * ratio)
    if shape._inline.docPr.get('descr') == '英文报告工作区':
        ratio = Inches(5.6) / shape.width
        shape.width = Inches(5.6)
        shape.height = int(shape.height * ratio)
# Style paragraphs with the three contribution items as a numbered list.
for paragraph in doc.paragraphs:
    if paragraph.text.startswith(('1. 设计并实现', '2. 实现内容结构', '3. 建立以')):
        paragraph.style = doc.styles['List Number']
        if paragraph.runs:
            paragraph.runs[0].text = paragraph.runs[0].text[3:]
# Keep compact result tables intact; the long experiment/catalog tables may flow.
widths = [
    [3.0, 6.5, 6.5], [2.5, 6.9, 1.8, 4.8], [3.0, 6.3, 4.5, 2.2],
    [3.4, 8.2, 4.4], [8.0, 4.0, 4.0], [4.4, 3.1, 4.1, 4.4],
    [6.3, 1.5, 2.2, 2.8, 3.2], [8.0, 4.0, 4.0], [5.5, 3.5, 3.5, 3.5],
    [6.1, 3.0, 3.45, 3.45], [7.0, 1.5, 7.5], [4.0, 4.5, 1.5, 6.0],
]
mapping_path=ROOT/'manuscript/v2_3/evidence/system_comparison_integration.json'
long_tables={2,11}
if mapping_path.exists():
    integration=json.loads(mapping_path.read_text())
    mapping=integration['table_mapping']
    old_widths={f'OLD{i+1}':w for i,w in enumerate(widths)}
    dimensions={**old_widths,'OLD3':[2.2,5.5,5.8,2.5],'BASE':[3.0,6.5,6.5],
                'SYS':[8.0,4.0,4.0],'PROFILE':[3.2,3.2,3.2,3.2,3.2],'SEM':[8.0,4.0,4.0]}
    dimensions.update(integration.get('table_widths',{}))
    widths=[dimensions[k] for k in sorted(mapping,key=mapping.get)]
    long_tables={mapping[k]-1 for k in ('OLD3','OLD12')}
assert len(doc.tables) == len(widths)
for ti, (table, dimensions) in enumerate(zip(doc.tables, widths)):
    for column, width in zip(table.columns, dimensions):
        column.width = Cm(width)
    for ri, row in enumerate(table.rows):
        for cell, width in zip(row.cells, dimensions):
            cell.width = Cm(width)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = ri == 0 or (ti not in long_tables and ri < len(table.rows) - 1)
                paragraph.paragraph_format.keep_together = True
                paragraph.paragraph_format.line_spacing = 1.12
                for run in paragraph.runs:
                    run.font.size = Pt(10)
doc.save(target)
