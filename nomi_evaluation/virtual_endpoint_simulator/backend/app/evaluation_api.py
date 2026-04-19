"""
Evaluation API Router — 三大類五場景研究設計
=============================================
REST + SSE endpoints.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response, StreamingResponse

from .services.chart_service import (generate_all_scenarios_chart_png,
                                     generate_scenario_chart_png)
from .services.evaluation_service import (EvaluationRunner, NomiHostClient,
                                          SimulatorClient, list_saved_results,
                                          load_result_file, load_scenarios,
                                          rescore_results,
                                          save_evaluation_results,
                                          save_scenarios)

logger = logging.getLogger(__name__)

evaluation_router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

_runner: Optional[EvaluationRunner] = None


def _detect_nomi_port(start: int = 8000, end: int = 8099) -> Optional[int]:
    """Find a reachable NOMI Host backend port by probing /health."""
    for port in range(start, end + 1):
        try:
            if NomiHostClient(port).healthy():
                return port
        except Exception:
            continue
    return None


# ── Health ───────────────────────────────────────────────────

@evaluation_router.get("/connectivity")
async def check_connectivity(
    request: Request,
    sim_port: Optional[int] = Query(None),
    nomi_port: Optional[int] = Query(None),
):
    # Default simulator port to current backend port when not provided.
    # This avoids stale hardcoded ports after dynamic startup.
    effective_sim_port = sim_port or request.url.port or 8001
    effective_nomi_port = nomi_port if nomi_port is not None else _detect_nomi_port()

    sim = SimulatorClient(effective_sim_port)
    nomi = NomiHostClient(effective_nomi_port) if effective_nomi_port else None

    # Run blocking HTTP checks in a thread pool to avoid self-deadlock
    loop = asyncio.get_event_loop()
    sim_ok = await loop.run_in_executor(None, sim.healthy)
    nomi_ok = False
    if nomi is not None:
        nomi_ok = await loop.run_in_executor(None, nomi.healthy)

    action_count = 0
    if sim_ok:
        try:
            action_count = await loop.run_in_executor(None, lambda: len(sim.list_actions()))
        except Exception:
            pass
    return {
        "simulator": {"connected": sim_ok, "port": effective_sim_port, "action_count": action_count},
        "nomi_host": {"connected": nomi_ok, "port": effective_nomi_port},
    }


@evaluation_router.get("/status")
async def get_status():
    global _runner
    return {"is_running": _runner.is_running if _runner else False}


# ── Scenarios CRUD ───────────────────────────────────────────

@evaluation_router.get("/scenarios")
async def get_scenarios():
    return load_scenarios()


@evaluation_router.put("/scenarios")
async def update_scenarios(data: dict):
    save_scenarios(data)
    cats = data.get("categories", [])
    total_sc = sum(len(c.get("scenarios", [])) for c in cats)
    return {"status": "ok", "categories": len(cats), "scenarios": total_sc}


# ── Run Evaluation (SSE) ─────────────────────────────────────

@evaluation_router.get("/run")
async def run_evaluation(
    request: Request,
    sim_port: Optional[int] = Query(None),
    nomi_port: Optional[int] = Query(None),
    use_judge: bool = Query(True),
    runs: Optional[int] = Query(None, ge=1, le=20),
):
    """
    Run the full evaluation (all categories, all scenarios, N runs each).
    Returns SSE stream.
    """
    global _runner
    if _runner and _runner.is_running:
        return {"error": "Evaluation already running"}

    scenarios_data = load_scenarios()
    categories = scenarios_data.get("categories", [])
    if not categories:
        return {"error": "No categories defined"}

    effective_sim_port = sim_port or request.url.port or 8001
    effective_nomi_port = nomi_port if nomi_port is not None else _detect_nomi_port()
    if effective_nomi_port is None:
        return {"error": "NOMI Host not reachable on ports 8000-8099"}

    _runner = EvaluationRunner(effective_sim_port, effective_nomi_port, use_judge)

    async def event_stream():
        async for event in _runner.run_full(scenarios_data, runs_override=runs):
            yield event
        # Auto-save
        if _runner._full_results:
            save_evaluation_results(_runner._full_results)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@evaluation_router.post("/cancel")
async def cancel_evaluation():
    global _runner
    if _runner and _runner.is_running:
        _runner.cancel()
        return {"status": "cancelling"}
    return {"status": "not_running"}


# ── Results ──────────────────────────────────────────────────

@evaluation_router.get("/results")
async def get_results():
    return list_saved_results()


@evaluation_router.get("/results/{filename}")
async def get_result_detail(filename: str):
    data = load_result_file(filename)
    if data is None:
        return {"error": "File not found"}
    return data


# ── Rescore (re-apply current label_score tables) ────────────

@evaluation_router.post("/rescore")
async def rescore(body: dict):
    """Re-score an existing evaluation result using the latest label matching
    tables.  Accepts the full eval result JSON and returns a rescored copy.
    """
    try:
        rescored = rescore_results(body)
        return rescored
    except Exception as exc:
        logger.exception("Rescore failed")
        return {"error": str(exc)}


# ── Chart image generation (matplotlib) ──────────────────────

@evaluation_router.post("/chart/scenario")
async def chart_scenario(body: dict):
    """
    Generate a single-scenario per-run chart PNG.

    POST body:
      { "scenario_id": "fall", "runs": [ { "no_env": {"score": 0.8}, "with_env": {"score": 1.0} }, ... ] }
    """
    sc_id = body.get("scenario_id", "scenario")
    runs = body.get("runs", [])
    if not runs:
        return Response(content=b"No runs", status_code=400)

    try:
        loop = asyncio.get_event_loop()
        png_bytes = await loop.run_in_executor(
            None,
            lambda: generate_scenario_chart_png(sc_id, runs),
        )
    except Exception as exc:
        logger.exception("Chart generation failed")
        return Response(content=str(exc).encode(), status_code=500)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="eval_{sc_id}.png"',
        },
    )


@evaluation_router.post("/chart/all")
async def chart_all(body: dict):
    """
    Generate a combined multi-panel chart PNG for all scenarios.

    POST body: same as eval_complete result (has 'categories' key).
    """
    categories = body.get("categories", [])
    if not categories:
        return Response(content=b"No categories", status_code=400)

    try:
        loop = asyncio.get_event_loop()
        png_bytes = await loop.run_in_executor(
            None,
            lambda: generate_all_scenarios_chart_png(categories),
        )
    except Exception as exc:
        logger.exception("Chart generation failed")
        return Response(content=str(exc).encode(), status_code=500)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": 'attachment; filename="eval_all_scenarios.png"',
        },
    )
