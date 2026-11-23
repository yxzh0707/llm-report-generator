"""Add bounded RQ2 automatic-evaluation evidence to v2.1, preserving prior editions."""
from pathlib import Path
import hashlib
import json
import re
import shutil

R=Path(__file__).resolve().parents[1]
V=R/'manuscript/v2_2'
P=R/'artifacts/rq2_infobench/pilot_v1'
summary=json.loads((P/'itemwise/summary.json').read_text())
assert summary['micro']['counts']=={'YES':36,'INVALID':10,'NO':1}
assert summary['controls']=={'content_items':18,'NO':18,'YES':0,'unresolved':0}
assert summary['repeats']['valid']==summary['repeats']['same']==22
assert summary['repeats']['planned']==26
assert not V.exists(), 'Use build for existing v2.2; do not overwrite edited prose'
V.mkdir();shutil.copytree(R/'manuscript/v2_1/figures',V/'figures')
(V/'evidence').mkdir()

reference='[12] Y. Qin, K. Song, Y. Hu, W. Yao, S. Cho, X. Wang, X. Wu, F. Liu, P. Liu and D. Yu (2024). InFoBench: Evaluating Instruction Following Ability in Large Language Models. Findings of the Association for Computational Linguistics: ACL 2024, 13025–13048. https://aclanthology.org/2024.findings-acl.772/'

related={
'en':"Qin et al. introduce InFoBench and the Decomposed Requirements Following Ratio (DRFR), which assesses complex instructions through simpler requirement-level questions [12]. This formulation is useful for a report that meets its requested format but omits a requested topic or does not adopt the specified style. The supplementary RQ2 analysis in this study adapts requirement decomposition to the saved reports, separating semantic judgments from programmatic checks. It uses local report tasks and an adapted evaluator rather than the official InFoBench dataset.",
'zh':"Qin 等提出 InFoBench 及分解要求遵循率（Decomposed Requirements Following Ratio，DRFR），将复杂指令拆成较简单的要求级问题进行评估 [12]。这一方法适用于格式符合要求、却可能遗漏主题或偏离指定风格的报告。本文的 RQ2 补充分析将要求分解用于已保存报告，并将语义判断与程序检查分开。评估采用本地报告任务及适配后的评审器，未运行官方 InFoBench 数据集。"}

methods={
'en':'''## 5.7 Supplementary automatic assessment of report requirements

A retrospective pilot adapted the requirement-decomposition approach of InFoBench [12] to the three existing customization pairs. The six reports were T2 uploaded-only repetition 1 and its structure variant, T4 uploaded-only repetition 1 and its style variant, and T3 uploaded-only repetition 1 and its depth variant. Selection followed the existing pair design to cover structure, style and depth. No new reports were generated. This analysis is separate from the main-study author review and does not alter its labels or strict-success definition.

The task text and original style instructions were decomposed into 36 content questions and 11 style questions. Content questions covered requested topics such as annual performance, quarterly performance and synthesis across documents; style questions concerned the requested register and, where instructed, the distinction between facts and interpretation. Each report also received one exploratory semantic-depth question. Since the original explicit depth constraint was principally a word range, these six additional diagnostic questions were excluded from the 47-item instruction-following aggregate. Headings, word ranges, citation identifiers and applicable formatting conditions were checked by code.

The evaluator received the request, report, actual source excerpts and decomposed questions in a fresh context for each call, with no previous scores or report-group labels. Questions were batched within a report. The available endpoint was labelled Qwen3.8-27B, the same deployment name as the historical generator; current weights were not independently identified. Temperature was zero, thinking was disabled, the output ceiling was 4,000 tokens per call, and failed evaluations were not retried. The model returned YES, NO or UNKNOWN, a short rationale and exact report or source quotations. UNKNOWN was reserved for insufficient evidence to decide. Requiring verbatim quotations and retaining UNKNOWN were adaptations beyond the original binary evaluation implementation.

The protocol, question packets and original-input hashes were saved before the 12 evaluator calls. Six calls assessed the original reports; three independently repeated the customized-report assessments; three assessed controls with body content removed but headings and Sources retained. This control tests whether an evaluator rejects gross content omission. It does not validate subtle judgments of style, reasoning or factual support. The pilot required no human scoring.

The initial validator rejected a whole response when any supplied quotation failed literal matching. After this failure mode was observed, a separately recorded secondary analysis isolated invalid items while retaining valid neighboring judgments. This was a post-hoc change in failure handling. It made no additional model calls, changed no model labels and accepted no approximate quotations. Both analyses were preserved. In the secondary analysis, the satisfaction lower bound is YES divided by all planned explicit semantic items; the upper bound also counts UNKNOWN and invalid items as potentially satisfied. These bounds describe unresolved items, not sampling confidence intervals. Micro aggregation and an equal-report macro average are reported separately.

''',
'zh':'''## 5.7 报告要求的补充自动评估

本文将 InFoBench 的要求分解方法 [12] 适配到已有三组定制配对，开展事后探索性试验。六份报告分别为 T2 仅上传模式第一次重复及其结构变体、T4 仅上传模式第一次重复及其风格变体、T3 仅上传模式第一次重复及其深度变体。选择依据是已有配对设计对结构、风格和深度的覆盖，本轮没有新增报告生成。该分析与主实验的作者复核分开，不改变原标签及严格成功定义。

任务文本与原始风格指令被拆为 36 项内容要求和 11 项风格要求。内容问题覆盖年度业绩、季度业绩和跨文档综合等指定主题；风格问题检查所要求的语体，以及指令要求时对事实和解释的区分。每份报告另设一项探索性的语义深度问题。由于原始深度设置的明确约束主要是字数范围，这六项新增诊断不计入 47 项指令遵循汇总。标题、字数、引用标识及适用的格式要求由程序分别检查。

每次评审在新上下文中提供请求、报告、实际来源摘录及分解问题，不提供既有评分或报告组别标签，同一报告的问题合并在一次调用内。可用端点标记为 Qwen3.8-27B，与历史生成模型的部署名称相同，当前权重未得到独立确认。温度设为零，关闭 thinking，每次输出上限为 4,000 token，失败评审不重试。模型输出 YES、NO 或 UNKNOWN、简短理由以及报告或来源的原文引句；UNKNOWN 用于证据不足以确定判断的情况。要求逐字引句及保留 UNKNOWN 是本文在原二元评估实现基础上的适配。

12 次评审调用前保存了协议、问题包和原始输入哈希。六次用于原报告，三次独立重复定制报告的评审，另三次用于删除正文、保留标题和 Sources 的对照。该对照检查评审器能否识别明显内容缺失，不能验证细微风格、推理或事实支持判断的正确性。本轮不需要人工评分。

初始校验规则在任一引句无法逐字匹配时，将整份评审响应记为无效。观察到这一失败方式后，另行记录的次级分析仅隔离无效条目，保留同一响应中可核验的其他判断。这属于事后调整失败处理方式，没有新增模型调用、改动模型标签或接受近似引句，两种分析均予保留。次级分析的满足率下界为 YES 数除以全部计划明确语义条目数，上界进一步将 UNKNOWN 和无效条目视为可能满足。上下界描述未解决条目带来的范围，不是抽样置信区间。结果分别报告条目汇总及每份报告等权的宏平均。

'''}

results={
'en':'''## 6.12 Supplementary requirement-level assessment

All 12 evaluator calls returned responses, but only six passed the initial whole-response quotation check. Among the six original-report assessments, two passed; the corresponding 47-item aggregate contained 15 YES and 32 invalid items. The resulting satisfaction bounds of 31.9–100% were too wide to support a useful quality estimate. These failures arose in validating the evaluator's quotations, rather than establishing that the reports violated the corresponding requirements.

The secondary itemwise analysis retained 36 YES, one NO and ten invalid judgments among the 47 explicit semantic requirements (Table 6). Nine invalid items concerned content and one concerned style. The one valid NO concerned principal business risks in the T4 base report. These are model judgments with validated quotation strings; string matching does not verify their semantic correctness. The micro satisfaction bounds were 76.6–97.9%, while the equal-report macro bounds were 78.0–98.1%. In particular, the 36 positive judgments cannot be treated as an independently validated report-accuracy rate.

Table 6. Secondary itemwise automatic judgments for six reports. The analysis isolates quotation failures after the initial whole-response validation; semantic-depth diagnostics are excluded.

| Requirement class | YES | NO | Invalid |
|---|---|---|---|
| Content | 26 | 1 | 9 |
| Style | 10 | 0 | 1 |
| Total | 36 | 1 | 10 |

All 18 content questions in the empty-body controls received valid NO judgments. Repeated assessment produced identical labels for all 22 pairs in which both judgments were valid; four of the 26 planned comparisons were invalid. This repeat analysis includes the semantic-depth diagnostics. It establishes limited stability under the tested settings, not evaluator accuracy. The deterministic checks separately identified the T3 brief base report as overlength at 806 words against 250–500, and the T4 standard base report at 1,691 against 650–1,400. The three customized reports passed the checks applied in this pilot; these checks did not include every original runtime gate.

The evaluator reported 92,423 input tokens and 12,619 output tokens, totalling 105,042. This assessment usage is additional to the historical generation totals. All 30 tracked original files remained unchanged. For RQ2, the pilot adds limited corroboration that several explicit content and style requirements are reflected in the saved outputs, while preserving unresolved items and independently detecting length failures. It provides no direct-generation comparison, causal estimate of customization benefit or official InFoBench benchmark score.

''',
'zh':'''## 6.12 要求级自动评估的补充结果

12 次评审调用均返回响应，但只有六份通过初始整份引句校验。在六份原报告的评审中，两份通过；对应的 47 项汇总包含 15 项 YES 和 32 项无效，满足率界限为 31.9–100%，范围过宽，难以用于质量估计。这些失败发生在评审器的引句核验环节，不能据此断定报告违反相应要求。

次级逐条分析在 47 项明确语义要求中保留了 36 项 YES、1 项 NO 和 10 项无效判断（表 6）。无效条目中九项涉及内容，一项涉及风格。唯一有效的 NO 对应 T4 基础报告中的主要业务风险要求。这些结果是引句字符串通过核验的模型判断，字符串匹配本身不能证明其语义判断正确。条目汇总的满足率界限为 76.6–97.9%，每份报告等权的宏平均界限为 78.0–98.1%。因此，36 项正向判断不能直接解释为经过独立验证的报告准确率。

表 6. 六份报告的次级逐条自动判断。该分析在初始整份校验后隔离引句失败，语义深度诊断不计入汇总。

| 要求类别 | YES | NO | 无效 |
|---|---|---|---|
| 内容 | 26 | 1 | 9 |
| 风格 | 10 | 0 | 1 |
| 合计 | 36 | 1 | 10 |

空正文对照中的 18 项内容问题全部得到有效 NO 判断。重复评审计划比较 26 项，其中 22 项两次均有效且标签一致，另外四项存在无效判断。该重复分析包含语义深度诊断，反映测试设置下有限的稳定性，不能证明评审准确性。确定性检查另行识别出两份超长基础报告：T3 简要报告为 806 词，要求为 250–500；T4 标准报告为 1,691 词，要求为 650–1,400。三份定制报告均通过本轮采用的程序检查，但这些检查未包含原运行的全部门禁。

评审服务报告输入 92,423 token、输出 12,619 token，合计 105,042，属于历史生成用量之外的新增评估开销。30 项被跟踪的原始文件均保持不变。对于 RQ2，本轮对已保存输出体现若干明确内容和风格要求提供了有限补充佐证，同时保留无法确定的条目，并通过独立的程序检查识别长度失败。结果不构成直接生成对比、定制收益的因果估计或官方 InFoBench 基准分数。

'''}

rq2={
'en':"The supplementary requirement-level pilot adds a second, fully automatic assessment of six paired reports. Its secondary analysis retains 36 positive judgments across 47 explicit semantic requirements, but ten invalid items and the use of the generator's deployment name as judge limit the strength of this corroboration. Together with deterministic length checks, it supports examining customization by individual requirement rather than treating a report's formal completeness as overall success.",
'zh':"要求级补充试验为六份配对报告增加了另一种全自动评估。次级分析在 47 项明确语义要求中保留了 36 项正向判断，但十项无效结果以及评审器与生成器采用相同部署名称，限制了这项佐证的强度。结合确定性长度检查，这些结果支持按具体要求分析定制表现，不能将形式完整直接视为整体成功。"}
limits={
'en':"The supplementary automatic pilot has separate limitations. It uses the same deployment name as the historical generator and supplies no independent human-agreement validation. Exact quotations make failures visible but do not establish entailment. The itemwise failure-isolation analysis was introduced after observing whole-response failures and is therefore exploratory. Agreement on 22 valid repeated items and rejection of empty-body controls cannot establish sensitivity to subtle semantic errors. The added semantic-depth definition also extends beyond the original word-range contract, so it is kept outside the explicit-requirement score.",
'zh':"补充自动试验还存在独立的限制：评审器与历史生成器采用同一部署名称，没有独立的人类一致性验证。逐字引句使失败可见，却不能建立事实蕴含。逐条隔离失败是在观察整份校验失败后引入的，因此属于探索性分析。22 项有效重复判断一致、以及空正文对照被拒绝，不能证明评审器能识别细微语义错误。新增语义深度定义也超出原字数合同，故未纳入明确要求得分。"}
conclusion={
'en':"The supplementary InFoBench-inspired pilot makes requirement-level automatic assessment concrete for RQ2. Its positive judgments offer bounded supporting evidence, while quotation failures and shared generator–judge identity prevent a strong quality claim. A future comparison should fix invalid-item handling in advance and use a separately configured evaluator.",
'zh':"借鉴 InFoBench 的补充试验为 RQ2 提供了具体的要求级自动评估。正向判断构成有限支持，而引句失败及生成与评审模型的身份重合，使其不足以支撑较强的质量结论。后续对比应预先固定无效条目处理方式，并采用单独配置的评审模型。"}

for lang in ('en','zh'):
    source=R/f'manuscript/v2_1/dissertation_draft_{lang}.md'
    s=source.read_text().replace('[12]','[13]')
    anchor='## 2.5 Long-form generation and report organization' if lang=='en' else '## 2.5 长文生成与报告组织'
    assert s.count(anchor)==1;s=s.replace(anchor,related[lang]+'\n\n'+anchor)
    anchor='# 6. Results' if lang=='en' else '# 6. 实验结果'
    s=s.replace(anchor,methods[lang]+anchor)
    anchor='# 7. Discussion' if lang=='en' else '# 7. 讨论'
    s=s.replace(anchor,results[lang]+anchor)
    anchor='For RQ3,' if lang=='en' else '对于 RQ3，'
    s=s.replace(anchor,rq2[lang]+'\n\n'+anchor,1)
    anchor='## 7.4 Implications for multi-source customization' if lang=='en' else '## 7.4 对多来源定制的启示'
    s=s.replace(anchor,limits[lang]+'\n\n'+anchor)
    anchor='# References' if lang=='en' else '# 参考文献'
    s=s.replace(anchor,conclusion[lang]+'\n\n'+anchor)
    # Preserve first-citation order and the reference-entry order.
    s=s.replace('[13] Y. Shao',reference+'\n\n[13] Y. Shao')
    if lang=='en':
        s=s.replace('Future evaluation could therefore compare explicit requirement coverage with the corresponding evidence before release.', 'The supplementary pilot begins this comparison at requirement level; further evaluation could improve the reliability of the judgments before release.')
        s=s.replace('Independent content review would strengthen the interpretation of quality.', 'An independently configured automatic evaluator would help test the sensitivity of quality conclusions to judge choice. Human agreement could be studied separately; it was not a requirement of the supplementary automatic pilot. Independent content review would also strengthen the interpretation of quality.')
        s+='\n# Appendix D. Supplementary Automatic Evaluation Records\n\nThe supplementary session is artifacts/rq2_infobench/pilot_v1. Its protocol.json and manifest.json identify the settings, input hashes and 12 calls; packets, requests, responses and results preserve the evaluator inputs and outputs. summary.json records the initial whole-response analysis; itemwise/summary.json and itemwise/items.json record the separately identified secondary analysis. The protocol and upstream commit record are also retained under experiments/rq2_infobench. These artifacts are distinct from the frozen main-study reviews.\n'
    else:
        s=s.replace('后续评估可以围绕具体任务要求，逐项比较报告内容与证据。','补充试验已开始围绕具体任务要求逐项比较报告内容与证据，后续仍需提高判断可靠性。')
        s=s.replace('独立内容复核可以加强质量结论。','采用单独配置的自动评审模型，有助于检验质量结论对 judge 选择的敏感性。人类一致性可另行研究，不是本轮补充自动试验的必要步骤。独立内容复核也可以加强质量结论。')
        s+='\n# 附录 D. 补充自动评估记录\n\n补充评估会话位于 artifacts/rq2_infobench/pilot_v1。protocol.json 与 manifest.json 记录设置、输入哈希和 12 次调用，packets、requests、responses 与 results 保存评审输入及输出。summary.json 对应初始整份响应分析，itemwise/summary.json 和 itemwise/items.json 对应单独标记的次级分析。协议及上游代码版本另存于 experiments/rq2_infobench。上述产物与冻结主实验的复核记录分别保存。\n'
    (V/f'dissertation_draft_{lang}.md').write_text(s)

receipt={'base':'v2_1','scope':['2.4','5.7','6.12','7.1','7.2','7.3','7.5','8','Appendix D'],
         'new_reference':reference,'primary':json.loads((P/'summary.json').read_text()),
         'secondary':summary,'new_model_calls':0,
         'input_sha256':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                        [P/'manifest.json',P/'summary.json',P/'itemwise/summary.json',P/'itemwise/items.json']}}
(V/'evidence/rq2_integration.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(V)
