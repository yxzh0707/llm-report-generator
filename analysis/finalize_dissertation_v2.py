"""Apply audited bibliographic details and version metadata to v2 sources."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]/'manuscript/v2'
for lang in ('en','zh'):
 p=root/f'dissertation_draft_{lang}.md';s=p.read_text()
 s=s.split('# Appendix D.')[0] if lang=='en' else s.split('# 附录 D.')[0]
 s=s.replace('This is a more informative integration behavior than appending two document summaries, because the report assigns facts to a shared annual/quarterly organization and preserves the corresponding citations.', 'The report assigns facts from both documents to a shared annual/quarterly organization and preserves the corresponding citations.')
 s=s.replace('这种做法按照共同的年度、季度框架组织事实并保留引用，较直接拼接两份摘要更能展示信息整合过程。','报告按照共同的年度、季度框架组织两份资料中的事实，并保留相应引用。')
 s=s.replace('取整后的数值','经四舍五入的数值').replace('取整收入数字','经四舍五入的收入数值')
 s=s.replace('The output interface accepts only the designated report and audit paths; it does not offer a general shell or an input-file browser.', 'The model-facing writer accepts only the designated report path; the internal store also permits the audit artifact. Neither interface provides general shell access or arbitrary input-file browsing.')
 s=s.replace('输出接口仅接受指定的报告和审计路径，不提供通用 shell 或输入文件浏览；', '模型可调用的写入工具仅接受指定报告路径，内部存储另允许保存审计产物；两者均不提供通用 shell 或任意输入文件浏览。')
 s=s.replace('The 18 supported claims out of the separate 20-claim sample describe that sample only.', 'Across the prespecified 20-claim sample, which includes this item, 18 claims were supported; that count describes the sample only.')
 s=s.replace('独立统计的 20 条陈述中有 18 条受支持，只能说明该样本，不能推广到所有报告事实。', '包含该条目的预设 20 条陈述样本中，18 条获得支持；这一统计仅描述该样本，不能推广到所有报告事实。')
 s=s.replace('These are targeted evidence gaps, not reasons to expand the application into a general agent platform or train a new model.', 'These studies would address specific gaps in the current evidence.')
 s=s.replace('这些是具体证据缺口，无需因此扩展为通用 Agent 平台或训练新模型。', '这些研究可以针对性地补足当前证据。')
 s=s.replace('Advances in Neural Information Processing Systems, 33. https://arxiv.org/abs/2005.11401', 'Advances in Neural Information Processing Systems, 33, 9459–9474. https://papers.nips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html')
 s=s.replace('Proceedings of EMNLP 2020.', 'Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing, 6769–6781.')
 s=s.replace('arXiv:2402.03216.', 'arXiv:2402.03216v1.')
 s=s.replace('Text with Citations. Proceedings of EMNLP 2023.', 'Text with Citations. Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing, 6465–6488.')
 s=s.replace('Long Form Text Generation. Proceedings of EMNLP 2023.', 'Long Form Text Generation. Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing, 12076–12100.')
 s=s.replace('T. She, S. Li and D. Radev', 'T. She, S. Li and D. R. Radev')
 s=s.replace('Proceedings of ACL 2019,', 'Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics,')
 s=s.replace('Proceedings of NAACL-HLT 2021,', 'Proceedings of the 2021 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies,')
 s=s.replace('Proceedings of EMNLP 2022,', 'Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing,')
 s=s.replace('Proceedings of NAACL-HLT 2024,', 'Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers),')
 s=s.replace('The present system consequently uses an explicit parent-context budget.', 'The present system also uses an explicit parent-context budget as an engineering constraint.')
 if '[10] Y. Shao' in s:
  s=re.sub(r'\[(10|11)\]',lambda m:'['+('11' if m[1]=='10' else '10')+']',s)
 start=s.index('# References' if lang=='en' else '# 参考文献')
 end=s.index('# Appendix A.' if lang=='en' else '# 附录 A.')
 refs=re.findall(r'(?m)^\[(\d+)\] (.+)$',s[start:end])
 header='# References' if lang=='en' else '# 参考文献'
 s=s[:start]+header+'\n\n'+'\n\n'.join(f'[{n}] {t}' for n,t in sorted(refs,key=lambda v:int(v[0])))+'\n\n'+s[end:]
 p.write_text(s)
print('Applied citation audit corrections, with STORM [11] and IFEval [10].')
