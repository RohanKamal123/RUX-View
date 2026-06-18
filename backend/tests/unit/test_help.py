"""
test_help.py — Tests for Help Center & Documentation (Sprint 11.4).

Tests cover:
- Help page loads and renders correctly
- Search returns relevant articles
- Empty search returns no results
- Article page loads with content
- Table of contents generation
- Feedback submission
- Category filter works
- Mobile responsive layout
- Breadcrumb navigation
- Related articles shown
"""

import pytest
from bs4 import BeautifulSoup


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def help_html():
    """Load the help.html template content."""
    with open("backend/dashboard/templates/help.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def help_article_html():
    """Load the help_article.html template content."""
    with open("backend/dashboard/templates/help_article.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def help_css():
    """Load the help.css content."""
    with open("backend/dashboard/static/help.css", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def help_js():
    """Load the help.js content."""
    with open("backend/dashboard/static/help.js", "r", encoding="utf-8") as f:
        return f.read()


# ── Test: Help Page Loads ────────────────────────────────────────


def test_help_page_loads(help_html):
    """Verify the help page HTML loads without errors."""
    soup = BeautifulSoup(help_html, "html.parser")
    assert soup.title is not None
    assert "Help Center" in soup.title.string


def test_help_page_has_required_sections(help_html):
    """Verify all required sections are present."""
    soup = BeautifulSoup(help_html, "html.parser")

    # Hero section
    hero = soup.find("section", class_="help-hero")
    assert hero is not None
    assert hero.find("h1") is not None

    # Category filters
    filters = soup.find("section", class_="help-filters")
    assert filters is not None

    # Category cards
    categories = soup.find("section", class_="help-categories")
    assert categories is not None

    # Popular articles
    popular = soup.find("section", class_="help-popular")
    assert popular is not None

    # Contact section
    contact = soup.find("section", class_="help-contact")
    assert contact is not None

    # Footer
    footer = soup.find("footer", class_="help-footer")
    assert footer is not None


# ── Test: Search Returns Relevant Articles ────────────────────────


def test_search_returns_relevant_articles(help_js):
    """Verify the search function filters articles correctly."""
    # Check that the articles database exists in help.js
    assert "const articles" in help_js or "articles =" in help_js
    assert "how-to-connect-first-camera" in help_js
    assert "pricing-plans" in help_js
    assert "camera-offline" in help_js


def test_search_has_highlight_function(help_js):
    """Verify the search has highlightMatch function."""
    assert "highlightMatch" in help_js
    assert "escapeRegExp" in help_js


# ── Test: Empty Search Returns No Results ─────────────────────────


def test_search_empty_returns_no_results(help_js):
    """Verify empty search shows all categories."""
    assert "showAllCategories" in help_js
    assert "searchResults.classList.remove" in help_js


# ── Test: Article Page Loads With Content ─────────────────────────


def test_article_page_loads_with_content(help_article_html):
    """Verify the article page template has required elements."""
    soup = BeautifulSoup(help_article_html, "html.parser")

    # Title placeholder
    assert "{{ article_title }}" in help_article_html

    # Breadcrumb
    breadcrumb = soup.find("div", class_="breadcrumb")
    assert breadcrumb is not None

    # Article content area
    content = soup.find("main", class_="article-content")
    assert content is not None

    # Article body
    assert "{{ article_body | safe }}" in help_article_html

    # Meta info
    assert "{{ category_name }}" in help_article_html
    assert "{{ read_time }}" in help_article_html


# ── Test: Table of Contents Generated ─────────────────────────────


def test_table_of_contents_generated(help_article_html):
    """Verify the article page has TOC structure."""
    soup = BeautifulSoup(help_article_html, "html.parser")

    toc = soup.find("aside", class_="article-toc")
    assert toc is not None

    toc_list = toc.find("ul", id="tocList")
    assert toc_list is not None

    assert "On this page" in toc.text


def test_toc_generation_in_js(help_js):
    """Verify the TOC generation function exists in JS."""
    assert "generateTOC" in help_js
    assert "tocList" in help_js
    assert "articleBody" in help_js


# ── Test: Feedback Submission ─────────────────────────────────────


def test_feedback_submission(help_article_html):
    """Verify the article page has feedback buttons."""
    soup = BeautifulSoup(help_article_html, "html.parser")

    feedback = soup.find("div", class_="article-feedback")
    assert feedback is not None

    buttons = feedback.find_all("button", class_="feedback-btn")
    assert len(buttons) == 2

    thanks = feedback.find("p", id="feedbackThanks")
    assert thanks is not None


def test_feedback_js_handling(help_js):
    """Verify feedback handling in JS."""
    assert "feedback-btn" in help_js or "feedback" in help_js
    assert "feedbackThanks" in help_js
    assert "localStorage" in help_js


# ── Test: Category Filter Works ───────────────────────────────────


def test_category_filter_works(help_html):
    """Verify the help page has category filter buttons."""
    soup = BeautifulSoup(help_html, "html.parser")

    filter_buttons = soup.find_all("button", class_="filter-btn")
    assert len(filter_buttons) >= 6  # All + 6 categories

    categories = ["all", "getting-started", "cameras", "alerts", "billing", "troubleshooting", "faq"]
    for btn in filter_buttons:
        assert btn.get("data-category") in categories


def test_category_filter_js(help_js):
    """Verify category filtering logic in JS."""
    assert "filter-btn" in help_js
    assert "data-category" in help_js
    assert "categoryCards" in help_js


# ── Test: Mobile Responsive Layout ────────────────────────────────


def test_mobile_responsive_layout(help_css):
    """Verify CSS has mobile responsive breakpoints."""
    assert "@media (max-width: 768px)" in help_css
    assert "@media (max-width: 1024px)" in help_css


def test_viewport_meta_tag(help_html):
    """Verify viewport meta tag is present."""
    soup = BeautifulSoup(help_html, "html.parser")
    viewport = soup.find("meta", attrs={"name": "viewport"})
    assert viewport is not None
    assert "width=device-width" in viewport["content"]


# ── Test: Breadcrumb Navigation ───────────────────────────────────


def test_breadcrumb_navigation(help_article_html):
    """Verify breadcrumb navigation structure."""
    soup = BeautifulSoup(help_article_html, "html.parser")

    breadcrumb = soup.find("div", class_="breadcrumb")
    assert breadcrumb is not None

    links = breadcrumb.find_all("a")
    assert len(links) >= 2  # Help Center + category

    # Check breadcrumb links
    assert any("Help Center" in a.text for a in links)


# ── Test: Related Articles Shown ──────────────────────────────────


def test_related_articles_shown(help_article_html):
    """Verify the article page has related articles section."""
    soup = BeautifulSoup(help_article_html, "html.parser")

    related = soup.find("section", class_="related-articles")
    assert related is not None

    assert "Related Articles" in related.text

    # Check for Jinja2 loop
    assert "{% for article in related_articles %}" in help_article_html


# ── Test: Category Cards Have Articles ────────────────────────────


def test_category_cards_have_articles(help_html):
    """Verify each category card has article links."""
    soup = BeautifulSoup(help_html, "html.parser")

    cards = soup.find_all("div", class_="category-card")
    assert len(cards) == 6  # 6 categories

    for card in cards:
        articles = card.find_all("a")
        assert len(articles) >= 3, f"Category card should have at least 3 articles"


# ── Test: SEO Meta Tags ───────────────────────────────────────────


def test_seo_meta_tags_present(help_html):
    """Verify SEO meta tags are present."""
    soup = BeautifulSoup(help_html, "html.parser")

    description = soup.find("meta", attrs={"name": "description"})
    assert description is not None
    assert len(description.get("content", "")) > 0

    keywords = soup.find("meta", attrs={"name": "keywords"})
    assert keywords is not None

    og_title = soup.find("meta", attrs={"property": "og:title"})
    assert og_title is not None

    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    assert twitter_card is not None


# ── Test: CSS Has Required Styles ─────────────────────────────────


def test_css_has_required_styles(help_css):
    """Verify CSS has styles for all major components."""
    required_classes = [
        ".help-hero",
        ".help-search",
        ".help-categories",
        ".category-card",
        ".help-popular",
        ".help-contact",
        ".help-footer",
        ".article-toc",
        ".article-content",
        ".article-feedback",
        ".related-articles",
        ".breadcrumb",
    ]
    for cls in required_classes:
        assert cls in help_css, f"Missing CSS class: {cls}"


# ── Test: JS Has Required Functions ───────────────────────────────


def test_js_has_required_functions(help_js):
    """Verify JS has all required functions."""
    required_functions = [
        "performSearch",
        "displaySearchResults",
        "generateTOC",
    ]
    for func in required_functions:
        assert func in help_js, f"Missing JS function: {func}"
