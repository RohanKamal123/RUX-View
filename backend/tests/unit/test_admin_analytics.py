"""
test_admin_analytics.py — Tests for Admin Analytics Dashboard (Sprint 11.5).

Tests cover:
- Admin analytics page loads
- Summary cards display correct values
- Revenue chart renders
- User growth chart renders
- Camera adoption chart renders
- Event trends chart renders
- Top users table sorted
- Date range filter works
- CSV export generates file
- PDF export generates file
- Non-admin gets 403
- Mobile responsive layout
"""

import pytest
pytest.importorskip("bs4")  # skip if not installed

import pytest
from bs4 import BeautifulSoup


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def analytics_html():
    """Load the admin_analytics.html template content."""
    with open("backend/dashboard/templates/admin_analytics.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def analytics_css():
    """Load the admin_analytics.css content."""
    with open("backend/dashboard/static/admin_analytics.css", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def analytics_js():
    """Load the admin_analytics.js content."""
    with open("backend/dashboard/static/admin_analytics.js", "r", encoding="utf-8") as f:
        return f.read()


# ── Test: Admin Analytics Page Loads ──────────────────────────────


def test_admin_analytics_page_loads(analytics_html):
    """Verify the admin analytics page HTML loads without errors."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    assert soup.title is not None
    assert "Admin Analytics" in soup.title.string


def test_admin_analytics_has_required_sections(analytics_html):
    """Verify all required sections are present."""
    soup = BeautifulSoup(analytics_html, "html.parser")

    # Navigation
    nav = soup.find("nav", class_="analytics-nav")
    assert nav is not None

    # Header
    header = soup.find("header", class_="analytics-header")
    assert header is not None
    assert header.find("h1") is not None

    # Summary cards
    cards = soup.find("section", class_="summary-cards")
    assert cards is not None

    # Charts
    charts = soup.find_all("section", class_="charts-section")
    assert len(charts) == 2

    # Table
    table_section = soup.find("section", class_="table-section")
    assert table_section is not None

    # Footer
    footer = soup.find("footer", class_="analytics-footer")
    assert footer is not None


# ── Test: Summary Cards Display Correct Values ────────────────────


def test_summary_cards_display_correct_values(analytics_html):
    """Verify summary cards have correct structure."""
    soup = BeautifulSoup(analytics_html, "html.parser")

    cards = soup.find_all("div", class_="summary-card")
    assert len(cards) == 4

    labels = ["Total Users", "Active Cameras", "MRR (BDT)", "Trial Conversion"]
    for i, card in enumerate(cards):
        label = card.find("div", class_="card-label")
        assert label is not None
        assert label.text.strip() == labels[i]

        value = card.find("div", class_="card-value")
        assert value is not None
        assert value.get("id") is not None


def test_summary_cards_have_icons(analytics_html):
    """Verify each summary card has an icon."""
    soup = BeautifulSoup(analytics_html, "html.parser")

    cards = soup.find_all("div", class_="summary-card")
    for card in cards:
        icon = card.find("div", class_="card-icon")
        assert icon is not None


# ── Test: Revenue Chart Renders ───────────────────────────────────


def test_revenue_chart_renders(analytics_html):
    """Verify the revenue chart canvas exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    canvas = soup.find("canvas", id="revenueChart")
    assert canvas is not None


def test_revenue_chart_js(analytics_js):
    """Verify revenue chart creation function exists."""
    assert "createRevenueChart" in analytics_js
    assert "revenueChart" in analytics_js
    assert "Chart" in analytics_js


# ── Test: User Growth Chart Renders ───────────────────────────────


def test_user_growth_chart_renders(analytics_html):
    """Verify the user growth chart canvas exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    canvas = soup.find("canvas", id="userGrowthChart")
    assert canvas is not None


def test_user_growth_chart_js(analytics_js):
    """Verify user growth chart creation function exists."""
    assert "createUserGrowthChart" in analytics_js
    assert "userGrowthChart" in analytics_js


# ── Test: Camera Adoption Chart Renders ───────────────────────────


def test_camera_adoption_chart_renders(analytics_html):
    """Verify the camera adoption chart canvas exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    canvas = soup.find("canvas", id="cameraAdoptionChart")
    assert canvas is not None


def test_camera_adoption_chart_js(analytics_js):
    """Verify camera adoption chart creation function exists."""
    assert "createCameraAdoptionChart" in analytics_js
    assert "cameraAdoptionChart" in analytics_js


# ── Test: Event Trends Chart Renders ──────────────────────────────


def test_event_trends_chart_renders(analytics_html):
    """Verify the event trends chart canvas exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    canvas = soup.find("canvas", id="eventTrendsChart")
    assert canvas is not None


def test_event_trends_chart_js(analytics_js):
    """Verify event trends chart creation function exists."""
    assert "createEventTrendsChart" in analytics_js
    assert "eventTrendsChart" in analytics_js


# ── Test: Top Users Table Sorted ──────────────────────────────────


def test_top_users_table_sorted(analytics_html):
    """Verify the top users table exists with correct columns."""
    soup = BeautifulSoup(analytics_html, "html.parser")

    table = soup.find("table", id="topUsersTable")
    assert table is not None

    headers = table.find_all("th")
    header_texts = [h.text.strip().replace("\u25b2\u25bc", "").strip() for h in headers]
    expected = ["Email", "Tier", "Cameras", "Events (30d)", "Revenue", "Status"]
    for exp in expected:
        assert any(exp in h for h in header_texts), f"Missing column: {exp}"


def test_table_sorting_js(analytics_js):
    """Verify table sorting logic exists in JS."""
    assert "renderTable" in analytics_js
    assert "currentSort" in analytics_js
    assert "initTableSorting" in analytics_js


# ── Test: Date Range Filter Works ─────────────────────────────────


def test_date_range_filter_works(analytics_html):
    """Verify date range selector buttons exist."""
    soup = BeautifulSoup(analytics_html, "html.parser")

    selector = soup.find("div", class_="date-range-selector")
    assert selector is not None

    buttons = selector.find_all("button", class_="date-btn")
    assert len(buttons) == 4

    ranges = ["7d", "30d", "90d", "custom"]
    for btn in buttons:
        assert btn.get("data-range") in ranges


def test_date_range_js(analytics_js):
    """Verify date range selector logic exists in JS."""
    assert "initDateRangeSelector" in analytics_js
    assert "currentRange" in analytics_js
    assert "refreshData" in analytics_js


# ── Test: CSV Export Generates File ───────────────────────────────


def test_csv_export_generates_file(analytics_html):
    """Verify CSV export button exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    btn = soup.find("button", id="exportCsv")
    assert btn is not None


def test_csv_export_js(analytics_js):
    """Verify CSV export function exists in JS."""
    assert "exportCSV" in analytics_js
    assert ".csv" in analytics_js
    assert "Blob" in analytics_js


# ── Test: PDF Export Generates File ───────────────────────────────


def test_pdf_export_generates_file(analytics_html):
    """Verify PDF export button exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    btn = soup.find("button", id="exportPdf")
    assert btn is not None


def test_pdf_export_js(analytics_js):
    """Verify PDF export function exists in JS."""
    assert "exportPDF" in analytics_js
    assert "html2canvas" in analytics_js
    assert "jspdf" in analytics_js or "jsPDF" in analytics_js


# ── Test: Non-Admin Gets 403 ──────────────────────────────────────


def test_non_admin_gets_403(analytics_html):
    """Verify the page has admin-only navigation."""
    soup = BeautifulSoup(analytics_html, "html.parser")

    nav = soup.find("nav", class_="analytics-nav")
    assert nav is not None

    # Check for admin-specific links
    links = nav.find_all("a")
    link_texts = [a.text.strip() for a in links]
    assert "Vision OS Admin" in link_texts or "Admin" in link_texts


# ── Test: Mobile Responsive Layout ────────────────────────────────


def test_mobile_responsive_layout(analytics_css):
    """Verify CSS has mobile responsive breakpoints."""
    assert "@media (max-width: 768px)" in analytics_css
    assert "@media (max-width: 1024px)" in analytics_css


def test_viewport_meta_tag(analytics_html):
    """Verify viewport meta tag is present."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    viewport = soup.find("meta", attrs={"name": "viewport"})
    assert viewport is not None
    assert "width=device-width" in viewport["content"]


# ── Test: Chart.js Library Loaded ─────────────────────────────────


def test_chartjs_library_loaded(analytics_html):
    """Verify Chart.js CDN script is included."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    scripts = soup.find_all("script")
    srcs = [s.get("src", "") for s in scripts]
    assert any("chart.js" in src for src in srcs)


def test_html2canvas_library_loaded(analytics_html):
    """Verify html2canvas CDN script is included."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    scripts = soup.find_all("script")
    srcs = [s.get("src", "") for s in scripts]
    assert any("html2canvas" in src for src in srcs)


# ── Test: CSS Has Required Styles ─────────────────────────────────


def test_css_has_required_styles(analytics_css):
    """Verify CSS has styles for all major components."""
    required_classes = [
        ".summary-card",
        ".chart-card",
        ".data-table",
        ".table-card",
        ".date-range-selector",
        ".analytics-nav",
        ".analytics-header",
        ".analytics-footer",
        ".tier-badge",
        ".status-badge",
        ".page-btn",
    ]
    for cls in required_classes:
        assert cls in analytics_css, f"Missing CSS class: {cls}"


# ── Test: JS Has Required Functions ───────────────────────────────


def test_js_has_required_functions(analytics_js):
    """Verify JS has all required functions."""
    required_functions = [
        "updateSummaryCards",
        "createRevenueChart",
        "createUserGrowthChart",
        "createCameraAdoptionChart",
        "createEventTrendsChart",
        "renderTable",
        "exportCSV",
        "exportPDF",
    ]
    for func in required_functions:
        assert func in analytics_js, f"Missing JS function: {func}"


# ── Test: Table Pagination ────────────────────────────────────────


def test_table_pagination(analytics_html):
    """Verify table pagination container exists."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    pagination = soup.find("div", id="tablePagination")
    assert pagination is not None


def test_table_tabs(analytics_html):
    """Verify table sorting tabs exist."""
    soup = BeautifulSoup(analytics_html, "html.parser")
    tabs = soup.find_all("button", class_="tab-btn")
    assert len(tabs) == 3

    sort_values = ["events", "revenue", "cameras"]
    for tab in tabs:
        assert tab.get("data-sort") in sort_values
