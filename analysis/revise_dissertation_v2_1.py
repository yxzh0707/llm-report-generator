"""Apply the bounded deployment-motivation and RQ/source-route clarification to v2."""
from pathlib import Path
import re,shutil
R=Path(__file__).resolve().parents[1]; V=R/'manuscript/v2_1';V.mkdir(exist_ok=True)
shutil.copytree(R/'manuscript/v2/figures',V/'figures',dirs_exist_ok=True)
ref='[2] S. M. U. Pirzada and S. Josic (2026). Run Qwen 3.8 27B on AMD Ryzen AI Max Agentic PCs and Radeon GPUs. AMD technical blog, 14 August 2026. Accessed 25 October 2026. https://www.amd.com/en/blogs/2026/run-qwen-3-8-27b-on-amd-ryzen-ai-max-and-radeon-graphics-cards-day-0.html'
intro={
'en':"Local deployment tools now offer practical routes to running 27B-class models on suitably equipped personal computers and workstations [2]. For financial workflows, keeping generation and embedding within user-controlled infrastructure could reduce external exposure of private documents. This is a motivation for the system's configurable model interface. The present experiments used a remote service labelled Qwen3.8-27B and remote embeddings; local performance and privacy protection were not evaluated.",
'zh':"本地部署工具已为在具备相应硬件的个人电脑和工作站上运行 27B 级模型提供了可行路径 [2]。对于涉及私密资料的金融工作，将生成和 embedding 保留在用户控制的基础设施内，有望减少文档向外部服务的暴露。这也是系统采用可配置模型接口的应用动机。本研究实际使用部署名称为 Qwen3.8-27B 的远程服务及远程 embedding，尚未评估本地运行性能或隐私保障。"}
financial={
'en':"The acquisition routes serve different information needs. General web search locates relevant pages, while SEC filing discovery locates regulatory documents whose text must then be opened before it can support a citation. SEC company facts exposes selected filing-derived numerical records; Tushare and Alpha Vantage provide additional structured-data query routes subject to the requested endpoint and access rights. The report layer places usable returns from these routes in the same evidence ledger, allowing document passages and structured observations to be cited together. Integration therefore concerns complementary evidence content as well as the number of available tools. The saved development checks cover a SEC-backed report, a document-plus-SEC report and individual API probes; they do not yet establish an end-to-end report combining all providers.",
'zh':"这些获取路径分别服务于不同的信息需求。通用网络搜索定位相关网页，SEC 文件发现定位监管披露文档；后者仍需打开正文，才可作为引用依据。SEC company facts 提供来自申报材料的指定数值记录，Tushare 与 Alpha Vantage 则在端点和访问权限允许的范围内提供其他结构化查询路径。报告层将可用返回内容登记到同一证据台账，使文档片段与结构化记录能够在报告中共同被引用。因此，整合的意义在于证据内容互补，而不只是工具数量增加。已保存的开发验证包括 SEC 数据报告、文档与 SEC 混合报告及各 API 探测，尚未建立同时组合所有 provider 的完整报告验证。"}
for lang in ['en','zh']:
 s=(R/f'manuscript/v2/dissertation_draft_{lang}.md').read_text()
 # Shift only numbered literature tokens; [S1] source identifiers are unaffected.
 s=re.sub(r'\[(\d+)\]',lambda m:f'[{int(m[1])+1}]' if int(m[1])>=2 else m[0],s)
 anchor='## 1.2 Research objectives and questions' if lang=='en' else '## 1.2 研究目标与问题'
 if anchor not in s and lang=='en':
  anchor=next(x for x in s.splitlines() if x.startswith('## 1.2'))
 assert s.count(anchor)==1;s=s.replace(anchor,intro[lang]+'\n\n'+anchor)
 if lang=='en':
  s=s.replace('while preserving source identity and enforceable source restrictions?', 'while preserving source identity, traceable citations and enforceable source restrictions?')
  s=s.replace('To what extent do generated reports follow requested structure, style and depth, and provide traceable citations?', 'To what extent do generated reports follow user requirements for content structure, writing style and depth?')
  marker='These questions support a systems contribution.'
  if marker not in s: marker=next(x for x in s.splitlines() if x.startswith('The contribution'))
  s=s.replace(marker,'Multi-source integration and customization are the two central application requirements. Financial acquisition tools support RQ1; explicit report settings and their observed effects address RQ2.\n\n'+marker,1)
  s=s.replace('Financial tools broaden the available acquisition methods,',financial[lang]+'\n\nFinancial tools broaden the available acquisition methods,',1)
  s=s.replace('For RQ2, structure and citation identifiers were consistently compliant in the main study, while depth compliance was weak.', 'For RQ2, required structural organization was consistently compliant in the main study, while length compliance, one observable aspect of depth, was weak.')
 else:
  s=s.replace('并保留来源身份、落实证据来源限制？','并保留来源身份与可追溯引用、落实证据来源限制？')
  s=s.replace('生成报告在多大程度上满足结构、风格和深度要求，并提供可追溯的引用？','生成报告在多大程度上满足用户对内容结构、写作风格和内容深度的要求？')
  marker='本文的贡献属于系统设计与集成。'
  s=s.replace(marker,'多来源整合与报告定制构成两项核心应用要求。金融信息获取工具服务于 RQ1，显式报告设置及其实际效果对应 RQ2。\n\n'+marker,1)
  s=s.replace('金融工具增加了获取信息的方式，',financial[lang]+'\n\n金融工具增加了获取信息的方式，',1)
  s=s.replace('对于 RQ2，主实验的结构与引用标识持续满足检查，深度合规则较弱，仅 7/21 通过全部自动约束。','对于 RQ2，主实验持续满足必需结构的检查，字数合规则较弱；字数只是深度的一个可观察方面。仅 7/21 通过全部自动约束。')
 # Bibliography reference 1 remains first; insert official deployment note second.
 lines=s.splitlines();idx=next(i for i,x in enumerate(lines) if x.startswith('[1] '))
 lines[idx+1:idx+1]=['',ref];s='\n'.join(lines)+'\n'
 assert intro[lang] in s and financial[lang] in s
 (V/f'dissertation_draft_{lang}.md').write_text(s)
print(V)
