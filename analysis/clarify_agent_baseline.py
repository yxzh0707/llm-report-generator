"""Describe the actual frozen comparator; no experimental regeneration."""
from pathlib import Path
import json,hashlib,shutil,datetime,re,importlib.metadata as md
R=Path(__file__).resolve().parents[1];M=R/'manuscript/v2_3';P=R/'artifacts/report_study/system_comparison_02';B=R/'artifacts/manuscript_revision/baseline_configuration/before';B.mkdir(parents=True,exist_ok=True)
for name in ['dissertation_draft_zh.md','dissertation_draft_zh.pdf','README_zh.md']:
 if not(B/name).exists():shutil.copyfile(M/name,B/name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
s=(B/'dissertation_draft_zh.md').read_text().replace('普通 Agent','通用 Agent 基线')
s=s.replace('与具备读取、计算和计数工具的通用 Agent 基线比较','与自建的通用工具型 Agent 基线比较')
a=s.index('通用 Agent 基线 采用通用研究与写作提示',s.index('## 5.3'));b=s.index('每个公司对设置四种任务',a)
s=s[:a]+'''本实验的比较对象为自建通用工具型 Agent 基线，以下简称通用 Agent 基线。它由通用研究提示和工具接口独立装配，复用第 4.8 节所述基础 Agent 框架的运行器，通过 LangChain 的 create_agent 接口执行单 Agent 的模型—工具循环。本文报告系统使用同一运行器，另行接入报告专用提示、证据管理和交付控制。主对照考察报告流程相对于这一明确配置的基线所产生的效果。

基线系统提示要求模型使用工具检查给定资料，按用户要求撰写报告，按需规划工作，核对计算与篇幅，以 [S#] 引用来源，区分证据与解释，并说明材料缺失。模型自行决定工具顺序及修订次数，可覆盖已保存的草稿。基线保留共同运行器的调用次数、工具权限和响应格式检查，但不加载本文的证据管理中间件、阶段性收尾门控和写入前内容校验。

基线开放五个工具：读取全部上传资料、读取全部归档网页、Decimal 四则运算、确定性正文词数统计，以及保存报告。两个资料工具均返回允许使用的完整提取文本及来源标识；本实验不执行实时网络搜索或 RAG 排序。计算器支持加、减、乘、除与括号，计数工具只返回词数，保存工具只检查输出路径。调用这些工具后是否修改报告，由基线模型自行决定。

本文报告系统采用当前启用计算与校验机制的配置，使用与证据、期间和结果标签绑定的计算工具；存在显式篇幅要求时，提供词数及 token 测量和目标反馈。写入前检查可验证的来源、结果和篇幅条件，失败反馈进入同一次运行。两组均接收相同的用户任务、章节顺序、风格和深度指令；其区别在于系统提示、工具接口及流程控制，表 4 汇总具体配置。

表 4. 自建通用 Agent 基线与本文报告系统的配置。

| 项目 | 通用 Agent 基线 | 本文报告系统 |
|---|---|---|
| 实现来源 | 本实验单独装配的通用工具型基线 | 第 4 章实现的报告系统 |
| 执行框架 | 基础运行器；LangChain create_agent；单 Agent 循环 | 相同 |
| 生成模型 | Qwen3.8-27B；温度 0.2 | 相同 |
| 用户任务与资料 | 共同写作要求；完整上传与归档网页文本 | 相同 |
| 系统提示 | 通用研究、写作与自行核验 | 报告专用组织、计算规划及修订指令 |
| 工具能力 | 两类读取、四则计算、词数统计、文件保存 | 两类读取、依赖计算、按需篇幅测量、文件保存 |
| 提交处理 | 检查保存路径；可自行重写 | 增加来源、绑定结果及篇幅检查，失败反馈 |
| 资源上限 | 16 次模型调用、24 次工具调用、900 秒 | 相同 |
| 最终评分 | 共同外部规则与匿名正文评价 | 相同 |

'''+s[b:]
# Give the formal name before any shorthand in the methods.
s=s.replace('系统级主对照比较本文报告系统与通用 Agent 基线 在相同资料和任务下的最终输出','系统级主对照比较本文报告系统与自建通用工具型 Agent 基线（简称通用 Agent 基线）在相同资料和任务下的最终输出')
s=s.replace('| 普通 Agent 内容 |','| 基线内容 |').replace('| 通用 Agent 基线 内容 |','| 基线内容 |').replace('| 通用 Agent 基线 形式 |','| 基线形式 |')
# Appendix identifies the executable baseline and preserves the complete prompt outside prose.
mark='原始正文、展示版本和检查记录分别保存。'
i=s.index(mark)
paragraph='''系统级主对照的基线入口为 experiments/system_comparison.py 中的 assemble_generic；提示词由 generic_package 构建，运行包名为 general_research_agent。五个工具的接口名分别为 retrieve_uploaded_documents、retrieve_web_documents、calculator、count_words 和 write_file。本文系统由 src/runtime_adapter.py 中的 assemble 装配，运行包名为 report_generator。每次运行均保存实际系统提示、工具清单、共同用户输入和调用轨迹；随稿配置清单收录基线提示全文及文件哈希，便于恢复同一比较对象。两组均关闭运行时学习，失败后不另起一次自动重试；预算内的多轮起草和修改仍被允许。

'''
s=s[:i]+paragraph+s[i:]
s=re.sub(r'基线 (?=[\u4e00-\u9fff])','基线',s).replace('与具备读取、计算和计数工具的通用 Agent 基线比较','与自建的通用工具型 Agent 基线比较').replace('通过通用 Agent 基线系统级对照','通过与通用 Agent 基线的系统级对照')
(M/'dissertation_draft_zh.md').write_text(s)
# Traceability from all32actual baseline packages, not a reconstructed hypothetical prompt.
jobs=read(P/'jobs.json');names=[x['run_id'] for x in jobs if x['arm']=='general_agent'];prompt=P/'runs'/names[0]/'agent/SKILL.md';assert len({sha(P/'runs'/n/'agent/SKILL.md') for n in names})==1
for task in {x['task_id'] for x in jobs}:
 fs=[P/'runs'/x['run_id']/'agent_input.json' for x in jobs if x['task_id']==task];assert len({sha(f) for f in fs})==1,task
config={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'name_zh':'自建通用工具型 Agent 基线','short_name_zh':'通用 Agent 基线','run_arm':'general_agent','is_codex_or_commercial_product':False,'implementation':'experiments/system_comparison.py:assemble_generic','prompt_builder':'experiments/system_comparison.py:generic_package','package_name':'general_research_agent','shared_runtime':'autoresearch_agent_langchain.LangChainRuntimeFactory -> langchain.agents.create_agent','runtime_source_path':'/path/to/authorised-runtime/src/autoresearch_agent_langchain/engine/factory.py','model':'Qwen3.8-27B','temperature':0.2,'baseline_tools':['retrieve_uploaded_documents','retrieve_web_documents','calculator','count_words','write_file'],'budget':read(P/'protocol.json')['budget'],'runtime_controls':['allowed tools','model/tool calls and input budget','tool response validation','observable retry wrapper with0retries','prompt loading and trajectory capture'],'report_controls_absent':['ReportEvidenceMiddleware','UploadedReportGate','report-specific save validation'],'prompt_path':str(prompt.relative_to(R)),'prompt_sha256':sha(prompt),'prompt_verbatim':prompt.read_text(),'baseline_packages_verified':32,'identical_user_input_verified_for_all_16_tasks':True,'comparison_scope':'Controlled production from acquired complete texts; not a benchmark of Codex or other commercial products.','dependencies_observed_at_configuration_audit':{n:md.version(n) for n in ['langchain','langgraph','langchain-core','langchain-openai']}}
(M/'evidence/baseline_configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
for name,key in [('report_study_integration.json','sha256'),('system_comparison_integration.json','source_sha256')]:
 f=M/'evidence'/name;d=read(f);d[key]=sha(M/'dissertation_draft_zh.md')
 if name=='report_study_integration.json':d['sources']['baseline_configuration']={'path':'manuscript/v2_3/evidence/baseline_configuration.json','sha256':sha(M/'evidence/baseline_configuration.json')}
 f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('Baseline definition, tools, runtime and prompt provenance clarified; all existing scores unchanged.')
