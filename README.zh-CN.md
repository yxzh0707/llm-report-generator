# 基于大语言模型的报告生成系统

[English README](README.md)

本仓库收录一项硕士论文研究的项目源码和已记录的实验结果。系统结合上传文档、网页和 API 证据，按指定结构、风格和详略生成英文报告，记录引文、核验有证据支撑的计算，并提供本地界面供查阅和导出报告。

## 核验已记录的实验结果

核验脚本只需 Python 3 标准库。它会检查仓库文件的哈希，并根据已保存的评审记录复算主结果表。

```sh
python3 scripts/verify_results.py --check-manifest
```

主对照为两套系统提供相同的可用来源文本，并使用同一 Qwen3.8-27B 部署。在 8 个任务的首轮运行中，报告生成系统有 **8/8** 满足必需内容和输出约束，原生 Hermes 为 **3/8**。计入每个系统预先指定的 4 次重复运行后，结果分别为 **12/12** 和 **4/12**。

这些是来自两组公司配对、共四家公司的描述性结果。主对照控制了证据获取差异。正文评审采用匿名模型评审和 AI 辅助来源审计，尚无独立读者校准。详见[结果表](results/main_results.csv)和[复现说明](REPRODUCE.md)。

## 仓库内容

| 路径 | 内容 |
| --- | --- |
| `src/` | 报告任务、证据检索、引文、计算、检查和本地界面 |
| `configs/` 和 `.env.example` | 请求与环境配置样例 |
| `experiments/` 和 `analysis/` | 实验运行、分析及论文构建脚本 |
| `tests/` | 工程回归测试和合成夹具 |
| `results/` | 主对照逐项评审、汇总表和来源清单 |

## 接入获授权的运行时

报告生成需要 Python 3.12、兼容且已获授权的 AutoResearch 运行时，以及配置好的模型服务。该运行时提供 `autoresearch_agent_core`、`autoresearch_agent_langchain` 和 `autoresearch_frontier_finance`。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.lock.txt
.venv/bin/python -m pip install --no-deps -e /path/to/authorised-runtime
cp .env.example .env.local
# 在 .env.local 中配置自己的模型服务及凭据引用。
.venv/bin/python src/report_server.py --port 8767
```

本地界面地址为 `http://127.0.0.1:8767`。历史模型名称对应论文实验使用的部署。重跑历史实验还需要对应的冻结输入和源码快照。详见[公开范围](RELEASE_REVIEW.md)。

## 许可证

本仓库公开源码供查阅，作者暂未授予开源许可证。依赖及复用信息见 [NOTICE.md](NOTICE.md)。
