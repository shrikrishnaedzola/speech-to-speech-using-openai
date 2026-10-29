"""Ready-made FastAPI routes. Each tester only supplies 4 small functions.

    from report_module.api import make_report_router
    app.include_router(make_report_router(
        get_call_data=...,   # (call_id: str) -> CallData | None
        save_report=...,     # (call_id: str, report: dict) -> None
        load_report=...,     # (call_id: str) -> dict | None
        save_ratings=...,    # (call_id: str, ratings: Ratings) -> None
    ))

Routes:
    POST /api/calls/{call_id}/report?ai_summary=false   generate / regenerate
    GET  /api/calls/{call_id}/report                    report JSON (generated if missing)
    POST /api/calls/{call_id}/ratings                   save tester 1-5 ratings, then regenerate
    GET  /api/calls/{call_id}/report/export?format=pdf|md|json
"""
import logging
from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from .call_data import CallData, Ratings
from .exporters import to_json, to_markdown, to_pdf
from .report_builder import build_report
from .settings import load_settings

log = logging.getLogger(__name__)


def make_report_router(
    *,
    get_call_data: Callable[[str], CallData | None],
    save_report: Callable[[str, dict], None],
    load_report: Callable[[str], dict | None],
    save_ratings: Callable[[str, Ratings], None],
    settings_path: str | None = None,
    prefix: str = "/api/calls",
    pdf_enabled: bool = True,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["report"])

    def generate(call_id: str, ai_summary: bool | None = None) -> dict:
        data = get_call_data(call_id)
        if data is None:
            raise HTTPException(404, "Call not found")
        report = build_report(data, load_settings(settings_path), with_ai_summary=ai_summary)
        # Keep an existing AI summary when regenerating without asking for a new one.
        if report["ai_summary"] is None and ai_summary is None:
            old = load_report(call_id)
            if old and old.get("ai_summary"):
                report["ai_summary"] = {**old["ai_summary"], "stale": True}
        save_report(call_id, report)
        return report

    # Plain `def` routes: FastAPI runs them in a thread pool, which the
    # synchronous PDF renderer (Playwright) needs.
    @router.post("/{call_id}/report")
    def create_report(call_id: str, ai_summary: bool = Query(False)):
        return generate(call_id, ai_summary=True if ai_summary else None)

    @router.get("/{call_id}/report")
    def get_report(call_id: str):
        return load_report(call_id) or generate(call_id)

    @router.post("/{call_id}/ratings")
    def post_ratings(call_id: str, ratings: Ratings):
        save_ratings(call_id, ratings)
        return generate(call_id)

    @router.get("/{call_id}/report/export")
    def export_report(call_id: str, format: str = Query("json", pattern="^(pdf|md|json)$")):
        report = load_report(call_id) or generate(call_id)
        name = report["file_name_base"]
        if format == "pdf":
            if not pdf_enabled:
                raise HTTPException(501, "PDF export is turned off on this deployment. Use Markdown or JSON.")
            try:
                content, media = to_pdf(report), "application/pdf"
            except RuntimeError as exc:  # Playwright/Chromium not installed
                raise HTTPException(501, str(exc))
        elif format == "md":
            content, media = to_markdown(report), "text/markdown; charset=utf-8"
        else:
            content, media = to_json(report), "application/json"
        return Response(content, media_type=media,
                        headers={"Content-Disposition": f'attachment; filename="{name}.{format}"'})

    router.generate_report = generate  # testers call this on End Call / complete_form
    return router
