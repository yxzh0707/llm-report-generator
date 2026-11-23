"""Create the prespecified review index without overwriting existing grades."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from prepare_audit import prepare
if __package__:
    from .review_validation import evidence_map
else:
    from review_validation import evidence_map


def link(label, target, document):
    relative=Path(os.path.relpath(target, document.parent)).as_posix()
    return f'[{label}]({quote(relative, safe="/")})'


def main(freeze):
    freeze=Path(freeze).resolve()
    rubric=json.loads((freeze/'rubric.json').read_text())
    ledger=json.loads((ROOT/'artifacts/experiments'/freeze.name/'ledger.json').read_text())
    index=ROOT/'docs/human_review_index.md'
    lines=['# 实际人工审计入口', '',
        '本页使用仓库相对链接。请在本地Markdown预览中打开；若聊天内预览无法跳转，可直接在Finder打开对应human_review目录。', '',
        '以下是冻结规则预先选定的四份正式报告，每份拟审5条事实，共20条。选择不因自动分数改变；重建入口不会代填判断。', '',
        '逐份打开审计包、原始报告与完整证据目录，核对原句与来源正文/区间，再填写同目录 review.json：actual_reviewer、selection_confirmed_by_actual_reviewer、judgment（supported / contradicted / insufficient）、reason。完成该份后设置 completed=true。原报告、候选条目和证据不能被改写或删掉。', '',
        '| 条件 | 原句与引用证据 | 完整上下文 | 可填写 JSON |', '|---|---|---|---|']
    chinese=ROOT/'docs/model_review_zh.html'
    if chinese.exists():
        lines[2:2]=[link('打开中文版逐题复核页（Astra high预评，待你确认）',chinese,index),
                    '中文页逐题提供原句、来源、证据译文和预评理由；实际人工确认仍需你完成。','']
    for sample in rubric['human_source_audit']['preselected']:
        cell=f"{sample['condition']}_r{sample['repetition']}"
        entry=next((r for r in ledger['entries'] if r['cell']==cell),None)
        if not entry or entry['status']=='started':
            lines.append(f'| {cell} | 缺失或仍运行，保留原抽样位置 | — | — |');continue
        local=ROOT/'artifacts/runs'/Path(entry['run_dir']).name
        run_dir=local if local.exists() else Path(entry['run_dir'])
        if not (run_dir/'human_review/review.json').exists():prepare(run_dir)
        catalog_path=run_dir/'human_review/evidence_catalog.md'
        catalog=['# 完整审计上下文', '', link('原始报告',run_dir/'raw_report.md',catalog_path)+' · '+link('可填写判断',run_dir/'human_review/review.json',catalog_path), '',
                 '以下仅为实际返回给模型的证据正文。原句无引用编号时也可在此检查支持；缺编号不能自动等同于事实不成立。若使用额外证据，在对应item填写reviewed_evidence_ids（例如 ["[S2]"]），判断和理由仍由实际评审者提供。', '']
        for identity,source in evidence_map(run_dir).items():
            catalog += [f'## {identity} — {source["document_id"]}', '',
                        f'来源类别：{source["source_kind"]}；字符区间：[{source["char_start"]}, {source["char_end"]})；excerpt SHA-256：{source["excerpt_sha256"]}。', '',
                        '```text',source['text'],'```','']
        catalog_path.write_text('\n'.join(catalog)+'\n')
        lines.append(f"| {cell} | "+' | '.join([
            link('原句与引用证据',run_dir/'human_review/review.md',index),
            link('原稿与全部证据',catalog_path,index),
            link('填写判断',run_dir/'human_review/review.json',index)])+' |')
    worksheet=ROOT/'artifacts/tables'/freeze.name/'human_content_worksheet.csv'
    lines+=['','内容覆盖、语气和语义深度另填 '+link('人工评分表',worksheet,index)+'。satisfied填true/false，并填写reason和actual_reviewer。未填项保持pending，不能按通过计算。', '',
        '若候选句只是报告范围说明或不适合作为重要事实，保留原item及其exact_claim/citation_ids/evidence，在该item增加selection_change，记录original_exact_claim、replacement_exact_claim和reason。替代句必须逐字出现在同一原稿正文中，仍占用原C1–C5位置；不能删除不利条目或换成另一份报告。引用与证据区间由汇总器从保存的来源映射重建。', '',
        '未带引用的句子若判定supported或contradicted，必须填写reviewed_evidence_ids指向完整证据目录中的实际来源。不要修改原evidence正文。部分完成可以保存，completed必须保持false。', '',
        '完成后执行：', '', '```bash',
        f'.venv-runtime/bin/python analysis/build_results.py --freeze artifacts/experiment_freezes/{freeze.name}',
        '```', '',
        '该重建入口保留既有人工作答。重新生成审计入口使用 analysis/prepare_reviews.py，已有review.json不会被覆盖。', '',
        '自动表格中的source linkage仅是链接启发式，不代表事实支持；来源审计只覆盖上述预选样本。']
    index.write_text('\n'.join(lines)+'\n')
    print(index)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True,type=Path)
    main(p.parse_args().freeze)
