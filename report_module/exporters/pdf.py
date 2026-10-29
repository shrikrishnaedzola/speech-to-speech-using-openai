"""PDF export: render templates/report.html.j2, then print it with headless Chromium.

Why Chromium (Playwright) and not ReportLab: Chromium shapes Hindi, Tamil and
other Indian scripts correctly (conjuncts, vowel signs). ReportLab does not.

Setup (once):  pip install -e "../report_module[pdf]"   then   playwright install chromium
"""
from .charts import latency_chart, score_parts_chart, stage_split_chart
from .view import PART_LABELS, make_env

FOOTER_TEMPLATE = """
<div style="font-size:7px; color:#52514e; width:100%; padding:0 12mm; display:flex; justify-content:space-between;">
  <span><b>{banner}</b> · {footer}</span>
  <span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span>
</div>"""


def to_html(report: dict) -> str:
    charts = {
        "parts": score_parts_chart(report["summary"]["parts"], PART_LABELS),
        "latency": latency_chart(report["latency"]["per_turn"], report["latency"]["thresholds"])
        if report["latency"]["per_turn"] else None,
        "stages": stage_split_chart(report["latency"]["per_turn"]) if report["latency"]["has_stage_split"] else None,
    }
    return make_env(autoescape=True).get_template("report.html.j2").render(r=report, charts=charts)


def to_pdf(report: dict) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('PDF export needs Playwright: pip install -e "../report_module[pdf]" '
                           "then playwright install chromium") from exc

    html = to_html(report)
    footer = FOOTER_TEMPLATE.format(banner=report["banner"], footer=report["footer"])
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=footer,
                margin={"top": "14mm", "bottom": "18mm", "left": "12mm", "right": "12mm"},
            )
            browser.close()
    except Exception as exc:  # most often: Chromium not downloaded yet
        raise RuntimeError(f"PDF rendering failed ({exc}). Did you run 'playwright install chromium'?") from exc
    return pdf
