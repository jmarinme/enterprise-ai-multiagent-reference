"""Unit tests for DurableClaimsWorkflowProvider against a real local aiohttp server simulating
the Durable Functions HTTP API (starter + statusQueryGetUri polling) — exercising the actual
start/poll transport, not mocking internals."""

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.core.workflow_provider.durable import DurableClaimsWorkflowProvider
from src.core.workflow_provider.models import ClaimsWorkflowInput

_STATE: dict[str, list[str]] = {}


def _workflow_input() -> ClaimsWorkflowInput:
    return ClaimsWorkflowInput(
        correlation_id="corr-1",
        conversation_id="conv-1",
        user_id="user-1",
        policy_number="SYN-POL-0001",
        event_date="2026-08-01",
        event_location="CDMX",
        loss_type="collision",
        loss_description="Fender bender",
        contact_name="Juan Pérez",
        contact_phone="555-0100",
    )


async def _start_completed_immediately(request: web.Request) -> web.Response:
    base = str(request.url.origin())
    return web.json_response({"statusQueryGetUri": f"{base}/status/completed"})


async def _status_completed(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "runtimeStatus": "Completed",
            "output": {
                "success": True,
                "claim_reference": "SYN-CLM-2026-0099",
                "adjuster_name": "Synthetic Adjuster A",
            },
        }
    )


async def _start_pending_then_completed(request: web.Request) -> web.Response:
    base = str(request.url.origin())
    return web.json_response({"statusQueryGetUri": f"{base}/status/eventually"})


async def _status_eventually(request: web.Request) -> web.Response:
    calls = _STATE.setdefault("eventually", [])
    calls.append("x")
    if len(calls) < 3:
        return web.json_response({"runtimeStatus": "Running"})
    return web.json_response(
        {"runtimeStatus": "Completed", "output": {"success": True, "claim_reference": "SYN-CLM-2026-0100"}}
    )


async def _start_failed(request: web.Request) -> web.Response:
    base = str(request.url.origin())
    return web.json_response({"statusQueryGetUri": f"{base}/status/failed"})


async def _status_failed(request: web.Request) -> web.Response:
    return web.json_response({"runtimeStatus": "Failed"})


async def _start_rejects(request: web.Request) -> web.Response:
    return web.json_response({"error": "bad request"}, status=400)


async def _start_slow(request: web.Request) -> web.Response:
    await asyncio.sleep(10)
    return web.json_response({})


def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/orchestrators/completed_workflow", _start_completed_immediately)
    app.router.add_get("/status/completed", _status_completed)
    app.router.add_post("/api/orchestrators/eventually_workflow", _start_pending_then_completed)
    app.router.add_get("/status/eventually", _status_eventually)
    app.router.add_post("/api/orchestrators/failed_workflow", _start_failed)
    app.router.add_get("/status/failed", _status_failed)
    app.router.add_post("/api/orchestrators/rejected_workflow", _start_rejects)
    app.router.add_post("/api/orchestrators/slow_workflow", _start_slow)
    return app


@pytest.fixture
async def server():
    srv = TestServer(_build_app())
    await srv.start_server()
    yield srv
    await srv.close()


async def test_completed_workflow_returns_result(server: TestServer) -> None:
    provider = DurableClaimsWorkflowProvider(
        base_url=str(server.make_url("")), orchestrator_name="completed_workflow"
    )

    result = await provider.run(_workflow_input())

    assert result.success is True
    assert result.claim_reference == "SYN-CLM-2026-0099"
    assert result.adjuster_name == "Synthetic Adjuster A"


async def test_polling_continues_until_completed(server: TestServer) -> None:
    provider = DurableClaimsWorkflowProvider(
        base_url=str(server.make_url("")),
        orchestrator_name="eventually_workflow",
        poll_interval_seconds=0.01,
        timeout_seconds=5.0,
    )

    result = await provider.run(_workflow_input())

    assert result.success is True
    assert result.claim_reference == "SYN-CLM-2026-0100"


async def test_failed_orchestration_status_normalizes_to_failed_result(server: TestServer) -> None:
    provider = DurableClaimsWorkflowProvider(
        base_url=str(server.make_url("")), orchestrator_name="failed_workflow"
    )

    result = await provider.run(_workflow_input())

    assert result.success is False
    assert result.error is not None
    assert "Failed" in result.error


async def test_starter_http_error_normalizes_to_failed_result(server: TestServer) -> None:
    provider = DurableClaimsWorkflowProvider(
        base_url=str(server.make_url("")), orchestrator_name="rejected_workflow"
    )

    result = await provider.run(_workflow_input())

    assert result.success is False
    assert result.error is not None


async def test_start_timeout_normalizes_to_failed_result_not_a_raised_exception(
    server: TestServer,
) -> None:
    provider = DurableClaimsWorkflowProvider(
        base_url=str(server.make_url("")), orchestrator_name="slow_workflow", timeout_seconds=0.05
    )

    result = await provider.run(_workflow_input())

    assert result.success is False
    assert result.error is not None


async def test_connection_failure_normalizes_to_failed_result_not_a_raised_exception() -> None:
    provider = DurableClaimsWorkflowProvider(base_url="http://127.0.0.1:1", timeout_seconds=1.0)

    result = await provider.run(_workflow_input())

    assert result.success is False
    assert result.error is not None
