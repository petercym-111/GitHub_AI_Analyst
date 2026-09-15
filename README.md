# GitHub Analyst + Tool Calling Agent

仅公开原有的三个 GitHub endpoints。仓库和分析接口通过可选的 `message`
执行 Agent 指令，使用 Responses API 循环、工具校验、天气查询和 Word 导出。

```text
GET /github/me
  -> GitHubService.get_user

GET /github/users/{username}/repos
  -> GitHubService.get_user_repos
  -> message 留空：返回原仓库列表
  -> message 有内容：当前仓库列表 -> Agent -> 原列表 + answer

POST /github/users/{username}/analysis
  -> get_or_create_analysis
       -> 查缓存；未命中：GitHub -> analyze_repositories -> LLMService.generate_text
       -> 校验结果、保存分析和请求日志
  -> message 留空：返回 {username, cached, analysis}
  -> message 有内容：当前分析结果 -> Agent -> 原结果 + answer

两个接口的 Agent 指令执行链：
get_agent_service -> AgentService.chat -> ToolExecutor.execute -> ToolRegistry
  get_weather         -> WeatherClient（原代码）
  get_github_me       -> GitHubService.get_user
  get_github_repos    -> GitHubService.get_user_repos
  get_github_analysis -> get_or_create_analysis
  get_word_doc        -> 解析 source_call_ids -> WordClient
```

核心边界：**HTTP route 与 Agent tool 调用相同的 service/use case**。
Agent 不向本机 HTTP endpoint 再发请求，也不直接调用 FastAPI route 函数。
`LLMService.generate_text` 继续负责分析所需的通用 JSON 文本调用；
`AgentService.chat` 负责工具编排，避免把 GitHub 业务塞回 LLM 客户端。

## 启动

在当前项目目录使用 Python 3.14 环境：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

继续使用现有 `.env` 的 `GITHUB_TOKEN`、`GROQ_API_KEY`、`DATABASE_URL`。
无需新增 API key；模型沿用 `openai/gpt-oss-120b`。
分析功能仍依赖已有 PostgreSQL 表（见 `database_sql`），启动代码不会自动创建表。
`requirements.txt` 为启动安装入口，旧 `requirement.txt` 也补齐了 Word 依赖；两者统一为 UTF-8。

打开 `http://127.0.0.1:8000/docs`，使用下面的三个 GitHub endpoints。
填写自由指令后，响应的 `answer` 包含 Agent 的回答；导出成功时可包含文件名和路径。
文件保存在本项目的 `generated_documents/`，属于服务端本地文件；目前没有 HTTP 下载接口。
同名文件再次导出时自动加后缀，避免覆盖已有文档。

## 在原 GitHub endpoint 中输入 Agent 指令

`/github/me` 保持原样。其余两个 endpoint 保留原输入，新增可选的 `message`：

| Endpoint | 原输入 | 新输入 |
| --- | --- | --- |
| `GET /github/users/{username}/repos` | `username`、`page=1`、`per_page=30` | `message` 查询参数文本框 |
| `POST /github/users/{username}/analysis` | `username` | JSON request body 中的 `message` |

在 Swagger 点 **Try it out** 后填写。仓库接口可在 `message` 中直接输入：

```text
把本页仓库完整写入 repos.docx，并简要说明这些仓库的用途。
```

分析接口保留上方的 `username` 输入，在新增的 JSON 编辑区填写：

```json
{
  "message": "把本次分析结果完整写入 analysis.docx，并用中文解释学习建议。"
}
```

省略 `message`、填写空字符串或纯空白，都跳过 Agent，返回原有数据结构。
POST 也允许省略整个 request body 或提交 `{}`。
填写有效指令时，仓库接口返回 `{username, page, per_page, repositories, answer}`；
分析接口保留 `{username, cached, analysis}` 并增加 `answer`。

执行路径：原 endpoint 获取结果 → 把该结果作为 Agent 上下文 → 执行自由指令。
该结果在本次请求中的引用是 `endpoint_result`，Word 可直接导出它，
不需要为了导出再取一遍同页仓库或重新生成分析。

输入 schema 校验：`message` 必须是字符串，最多 10000 个字符；POST 拒绝多余 JSON 字段。
不合法的输入返回 HTTP 422。分析输出也使用 `GitHubAnalysisSchema` 验证，
新结果在保存前校验，已有缓存在使用前校验；已知字段类型错误或缺失会作为分析失败处理。
额外分析字段及仓库对象原始字段会保留。

GET 保留查询参数形式，因为浏览器和 Swagger 对 GET request body 的支持不可靠：
[FastAPI request body](https://fastapi.tiangolo.com/tutorial/body/)。
仓库接口的查询参数会出现在 URL 中，不适合承载敏感内容。
当前按要求保留 GET 方法；部署为公共 API 时，应把会写文件的操作放在 POST 上。

## Word 的数据路径

保留 `get_weather_tool` 和 `get_word_doc_tool` 两个 Python schema 变量。
它们对模型公开的函数名仍然分别是 `get_weather` 和 `get_word_doc`。
新增工具为 `get_github_me`、`get_github_repos`、`get_github_analysis`。

```python
# 模型先调用数据工具；执行器保存本次请求中的原始返回值。
registry.results["call_profile"] = {
    "tool_name": "get_github_me",
    "result": {"login": "octocat", "bio": None},
}

# 模型随后发出的 Word 工具参数示例。
arguments = {
    "content": "GitHub 报告",             # 标题或补充说明
    "filename": "github_report.docx",
    "source_call_ids": ["call_profile"], # 引用本次请求中真实存在的 call_id
}

# ToolRegistry.get_word_doc 在 Python 中直接序列化原始数据，再交给 WordClient。
# 原始字段、嵌套对象、数组、null、布尔值和中文均保留，不要求模型重新抄写。
```

`source_call_ids` 可引用多个天气/GitHub 结果，不能引用未知 ID、其他请求的 ID
或 Word 创建结果。模型的 strict schema 要求此参数出现；不引用数据时传 `null`。
原来的 Python 调用 `get_word_doc(content=..., filename=...)` 仍然可用。
用户已粘贴的 endpoint JSON 也可通过 `content` 写入。

直接引用结果的优点是完整保留数据，代价是文档主要呈现原始 JSON，排版较简单。
`content` 自由文本路径仍经过模型，精确导出已获取的数据应使用 `source_call_ids`。

## 验证

```powershell
python -B -m unittest discover -s tests -v
```

测试会在导入应用前设置假凭据和 SQLite URL，再模拟数据库操作、GitHub 与模型调用。
不会连接真实数据库或外部 API，Word 只写临时目录，并使用 `python-docx` 读回验证内容。
覆盖四类独立导出、混合导出、两参数兼容、文件覆盖保护、缓存命中/未命中、失败日志、
严格参数校验、超时、Agent 错误码、完整 Responses 循环及 HTTP 依赖接线。
另外覆盖原 endpoint 的自由指令、空输入兼容、Swagger 字段定义、422 校验、
分析结构校验以及用当前 endpoint 结果生成 Word。

## MVP 边界

- 天气客户端及 schema 与源项目逐字节相同，包括地点选首个匹配、单位和返回字段。
- 每次带指令的 GitHub 请求使用独立 Agent 历史；当前接口结果直接传入本次指令上下文。
- `/me` 始终返回服务器配置的 GitHub token 所属用户；本项目仍是单账户 MVP。
- 仓库工具保留分页；分析沿用第一页最多 30 个仓库以及原有缓存策略，没有自动过期机制。
- Agent 最多 8 轮模型调用；普通工具保留 10 秒超时，含嵌套模型调用的分析工具为 120 秒。
- 数据库仍沿用同步 SQLAlchemy Session；工具顺序执行，不并发共享 Session。
  后续若处理较高并发，再学习异步数据库驱动与事务边界。
- Word 写入在线程中执行。协程超时不能强制终止已经开始的文件写入，因此超时后文件仍可能生成。
  当前没有导出任务队列或幂等重试机制。

Responses 循环保留模型全部 output，再追加带 `call_id` 的 `function_call_output`：
[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)。
Groq 当前要求客户端携带历史，不支持 `previous_response_id` / `store`：
[Groq Responses API](https://console.groq.com/docs/responses-api)。
离线测试不代表真实凭据、模型推理选择或部署数据库已通过端到端验证。
