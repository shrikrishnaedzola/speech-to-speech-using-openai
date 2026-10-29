"""Report exports: JSON (fixed schema), Markdown and PDF."""
from .json_schema import to_json, validate_report
from .markdown import to_markdown


def to_pdf(report: dict) -> bytes:
    """Imported only when used: PDF needs matplotlib + Playwright (the [pdf] extra),
    which are not installed on serverless hosts such as Vercel."""
    try:
        from .pdf import to_pdf as _to_pdf
    except ImportError as exc:
        raise RuntimeError('PDF export is not installed here: pip install -e "../report_module[pdf]"') from exc
    return _to_pdf(report)

__all__ = ["to_json", "to_markdown", "to_pdf", "validate_report"]
