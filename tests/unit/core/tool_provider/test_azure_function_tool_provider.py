"""Unit tests for AzureFunctionToolProvider against a real local aiohttp server
(aiohttp.test_utils), exercising the actual HTTP transport rather than mocking internals:
success, tool-side failure (4xx with a JSON error body), timeout, and connection failure — all
must normalize into ToolResult(success=False, error=...), never raise.
"""

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.core.tool_provider.azure_function import AzureFunctionToolProvider
from src.tools.models import ToolRequest


async def _ok_handler(request: web.Request) -> web.Response:
    body = await request.json()
    return web.json_response(
        {
            "tool_name": "policy_lookup",
            "success": True,
            "data": {"echoed": body["tool_input"]},
            "correlation_id": body.get("correlation_id"),
        }
    )


async def _not_found_handler(request: web.Request) -> web.Response:
    return web.json_response({"error": "No synthetic policy found"}, status=404)


async def _timeout_handler(request: web.Request) -> web.Response:
    await asyncio.sleep(10)
    return web.json_response({"success": True})


def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/tools/policy_lookup", _ok_handler)
    app.router.add_post("/api/tools/missing_tool", _not_found_handler)
    app.router.add_post("/api/tools/slow_tool", _timeout_handler)
    return app


@pytest.fixture
async def server():
    srv = TestServer(_build_app())
    await srv.start_server()
    yield srv
    await srv.close()


async def test_successful_call_returns_parsed_tool_result(server: TestServer) -> None:
    base_url = str(server.make_url(""))
    provider = AzureFunctionToolProvider(base_url=base_url)

    result = await provider.execute(
        ToolRequest(
            tool_name="policy_lookup",
            tool_input={"policy_number": "SYN-POL-0001"},
            correlation_id="corr-1",
        )
    )

    assert result.success is True
    assert result.correlation_id == "corr-1"
    assert result.data == {"echoed": {"policy_number": "SYN-POL-0001"}}


async def test_http_error_status_normalizes_to_failed_result_with_body_error(
    server: TestServer,
) -> None:
    base_url = str(server.make_url(""))
    provider = AzureFunctionToolProvider(base_url=base_url)

    result = await provider.execute(
        ToolRequest(tool_name="missing_tool", tool_input={"policy_number": "SYN-POL-9999"})
    )

    assert result.success is False
    assert result.error == "No synthetic policy found"


async def test_timeout_normalizes_to_failed_result_not_a_raised_exception(
    server: TestServer,
) -> None:
    base_url = str(server.make_url(""))
    provider = AzureFunctionToolProvider(base_url=base_url, timeout_seconds=0.05)

    result = await provider.execute(ToolRequest(tool_name="slow_tool", tool_input={}))

    assert result.success is False
    assert result.error is not None
    assert "timed out" in result.error


async def test_connection_failure_normalizes_to_failed_result_not_a_raised_exception() -> None:
    provider = AzureFunctionToolProvider(base_url="http://127.0.0.1:1", timeout_seconds=1.0)

    result = await provider.execute(ToolRequest(tool_name="policy_lookup", tool_input={}))

    assert result.success is False
    assert result.error is not None
