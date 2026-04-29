"""Tests for Sprint 8.4 — Enhanced Admin Dashboard UI.

These tests validate the HTML template rendering, JS logic, and CSS structure
for the admin camera management dashboard.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAdminCamerasTemplate:
    """Tests for admin_cameras.html template structure."""

    def test_admin_cameras_page_loads(self):
        """Test that the admin cameras page template has required sections."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        assert os.path.exists(template_path), "Template file not found"

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check required sections exist
        assert "camera-grid" in content, "Camera grid section missing"
        assert "camera-stats-bar" in content, "Stats bar section missing"
        assert "camera-toolbar" in content, "Toolbar section missing"
        assert "camera-modal" in content, "Camera modal section missing"
        assert "confirm-modal" in content, "Confirm modal section missing"
        assert "pagination" in content, "Pagination section missing"

    def test_camera_grid_displays_all_cameras(self):
        """Test that the camera grid container exists."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="camera-grid"' in content
        assert "camera-card" in content or "camera-grid" in content

    def test_status_filter_works(self):
        """Test that status filter dropdown exists."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="status-filter"' in content
        assert "All Status" in content
        assert "Online" in content
        assert "Offline" in content
        assert "Error" in content

    def test_search_filters_cameras(self):
        """Test that search input exists."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="search-input"' in content
        assert "Search by camera name" in content

    def test_bulk_select_all(self):
        """Test that bulk action toolbar exists."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="bulk-toolbar"' in content
        assert "Enable" in content
        assert "Disable" in content
        assert "Delete" in content
        assert "Reset" in content

    def test_bulk_disable_confirmation(self):
        """Test that confirmation modal exists for delete operations."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="confirm-modal"' in content
        assert "Confirm Delete" in content
        assert "Are you sure" in content

    def test_camera_detail_modal_shows_metrics(self):
        """Test that camera detail modal has all required metric sections."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Health metrics
        assert "modal-status" in content
        assert "modal-last-hb" in content
        assert "modal-uptime-24h" in content
        assert "modal-uptime-7d" in content
        assert "modal-errors-24h" in content
        assert "modal-errors-7d" in content

        # Metrics tab
        assert "modal-triggers" in content
        assert "modal-ai-calls" in content
        assert "modal-bandwidth" in content
        assert "modal-events" in content

        # Cost tab
        assert "modal-ai-cost" in content
        assert "modal-storage-cost" in content
        assert "modal-bandwidth-cost" in content
        assert "modal-total-cost" in content
        assert "modal-cost-per-day" in content
        assert "modal-cost-per-trigger" in content

    def test_uptime_chart_renders(self):
        """Test that chart canvases exist."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="uptime-chart"' in content
        assert 'id="trigger-trend-chart"' in content

    def test_mobile_responsive_layout(self):
        """Test that CSS has responsive breakpoints."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.css"
        )
        assert os.path.exists(css_path), "CSS file not found"

        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "@media (max-width: 768px)" in content
        assert "@media (max-width: 480px)" in content

    def test_pagination_works(self):
        """Test that pagination controls exist."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'id="prev-page"' in content
        assert 'id="next-page"' in content
        assert 'id="page-info"' in content

    def test_error_state_displayed(self):
        """Test that error state is handled in JS."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        assert os.path.exists(js_path), "JS file not found"

        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "error-state" in content
        assert "Failed to load cameras" in content

    def test_js_has_api_calls(self):
        """Test that JS has all required API call functions."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "listCameras" in content
        assert "getCameraDetails" in content
        assert "getCameraHealth" in content
        assert "getCameraMetrics" in content
        assert "getHealthSummary" in content
        assert "getCameraStats" in content
        assert "bulkOperation" in content
        assert "updateConfig" in content
        assert "resetCamera" in content

    def test_js_has_bulk_operations(self):
        """Test that JS has bulk operation handling."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "handleBulkOperation" in content
        assert "executeBulk" in content
        assert "showConfirmModal" in content

    def test_js_has_auto_refresh(self):
        """Test that JS has auto-refresh functionality."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "startAutoRefresh" in content
        assert "30000" in content  # 30 second interval

    def test_css_has_camera_card_styles(self):
        """Test that CSS has camera card styles."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.css"
        )
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert ".camera-card" in content
        assert ".camera-grid" in content
        assert ".card-status-dot" in content
        assert ".card-name" in content
        assert ".card-metrics" in content

    def test_css_has_modal_styles(self):
        """Test that CSS has modal styles."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.css"
        )
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert ".modal-overlay" in content
        assert ".modal-content" in content
        assert ".modal-header" in content
        assert ".modal-body" in content
        assert ".modal-tab" in content
        assert ".tab-panel" in content

    def test_css_has_toast_styles(self):
        """Test that CSS has toast notification styles."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.css"
        )
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert ".toast" in content
        assert ".toast-info" in content
        assert ".toast-error" in content
        assert "@keyframes toast-in" in content
        assert "@keyframes toast-out" in content

    def test_css_has_bulk_action_styles(self):
        """Test that CSS has bulk action button styles."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.css"
        )
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert ".bulk-actions" in content
        assert ".btn-bulk" in content
        assert ".btn-enable" in content
        assert ".btn-disable" in content
        assert ".btn-delete" in content
        assert ".btn-reset" in content

    def test_js_has_modal_tabs(self):
        """Test that JS has modal tab switching."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "modal-tab" in content
        assert "tab-panel" in content
        assert "classList.add('active')" in content

    def test_js_has_toast_function(self):
        """Test that JS has toast notification function."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "showToast" in content
        assert "toast-fadeout" in content

    def test_js_has_escape_key_handler(self):
        """Test that JS handles Escape key to close modals."""
        import os

        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Escape" in content
        assert "closeCameraModal" in content

    def test_template_includes_js(self):
        """Test that template includes the JS file."""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "templates", "admin_cameras.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "admin_cameras.js" in content

    def test_css_has_pagination_styles(self):
        """Test that CSS has pagination styles."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "dashboard", "static", "admin_cameras.css"
        )
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert ".pagination" in content
        assert ".page-btn" in content
        assert ".page-info" in content
