"""Markdown export (templates/report.md.j2)."""
from .view import make_env


def to_markdown(report: dict) -> str:
    return make_env(autoescape=False).get_template("report.md.j2").render(r=report)
