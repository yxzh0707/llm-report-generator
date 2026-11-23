"""Evidence-bound v2 additions; keeps v1 and all formal results unchanged."""
from pathlib import Path
import re
BASE=Path(__file__).resolve().parents[1]/'manuscript'
OUT=BASE/'v2'
texts={l:(BASE/f'dissertation_draft_{l}.md').read_text() for l in ('en','zh')}

def before(lang, anchor, addition):
    assert texts[lang].count(anchor)==1, anchor
    texts[lang]=texts[lang].replace(anchor,addition.strip()+'\n\n'+anchor)

before('en','# 2. Related Work', '''
## 1.4 From a writing request to an evaluable reporting task

A report request contains several decisions that ordinary question answering can leave implicit. The user may specify the documents that are admissible, the period to be discussed, the intended reader and the form of the final document. A response can be accurate at the sentence level yet fail the request by omitting an important business area. Conversely, a complete-looking report can introduce an unsupported explanation while linking to a real source. The application therefore treats evidence selection, organization and compliance as related but distinct parts of the task.

The distinction matters in the selected financial setting. An annual filing supplies business descriptions and accounting disclosures; a quarterly announcement concentrates on recent performance. Combining them requires attention to the difference between annual and quarterly observations. A comparison between companies also requires the report to preserve each company's reporting period and categories. The intended output is an organized synthesis with explicit qualifications, rather than a sequence of unrelated source summaries. This requirement motivates the use of comparative sections and task-specific content review alongside basic citation checks.

Customization introduces another source of tension. A brief report has less space to cover risks and definitions, while a detailed report has more opportunity to introduce unsupported elaboration. A fixed section list may make the output easier to navigate but does not allocate the available words intelligently. These tensions give the evaluation a practical purpose: establish which parts of the reporting request the implemented system can meet, and locate the points at which a completed output still requires correction.

Three concrete artifacts carry the contribution. First, the application provides a common request and evidence interface across selected files and permitted web sources. Second, it makes the three customization dimensions explicit and connects them to inspectable output conditions. Third, a frozen collection of reports, evidence and judgments permits the measured outcomes to be checked without relying on a successful demonstration. The contribution is the design and evaluation of this application; the embedding model and the general language-generation capability are adopted components.

## 1.5 Organization of the dissertation

Chapter 2 positions the work in retrieval, multi-document synthesis, controllable writing and evidence assessment. Chapters 3 and 4 explain the reporting contract and its implementation, including the current financial-source and browser extensions. Chapter 5 defines the frozen evaluation and its review procedure. Chapter 6 presents aggregate results and examines selected reports in detail. Chapter 7 interprets the findings and identifies the limitations of both the system and the evaluation. Chapter 8 concludes with the capabilities established by the study and the improvements most directly motivated by its results.
''')
before('zh','# 2. 相关研究', '''
## 1.4 从写作要求到可评估的报告任务

报告请求包含一些普通问答容易省略的条件：哪些资料可以使用、讨论哪个时间段、面向什么读者，以及最终文档应如何组织。一份报告即使各句事实正确，也可能因为遗漏重要业务领域而没有完成任务。另一份报告则可能看似完整，并链接到真实来源，却在解释部分加入证据没有支持的联系。因此，本文将证据选择、内容组织和要求遵循视为相互关联但需要分别检查的环节。

金融资料能够具体呈现这些问题。年报包含业务描述和会计披露，季度公告集中说明近期业绩。两者的整合需要区分全年与季度指标；跨公司比较还要保留各自的财年和业务分类。期望的输出是围绕问题组织、说明必要差异的综合报告，而不是把几份摘要依次拼接。比较章节以及任务内容复核由此成为引用检查之外的必要部分。

定制也会引入约束之间的张力。简短报告能用于说明风险和定义的空间较少，详细报告则有更多机会产生没有依据的延伸解释。固定章节便于读者查找内容，但不会自动解决篇幅分配问题。实验因此需要回答一个具体问题：系统能满足报告请求中的哪些条件，又会在哪些位置出现“已生成但仍需修改”的结果。

本文的工作由三个具体产物体现。第一，应用通过共同的请求与证据接口连接选定文件和允许使用的网络来源。第二，将结构、风格和深度显式化，并连接到可检查的输出条件。第三，冻结的报告、证据和评审记录使结果能够脱离单次演示进行核查。贡献在于这一应用的设计与评估；embedding 模型和通用语言生成能力属于采用的已有组件。

## 1.5 论文组织

第 2 章讨论检索、多文档综合、可控写作及证据评估。第 3、4 章分别说明报告需求和实现，包括当前金融来源与浏览器扩展。第 5 章定义冻结实验与复核方法。第 6 章给出汇总结果并分析具体报告。第 7 章讨论系统和评估的局限，第 8 章总结已获得验证的能力与结果直接支持的改进方向。
''')

# Broaden the literature around the allocated problem, preserving existing references.
for lang in texts:
    texts[lang]=texts[lang].replace('## 2.3 Position of this study','## 2.6 Position of this study').replace('## 2.3 本文定位','## 2.6 本文定位')
before('en','## 2.6 Position of this study', '''
## 2.3 Multi-document and task-directed synthesis

Multi-News provides a large-scale setting for summarizing several news documents, together with a hierarchical approach that accounts for relevance and redundancy [7]. It establishes multi-document summarization as a task in which selecting complementary information matters. The present application shares that need, but its output is organized around a user request and explicit report sections. It does not train on Multi-News or report that dataset's benchmark scores.

QMSum frames summarization around a user's query and investigates locating relevant meeting spans before summarizing them [8]. Its domain differs from company disclosures, but the task formulation makes a useful distinction: the same long source can support different summaries depending on the question. In this project, the task description and configured retrieval queries determine which portions of the selected documents enter the evidence package. A file being available to the application does not imply that all its relevant contents reach the generator.

For a reporting application, there are at least three different meanings of source coverage. Access coverage concerns whether an allowed document can be retrieved. Representational coverage concerns whether selected excerpts from that document appear in the generation context. Substantive coverage concerns whether the final report addresses the task using sufficient information. These are analytical distinctions used in this dissertation, not new benchmark metrics. The implementation checks document identity and citation use, while the review assesses specified content requirements. Chapter 6 shows why the latter cannot be inferred from the former.

## 2.4 Controlling output and checking instructions

CTRLsum controls summaries through keywords and a control function, including applications to length and question-guided summarization [9]. It demonstrates a formulation in which user preferences are explicit inputs. This project uses a different mechanism: a deployed instruction-following model receives a structured reporting request and ordinary text instructions. There is no task-specific model training, learned controller or claim to reproduce CTRLsum's results.

IFEval focuses on instructions whose satisfaction can be checked programmatically, such as length and formatting requirements [11]. This provides a useful point of comparison for the present checks. A word-range condition gives a reproducible answer to a narrow question; it does not determine whether the explanation is insightful or whether the tone suits the reader. The application's checks are task-specific and are not an implementation of the IFEval benchmark.

Structure, style and depth also differ in how directly they can be observed. A heading sequence is explicit in the output. Style includes visible features such as bullets, but also judgments about register and clarity. Depth includes extent, coverage and explanation; only the first can be reduced to a word count here. The system exposes all three controls, while the evaluation keeps their observable proxies separate from content judgments. This separation avoids treating a longer answer as automatically deeper or a bullet list as automatically better suited to its purpose.

## 2.5 Long-form generation and report organization

STORM treats grounded long-form writing as a process that includes gathering information and constructing an outline before drafting. It uses perspective-guided questions and simulated conversations to support this preparation [10]. That approach is closely related to the present concern with organized synthesis, although the application here uses bounded report presets and selected evidence rather than an open-ended article-research procedure. No direct system comparison is conducted.

The practical choice in this dissertation is to make the reporting contract manageable and observable. Preset sections reduce the ambiguity of the requested organization; a fixed evidence package makes it possible to inspect what the model could use. This choice also limits the system: a preset cannot ensure that the most important evidence was selected, and a frozen package cannot acquire a missing fact during formal generation. The case analyses consequently examine both the benefit of explicit organization and the gaps that remain within an apparently well-formed report.
''')
before('zh','## 2.6 本文定位', '''
## 2.3 多文档与任务导向的综合

Multi-News 为多篇新闻的摘要提供了较大规模的数据集，并提出兼顾相关性与冗余的层次化方法 [7]。它所处理的问题与本系统的一个需求相通：多文档输入需要选择互补信息。本文输出进一步受到用户任务和报告章节的约束，没有使用 Multi-News 训练模型，也不报告该数据集上的基准分数。

QMSum 将摘要与用户查询联系起来，并研究先定位相关会议片段、再生成摘要的方法 [8]。其领域虽然不同，但任务定义说明，同一长文档可以根据问题产生不同摘要。在本项目中，任务描述与配置的检索查询决定选定文档的哪些部分进入证据包。应用能够访问某文件，并不意味着生成模型已经获得其中全部相关内容。

对报告应用而言，来源覆盖至少包含三种不同含义：访问覆盖关注允许的文件是否可检索；上下文覆盖关注该文件的哪些摘录进入生成输入；实质内容覆盖关注最终报告是否借助充分信息回答任务。这些是本文用于解释结果的区分，并非新增基准指标。实现检查文档身份和引用使用，复核则检查指定内容要求。第 6 章将展示，不能根据前两者直接推断最后一种覆盖。

## 2.4 输出控制与指令检查

CTRLsum 通过关键词和控制函数引导摘要，包含长度控制与问题引导摘要等应用 [9]。它说明用户偏好可以成为显式输入。本文采取不同实现：向已部署的指令遵循模型提供结构化请求和文本要求，没有训练任务专用模型或学习控制器，也没有复现 CTRLsum 的实验结果。

IFEval 关注可以用程序判断的指令，例如长度与格式条件 [11]。这为本系统的检查提供了参照：字数区间能够对一个范围明确的问题给出可复查的判断，但不能决定解释是否深入或语气是否适合读者。本文的检查依据自身报告任务制定，不属于 IFEval 基准的实现。

结构、风格和深度的可观察程度也不同。标题顺序直接存在于输出中；风格既包括项目符号等可见形式，也包括语体与清晰度判断；深度涉及篇幅、覆盖和解释，本文只有篇幅能直接化为字数条件。系统提供三个设置，评估则将代理指标与内容判断分开，避免把更长的回答直接视为更深入，或把项目符号直接视为更适合用户。

## 2.5 长文生成与报告组织

STORM 将有依据的长文写作分为资料搜集、提纲构建与起草等过程，通过不同视角的问题和模拟对话支持写作准备 [10]。这一工作与本文关注的有组织综合密切相关，但本系统采用有界的报告预设和选定证据，没有实现开放式文章研究过程，也没有开展两个系统的直接性能比较。

本文选择让报告要求保持可操作、可观察。预设章节减少了组织形式的歧义，固定证据包则便于检查模型能够使用什么。这一选择也有代价：章节预设不能保证重要证据已经被选中，冻结证据包不能在正式生成时继续获取遗漏事实。因此，案例分析同时讨论显式组织的作用，以及形式完整的报告中仍然存在的信息缺口。
''')

before('en','# 4. Implementation', '''
## 3.5 Design alternatives and boundaries

The central design decision is to retain a common generation path while varying the admissible evidence and the reporting request. Separate generators for document-only, web-only and hybrid tasks would make it harder to tell whether a difference arose from the source mode or from a different writing procedure. A shared path makes that boundary more explicit, although the frozen experiment still uses different evidence content across source conditions. Shared execution therefore supports interpretability without making the conditions causally equivalent.

Several simpler alternatives clarify what the implemented components contribute. Concatenating all selected files would remove the need to select passages, but the application would then have to accommodate the full text rather than the bounded evidence used here. Returning only the matched child chunks would retain focused matches but omit some adjacent context. Returning expanded parents uses more of the budget and may include irrelevant text. The selected approach fixes these costs through explicit limits and records the resulting passages. No experiment in this dissertation establishes an optimal chunk size or a quality advantage over these alternatives.

A prompt alone could ask the model to avoid external sources. The implemented source policy additionally removes incompatible evidence tools and prevents unauthorized input-file access through the exposed file interface. This design addresses the concrete paths available in the application. It is not a claim that the model has forgotten its pretraining knowledge or cannot generate an uncited statement. The report instructions and subsequent review remain necessary because tool restrictions govern acquisition, not every sentence the model may produce.

Similarly, a citation can be attached either to a discovered URL or to the passage actually opened. The latter is used here because it makes the relationship inspectable. A URL identifies a location; the saved passage identifies what was supplied during that run. The evidence ledger preserves both where available. Discovery results can help find evidence, but their existence alone does not establish that the report's factual claim is supported.

## 3.6 Sources as complementary views

Multi-source integration in this system has an operational layer and a semantic layer. The operational layer collects admissible excerpts under common source identifiers. The semantic layer is the model's synthesis of those excerpts into a report. The application implements the first directly and evaluates selected properties of the second. It does not contain a general-purpose financial reconciliation engine that automatically resolves all contradictory disclosures.

Three relationships between sources are relevant to the tasks. Complementary sources contribute different information, such as an annual business description and a recent quarterly result. Overlapping sources repeat a figure or explanation. Differently scoped sources describe related concepts using different periods, units or categories. The reporting instructions require distinctions between reported facts, calculations and interpretation, but actual preservation of these relationships must be checked in the output. A common source format is useful precisely because it keeps the origin of each excerpt available during that assessment.

The financial adapters extend this representation to structured records. An API response may preserve a metric name, unit and date more explicitly than a flattened table. Its provider identity, however, does not necessarily identify an independent underlying disclosure. A company filing retrieved as a document and a company-facts observation derived from filings may overlap in origin. The intended role of these adapters is to make relevant evidence accessible through the report system, not to inflate the count of independent confirmations.

## 3.7 User interaction and acceptance

The user-facing workflow begins with a task, selected files and reporting preferences. After submission, the interface separates execution activity from the final report. Once generation ends, the reader can inspect citations and check results before downloading the output. This supports a practical acceptance decision: whether the report addresses the request and whether its flagged limitations are tolerable for the intended use.

The interface therefore needs to expose an important intermediate outcome: generated but requiring review. A runtime error means no usable completion was established. A length failure means a document exists but violates a specific constraint. A missing factual basis is a content issue that may remain even when the automatic checks pass. Presenting these outcomes separately gives the reader more useful information than a single success badge. The two live browser examples in Section 6.6 demonstrate why this distinction is necessary.
''')
before('zh','# 4. 系统实现', '''
## 3.5 设计取舍与能力边界

核心选择是保留共同的生成流程，同时改变允许使用的证据和报告请求。如果仅文档、仅网络和混合任务分别采用不同生成器，观察到的差异就更难归因于来源还是写作流程。共同流程让这一边界更明确，不过正式实验中不同来源条件的证据内容仍然不同，因此不能据此将它们视为因果等价的条件。

若干较简单的方案有助于解释当前设计。把所有选定文件直接拼接起来，可以免去片段选择，却需要处理完整文本。只返回命中的子块，能够保持匹配集中，但可能缺少相邻解释；展开父块补充了上下文，也会消耗更多预算并引入不相关内容。当前方法以明确上限约束这些成本，并记录最终返回的正文。本文没有通过实验确定最优切片大小，也没有证明其优于这些替代方案。

仅用提示词也可以要求模型不要访问外部来源。本实现进一步移除不兼容的证据工具，并通过受限文件接口阻断额外输入文件读取。这覆盖的是应用实际暴露的访问路径，不能说明模型忘记了预训练知识，或不可能生成没有引用的句子。因此，来源获取限制之外仍需要报告指令和内容复核。

引用可以关联到发现的 URL，也可以关联到实际打开的片段。本文采用后者来保证可检查性：URL 指向资料位置，保存的片段说明该次运行究竟获得了什么。证据台账在可用时同时保留两者。发现结果可以用于继续寻找资料，但仅有链接并不能建立报告陈述与正文证据之间的支持关系。

## 3.6 来源的互补关系

系统中的多来源整合包含操作与语义两个层面。操作层将允许的摘录登记到共同来源表示中，语义层由模型把摘录综合为报告。应用直接实现前者，并通过实验评估后者的部分性质，没有实现自动解决全部披露冲突的通用财务对账引擎。

任务中主要涉及三类来源关系。互补来源分别提供信息，例如年报中的业务描述和近期公告中的季度结果；重叠来源重复某个数字或解释；口径不同的来源则使用不同期间、单位或分类描述相关概念。指令要求区分披露事实、计算和解释，但这些关系是否被正确保留，仍需检查输出。共同来源表示的作用，是在判断时能够找到每个片段的原始出处。

金融适配器将这种表示延伸到结构化记录。与展开后的表格相比，API 响应可能更明确地保留指标名、单位和日期，但 provider 身份不同并不意味着底层披露相互独立。作为文档获取的公司文件，与从申报材料整理的 company facts 记录可能具有共同来源。接入这些工具是为了提供相关证据，而不是增加表面上的独立印证数量。

## 3.7 用户交互与报告验收

用户从任务、选定文件和报告偏好开始操作。提交后，界面分别展示执行活动与报告；生成结束后，可以检查引用和约束结果，再下载文档。这支持一个实际判断：报告是否回答了请求，所标出的局限是否适合当前用途。

界面需要表达“已生成但需要复核”这一中间状态。运行错误意味着没有建立有效完成；长度失败意味着文档已经存在，但违反某个具体条件；事实依据不足则属于内容问题，即使自动检查通过也可能存在。分别展示这些结果，比单一成功标记更有帮助。6.6 节的两次真实浏览器运行体现了这种区分的必要性。
''')

before('en','# 5. Evaluation Methodology', '''
## 4.5 From a child hit to a cited passage

The retrieval path keeps a distinction between the object used to rank evidence and the object exposed for generation. After text normalization, each child has a document identity and character offsets, together with a parent identity. Similarity is computed for the child representation. The selected child's parent is then looked up, deduplicated and admitted subject to the shared context limit. Multiple child hits can therefore result in fewer distinct parent passages. Top-k is a limit on selected hits, not a promise of eight independent documents or eight distinct facts.

Where multiple retrieval queries are configured, the implementation merges their rankings round-robin and removes duplicate child IDs until the total hit limit is reached. This gives configured task facets opportunities to contribute evidence without assigning each query a separate full context budget. It does not guarantee that every facet has a relevant match. The saved retrieval record includes the queries, child scores, parent identities and represented documents, allowing a reviewer to distinguish selection from subsequent use.

The source entry is created from the final parent passage. Its start and end positions refer to the normalized source text, so slicing that text can recover the supplied evidence. This is important when interpreting a citation: a child may have matched a phrase about a business segment, while the parent also includes a definition that changes how that phrase should be understood. Conversely, the parent may still omit the table needed for an annual-performance claim. Location integrity shows that the evidence can be found again; it does not establish that the selected evidence was sufficient.

The cache serves a separate purpose. It avoids requesting the same embedding again for the same endpoint, model label and input text. Cache reuse saves service calls but does not make an old report a valid test of a new chunking policy. The evidence package, retrieval-version record and actual supplied passages determine which retrieval configuration a report can support as evidence. Formal generation in this study used the already prepared packages and did not refresh embeddings during the batch.

## 4.6 Runtime integration and source isolation

The task adapter registers retrieval and fixed-output tools with the existing execution engine. The engine owns the model cycle, provider interaction and execution limits. The report-specific layer supplies the request, source policy, evidence mapping and output conditions. This separation keeps source acquisition and report delivery within one controlled run rather than launching a second autonomous writer after retrieval.

Source isolation must hold beyond the visible tool list. The output interface accepts only the designated report and audit paths; it does not offer a general shell or an input-file browser. Uploaded-document selection is checked before retrieval, and web-only tasks omit the uploaded-document path. Cached vectors do not independently authorize a document: the selected-document scope still determines the chunks eligible for retrieval. These are concrete restrictions on the application's interfaces, not a formal proof of information-flow security.

Evidence registration and output saving are also separate actions. Retrieval adds source entries and the model may refer to those entries in its report. Saving requires the expected source classes to have been retrieved. The subsequent body-citation check determines whether the output actually cites them. In hybrid mode, having both tool classes available is therefore insufficient; the saved report must include body citations to both. This distinction is particularly relevant to a system that might otherwise list unused sources at the end of a report.

## 4.7 Engineering verification and its limits

Offline checks exercise deterministic properties: sentence and parent boundaries, recoverable text offsets, source-ID mapping, selected-document restrictions, fixed output paths and shared context budgets. Runtime fixtures test assembly and controlled failure behavior. Separate post-processing checks test that saved results can be summarized consistently and that review records are preserved. These checks answer implementation questions and do not score the prose generated by a real model.

Live development tasks then establish that the interfaces work with the configured services. They include document retrieval, two-company comparison and mixed evidence. The browser checks additionally cover upload, report viewing, citation access and downloads. The distinction between offline and live evidence is retained because a simulated timeout checks the application's response to an injected event, whereas a successful live request only establishes that the service returned on that occasion. Neither establishes a general service reliability estimate.

For the dissertation, these checks support the interpretation of the generation results. If an excerpt has a stable location and the output remains available after a failed constraint check, a content problem can be investigated rather than lost. The system's observability makes such investigation possible; it does not remove the need to perform it.
''')
before('zh','# 5. 实验方法', '''
## 4.5 从子块命中到实际引用片段

检索路径区分用于排序的对象与提供给模型的对象。规范化文本后，每个子块具有文档身份、字符区间和父块身份。相似度根据子块表示计算，命中后再查找父块、去重，并按共同上下文上限决定返回内容。因此，多个子块命中可能只产生较少的不同父块；top-k 限制的是选定命中数，并不保证八份独立文档或八项不同事实。

当配置多个检索查询时，实现按轮转顺序合并各自排名，移除重复子块 ID，直到达到总命中上限。这让配置的任务侧面有机会贡献证据，同时避免每条查询分别占用完整上下文预算，但不能保证每个侧面都存在相关匹配。检索记录保留查询、子块分数、父块身份和已覆盖文档，便于区分证据被选中与随后被使用两个步骤。

来源条目根据最终父块建立，其起止位置对应规范化正文，可以通过切片恢复模型实际获得的内容。子块可能因某个业务词语被匹配，父块则补充影响解释的定义；也可能仍然没有包含回答年度业绩所需的表格。因此，定位完整性只说明证据可以再次找到，并不能建立所选证据的充分性。

缓存解决的是另一个问题：同一端点、模型标签和输入文本无需重复请求 embedding。它可以减少服务调用，却不能使旧报告成为新切片策略的验证证据。只有证据包、检索版本记录和实际输入片段能够说明报告对应哪个配置。正式生成使用提前准备的证据包，没有在批次内刷新 embedding。

## 4.6 运行集成与来源隔离

任务适配器将检索与固定输出工具注册到已有执行引擎。引擎负责模型循环、provider 交互和运行限制，报告层提供请求、来源策略、证据映射与输出条件。来源获取和报告交付因此位于同一个有界运行中，无需在检索结束后另启一个自主写作流程。

来源隔离还要覆盖工具列表之外的路径。输出接口仅接受指定的报告和审计路径，不提供通用 shell 或输入文件浏览；上传文档的选定范围在检索前核验，web-only 任务不接入上传检索路径。已有缓存向量也不会自动授权某份文件，候选切片仍受选定文档集合限制。这些是对具体接口的约束，不属于信息流安全的形式化证明。

证据登记与报告保存是两个步骤。检索增加来源条目，模型可在正文引用这些条目；保存前要求必要来源类别已被检索，保存后的检查进一步判断正文是否实际引用。混合模式因此不能仅凭两类工具可用而通过，还必须在正文中引用两类来源，避免将未使用资料列在文末就算完成整合。

## 4.7 工程验证及其边界

离线检查覆盖句子与父块边界、字符位置恢复、来源编号映射、选定文档限制、固定输出路径和共同预算等确定性性质。运行 fixture 检查装配与受控故障行为，后处理检查则验证结果汇总一致性和评审记录保留。这些检查回答实现是否按合同工作，不直接评价真实模型生成的文字质量。

真实开发任务继续验证服务配置下的接口，包括文档检索、跨公司比较和混合证据；浏览器检查还覆盖上传、报告阅读、引用查看与下载。离线和真实验证分开记录，因为注入超时只检验应用如何处理指定事件，而一次真实成功只说明服务当时返回了结果，二者都不足以估计普遍服务可靠性。

这些验证为论文中的生成结果提供解释基础。如果摘录具有稳定位置，约束失败后的报告也仍然可用，就可以继续定位内容问题。可观察性让调查成为可能，却不能代替调查本身。
''')

before('en','# 6. Results', '''
## 5.5 Why these tasks and sources were selected

The six task definitions form a small progression in reporting demands. A single annual report tests selection and organization within one document. Adding a second disclosure introduces complementary and repeated material. Comparing two companies requires the report to organize evidence by a common question while preserving differences in period and categories. The hybrid task adds the requirement that both uploaded and web evidence contribute to the body. This progression gives each condition a reason to exist without attempting a broad industry benchmark.

The corpus was selected for inspectability. Public company disclosures provide named entities, dates, units and identifiable sections that can be checked against saved passages. The two companies also provide related subject matter for comparison. That similarity narrows the experiment: it does not test whether the design transfers to medical, legal or literary reports. The experiment concerns the reporting application on this corpus, rather than the completeness or neutrality of company disclosure as a representation of business reality.

The formal evidence packages hold selection constant within each repeated condition. This makes a repeated run interpretable as another generation from the same prepared input. It does not measure how often a fresh live search would return that input. The source-mode conditions also differ in actual evidence, so their outcome differences may reflect available facts and context composition as well as mode. A stronger source-mode effect estimate would require a separately designed matched-information comparison.

The customization pairs address a narrower question. Each retains the task and evidence of a specified main run while changing one request field. The structure pair compares two ways of organizing NVIDIA's two-document synthesis; it is not a new two-company experiment. The style pair changes presentation while retaining standard depth. The depth pair changes requested extent while retaining formal analytical style. This distinction prevents the common mistake of interpreting concise style and brief depth as the same setting.

## 5.6 Evaluation units and interpretation rules

The results have several denominators because they answer different questions. A run is the unit for completion, automatic compliance and strict success. A citation occurrence is the unit for checking whether a body marker names a registered source. A review item is the unit for a particular content or customization requirement. A sampled claim is the unit for evidence support. The 1239 citation occurrences do not constitute 1239 independent factual judgments, and repeated citations to one passage do not increase the number of independent sources.

Strict success is conjunctive: all required automatic conditions and applicable reviewed task/style conditions must hold. It is useful for identifying a report that meets the whole specified contract, but the aggregate conceals the failure mechanism unless accompanied by component results. A length failure alone can make a substantively adequate report fail. Equally, a report can satisfy the length limit yet fail the annual-performance requirement. Both outcomes are retained rather than averaged into an unexplained quality score.

The review uses the material actually supplied during generation. The original filing may contain an answer that was absent from the selected passage. Searching the complete filing afterwards could establish the real-world fact but would answer a different question from whether this report was supported by its available evidence. For the same reason, a fact supplied only by the task request is not automatically evidence from an allowed source. This rule is particularly important for period labels and compound statements.

The detailed examples in Chapter 6 were selected after examining the results to explain observed mechanisms. They are illustrative, not an additional random sample or a replacement for the frozen review. They preserve run identity and existing judgments. No additional report generation, label revision or change of thresholds is performed for the case analysis.
''')
before('zh','# 6. 实验结果', '''
## 5.5 任务与来源的选择理由

六个任务定义形成一个较小的需求递进。单年报任务检验文档内选择与组织；加入第二份披露后，系统需要处理互补和重复材料；跨公司比较要求按共同问题组织信息，同时保留期间与分类差异；混合任务进一步要求上传和网络证据都进入正文。每种条件因此对应具体报告需求，而不扩展成广泛的行业基准。

语料选择首先考虑可检查性。公开披露具有实体、日期、单位和可识别章节，便于与保存片段核对。两家公司在主题上的相关性也提供了比较基础，但同时缩小了实验范围：它不能检验设计是否适用于医学、法律或文学报告。研究评估的是系统在该语料上的表现，不是公司披露对真实经营活动的完整性或中立性。

同一条件的重复实验使用固定证据包，因此可解释为对相同准备输入的再次生成，而不能衡量实时搜索重复返回这些输入的概率。不同来源模式下证据内容也发生变化，结果差异可能来自可用事实和上下文组成。若要估计来源模式自身的作用，还需要另行设计信息量匹配的比较。

三组定制配对回答更窄的问题：保留指定主实验的任务和证据，只改变一个请求字段。结构配对比较 NVIDIA 两文档综合的组织方式，不是新增跨公司任务；风格配对保留标准深度，只改变表达形式；深度配对保留正式分析风格，只改变所要求的篇幅。因此，简洁风格与简要深度不能混为同一个设置。

## 5.6 评估单位与解释规则

结果使用不同分母，因为它们对应不同问题。运行是完成、自动合规和严格成功的单位；引用出现次数用于检查正文标记是否对应已登记来源；评审条目对应某项内容或定制要求；抽样陈述用于判断证据支持。1239 次引用不等于 1239 项独立事实判断，重复引用同一片段也不会增加独立来源数量。

严格成功要求所有必要自动条件以及适用的任务、风格复核同时成立。它适合识别符合完整要求的报告，但必须同时查看分项结果，否则无法解释失败原因。内容充分的报告可能仅因超长失败，长度合格的报告也可能没有回答年度业绩要求。本文分别保留这些情况，不将其平均为缺少解释的质量分数。

复核依据是生成时真正提供的材料。完整年报可能包含答案，但被选中的片段未必包含。事后搜索全文可以确认现实中的事实，却不能替代“该报告是否受到当时证据支持”的判断。同理，仅出现在任务描述中的事实也不能自动当作允许来源中的证据。期间标签和复合陈述尤其需要遵守这一规则。

第 6 章的详细案例在查看结果后选定，用于解释已经出现的问题。它们属于说明性案例，不构成新增随机样本，也不替代冻结复核；运行身份与既有判断均予保留。案例分析没有新增报告生成、改写标签或调整门槛。
''')

# Case analysis and figures are added by the companion revision script.
for lang in texts:
    texts[lang]=texts[lang].replace('# 7. Discussion and Conclusion','# 7. Discussion').replace('# 7. 讨论与结论','# 7. 讨论')
    texts[lang]=texts[lang].replace('## 7.4 Conclusion','# 8. Conclusion').replace('## 7.4 结论','# 8. 结论')
    refs='''[7] A. R. Fabbri, I. Li, T. She, S. Li and D. Radev (2019). Multi-News: A Large-Scale Multi-Document Summarization Dataset and Abstractive Hierarchical Model. Proceedings of ACL 2019, 1074–1084. https://aclanthology.org/P19-1102/

[8] M. Zhong et al. (2021). QMSum: A New Benchmark for Query-based Multi-domain Meeting Summarization. Proceedings of NAACL-HLT 2021, 5905–5921. https://aclanthology.org/2021.naacl-main.472/

[9] J. He, W. Kryscinski, B. McCann, N. Rajani and C. Xiong (2022). CTRLsum: Towards Generic Controllable Text Summarization. Proceedings of EMNLP 2022, 5879–5915. https://aclanthology.org/2022.emnlp-main.396/

[10] Y. Shao, Y. Jiang, T. A. Kanell, P. Xu, O. Khattab and M. S. Lam (2024). Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models. Proceedings of NAACL-HLT 2024, 6252–6278. https://aclanthology.org/2024.naacl-long.347/

[11] J. Zhou et al. (2023). Instruction-Following Evaluation for Large Language Models. arXiv:2311.07911v1. https://arxiv.org/abs/2311.07911v1
'''
    before(lang,'# Appendix A.' if lang=='en' else '# 附录 A.',refs)
    (OUT/f'dissertation_draft_{lang}.md').write_text(texts[lang])
print('Wrote bilingual v2 expansion.')
