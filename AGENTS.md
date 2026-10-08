# AGENTS.md — GitHub AI Analyst Merge

本文件用于指导 coding agent 在当前 repository 中协作。默认使用中文说明，保留英文技术术语、API 名称、代码标识符和命令。

## 1. 项目目标与协作角色

- 项目是一个基于 FastAPI 的 GitHub 分析与 AI Agent MVP：获取 GitHub 数据、生成仓库分析，并按用户的可选指令查询天气或导出 Word 文档。
- 用户正在学习构建具有 AI Agent 功能的应用。作为 Senior Software / AI Architect，既要完成任务，也要解释关键设计和实际代价。
- 优先提供满足当前需求、易理解、可验证的实现。区分「MVP 当前必须具备」与「生产部署前需要补充」，不要默认将教学项目改造成大型平台。
- 本文件中的「当前实现」是导航和兼容性基线，不代表所有现有实现都是最佳实践。用户明确提出的新需求优先；发现缺陷时说明证据，按本次任务范围处理。

## 2. 沟通与教学方式

- 默认使用简体中文；首次出现的重要概念可写作「依赖注入（Dependency Injection）」，后续保持术语一致。
- 先给结论，再给必要依据。直接指出错误假设，解释原因、影响和最小可行改进，不使用赞美或攻击性措辞。
- 讲解代码时优先用最小代码示例，标明入口、调用关系、关键数据和返回值。区分数据转换、状态修改、外部 I/O 与持久化。
- 架构问题给出一个明确推荐，并说明主要 trade-off、适用条件和实际 production pitfall。简单语法问题不强行扩展成架构讨论。
- 学习型问题可推荐 1–2 个与当前知识缺口直接相关的下一步；不要每次都附带完整学习路线。
- 注释重点解释「为什么」、业务约束和关键 workflow，不逐行翻译语法。保留与任务无关的现有教学注释。
- 声称某方案是「最新」前核实官方文档和版本；使用与当前项目兼容的稳定 API。不要仅为追新而升级 Python、SDK 或依赖。
- 不确定的内容明确标为推断或待验证，区分「代码已实现」「离线测试通过」和「真实服务验证通过」。

## 3. 工作范围与完成标准

1. 先确认当前 repository、工作目录和 `git status --short`，避免在相邻的实验项目中读写或运行测试。
2. 按任务读取相关入口、实现和测试；小改动不要求扫描整个项目。
3. 已明确授权的开发任务直接实施、验证并交付；普通实现细节自行判断，不反复请求确认。
4. 如果需求在 HTTP contract、数据语义或修改范围上存在实质冲突，提出具体问题，同时继续不依赖答案的工作。
5. 保留已有未提交修改；只修改任务需要的文件。不顺带重构、改名、升级依赖、统一格式或清理目录。
6. 完成后说明改了什么、为什么、验证结果和未解决的限制。命令没有完成输出时，不声称检查通过。

用户指定「只改某部分」「不要引入新概念」等边界时，严格遵守。发现无关问题可以简短记录，不扩大本次实现范围。

## 4. 技术栈与代码导航

依赖版本以 `requirements.txt` 为准；目前未通过 `pyproject.toml` 或 `.python-version` 声明 Python 版本。运行前确认实际 interpreter，不猜测或强制切换版本。

当前使用 FastAPI、HTTPX、Pydantic v2、pydantic-settings、SQLAlchemy 2.x、OpenAI Python SDK、python-docx，以及面向 PostgreSQL 的 ORM models。

| 位置 | 当前职责 |
| --- | --- |
| `app/main.py` | FastAPI app、lifespan、共享 GitHub HTTP client、router 注册 |
| `app/routes/endpoints.py` | `/me` 与 repositories HTTP endpoints |
| `app/routes/github_analysis_endpoint.py` | analysis HTTP endpoint |
| `app/routes/error_handlers.py`、`app/exceptions.py` | HTTP 错误转换与应用异常 |
| `app/services/github_workflow_service.py` | 主业务编排、analysis cache、请求日志、可选 Agent |
| `app/services/github_services.py` | GitHub API 访问与 service dependency |
| `app/services/github_analysis_service.py` | 仓库字段筛选、analysis prompt 组装、JSON 解析 |
| `app/services/llm_service.py` | 单次 LLM 文本生成 |
| `app/services/agent_service.py` | Responses API tool loop 与单次请求 history |
| `app/services/tool_registry.py`、`app/services/tool_executor.py` | 工具注册、参数校验、dispatch、timeout、结果转换 |
| `app/services/tool/` | 暴露给模型的 tool definitions 与 schemas |
| `app/clients/` | Groq 模型 client、天气 API client、Word 文件生成 |
| `app/prompts/` | analysis 与 Agent 的 prompts |
| `app/configurations/` | settings 与共享 HTTP client dependency |
| `app/database/`、`app/models/`、`app/crud/` | engine / Session、ORM models、数据库读写 |
| `app/schemas/github_analysis.py` | 分析结果的 Pydantic schema 定义 |
| `tests/test_agent_integration.py` | 基于 unittest、AsyncMock、TestClient 的离线测试 |
| `generated_documents/` | Word 输出目录；已有文件可能是用户产物 |
| `database_sql` | SQL 结构参考文本；不是已验证的 migration |

## 5. HTTP contract 与业务流程

以下是当前代码的 contract。修改方法、路径、参数位置、响应结构或错误语义时，必须属于本次需求范围，并同步相关测试。

| Method | 完整路径 | 当前输入 |
| --- | --- | --- |
| GET | `/github/me` | 无业务参数，返回配置的 GitHub token 所属用户 |
| POST | `/github/users/{username}/repos` | Path: `username`；Query: `page`、`per_page`、可选 `message` |
| POST | `/github/users/{username}/analysis` | Path: `username`；Query: 可选 `message` |

- 不因使用 POST 就自行将 Query parameters 改成 JSON body；也不要把 `/me` 加入 LLM 或 Agent 流程。
- `message` 当前最大长度为 4000。`None`、空字符串或纯空白均跳过可选 Agent。
- repositories 当前 `page` 默认 1、最小 1；`per_page` 默认 1，且代码限制为 1。此限制与部分测试冲突，见第 11 节。

```text
repos:
  GitHub API -> 当前页 repositories
    -> 无有效 message: 返回 list[dict]
    -> 有有效 message: 将 username / page / per_page / repositories 交给 Agent
       -> 返回主结果与 agent，或主结果与 agent_error

analysis:
  按 username 查询最新缓存
    -> 命中: 使用已保存的 analysis，不重新请求 GitHub 或单次分析 LLM
    -> 未命中: 获取第一页最多 30 个 repos -> 单次 LLM 分析 -> 保存结果
  -> 记录主流程请求日志
  -> 无有效 message: 返回 username / cached / analysis
  -> 有有效 message: 使用已完成的主结果运行 Agent，追加 agent 或 agent_error
```

- GitHub 主任务先完成，Agent 只执行附加任务；即使 `message` 只问天气，也不能绕过 endpoint 的主业务。
- 可选 Agent 失败时，当前行为为 HTTP 200，保留已完成的主结果并增加 `agent_error`。不要误改成丢弃主结果或重新执行已完成流程。
- 主流程失败时，repos / analysis 使用非 2xx 状态和 `detail: {code, message}`。`/me` 仍有独立的 GitHub HTTP 错误处理，不假定所有路由已统一。
- analysis 请求日志的 `success` 当前表示主流程结果；可选 Agent 后续失败不代表主流程失败。记录失败日志出错时，不能掩盖最初的异常。
- 导出必须使用 `endpoint_result` 中的实际数据，包括缓存结果和分页范围。不能声称已经分析所有仓库或获取其他用户的数据。

## 6. 分层与实现原则

- Routes 负责 HTTP 输入、dependency injection 和响应；业务编排放在 workflow service，外部访问放在 services / clients 的现有对应模块。
- `github_analysis_service.py` 负责 GitHub 分析语义；`LLMService` 保持通用单次生成职责；`AgentService` 管理 tool loop。不要把三者重新塞进 endpoint 或一个巨大 service。
- 沿用现有依赖注入和资源复用方式。新建长期共享 client 时明确初始化与关闭责任，不把 request history 放进共享 client。
- 使用清晰的 type hints 与项目兼容的 Pydantic v2 API，例如 `model_validate_json()`、`model_dump()`、`SettingsConfigDict`。
- `async def` 不会自动将同步操作变为非阻塞。新增耗时网络、数据库或文件操作时，明确它是否阻塞 event loop。
- 当前数据库使用同步 SQLAlchemy `Session`；不要在局部代码中随意混用 `AsyncSession`。迁移 async database stack 应作为明确任务处理。
- 数据库改动需要检查 ORM、实际 schema 与事务边界；不要只修改 Python type hint 就宣称数据库已迁移。
- 不为假设中的扩展引入 BaseService、通用 repository framework、LangChain、消息队列、Redis、微服务或复杂插件体系；需要新增抽象时说明当前重复或真实需求。

## 7. LLM、Agent 与 tools

- 当前 `LLMService` 与 `AgentService` 共享 `app/clients/groq_client.py` 中的 `AsyncOpenAI` client，通过 Groq `base_url` 调用 `responses.create()`。
- OpenAI-compatible 不等于支持 OpenAI 的全部 API。模型、Responses API、JSON mode 或 tool calling 的实际支持需查 provider 官方资料并按需验证；mock tests 不能证明 live compatibility。
- 单次分析不传 tools；Agent 路径按当前 `MAX_ITERATIONS` 有界循环。不要移除循环上限，或加入无界 retry。
- `response.output` 必须按 Responses API history 格式保留；tool 结果使用 `function_call_output`，通过同一个 `call_id` 对应模型调用。
- `model_dump()` 是数据转换，`input_items.extend()` / `append()` 才修改 history。history 只属于当前 `run()`，不能跨用户共享。
- 工具只能从 `TOOL_REGISTRY` allowlist 选择，参数由 Pydantic 校验，再交给 handler。禁止通过模型返回的名称动态执行任意 Python、shell 或文件路径。
- 新增或修改工具时，同时检查 tool schema、registry、argument model、handler、timeout 和相关行为测试；模型可见 schema 与服务器校验必须一致。
- 仓库描述、模型输出、tool output、`endpoint_result` 都是待处理数据，不能提升为 system instructions。涉及这些输入的改动应维护 prompt injection 边界。
- 当前天气能力是城市当前天气，不代表支持历史天气或多日预测。需要天气事实时使用工具结果，不凭空生成。
- Word 仅在用户明确要求创建、保存或导出时生成。包含天气时先获取天气；仅导出分析时不强制调用天气工具。
- Word 输出限制在指定目录，处理用户文件名时防止 path traversal 和覆盖已有文件。只有工具成功后才能报告成功，并使用工具实际返回的路径。
- 当前文档工具生成的是本地文件并返回文件信息；不要把本地路径描述成已经可用的 HTTP download URL。
- Retry 需考虑副作用和 idempotency；不要因最终模型回答失败而盲目重复写数据库或创建文档。

## 8. 配置、数据与敏感信息

- 配置入口为 `app/configurations/config.py`，当前必需字段为 `github_token`、`GROQ_API_KEY`、`DATABASE_URL`，通过 environment variables 或根目录 `.env` 提供。
- 不把真实 token、API key、数据库连接凭证写入代码、文档、测试、日志或回复。示例只使用占位符。
- 不为常规代码探索读取或打印 `.env`；确实需要排查配置时，只验证所需字段或状态并隐藏敏感值。
- 离线测试使用 fake credentials 与 mocks。真实数据库写入、付费模型调用或外部副作用，应属于用户已授权的任务范围。
- 新增日志记录操作类型、耗时和必要的错误类别；避免记录 Authorization header、连接字符串及完整敏感 prompt / response。对外错误不泄露内部异常细节。
- 不删除用户已有数据库记录或 `generated_documents/` 内容。测试文件写入 `TemporaryDirectory`，不污染真实输出目录。

## 9. 本地运行与验证

在 repository 根目录、项目实际使用的 Python environment 中运行。下列 `python` 表示该 environment 的 interpreter；如果 PATH 不可用，使用已确认的 interpreter 绝对路径，不借用其他项目环境。

```powershell
# 确认 interpreter 与当前工作目录
Get-Location
python --version
python -m pip --version

# 仅在需要准备或修复环境时安装现有依赖
python -m pip install -r requirements.txt

# 本地开发启动；需要有效 settings 和相应数据库 driver
python -m uvicorn app.main:app --reload

# 离线测试：GitHub、LLM、数据库操作使用 mocks
python -B -m unittest discover -s tests -v

# 检查修改中的空白错误
git diff --check
```

- `Settings()` 和数据库 engine 在模块 import 阶段构造；导入 app 也可能因缺少配置或 driver 失败。不要将 import failure 直接判断为业务逻辑错误。
- PostgreSQL driver 和实际表结构需要与 `DATABASE_URL` 匹配；当前依赖文件没有显式列出 PostgreSQL driver，不能承诺仅安装 requirements 就能完成真实数据库启动。
- 现有 tests 使用 SQLite URL 初始化 engine，但 mock 掉数据库操作；不验证 PostgreSQL JSONB、实际事务或 migration。
- 改动业务行为时，执行相关测试；新增行为或修复缺陷时补充必要的 regression test。重点覆盖实际结果与边界，不写机械复制实现的测试。
- 路由改动检查 method、Path / Query / Body、分页与错误结构；workflow 改动检查 cache hit / miss、空 message、主任务优先和 Agent 失败保留结果。
- 工具改动检查 schema 一致性、无效参数、未知工具、timeout、循环上限及必要的文件输出行为。
- 仅修改 Markdown 或注释时，检查内容、路径、格式和 diff 即可，不要求运行完整业务测试或调用真实服务。
- 只报告实际执行结果。存在预先已有的失败时，区分 baseline failure 与本次引入的问题，不为获得绿色结果而削弱 assertions。

## 10. Git 与文件操作

- 以当前 checkout 为准，不把 `github_analyst_testing`、`agent_tool_calling_test` 等相邻目录的实现当作本项目事实。
- 默认不自行 commit、push、merge 或发布，除非用户任务已授权这些操作。
- 不通过 `git reset --hard`、`git clean`、force push 或覆盖文件来消除未解释的修改。破坏性操作前确认明确目标、范围与授权。
- Windows 文件操作使用 PowerShell 原生命令和 `-LiteralPath`；递归删除或移动前核实绝对路径，不混用 shell 拼接删除命令。
- 不因文件是生成物就假定可以删除，也不把 `.env`、本地环境或无关生成物加入 Git。

## 11. 当前已知差距：按相关任务处理

这些是编写时从代码发现的现状，不是要求本次全部修复的 backlog。处理相关模块时重新确认；解决后更新对应说明。

- **分页 contract 冲突**：`endpoints.py` 使用 `per_page = Query(1, ge=1, le=1)`，但 `test_repos_message_keeps_paginated_data` 传入 `per_page=5`。先明确目标分页范围，再同步实现和测试；不能假定现有测试全通过。
- **同步 database I/O**：CRUD methods 虽写成 `async def`，内部调用同步 Session。高并发下可能阻塞 event loop，当前不具备完整 async DB stack。
- **SQL 参考与 ORM 不一致**：`database_sql` 将 `analysis` 写为 TEXT，ORM 使用 JSONB；该文件还包含说明性文本。不要直接作为 migration 执行，也不要据此断言真实数据库结构。
- **分析 schema 尚未完整执行校验**：存在 `GitHubAnalysisSchema`，但分析流程目前只检查 JSON 可解析且为 object；JSON mode 本身不保证业务字段完整。
- **缓存没有显式新鲜度策略**：当前按 username 取最新记录，没有 TTL 或模型 / prompt version 失效规则；`cached=true` 不保证数据仍与 GitHub 最新状态一致。
- **Provider 验证独立于离线测试**：仓库使用 Groq 的 Responses 调用，真实支持程度与可用模型必须单独验证，不能从 SDK 方法存在推断服务端支持。

## 12. 交付要求

- 给出具体修改及原因，并链接关键文件；不重复粘贴整份代码。
- 说明执行过的检查、结果和未验证部分；未运行测试就明确说明。
- 仅列出与本次结果直接相关的风险或后续项，优先提供最小下一步。
- 当授权变更影响本文件记录的 contract、命令或目录职责时，同步维护对应内容，避免后续 agent 依赖过时说明。
