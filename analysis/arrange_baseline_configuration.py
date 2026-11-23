from pathlib import Path
import json,hashlib
p=Path('manuscript/v2_3/dissertation_draft_zh.md');s=p.read_text()
a=s.index('基线系统提示要求');b=s.index('本文报告系统采用当前启用',a);details=s[a:b];s=s[:a]+s[b:];i=s.index('每个公司对设置四种任务');s=s[:i]+details+s[i:]
paragraphs=[]
for start in ['在同一批任务中，本文系统累计','多来源内容评价包含季度事实和指定业务主题。']:
 a=s.index(start);b=s.index('\n\n',a)+2;paragraphs.append(s[a:b]);s=s[:a]+s[b:]
i=s.index('表 6. 系统级主对照：');s=s[:i]+''.join(paragraphs)+s[i:]
p.write_text(s)
for name,key in [('report_study_integration.json','sha256'),('system_comparison_integration.json','source_sha256')]:
 f=Path('manuscript/v2_3/evidence')/name;d=json.loads(f.read_text());d[key]=hashlib.sha256(p.read_bytes()).hexdigest();f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
