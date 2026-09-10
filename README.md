# Green Claims Checker

AI-driven comparison, testing and greenwashing screening for a one-day CRO hackathon.

**English overview:** [Business context and end-to-end methodology](BUSINESS_AND_METHODOLOGY_SUMMARY.md).

**主路径：在 Databricks 中运行 Python，调用团队已有的 Azure OpenAI，在 Notebook 内展示审核结果。本机只需要浏览器，不需要 Python、Streamlit、Docker 或 Node.js。**

**公司电脑快速入口：** 打开 [Notebook](Green_Claims_Databricks.ipynb)，点击 **Download raw file** 下载，再导入 Databricks。也可以点击仓库的 **Code → Download ZIP** 获取完整项目。三分钟讲稿见 [PITCH_3_MINUTES.md](PITCH_3_MINUTES.md)。

## 明天怎么启动

1. 在 Databricks Workspace 中导入 `Green_Claims_Databricks.ipynb`，选择 Python compute。
2. 直接 Run All。代码、三家虚构公司的九条声明、对照披露和虚构演示规则已经内置，不需要下载其他文件。默认不调用模型。
3. 在末尾界面选择 A/B/C，点击 **Compare & screen**。先确认结果能展示。
4. 要运行 AI，在配置 cell 中填 `API_URL`（完整 chat/completions 地址）、`MODEL`（部署名）、`SECRET_SCOPE` 与 `SECRET_KEY`（Databricks secret 的名称，不是实际密钥）。再运行配置 cell，在界面选择 **Live AI**。
5. 要用新法规，选择 **Upload regulation**，上传 PDF/TXT/MD，填写版本标签。文件会替换虚构标准。再次点击 Compare 才会产生新结论。

`Green_Claims_Databricks.py` 是同一 Notebook 的 Databricks source 格式，作为 `.ipynb` 导入失败时的备选。两份 Notebook 都是自包含的，导入任意一份即可。

Notebook 的 `from __future__` 语句位于独立 cell 顶部，这是正常的；不要将多个 cell 直接拼成普通 Python 脚本执行。

## 本机没有 Python：如何预演

解压后双击 **`demo.html`**，用 Edge、Chrome、Firefox 或 Safari 打开。无需联网。

页面可以切换三组审核结果。这是明确标记的**预置案例演示**，没有实时 AI 调用，不会分析新法规。实时 AI 和上传法规在 Databricks Notebook 里完成。Notebook 还可导出真实运行的 `review.html`，下载后同样能在本机浏览器展示。

## 如果 Notebook 上传按钮或交互界面不工作

界面使用 Databricks 支持的 ipywidgets，但你们的 runtime、网络和浏览器设置可能限制它。本项目已保留不依赖 ipywidgets 的方案：

1. 在 Databricks 的 Workspace 或 Unity Catalog Volume 上传法规文件。
2. 在 Notebook 的 **Fallback** cell 设置 `RUN_FALLBACK = True`。
3. 填 `FALLBACK_CASE`、`FALLBACK_MODE`、`REGULATION_PATH` 与 `REGULATION_VERSION`。
4. 运行该 cell，用 `displayHTML` 展示结果。不需要部署网站或启动服务器。

文本/Markdown 法规不需要额外解析库。文本型 PDF 需要 `pypdf`；如果环境缺少且允许安装，可在单独的 Notebook cell 运行 `%pip install pypdf`，然后按环境提示重启 Python 并重跑。若不允许安装，先把需要的法规段落保存为 UTF-8 TXT/MD。扫描件不提供 OCR；无可提取文字的页会被报告，不会静默当成已分析。

## Azure OpenAI 连接

本项目用 Python 标准库发送一次 OpenAI-compatible Chat Completions HTTP 请求，无 SDK/Agent 框架依赖。请向组织者要**已经可用的完整推理 URL、部署名以及读取 credential 的方式**。

`AUTH_TYPE = "api-key"` 用于 Azure API-key header；`"bearer"` 用于团队提供的适当 bearer credential。这里不实现 Entra token 自动获取或刷新。若团队已有 Azure OpenAI SDK、Entra ID 或内部 gateway wrapper，把 `live_analysis()` 的 HTTP 调用部分替换成已获批的客户端，保留 prompt、返回 JSON 和校验逻辑。不要为一天的活动新搭认证系统。

实际密钥仅从 `dbutils.secrets.get()` 或 `AZURE_OPENAI_API_KEY` 环境变量读取。Notebook 不把密钥写进 HTML/JSON，也不显示服务端原始错误响应。Live AI 按钮会将声明、披露和选中的法规片段发送到配置的 endpoint。

没有凭据时只能运行离线演示；不会偷偷退回预置结果冒充真实 AI。

## 结果与引用

| 检查 | 输出 |
|---|---|
| Comparison | `supported` / `contradicted` / `insufficient_evidence` / `not_comparable` |
| Testing | 数字、时间、范围、绝对量与强度、目标与实际表现 |
| Screening | 每条声明的证据、解释和建议追问 |
| Regulation | `potential_issue` / `no_issue_identified` / `insufficient_information` / `not_assessed`，并附引用 |

“supported”仅表示与提供材料一致。缺少证据不等于声明为假，`no_issue_identified` 也不是合法合规认证。

每条法规引用包括**文件名、上传者填写的版本、PDF 物理页码或文本段落号、原文摘录**。报告还带文件 SHA-256，便于区分同名不同版本。页码是 PDF 文件第几页，不保证等于页脚印刷页码；长段落分片附 part 编号。

Python 校验引用 ID 和引文是否存在于当次分析的源文本中（忽略空白差异）。引用不存在时，相关结论降级。**这只验证引用存在，不证明它的语义相关性、模型推理或法律适用性正确。**

上传的版本不会联网核实是否最新、生效或适用于该公司。长法规超过约 30,000 字符上下文预算时，使用简单关键词筛选，显示使用的片段数；可能漏掉定义、例外和相关条款。单文件上限 10 MB、250 页、提取文本 500,000 字符。

模型输入中的文件内容被声明为不可信数据，不能作为指令执行。当前工具没有浏览器、执行 shell 或外部检索工具。提示注入防护不是绝对保证。

## 数据

| 案例 | 设计 | 预期 |
|---|---|---|
| A · Verdant Manufacturing | 强度冒充总量、60% 冒充全部、未来目标冒充已实现 | 3 个 contradicted |
| B · Blueleaf Consumer Goods | 区域证据支撑全球、公司数据支撑产品全生命周期、统计边界变化 | 2 个 insufficient_evidence，1 个 not_comparable |
| C · Clearpath Components | 口径、范围、年份与目标描述一致 | 3 个 supported |

所有公司和数值均为虚构。`data/demo_regulation.md` 是**虚构训练标准，不是真实法规**。`data/cases.json` 含人工预期结果；每家公司另外提供 claims/disclosure TXT。实时模型只收到声明和披露，不会收到预期答案。

离线模式是严格匹配预置案例的 fixture replay，文本修改后会要求使用 Live AI。法规上传在离线模式中只显示候选原文，不假装完成法规适用性分析。

## 文件结构

```text
Green_Claims_Databricks.ipynb   主交付：自包含 Notebook
Green_Claims_Databricks.py      同一 Notebook 的 Databricks source 格式
demo.html                      无 Python 的本机演示页
PITCH_3_MINUTES.md              英文 pitch 稿与现场操作顺序
documents.py                   PDF/TXT/MD 解析、选段、引用验证
engine.py                      输出校验、演示案例、报告
ai_client.py                   Azure-compatible HTTP 调用
render.py                      HTML 审核结果
notebook_ui.py                 上传、选择案例和按钮
data/                          三家公司和虚构规则
tests/test_workflow.py          自动化测试
build_samples.py                重建模拟数据
build_deliverables.py           从模块重建 Notebook 和 HTML
```

修改模块后，在有 Python 的环境中运行 `python build_deliverables.py`，让 Notebook 与模块保持一致。只修改数据生成脚本时，先运行 `python build_samples.py`。

## 验证记录

开发环境 Python 3.12，**15 项自动化测试通过**，包括 9 条声明的预置输出、无依据结论降级、法规替换、PDF 页码、HTML 转义、模拟 Azure-compatible HTTP 请求、以及自包含 Notebook 的执行。

```bash
python -m unittest discover -s tests -v
```

PDF 测试使用已安装的 pypdf；未安装时该测试跳过。**未访问真实 Azure endpoint，也未在你们的 Databricks workspace 中验证 UI。**这些测试验证程序行为，不代表在真实绿色声明上的检测准确率。

## GitHub

本项目目标仓库：[yulun1992/cro_hackathon_greenwashing](https://github.com/yulun1992/cro_hackathon_greenwashing)。项目包含代码、数据、Notebook、HTML 演示页和测试。向团队分享 Notebook 时先清除输出和上传的 widget 状态，避免连同实际材料一起提交。

## 官方参考

- Databricks ipywidgets: https://learn.microsoft.com/en-us/azure/databricks/notebooks/ipywidgets
- Notebook 导入: https://learn.microsoft.com/en-us/azure/databricks/notebooks/notebook-export-import
- displayHTML: https://learn.microsoft.com/en-us/azure/databricks/notebooks/notebook-media
- pypdf 文本提取: https://pypdf.readthedocs.io/en/stable/user/extract-text.html
