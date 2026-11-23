"""Integrate existing formal cases; no new scores or generation."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]/'manuscript/v2'
texts={l:(ROOT/f'dissertation_draft_{l}.md').read_text() for l in ('en','zh')}
def before(l,a,b):
    assert texts[l].count(a)==1,a
    texts[l]=texts[l].replace(a,b.strip()+'\n\n'+a)

before('en','# 7. Discussion', '''
## 6.7 Case analysis: integrating two NVIDIA disclosures

The first T2 run provides a concrete view of how multiple documents enter one report. Its request asks for business and AI strategy, annual and quarterly performance, and evidence limitations, with an explicit distinction between reportable segments and market platforms. The supplied evidence contains the annual filing and CFO commentary. The resulting standard report has 1391 body words and passes the applicable automatic checks. Its source identifiers remain local to that run: S2 refers to a CFO-commentary passage, while S4 refers to the annual filing's income-statement passage.

The output brings together overlapping annual figures and complementary quarterly detail. Its executive summary associates annual revenue of $130,497 million with S2 and S4, and quarterly revenue of $39,331 million with S2. The former occurs in both supplied passages; the latter is available in the CFO passage. This is a more informative integration behavior than appending two document summaries, because the report assigns facts to a shared annual/quarterly organization and preserves the corresponding citations.

The structure variant reorganizes the same evidence into a comparison of the two disclosures. Its table places the annual revenue values side by side and labels their agreement, while distinguishing quarterly material that is absent from the returned annual-filing excerpt. It also distinguishes reportable accounting segments from market-platform categories. The variant contains 1296 words, passes automatic checks and has satisfied labels for the five applicable content/customization items. The case establishes that a different organization can be produced from the same evidence; both it and the baseline already pass the automatic conditions, so it does not establish a quality improvement caused by the preset.

The report also illustrates a wording risk. One table cell describes the annual filing as silent, and another passage describes the CFO commentary as purely financial. The saved evidence supports a narrower statement about the returned excerpts. A generator should not generalize a passage-level absence to the entire source document. The case is therefore useful even though its recorded strict result is successful: the rubric's success decision is not a certification of every sentence.

The relevant evidence can be traced beyond the source labels. In the structure variant, S2 covers normalized characters 0–2385 of the CFO commentary; S4 covers characters 265843–268231 of the annual filing. Their parent identities and hashes are preserved with the run. A reader can inspect the exact passages used to establish agreement without retrieving a later version of either document. Appendix C identifies this variant and its paired baseline.

## 6.8 Case analysis: concise style with incomplete coverage

The AMD style pair changes formal analytical writing to concise briefing while keeping standard depth and the same evidence. The baseline has 1691 words; the variant has 710 words and 41 bullet items. The automatic checks accept the variant's word range and bullet constraints. The observed change is therefore not just a label in the request: it is visible in the form and extent of the saved report.

The shorter report nevertheless does not cover all requested segment and risk information. It explicitly says that AMD reports four segments but that the returned excerpts do not enumerate the other three alongside Data Center. The relevant annual-report passage ends immediately after the introduction to the segment list. This provides a concrete link between a content gap in the report and the boundary of its available evidence. The report discloses the limitation, which is useful to a reader, but disclosure does not supply the missing coverage. The existing Q137 review therefore records the requirement as not satisfied.

Another sentence attributes the GAAP-to-non-GAAP gap largely to approximately $946 million of acquisition-related intangible amortization. In its cited S6 passage, that amount belongs to the gross-profit reconciliation. Extending it to an undifferentiated earnings gap loses the metric context. Q138 consequently retains uncertainty for the combined style/tone and semantic-depth judgment, despite the visible briefing form. The example shows why checking short bullets alone cannot assess the adequacy of a financial explanation.

The paired evidence is important when interpreting this result. The segment-list boundary is present in the common input, and the experiment does not isolate brevity as the cause of missing coverage. The supported conclusion is that the requested style is observable while substantive requirements remain unmet. A design response should examine evidence sufficiency as well as wording; simply asking for more bullets would not recover a list missing from the supplied passage.

## 6.9 Case analysis: more text and a faulty calculation

The AMD depth pair retains formal analytical style and changes brief depth to detailed depth. The saved reports grow from 806 to 2254 words. The baseline already exceeds its 250–500-word brief range, while the variant falls within the detailed interval of 1500–2300 words. The pair therefore demonstrates expansion into the requested detailed range, without demonstrating reliable control at both ends of the scale.

The detailed report includes a claim that Gaming and Embedded together represented approximately 42% of 2023 revenue. The cited S3 passage gives rounded values of $6.2 billion for Gaming, $5.3 billion for Embedded and $22.7 billion for total revenue. Applying the stated relationship to these values gives (6.2 + 5.3) / 22.7 × 100, approximately 50.7%. The report's 42% does not follow from its supplied figures. This arithmetic check explains an existing review finding; it does not add a new sampled claim or alter the formal scoring denominator.

The same report explains ROCm investment as addressing a historical barrier to AMD GPU adoption. Its cited passage describes software performance optimization, framework support and developer experience, but does not establish that historical adoption claim. A plausible domain explanation has therefore exceeded the returned evidence. The existing Q143 judgment is uncertain, acknowledging useful elaboration while retaining the calculation and support concerns. The variant's strict outcome remains indeterminate, as recorded.

This case separates extent from semantic depth. More paragraphs create room for explanation, but the reliability of that explanation depends on valid calculations and supported relationships. The experiment has one such depth pair, so it cannot establish that requesting detail generally increases errors. It does show why a depth assessment needs to examine the extra content rather than count it alone.

## 6.10 Case analysis: a comparison caveat without sufficient premises

The first web-only company comparison contains the reasonable-sounding caution that the companies' fiscal years are not calendar-aligned and their segment definitions differ. The source-support review considers the two returned official-release snapshots, each limited to 6000 characters. NVIDIA's passage identifies its January quarter end; the AMD passage does not establish the December fiscal-year-end date in the returned text. The snapshots also do not establish NVIDIA's formal reportable-segment definitions, even though they discuss Data Center performance and AMD's segments.

The problem is not that cautious comparison is undesirable. The statement combines factual premises that must themselves be supported. The task request contains period information, but a task instruction is not a substitute for source evidence. Nor can the annual filings supplied in other runs repair this web-only report's evidence retrospectively. The existing Q015 label is therefore insufficient rather than contradicted. The sampled sentence has no citation marker; the review nevertheless considers all evidence supplied to that run.

This case exposes the gap between citation validity and citation sufficiency. Every citation marker that does occur can name a real entry while a material sentence remains unsupported. For the system, the consequence is an evaluation requirement: registered identifiers and source-class coverage need to be supplemented by inspection of claims and their premises. The 18 supported claims out of the separate 20-claim sample describe that sample only.

## 6.11 What the cases add to the aggregate results

The cases explain different outcomes hidden by a single completion measure. The NVIDIA example makes overlapping and complementary evidence visible in a common report structure. The AMD briefing example meets observable style conditions but lacks required scope. The detailed example reaches its length target while retaining faulty or unsupported explanation. The web-only example gives an appropriate-looking caveat whose factual basis is incomplete in the returned evidence.

These are selected illustrations of the saved results, not estimates of failure frequency. They show how the reporting objective connects to the evaluation: a usable report needs relevant evidence, an organization suited to the task, faithful treatment of numbers and categories, and an appropriate level of explanation. The application exposes these components for inspection, while the recorded outputs show that they do not always succeed together.
''')
before('zh','# 7. 讨论', '''
## 6.7 案例：综合 NVIDIA 的两份披露

T2 的首次运行可以具体展示多份资料如何进入同一报告。请求要求说明业务与 AI 战略、全年和季度业绩、证据局限，并区分报告分部与市场平台。输入包括年报和 CFO 说明。标准结构报告正文为 1391 词，通过适用的自动检查。来源编号仅在该运行内有效：S2 对应 CFO 说明片段，S4 对应年报利润表片段。

输出同时组织了重叠的年度数字与互补的季度信息。执行摘要把年度收入 130,497 百万美元关联到 S2 和 S4，把季度收入 39,331 百万美元关联到 S2。前者存在于两份返回片段中，后者由 CFO 片段提供。这种做法按照共同的年度、季度框架组织事实并保留引用，较直接拼接两份摘要更能展示信息整合过程。

结构变体使用相同证据，将报告改为两份披露之间的比较。表格并排列出相同的年度收入，标示其一致性，并区分返回的年报片段中没有出现的季度信息；报告也区分了会计报告分部与市场平台。变体正文为 1296 词，通过自动检查，五项适用内容和定制复核均为满足。它说明同一证据可以被组织成不同形式；由于基准本来也自动合格，不能据此认定比较预设导致质量提升。

这一案例仍有措辞风险。某个表格单元将年报描述为没有相关信息，另一个段落将 CFO 说明描述为纯财务内容；保存证据只支持关于返回片段的较窄判断。生成器不应将片段没有出现某内容推广为全文没有该内容。因此，即使既有严格结果为成功，仍可从案例中发现值得改进的表述；rubric 的成功不代表每句话均已认证。

来源还可以追溯到编号之外。在结构变体中，S2 对应 CFO 说明规范化正文的 0–2385 字符，S4 对应年报的 265843–268231 字符。父块身份与哈希保存在运行记录中，读者无需重新获取可能变化的资料，就能检查支持一致性判断的实际片段。附录 C 列出变体及配对基准身份。

## 6.8 案例：简洁形式成立，内容覆盖仍不足

AMD 风格配对将正式分析改为简洁简报，保留标准深度和相同证据。正文从 1691 词变为 710 词，变体具有 41 个项目符号条目，字数和条目长度均通过自动检查。因此，设置变化确实体现在保存输出的形式和篇幅上。

较短报告仍未覆盖全部分部和主要风险。它明确指出 AMD 有四个分部，但返回摘录除了 Data Center 外没有列全另外三个。对应年报片段恰好结束于分部列表的引入位置，将输出缺口与可用证据边界联系起来。报告披露这一局限有助于读者理解，但披露不能补足内容要求，因此既有 Q137 判断为不满足。

另一句把 GAAP 与 non-GAAP 差异主要归于约 946 百万美元的收购相关无形资产摊销。在引用的 S6 片段中，该金额属于毛利润调节表，将其泛化到未明确指标的整体盈利差异，丢失了原始口径。Q138 因而对风格、语气和语义深度的综合判断保留不确定，即使简报形式本身已经出现。这说明短条目检查不能评价财务解释是否充分。

配对输入限制了归因范围。分部列表截断已经存在于共同证据包中，实验没有把简洁风格单独识别为遗漏原因。可支持的结论是：风格响应可见，但实质要求仍未满足。改进时应同时检查证据充分性和表述，仅要求增加项目符号无法找回输入中缺失的列表。

## 6.9 案例：篇幅增加与计算错误并存

AMD 深度配对保留正式分析风格，将简要深度改为详细深度，保存正文从 806 词增加到 2254 词。基准已超过简要区间 250–500 词，变体则位于详细区间 1500–2300 词。因此，它显示输出扩展进入了详细范围，却没有说明两个深度等级都能被可靠控制。

详细报告声称 Gaming 与 Embedded 合计约占 2023 年收入的 42%。引用的 S3 片段给出取整后的数值：Gaming 为 6.2 十亿美元，Embedded 为 5.3 十亿美元，总收入为 22.7 十亿美元。按所述关系计算，(6.2 + 5.3) / 22.7 × 100 约为 50.7%，不能得到报告中的 42%。此计算用于解释既有复核发现，没有新增抽样陈述或改变正式评分分母。

同一报告将 ROCm 投资解释为解决 AMD GPU 采用过程中的历史障碍。所引片段讨论软件性能优化、框架支持和开发体验，没有建立该历史采用判断。看似合理的领域解释因此超出了返回证据。Q143 在承认部分解释有用的同时，保留计算和支持问题，标签为不确定；变体严格结果仍按记录保留为未确定。

这一案例把篇幅与语义深度分开。更多段落提供了解释空间，但解释的可靠性还取决于计算和事实关系。实验只有一组深度配对，不能据此推断要求详细回答一般会增加错误。它能说明的是，深度评估必须检查新增内容，而不能仅统计数量。

## 6.10 案例：比较提醒缺少充分事实前提

首次仅网络公司比较包含一个听起来合理的提醒：两家公司财年不按相同日历对齐，分部定义不同，因此直接比较需要谨慎。来源支持复核检查了两份各限定为 6000 字符的官方公告快照。NVIDIA 片段给出一月季度结束日期，AMD 返回正文没有建立十二月财年结束日期；快照虽然讨论了 Data Center 业绩和 AMD 分部，也没有说明 NVIDIA 正式报告分部的定义。

问题不在于谨慎比较这一建议，而在于其组合的事实前提也需要依据。任务描述中的期间信息不能替代来源证据，其他运行中的上传年报也不能事后补足该仅网络报告。Q015 因此判为证据不足，而非矛盾。被抽样句子本身没有引用标记，但复核仍检查了该次运行获得的全部证据。

案例说明引用有效性与证据充分性之间的差距：已经出现的标记都可以对应真实条目，同时仍有重要句子缺少支持。系统评估需要在编号和来源类别覆盖之外，检查陈述及其前提。独立统计的 20 条陈述中有 18 条受支持，只能说明该样本，不能推广到所有报告事实。

## 6.11 案例对汇总结果的补充

这些案例解释了单一完成率掩盖的不同情况。NVIDIA 案例将重叠和互补证据组织在共同结构中；AMD 简报满足可观察风格，却缺少必要内容；详细报告达到篇幅要求，仍包含计算和依据问题；仅网络报告的合理提醒则没有完整的返回证据前提。

它们属于保存结果中的选定实例，不用于估计问题发生频率。案例将报告目标与评估连接起来：可用输出需要相关证据、适合任务的组织方式、对数字和类别的忠实处理，以及适当解释。系统让这些部分可以被检查，而实际结果显示它们并不总能同时满足。
''')

before('en','# 8. Conclusion', '''
## 7.4 Implications for multi-source customization

The strongest supported outcome is a working integration whose behavior can be examined at the level of individual reports. In the NVIDIA case, the comparative preset makes overlapping figures and complementary disclosure scope visible. In the AMD cases, output form changes while unresolved information gaps and interpretation errors remain. Together, these findings place the main design problem at the relationship between the requested report and the evidence available for writing it.

This relationship connects the system to the literature without establishing a benchmark comparison. Task-directed selection, as emphasized in query-based summarization [8], is relevant when a long filing contains much more information than one report can include. Explicit preference inputs, as explored in controllable summarization [9], motivate making the desired output form part of the request. This study examines an application that combines these concerns with source references. Its results should be judged through the implemented reporting contract rather than through scores borrowed from those different tasks.

A useful next improvement would be a bounded pre-drafting coverage check against the task's required content. If annual performance is requested, the system should identify whether the supplied evidence includes the relevant annual measures before writing an apparently complete report. Such a check could expose missing material earlier, but its quality would need separate evaluation: a checklist can itself misunderstand a metric or accept an irrelevant passage. The present system does not establish this proposed mechanism's effectiveness.

Length correction is a separate issue. A constrained editing pass might shorten the 14 overlength main outputs, but a shorter version could omit a qualifying period, a risk or a source citation. Evaluating that change would require retaining the first output, saving the edited output and comparing content as well as length. The current results provide a clear motivation for such a study; they do not justify treating an unmeasured revision step as an existing solution.

## 7.5 What further evidence would change the conclusions

The current study supports feasibility and identifies specific weaknesses. To support a comparative improvement claim, an additional study would need an explicit baseline under matched tasks, evidence and resource limits. For example, a direct prompt using the same evidence could be compared with the configured report process. That would test a narrower question than comparing unrelated services with different retrieval results. No such result is asserted here.

Retrieval design would require a different control. Comparing child-only context with parent-expanded context while keeping the model and task fixed could examine the value and cost of expansion. The analysis would need to account for changed context content and size, and inspect whether definitions or complete tables were retained. The present offset and budget checks establish implementation integrity, not that comparison's outcome.

Independent content review would strengthen the interpretation of quality. A reviewer who has not seen the model's labels could evaluate a defined subset using the same evidence and criteria. Disagreements would need to be retained rather than reconciled by default to the earlier label. Broader corpora would address transfer beyond the selected companies. These are targeted evidence gaps, not reasons to expand the application into a general agent platform or train a new model.
''')
before('zh','# 8. 结论', '''
## 7.4 对多来源定制的启示

证据最充分的成果是一个能够运行、且能逐份检查行为的集成系统。NVIDIA 案例中，比较预设让相同数字和互补披露范围变得可见；AMD 案例则显示，输出形式改变后，信息缺口和解释错误仍然存在。这些结果将设计重点指向用户所要求的报告与写作时可用证据之间的关系。

这也说明系统与相关研究的联系，但不构成基准比较。查询摘要所强调的任务导向选择 [8]，适用于年报信息远多于单份报告篇幅的情形；可控摘要研究中的显式偏好输入 [9]，支持将输出形式写入请求。本研究评估的是同时处理这些问题和来源引用的应用，其结果应依据自身报告合同解释，而不能借用其他任务的分数。

有针对性的下一步是，在起草前按任务要求进行有界内容覆盖检查。例如，用户要求年度业绩时，应先判断证据是否包含所需年度指标，而不是写完形式完整的报告后才发现缺失。这可能更早暴露资料不足，但检查机制也可能误解指标或接受不相关片段，需要单独评估；本文没有证明它已经有效。

长度修正应作为另一个问题处理。受约束编辑可能缩短 14 份超长主实验报告，但也可能删去期间限定、风险或引用。评估这种改动，需要保留首次输出和编辑输出，同时比较内容与长度。现有结果提供了明确动机，却不能把尚未测量的修订步骤当作已经解决问题。

## 7.5 哪些新增证据会改变当前结论

当前研究支持可行性并定位具体弱点。若要提出改进优越性的结论，新增研究应在任务、证据和资源限制匹配的条件下设置明确基准，例如比较相同证据下的直接提示与配置后的报告流程。这比比较采用不同检索结果的无关服务回答了更清楚的问题，本文尚无该对照结果。

检索设计需要另一种控制：固定模型和任务，比较仅子块与展开父块的上下文，检查定义或完整表格是否保留，并考虑内容与体量同时变化。当前偏移和预算检查建立的是实现完整性，不是该实验的结果。

独立内容复核可以加强质量结论。未看到模型标签的评审者可按相同证据和标准判断预定子集，保留分歧，而不默认向旧标签靠拢。更广语料则检验超出两家公司的迁移情况。这些是具体证据缺口，无需因此扩展为通用 Agent 平台或训练新模型。
''')

append_en='''
# Appendix C. Case locators and reporting distinctions

All case identifiers below belong to formal batch 20261020T032924986612Z. They identify existing reports, not additional runs. The associated evidence ledgers preserve excerpt text, offsets and hashes; review labels remain those confirmed after model pre-review.

- NVIDIA standard synthesis: T2_uploaded_only_r1_a001; comparative variant: C_structure_r1_a001. The comparative review comprises Q129–Q133. S2 and S4 in the variant identify the CFO commentary and annual income-statement passages respectively.
- AMD concise-style pair: T4_uploaded_only_r1_a001 and C_style_r1_a001. Q137 concerns business-segment scope and risks; Q138 concerns style/tone and semantic depth. S5 ends at the introduction to the segment list; S6 contains the gross-profit reconciliation.
- AMD depth pair: T3_uploaded_only_r1_a001 and C_depth_r1_a001. Q143 records the semantic-depth uncertainty. S3 supplies the rounded revenue figures used in the arithmetic example; S6 supplies the software discussion.
- Web-only comparison: T5_web_only_r1_a001. Sampled claim C5 is review item Q015. Its judgment is insufficient, not contradicted.

The prefix is common to all run identifiers and is prepended to each suffix when locating a run directory. Source labels such as S2 are meaningful only inside that run. The same source passage may receive a different label in another report. A source label is consequently never used as a global document identifier.

# Appendix D. Reading the system's outputs

The original report records what the generator wrote. The display report reconstructs source presentation from the evidence ledger. Automatic checks apply to the original text. A readable display version therefore cannot retroactively repair the generated content or change a failed constraint into a pass.

The reader can follow a body citation to the supplied excerpt and compare the relevant claim with its wording, period, unit and scope. If the excerpt lacks the required information, that absence should be distinguished from a contradiction. If the report includes a calculation, the relationship and denominator must be checked separately from the validity of its source marker. For multi-source comparisons, the reader should also determine whether two citations represent complementary disclosures, repeated information or genuinely independent origins.

Completion, automatic compliance, content judgments and sampled source support should be read together. A completed run establishes that the generation path ended with an output. An automatic pass establishes the specified observable conditions. Reviewed content labels address the listed criteria under the stated procedure. None of these outcomes alone certifies every statement in a report. This interpretation applies equally to the successful examples and the retained failures.
'''
append_zh='''
# 附录 C. 案例定位与报告身份

以下案例均属于正式批次 20261020T032924986612Z，是已有报告而非新增运行。相应证据台账保存片段、偏移和哈希；标签保留为模型预评后作者确认的结果。

- NVIDIA 标准综合：T2_uploaded_only_r1_a001；比较变体：C_structure_r1_a001。比较变体对应 Q129–Q133，其中 S2、S4 分别指向 CFO 说明和年报利润表片段。
- AMD 简洁风格配对：T4_uploaded_only_r1_a001 与 C_style_r1_a001。Q137 检查业务分部范围和风险，Q138 检查风格、语气和语义深度。S5 结束于分部列表引入处，S6 包含毛利润调节信息。
- AMD 深度配对：T3_uploaded_only_r1_a001 与 C_depth_r1_a001。Q143 记录语义深度不确定；S3 提供计算例子中的取整收入数字，S6 提供软件讨论。
- 仅网络比较：T5_web_only_r1_a001。抽样陈述 C5 对应 Q015，判断为证据不足而非矛盾。

定位运行目录时，应在上述后缀前加上共同批次前缀。S2 等来源编号只在所属运行内有效，同一片段在另一报告中可能获得不同编号，因此不能把引用标记当作全局文档身份。

# 附录 D. 如何理解系统输出

原始报告记录生成器实际写出的内容，展示报告根据证据台账重建来源呈现，自动检查依据原始正文。因此，更便于阅读的展示版本不能追溯性地修复内容，也不能将失败条件变为通过。

读者可从正文引用进入实际片段，对照陈述的措辞、期间、单位与范围。片段缺少必要信息，应与片段明确反驳陈述区分；涉及计算时，应在来源标记有效之外单独核验关系与分母。多来源比较还需判断，两条引用对应的是互补披露、重复信息，还是确实独立的出处。

运行完成、自动合规、内容判断与抽样支持应结合阅读。完成说明生成流程结束并保留输出；自动通过说明规定的可观察条件成立；内容标签在所述程序下对应列出的标准。任何单项都不能认证整份报告每个陈述，这一解释同样适用于成功案例和保留的失败。
'''
for l in texts:
    texts[l]+=append_en if l=='en' else append_zh
    # Figure numbering: current overview 1, evaluated pipeline 2, UI 3.
    texts[l]=re.sub(r'(Figure|图) ([12])',lambda m:m[1]+' '+str(int(m[2])+1),texts[l])
overview={
'en':'''Figure 1 summarizes the current application's reporting contract. Source adapters feed evidence to a common generator, while structure, style and depth act as user controls. This conceptual view includes the later financial-source extension; Figure 2 separately identifies the pipeline used in the frozen evaluation.

![Current report-generator concept](figures/system_concept.png)

Figure 1. Conceptual overview of the current report generator. The allowed source mode determines which inputs are available. Source labels and paragraph marks are schematic. Financial APIs were added after the formal evaluation and are not part of its 21+3 runs.

''',
'zh':'''图 1 概括当前应用的报告要求：来源适配器向共同生成器提供证据，结构、风格和深度作为用户控制项。概念图包含后续金融来源扩展；图 2 单独说明冻结实验使用的流程。

![当前报告生成系统概念图](figures/system_concept.png)

图 1. 当前报告生成系统的概念总览。来源模式决定允许的输入；来源编号和段落线条均为示意。金融 API 在正式评测后加入，不属于原 21+3 次实验。

'''}
for l in texts:
    anchor='## 3.2 Architecture' if l=='en' else '## 3.2 系统架构'
    texts[l]=texts[l].replace(anchor+'\n\n',anchor+'\n\n'+overview[l])
    anchor='## 6.2 ' # place length visual after first results unit
    pos=texts[l].index(anchor)
    block=('''Figure 4 plots each main run's observed body length against its requested upper bound. The brief AMD condition is particularly clear: all three outputs exceed 500 words. Standard-depth conditions also have failures, so the problem is not confined to one request. The points are individual reports, not independent samples of a wider population.

![Body length relative to the requested upper bound](figures/length_compliance.png)

Figure 4. Body words divided by the applicable upper word limit for all 21 main runs. The dashed line marks 1.0; values above it exceed the upper limit. Each condition has three runs. T3 uses a 500-word upper limit; the other conditions use 1400. Colors indicate the saved automatic result, not factual accuracy.

''' if l=='en' else '''图 4 将每次主实验的正文长度与对应上限比较。AMD 简要条件的三份输出都超过 500 词，标准深度条件也有多份失败，因此问题并不限于一种请求。图中每个点代表一份报告，不是更广总体的独立样本。

![正文长度与要求上限的关系](figures/length_compliance.png)

图 4. 全部 21 次主实验的正文词数除以适用上限。虚线为 1.0，高于该线表示超长；每条件三次。T3 上限为 500 词，其余为 1400。颜色表示保存的自动结果，不表示事实准确性。

''')
    texts[l]=texts[l][:pos]+block+texts[l][pos:]
    anchor='## 6.5 '
    pos=texts[l].index(anchor)
    block=('''Figure 5 displays the three paired changes in body extent. Their different settings and single observations must be kept in view: these are not replicated estimates of a common treatment effect. In particular, concise style retains standard depth, whereas the depth pair changes the requested word interval.

![Matched-evidence customization pairs](figures/customization_pairs.png)

Figure 5. Body words in the three single-setting pairs, using the same evidence within each pair. Structure, style and depth are changed in separate tasks. A decrease or increase in length is an observed output difference, not a quality score. The brief-depth baseline is itself overlength.

''' if l=='en' else '''图 5 展示三组配对的正文篇幅变化。它们采用不同设置，每组只有一次变体观察，不是同一种处理效应的重复估计。尤其是简洁风格仍保持标准深度，深度配对才改变所要求的字数区间。

![相同证据下的定制配对](figures/customization_pairs.png)

图 5. 三组单设置配对的正文词数，每对内部使用相同证据。结构、风格、深度分别在不同任务中改变。篇幅增减是观察到的输出差异，不是质量分数；简要深度基准自身已超长。

''')
    texts[l]=texts[l][:pos]+block+texts[l][pos:]
    (ROOT/f'dissertation_draft_{l}.md').write_text(texts[l])
print('Integrated bilingual cases, discussion, appendices and figure references.')
