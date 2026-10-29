"""Shared post-call report module for the Zolabs voice form testers.

Typical use inside a tester app:

    from report_module import build_report, load_settings
    from report_module.adapters.openai_tester import load_call_data

    call_data = load_call_data(db, call_id)      # tester-specific adapter
    report = build_report(call_data, load_settings())

See README.md "Plugging the report into a tester".
"""
from .call_data import CallData
from .report_builder import build_report
from .settings import load_settings

__all__ = ["CallData", "build_report", "load_settings"]
