import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy.exc import SQLAlchemyError

# Offline tests: never contact the real GitHub, model provider or database.
os.environ.update(github_token="test", GROQ_API_KEY="test", DATABASE_URL="sqlite://")

from fastapi.testclient import TestClient
from docx import Document

from app.main import app
from app.database.dependencies import get_db
from app.services.github_services import get_github_service
from app.services.llm_service import LLMService
from app.services.agent_service import AgentService
from app.services.tool_executor import ToolExecutor
from app.clients.word_doc_client import WordClient
from app.services import github_workflow_service as analysis_route
from app.exceptions import (AgentLoopLimitError, EmptyModelResponseError,
                            InvalidModelResponseError, ToolArgumentError,
                            ToolExecutionError, ToolTimeoutError, UnknownToolError)
from app.services.tool_registry import TOOL_REGISTRY, ToolDefinition
from app.services.tool_registry import WeatherArguments
from app.services.tool.tool_schemas import TOOLS


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.github = SimpleNamespace(get_user_repos=AsyncMock(return_value=[{"name": "demo"}]),
                                      get_user=AsyncMock(return_value={"login": "me"}))
        self.llm = LLMService()
        self.llm.client = SimpleNamespace(responses=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(output_text='{"summary":"ok"}'))))
        self.agent = AgentService()
        self.agent.run = AsyncMock(return_value={"answer": "done", "documents": []})
        app.dependency_overrides.update({get_github_service: lambda: self.github,
                                        get_db: lambda: None, LLMService: lambda: self.llm,
                                        AgentService: lambda: self.agent})
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_http_contract_and_me(self):
        paths = app.openapi()["paths"]
        self.assertIn("get", paths["/github/me"])
        self.assertNotIn("get", paths["/github/users/{username}/repos"])
        params = paths["/github/users/{username}/repos"]["post"]["parameters"]
        self.assertEqual({p["name"] for p in params}, {"username", "page", "per_page", "message"})
        params = paths["/github/users/{username}/analysis"]["post"]["parameters"]
        self.assertEqual({p["name"] for p in params}, {"username", "message"})
        self.assertEqual(self.client.get("/github/me").json(), {"login": "me"})
        self.assertEqual(self.client.get("/github/users/test/repos").status_code, 405)
        self.assertEqual(self.client.post("/github/users/test/repos", params={"page": 0}).status_code, 422)

    def test_repos_empty_message_skips_agent(self):
        for message in (None, "", "  "):
            response = self.client.post("/github/users/test/repos", params={} if message is None else {"message": message})
            self.assertEqual(response.json(), [{"name": "demo"}])
        self.agent.run.assert_not_awaited()

    def test_repos_message_keeps_paginated_data(self):
        response = self.client.post("/github/users/test/repos", params={"page": 2, "per_page": 5, "message": "weather and Word"})
        self.assertEqual(response.json()["repositories"], [{"name": "demo"}])
        self.github.get_user_repos.assert_awaited_once_with("test", 2, 5)
        context = self.agent.run.call_args.kwargs["endpoint_result"]
        self.assertEqual(context["page"], 2)

    def test_analysis_cached_and_fresh_with_optional_messages(self):
        for cached in (True, False):
            for message in ("", "weather", "export analysis to Word"):
                with self.subTest(cached=cached, message=message):
                    self.agent.run.reset_mock()
                    self.llm.client.responses.create.reset_mock()
                    value = SimpleNamespace(id=1, analysis={"summary": "ok"}) if cached else None
                    with patch.object(analysis_route.GitHubAnalysisCRUD, "get_by_username", AsyncMock(return_value=value)), \
                         patch.object(analysis_route.GitHubAnalysisCRUD, "create", AsyncMock(return_value=SimpleNamespace(id=1))), \
                         patch.object(analysis_route.AnalysisRequestLogCRUD, "create", AsyncMock()):
                        response = self.client.post("/github/users/test/analysis", params={"message": message})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["analysis"], {"summary": "ok"})
                    self.assertEqual(response.json()["cached"], cached)
                    self.assertEqual(self.agent.run.await_count, int(bool(message)))
                    self.assertEqual(self.llm.client.responses.create.await_count, int(not cached))
                    if not cached:
                        self.assertNotIn("tools", self.llm.client.responses.create.call_args.kwargs)

    def test_agent_failure_preserves_repos(self):
        self.agent.run.side_effect = RuntimeError("tool failed")
        with self.assertLogs("app.services.github_workflow_service", level="ERROR"):
            response = self.client.post("/github/users/test/repos", params={"message": "weather"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["repositories"], [{"name": "demo"}])
        self.assertIn("agent_error", response.json())

    def test_agent_failure_preserves_cached_analysis(self):
        self.agent.run.side_effect = RuntimeError("tool failed")
        with patch.object(analysis_route.GitHubAnalysisCRUD, "get_by_username", AsyncMock(
                return_value=SimpleNamespace(id=1, analysis={"summary": "ok"}))), \
             patch.object(analysis_route.AnalysisRequestLogCRUD, "create", AsyncMock()) as log, \
             self.assertLogs("app.services.github_workflow_service", level="ERROR"):
            response = self.client.post("/github/users/test/analysis", params={"message": "Word"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["analysis"], {"summary": "ok"})
        self.assertIn("agent_error", response.json())
        self.assertTrue(log.call_args.kwargs["success"])

    def test_specific_optional_errors_preserve_core_results(self):
        cases = [
            (UnknownToolError(), "UNKNOWN_TOOL"),
            (ToolArgumentError(), "TOOL_ARGUMENT_ERROR"),
            (ToolTimeoutError(), "TOOL_TIMEOUT"),
            (ToolExecutionError(), "TOOL_EXECUTION_ERROR"),
            (EmptyModelResponseError(), "EMPTY_MODEL_RESPONSE"),
            (AgentLoopLimitError(), "AGENT_LOOP_LIMIT"),
        ]
        for error, code in cases:
            with self.subTest(code=code):
                self.agent.run.side_effect = error
                with self.assertLogs("app.services.github_workflow_service", level="ERROR"):
                    response = self.client.post("/github/users/test/repos", params={"message": "weather"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["agent_error"]["code"], code)
                self.assertEqual(response.json()["repositories"], [{"name": "demo"}])

    def test_github_failures_are_mapped_at_endpoint(self):
        request = httpx.Request("GET", "https://example.test/repos")
        cases = [
            (httpx.HTTPStatusError("private detail", request=request,
                                  response=httpx.Response(404, request=request)), 404, "GITHUB_API_ERROR"),
            (httpx.ReadTimeout("private detail"), 504, "GITHUB_TIMEOUT"),
            (httpx.ConnectError("private detail"), 502, "GITHUB_CONNECTION_ERROR"),
        ]
        for error, status, code in cases:
            with self.subTest(code=code):
                self.github.get_user_repos.side_effect = error
                response = self.client.post("/github/users/test/repos")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["detail"]["code"], code)
                self.assertNotIn("private detail", response.text)
        self.agent.run.assert_not_awaited()

    def test_model_and_database_errors_reach_endpoint(self):
        request = httpx.Request("POST", "https://example.test/responses")
        cases = [
            (APITimeoutError(request=request), 504, "MODEL_TIMEOUT"),
            (RateLimitError("private detail", response=httpx.Response(429, request=request), body=None), 503, "MODEL_RATE_LIMIT"),
            (APIConnectionError(request=request), 502, "MODEL_CONNECTION_ERROR"),
            (APIStatusError("private detail", response=httpx.Response(500, request=request), body=None), 502, "MODEL_API_ERROR"),
            (SQLAlchemyError("private detail"), 500, "DATABASE_ERROR"),
            (InvalidModelResponseError(), 502, "INVALID_MODEL_RESPONSE"),
            (RuntimeError("private detail"), 500, "INTERNAL_ERROR"),
        ]
        for error, status, code in cases:
            with self.subTest(code=code), \
                 patch.object(analysis_route.GitHubAnalysisCRUD, "get_by_username", AsyncMock(side_effect=error)), \
                 patch.object(analysis_route.AnalysisRequestLogCRUD, "create", AsyncMock()) as log:
                response = self.client.post("/github/users/test/analysis")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["detail"]["code"], code)
                self.assertNotIn("private detail", response.text)
                self.assertFalse(log.call_args.kwargs["success"])

    def test_failure_log_does_not_hide_original_error(self):
        with patch.object(analysis_route.GitHubAnalysisCRUD, "get_by_username", AsyncMock(side_effect=httpx.ReadTimeout("timeout"))), \
             patch.object(analysis_route.AnalysisRequestLogCRUD, "create", AsyncMock(side_effect=SQLAlchemyError("db failed"))), \
             self.assertLogs("app.services.github_workflow_service", level="ERROR"):
            response = self.client.post("/github/users/test/analysis")
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"]["code"], "GITHUB_TIMEOUT")


def call(name, arguments, call_id):
    data = {"type": "function_call", "name": name,
            "arguments": json.dumps(arguments), "call_id": call_id}
    return SimpleNamespace(**data, model_dump=lambda **kwargs: data)


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def test_advertised_schemas_match_server_validation(self):
        # Explicit JSON schemas and Pydantic validation must accept the same shape.
        def constraints(value):
            if isinstance(value, dict):
                return {key: constraints(item) for key, item in value.items()
                        if key not in {"title", "description"}}
            if isinstance(value, list):
                return [constraints(item) for item in value]
            return value

        self.assertEqual({tool["name"] for tool in TOOLS}, set(TOOL_REGISTRY))
        self.assertEqual(len(TOOLS), len(TOOL_REGISTRY))
        for tool in TOOLS:
            with self.subTest(tool=tool["name"]):
                self.assertEqual(tool["type"], "function")
                self.assertTrue(tool["strict"])
                self.assertEqual(
                    constraints(tool["parameters"]),
                    constraints(TOOL_REGISTRY[tool["name"]].arguments.model_json_schema()),
                )

    async def test_weather_then_word_loop_and_real_document(self):
        agent = AgentService()
        calls = [
            SimpleNamespace(output=[call("get_weather", {"location": "Tokyo", "units": "celsius"}, "w")], output_text=""),
            SimpleNamespace(output=[call("create_doc_word", {"content": "分析 ok; Tokyo 25 C", "filename": "../report.docx"}, "d")], output_text=""),
            SimpleNamespace(output=[], output_text="Created"),
        ]
        history = []
        async def respond(**kwargs):
            history.append(copy.deepcopy(kwargs["input"]))
            return calls.pop(0)
        agent.client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(side_effect=respond)))
        with TemporaryDirectory() as folder, \
             patch.object(WordClient, "OUTPUT_DIR", Path(folder)), \
             patch("app.services.tool_registry.WeatherClient.get_weather", AsyncMock(return_value={"temperature": 25})):
            result = await agent.run(message="weather and analysis to Word", endpoint_result={"analysis": "ok"})
            path = Path(result["documents"][0]["path"])
            self.assertEqual(path.parent, Path(folder))
            self.assertEqual(Document(path).paragraphs[0].text, "分析 ok; Tokyo 25 C")
        self.assertEqual([i["call_id"] for i in history[2] if i.get("type") == "function_call_output"], ["w", "d"])
        self.assertEqual(json.loads(history[0][1]["content"])["endpoint_result"], {"analysis": "ok"})

    async def test_loop_limit_and_empty_response(self):
        agent = AgentService()
        agent.client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(
            return_value=SimpleNamespace(output=[], output_text=""))))
        with self.assertRaisesRegex(EmptyModelResponseError, "empty"):
            await agent.run(message="hello", endpoint_result={})
        agent.client.responses.create.return_value = SimpleNamespace(
            output=[call("get_weather", {}, "w")], output_text="")
        agent.tool_executor.execute = AsyncMock(return_value={"type": "function_call_output", "call_id": "w", "output": "{}"})
        with self.assertRaisesRegex(AgentLoopLimitError, "maximum"):
            await agent.run(message="weather", endpoint_result={})
        self.assertEqual(agent.tool_executor.execute.await_count, agent.MAX_ITERATIONS)

    async def test_tool_validation(self):
        executor = ToolExecutor()
        for name, arguments in (("unknown", {}), ("get_weather", {"location": "Tokyo", "units": "bad"}),
                                ("create_doc_word", {"content": "hi", "filename": "a", "extra": True})):
            with self.assertRaises(UnknownToolError if name == "unknown" else ToolArgumentError):
                await executor.execute(call(name, arguments, "invalid"))

    async def test_registry_dispatch_and_tool_errors(self):
        executor = ToolExecutor()
        arguments = {"location": "Tokyo", "units": "celsius"}
        handler = AsyncMock(return_value={"ok": True})
        # A new name works without changing the executor's code.
        with patch.dict(TOOL_REGISTRY, {"test_tool": ToolDefinition(
            handler=handler, arguments=WeatherArguments, description="Test"
        )}):
            result = await executor.execute(call("test_tool", arguments, "test"))
            self.assertEqual(json.loads(result["output"]), {"ok": True})
            handler.assert_awaited_once_with(**arguments)
            for failure, expected in (
                (TimeoutError(), ToolTimeoutError),
                (httpx.ReadTimeout("timeout"), ToolTimeoutError),
                (ValueError("failed"), ToolExecutionError),
            ):
                handler.side_effect = failure
                with self.assertRaises(expected):
                    await executor.execute(call("test_tool", arguments, "test"))

    async def test_invalid_analysis_output(self):
        from app.services.github_analysis_service import analyze_repositories
        llm = SimpleNamespace(generate_text=AsyncMock())
        for content in ("not JSON", "[]"):
            llm.generate_text.return_value = content
            with self.assertRaises(InvalidModelResponseError):
                await analyze_repositories([], llm)


if __name__ == "__main__":
    unittest.main()
