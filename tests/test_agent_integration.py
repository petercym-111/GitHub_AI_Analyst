"""Offline integration checks: no real credentials, database, or persistent files."""

import asyncio
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Override before importing app settings; never use the developer's real database.
os.environ["GITHUB_TOKEN"] = "offline-test-token"
os.environ["GROQ_API_KEY"] = "offline-test-key"
os.environ["DATABASE_URL"] = "sqlite://"

import httpx
from docx import Document
from fastapi.testclient import TestClient
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from openai.types.responses import ResponseFunctionToolCall, ResponseReasoningItem

from app.clients.weather_client import WeatherClient
from app.clients.word_doc_client import WordClient
from app.configurations.agent import get_agent_service
from app.database.dependencies import get_db
from app.main import app
from app.routes.endpoints import get_me, get_repos
from app.routes.github_analysis_endpoint import analyze_user_repositories
from app.schemas.endpoint_instruction import EndpointInstruction
from app.services.agent_service import (
    AgentLoopLimitError, AgentService, EmptyModelResponseError,
)
from app.services.github_analysis_workflow import get_or_create_analysis
from app.services.github_services import GitHubService, get_github_service
from app.services.LLM_services import LLMService
from app.services.tool_executor import (
    ToolArgumentError, ToolExecutionError, ToolExecutor, ToolTimeoutError, UnknownToolError,
)
from app.services.tool_registry import ToolRegistry
from app.services.tools.tool_schemas import TOOLS


PROFILE = {"login": "octocat", "name": "测试用户", "bio": None, "public_repos": 1}
REPOS = [{"name": "demo", "description": "天气工具", "topics": ["ai"], "private": False}]
ANALYSIS = {
    "overall_profile": "测试分析",
    "main_technologies": ["Python"],
    "project_categories": ["AI"],
    "repository_quality": ["MVP"],
    "learning_recommendations": ["Integration testing"],
}
WEATHER = {"location": "Kuala Lumpur", "temperature": 30.5, "unit": "celsius"}
WORKFLOW = "app.services.github_analysis_workflow."


def tool_call(name, arguments, call_id="call_1"):
    return ResponseFunctionToolCall(
        type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id,
    )


def model_response(*output, text=""):
    return SimpleNamespace(output=list(output), output_text=text)


def make_registry(word_client=None):
    github = SimpleNamespace(
        get_user=AsyncMock(return_value=copy.deepcopy(PROFILE)),
        get_public_user=AsyncMock(return_value=copy.deepcopy(PROFILE)),
        get_user_repos=AsyncMock(return_value=copy.deepcopy(REPOS)),
    )
    llm = SimpleNamespace(
        MODEL_NAME=LLMService.MODEL_NAME,
        generate_text=AsyncMock(return_value=json.dumps(ANALYSIS)),
    )
    weather = SimpleNamespace(get_weather=AsyncMock(return_value=copy.deepcopy(WEATHER)))
    return ToolRegistry(github, llm, Mock(), weather_client=weather, word_client=word_client)


class ExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_four_sources_export_exact_payloads(self):
        """HTTP and tools share outputs; DOCX round-trip retains every source field."""
        with tempfile.TemporaryDirectory() as directory:
            registry = make_registry(WordClient(Path(directory)))
            executor = ToolExecutor(registry)
            with patch(WORKFLOW + "GitHubAnalysisCRUD.get_by_username", AsyncMock(return_value=None)), \
                 patch(WORKFLOW + "GitHubAnalysisCRUD.create", AsyncMock(return_value=SimpleNamespace(id="saved"))) as save, \
                 patch(WORKFLOW + "AnalysisRequestLogCRUD.create", AsyncMock()) as log:
                cases = [
                    ("get_weather", {"location": "Kuala Lumpur", "units": "celsius"}, WEATHER),
                    ("get_github_me", {}, await get_me(registry.github_service)),
                    ("get_github_repos", {"username": "octocat", "page": 2, "per_page": 10},
                     (await get_repos(EndpointInstruction(username="octocat"), 2, 10, registry.github_service))["repositories"]),
                    ("get_github_analysis", {"username": "octocat"},
                     await analyze_user_repositories(EndpointInstruction(username="octocat"), registry.github_service, registry.llm_service, registry.db)),
                ]
                for index, (name, args, expected) in enumerate(cases):
                    with self.subTest(tool=name):
                        call_id = f"source_{index}"
                        output = await executor.execute(tool_call(name, args, call_id))
                        self.assertEqual(output["call_id"], call_id)
                        self.assertEqual(json.loads(output["output"]), expected)
                        exported = await executor.execute(tool_call("get_word_doc", {
                            "content": "", "filename": f"{name}.docx", "source_call_ids": [call_id],
                        }, f"export_{index}"))
                        result = json.loads(exported["output"])
                        self.assertTrue(result["success"])
                        content = Document(result["path"]).paragraphs[0].text
                        self.assertEqual(json.loads(content.split("\n", 1)[1]), expected)
                self.assertEqual(save.await_count, 2)
                self.assertEqual(log.await_count, 2)
                self.assertEqual(save.call_args.kwargs["repo_snapshot"], REPOS)

            combined = await registry.get_word_doc("完整报告", "combined.docx", [f"source_{i}" for i in range(4)])
            content = Document(combined["path"]).paragraphs[0].text
            self.assertTrue(content.startswith("完整报告"))
            for _, _, payload in cases:
                self.assertIn(json.dumps(payload, ensure_ascii=False, indent=2), content)

    async def test_legacy_content_and_filename_call_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            executor = ToolExecutor(make_registry(WordClient(Path(directory))))
            result = await executor.execute(tool_call("get_word_doc", {
                "content": "Kuala Lumpur: 30.5°C", "filename": "weather",
            }))
            saved = json.loads(result["output"])
            self.assertEqual(saved["filename"], "weather.docx")
            self.assertEqual(Document(saved["path"]).paragraphs[0].text, "Kuala Lumpur: 30.5°C")

    async def test_exports_are_confined_and_existing_files_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = WordClient(Path(directory))
            first = await writer.create_document("first", "../../report.docx")
            second = await writer.create_document("second", r"..\..\report.docx")
            self.assertEqual(Path(first["path"]).parent, Path(directory))
            self.assertEqual(Path(second["path"]).parent, Path(directory))
            self.assertNotEqual(first["path"], second["path"])
            self.assertEqual(Document(first["path"]).paragraphs[0].text, "first")
            self.assertEqual(Document(second["path"]).paragraphs[0].text, "second")

    async def test_unknown_cross_request_and_document_sources_are_rejected(self):
        writer = SimpleNamespace(create_document=AsyncMock())
        first, second = make_registry(writer), make_registry(writer)
        await ToolExecutor(first).execute(tool_call("get_github_me", {}, "private_source"))
        second.results["document"] = {"tool_name": "get_word_doc", "result": {"path": "x"}}
        for source in ["missing", "private_source", "document"]:
            with self.subTest(source=source), self.assertRaises(ToolArgumentError):
                await ToolExecutor(second).execute(tool_call("get_word_doc", {
                    "content": "", "filename": "x.docx", "source_call_ids": [source],
                }))
        writer.create_document.assert_not_awaited()

    async def test_empty_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ToolArgumentError):
                await ToolExecutor(make_registry(WordClient(Path(directory)))).execute(
                    tool_call("get_word_doc", {"content": " ", "filename": "x.docx"})
                )
            self.assertEqual(list(Path(directory).iterdir()), [])


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_analysis_matches_endpoint_without_fetching_or_generating(self):
        registry = make_registry()
        cached = SimpleNamespace(id="cached-id", analysis=ANALYSIS)
        with patch(WORKFLOW + "GitHubAnalysisCRUD.get_by_username", AsyncMock(return_value=cached)), \
             patch(WORKFLOW + "GitHubAnalysisCRUD.create", AsyncMock()) as save, \
             patch(WORKFLOW + "AnalysisRequestLogCRUD.create", AsyncMock()) as log:
            http_result = await analyze_user_repositories(EndpointInstruction(username="octocat"), registry.github_service, registry.llm_service, registry.db)
            tool_result = await registry.get_github_analysis("octocat")
            self.assertEqual(tool_result, http_result)
            self.assertEqual(tool_result, {"username": "octocat", "cached": True, "analysis": ANALYSIS})
            registry.github_service.get_user_repos.assert_not_awaited()
            registry.llm_service.generate_text.assert_not_awaited()
            save.assert_not_awaited()
            self.assertEqual(log.await_count, 2)
            self.assertTrue(log.call_args.kwargs["success"])

    async def test_analysis_failure_rolls_back_and_logs_original_error(self):
        registry = make_registry()
        failure = RuntimeError("database unavailable")
        with patch(WORKFLOW + "GitHubAnalysisCRUD.get_by_username", AsyncMock(side_effect=failure)), \
             patch(WORKFLOW + "AnalysisRequestLogCRUD.create", AsyncMock()) as log:
            with self.assertRaises(RuntimeError) as caught:
                await registry.get_github_analysis("octocat")
            self.assertIs(caught.exception, failure)
            registry.db.rollback.assert_called_once()
            self.assertFalse(log.call_args.kwargs["success"])
            self.assertEqual(log.call_args.kwargs["error_message"], str(failure))

    async def test_failure_logging_does_not_replace_model_error(self):
        registry = make_registry()
        failure = APITimeoutError(request=httpx.Request("POST", "https://example.test"))
        with patch(WORKFLOW + "GitHubAnalysisCRUD.get_by_username", AsyncMock(side_effect=failure)), \
             patch(WORKFLOW + "AnalysisRequestLogCRUD.create", AsyncMock(side_effect=RuntimeError("DB"))), \
             self.assertLogs("app.services.github_analysis_workflow", level="ERROR"):
            with self.assertRaises(APITimeoutError) as caught:
                await ToolExecutor(registry).execute(tool_call("get_github_analysis", {"username": "octocat"}))
            self.assertIs(caught.exception, failure)

    async def test_github_service_forwards_auth_and_pagination(self):
        async def upstream(request):
            self.assertEqual(request.headers["Authorization"], "Bearer offline-token")
            if request.url.path == "/user":
                return httpx.Response(200, json=PROFILE)
            self.assertEqual(request.url.path, "/users/octocat/repos")
            self.assertEqual(dict(request.url.params), {"page": "2", "per_page": "10"})
            return httpx.Response(200, json=REPOS)

        async with httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(upstream)) as client:
            registry = make_registry()
            registry.github_service = GitHubService("offline-token", client)
            self.assertEqual(await registry.get_github_me(), PROFILE)
            self.assertEqual(await registry.get_github_repos("octocat", 2, 10), REPOS)

    async def test_weather_uses_original_geocoding_forecast_and_units(self):
        real_client = httpx.AsyncClient
        for units in ("celsius", "fahrenheit"):
            requests = []

            async def upstream(request):
                requests.append(request)
                if request.url.host == "geocoding-api.open-meteo.com":
                    self.assertEqual(dict(request.url.params), {"name": "Kuala Lumpur", "count": "1"})
                    return httpx.Response(200, json={"results": [{"latitude": 3.1, "longitude": 101.6}]})
                self.assertEqual(request.url.host, "api.open-meteo.com")
                self.assertEqual(request.url.params["temperature_unit"], units)
                self.assertEqual(request.url.params["current_weather"], "true")
                return httpx.Response(200, json={"current_weather": {"temperature": 30.5}})

            with patch("app.clients.weather_client.httpx.AsyncClient", side_effect=lambda: real_client(transport=httpx.MockTransport(upstream))):
                self.assertEqual(await WeatherClient().get_weather("Kuala Lumpur", units),
                                 {"location": "Kuala Lumpur", "temperature": 30.5, "unit": units})
            self.assertEqual(len(requests), 2)


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_responses_loop_fetches_exports_and_preserves_reasoning(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = make_registry(WordClient(Path(directory)))
            calls = []
            reasoning = ResponseReasoningItem(id="rs_1", type="reasoning", summary=[])
            responses = iter([
                model_response(reasoning, tool_call("get_github_me", {}, "profile"),
                               tool_call("get_weather", {"location": "Kuala Lumpur", "units": "celsius"}, "weather")),
                model_response(tool_call("get_word_doc", {
                    "content": "报告", "filename": "report.docx", "source_call_ids": ["profile", "weather"],
                }, "word")),
                model_response(text="文档已生成"),
            ])

            async def create(**kwargs):
                calls.append(copy.deepcopy(kwargs))
                return next(responses)

            agent = AgentService(ToolExecutor(registry), client=SimpleNamespace(responses=SimpleNamespace(create=create)))
            self.assertEqual(await agent.chat("导出个人资料和天气"), "文档已生成")
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0]["model"], LLMService.MODEL_NAME)
            self.assertIn(reasoning.model_dump(mode="json", exclude_none=True), calls[1]["input"])
            outputs = [item for item in calls[2]["input"] if item.get("type") == "function_call_output"]
            self.assertEqual([item["call_id"] for item in outputs], ["profile", "weather", "word"])
            saved = json.loads(outputs[-1]["output"])
            text = Document(saved["path"]).paragraphs[0].text
            self.assertIn(json.dumps(PROFILE, ensure_ascii=False, indent=2), text)
            self.assertIn(json.dumps(WEATHER, ensure_ascii=False, indent=2), text)

    async def test_plain_answer_does_not_execute_tools(self):
        executor = ToolExecutor(make_registry())
        executor.execute = AsyncMock()
        client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=model_response(text="Hello"))))
        self.assertEqual(await AgentService(executor, client=client).chat("Hi"), "Hello")
        executor.execute.assert_not_awaited()

    async def test_empty_answer_and_iteration_limit_raise_distinct_errors(self):
        for response, error in [
            (model_response(text=" "), EmptyModelResponseError),
            (model_response(tool_call("get_github_me", {})), AgentLoopLimitError),
        ]:
            client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=response)))
            agent = AgentService(ToolExecutor(make_registry()), client=client)
            agent.MAX_ITERATIONS = 2
            with self.subTest(error=error), self.assertRaises(error):
                await agent.chat("test")
            self.assertLessEqual(client.responses.create.await_count, 2)

    async def test_arguments_are_validated_before_execution(self):
        registry = make_registry()
        executor = ToolExecutor(registry)
        invalid = [
            ("get_weather", "{broken"),
            ("get_weather", "[]"),
            ("get_weather", '{"location":"KL","units":"kelvin"}'),
            ("get_weather", '{"location":42,"units":"celsius"}'),
            ("get_github_me", '{"extra":true}'),
            ("get_github_repos", '{"username":"octocat","page":0,"per_page":101}'),
            ("get_github_repos", '{"username":"octocat","page":"2"}'),
            ("get_github_analysis", '{"username":"../me"}'),
        ]
        for name, arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ToolArgumentError):
                await executor.execute(SimpleNamespace(name=name, arguments=arguments, call_id="bad"))
        registry.weather_client.get_weather.assert_not_awaited()
        registry.github_service.get_user.assert_not_awaited()
        registry.github_service.get_user_repos.assert_not_awaited()
        self.assertEqual(registry.results, {})
        with self.assertRaises(UnknownToolError):
            await executor.execute(tool_call("delete_database", {}))

    async def test_http_timeout_and_execution_timeout_have_same_contract(self):
        registry = make_registry()
        registry.tools["get_github_me"] = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        executor = ToolExecutor(registry)
        with self.assertRaises(ToolTimeoutError):
            await executor.execute(tool_call("get_github_me", {}))

        async def slow():
            await asyncio.sleep(1)

        registry.tools["get_github_me"] = slow
        executor.TOOL_TIMEOUT = 0.001
        with self.assertRaises(ToolTimeoutError):
            await executor.execute(tool_call("get_github_me", {}))


class RouteTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_only_three_github_endpoints_are_exposed(self):
        with TestClient(app) as client:
            schema = client.get("/openapi.json").json()
            operations = {(path, method) for path, methods in schema["paths"].items() for method in methods}
            self.assertEqual(operations, {
                ("/github/me", "get"), ("/github/users/repos", "post"),
                ("/github/users/analysis", "post"),
            })
            self.assertEqual(set(schema["components"]["schemas"]), {
                "EndpointInstruction", "GitHubAnalysisResponse", "GitHubAnalysisSchema",
                "HTTPValidationError", "RepositoryAgentResponse", "ValidationError",
                "AgentError",
            })

    def test_agent_error_contracts_on_repositories_endpoint(self):
        registry = make_registry()
        app.dependency_overrides[get_github_service] = lambda: registry.github_service
        request = httpx.Request("POST", "https://example.test")
        cases = [
            (UnknownToolError(), 502, "UNKNOWN_TOOL"),
            (ToolArgumentError(), 502, "TOOL_ARGUMENT_ERROR"),
            (ToolTimeoutError(), 504, "TOOL_TIMEOUT"),
            (ToolExecutionError(), 500, "TOOL_EXECUTION_ERROR"),
            (EmptyModelResponseError(), 502, "EMPTY_MODEL_RESPONSE"),
            (AgentLoopLimitError(), 500, "AGENT_LOOP_LIMIT"),
            (APITimeoutError(request=request), 504, "MODEL_TIMEOUT"),
            (RateLimitError("rate", response=httpx.Response(429, request=request), body=None), 503, "MODEL_RATE_LIMIT"),
            (APIConnectionError(request=request), 502, "MODEL_CONNECTION_ERROR"),
            (APIStatusError("upstream", response=httpx.Response(500, request=request), body=None), 502, "MODEL_API_ERROR"),
        ]
        for error, status, code in cases:
            with self.subTest(code=code):
                service = SimpleNamespace(chat=AsyncMock(side_effect=error))
                app.dependency_overrides[get_agent_service] = lambda: service
                with TestClient(app) as client:
                    response = client.post("/github/users/repos", json={"username": "octocat", "message": "test"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["agent_error"]["code"], code)
                self.assertEqual(response.json()["repositories"], REPOS)

    def test_real_dependency_wiring_runs_repositories_to_document(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = make_registry()
            app.dependency_overrides[get_github_service] = lambda: registry.github_service
            app.dependency_overrides[get_db] = lambda: registry.db
            with patch("app.clients.groq_client.groq_client.responses.create", AsyncMock(side_effect=[
                model_response(tool_call("get_word_doc", {
                    "content": "", "filename": "repos.docx", "source_call_ids": ["endpoint_result"],
                }, "doc")),
                model_response(text="done"),
            ])), patch.object(WordClient, "OUTPUT_DIR", Path(directory)):
                with TestClient(app) as client:
                    response = client.post("/github/users/repos", json={"username": "octocat", "message": "Export these repositories"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {
                "username": "octocat", "page": 1, "per_page": 30,
                "repositories": REPOS, "answer": "done",
            })
            registry.github_service.get_user_repos.assert_awaited_once_with("octocat", 1, 30)
            content = Document(Path(directory) / "repos.docx").paragraphs[0].text
            self.assertEqual(json.loads(content.split("\n", 1)[1]), REPOS)

    def test_schemas_registry_and_server_validation_are_aligned(self):
        from app.schemas.tool_arguments import TOOL_ARGUMENT_MODELS
        names = {tool["name"] for tool in TOOLS}
        self.assertEqual(names, set(make_registry().tools))
        self.assertEqual(names, set(TOOL_ARGUMENT_MODELS))
        for tool in TOOLS:
            self.assertTrue(tool["strict"])
            self.assertFalse(tool["parameters"]["additionalProperties"])
            self.assertEqual(set(tool["parameters"]["required"]), set(tool["parameters"]["properties"]))


if __name__ == "__main__":
    unittest.main()
