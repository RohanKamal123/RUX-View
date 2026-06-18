"""
test_landing.py — Tests for the Public Landing Page (Sprint 11.1).

Tests cover:
- Page loads and renders correctly
- Hero section visible with tagline and CTA
- Features section has 6 feature cards
- Pricing section has 3 pricing tiers
- How It Works section has 3 steps
- FAQ accordion works
- Mobile responsive layout
- CTA buttons link to /login
- SEO meta tags present
- Fast load time (static page)
"""

import pytest
from bs4 import BeautifulSoup
from pathlib import Path


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def landing_html():
    """Load the landing.html template file."""
    path = Path("backend/dashboard/templates/landing.html")
    assert path.exists(), f"landing.html not found at {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def soup(landing_html):
    """Parse the HTML with BeautifulSoup."""
    return BeautifulSoup(landing_html, "html.parser")


# ── Test: Landing Page Loads ──────────────────────────────────────


def test_landing_page_loads(soup):
    """Verify the landing page HTML loads without errors."""
    assert soup is not None
    assert soup.html is not None
    assert soup.title is not None


def test_landing_page_has_doctype(landing_html):
    """Verify the page starts with a proper DOCTYPE."""
    assert landing_html.strip().startswith("<!DOCTYPE html>")


# ── Test: Hero Section Visible ────────────────────────────────────


def test_hero_section_visible(soup):
    """Verify the hero section exists with tagline and subtitle."""
    hero = soup.find("section", class_="hero")
    assert hero is not None, "Hero section not found"

    tagline = hero.find("h1", class_="hero-tagline")
    assert tagline is not None, "Hero tagline not found"
    assert "AI-Powered Security" in tagline.get_text()

    subtitle = hero.find("p", class_="hero-subtitle")
    assert subtitle is not None, "Hero subtitle not found"
    assert "299 BDT" in subtitle.get_text()


# ── Test: Features Section Has 6 Cards ────────────────────────────


def test_features_section_has_6_cards(soup):
    """Verify the features section contains exactly 6 feature cards."""
    features = soup.find("section", class_="features")
    assert features is not None, "Features section not found"

    cards = features.find_all("div", class_="feature-card")
    assert len(cards) == 6, f"Expected 6 feature cards, found {len(cards)}"


def test_features_have_titles_and_descriptions(soup):
    """Verify each feature card has a title and description."""
    features = soup.find("section", class_="features")
    cards = features.find_all("div", class_="feature-card")

    for card in cards:
        title = card.find("h3", class_="feature-title")
        desc = card.find("p", class_="feature-desc")
        assert title is not None, f"Feature card missing title: {card}"
        assert desc is not None, f"Feature card missing description: {card}"
        assert len(title.get_text().strip()) > 0
        assert len(desc.get_text().strip()) > 0


# ── Test: Pricing Section Has 3 Tiers ─────────────────────────────


def test_pricing_section_has_3_tiers(soup):
    """Verify the pricing section contains exactly 3 pricing cards."""
    pricing = soup.find("section", class_="pricing")
    assert pricing is not None, "Pricing section not found"

    cards = pricing.find_all("div", class_="pricing-card")
    assert len(cards) == 3, f"Expected 3 pricing cards, found {len(cards)}"


def test_pricing_has_household_featured(soup):
    """Verify the Household tier is marked as 'Most Popular'."""
    pricing = soup.find("section", class_="pricing")
    featured = pricing.find("div", class_="pricing-featured")
    assert featured is not None, "Featured pricing card not found"

    badge = featured.find("div", class_="pricing-badge")
    assert badge is not None, "Pricing badge not found on featured card"
    assert "Most Popular" in badge.get_text()


def test_pricing_has_correct_amounts(soup):
    """Verify pricing amounts are correct."""
    pricing = soup.find("section", class_="pricing")
    cards = pricing.find_all("div", class_="pricing-card")

    amounts = []
    for card in cards:
        value = card.find("span", class_="pricing-value")
        amounts.append(value.get_text().strip())

    assert "0" in amounts, "Free tier amount not found"
    assert "299" in amounts, "Household tier amount not found"
    assert "499" in amounts, "Business tier amount not found"


# ── Test: How It Works Has 3 Steps ────────────────────────────────


def test_how_it_works_3_steps(soup):
    """Verify the How It Works section has exactly 3 steps."""
    how = soup.find("section", class_="how-it-works")
    assert how is not None, "How It Works section not found"

    steps = how.find_all("div", class_="step-card")
    assert len(steps) == 3, f"Expected 3 steps, found {len(steps)}"


def test_how_it_works_step_numbers(soup):
    """Verify each step has a number."""
    how = soup.find("section", class_="how-it-works")
    steps = how.find_all("div", class_="step-card")

    for i, step in enumerate(steps, 1):
        number = step.find("div", class_="step-number")
        assert number is not None, f"Step {i} missing step number"
        assert number.get_text().strip() == str(i), f"Step {i} has wrong number"


# ── Test: FAQ Accordion Works ─────────────────────────────────────


def test_faq_accordion_works(soup):
    """Verify the FAQ section has accordion items with questions and answers."""
    faq = soup.find("section", class_="faq")
    assert faq is not None, "FAQ section not found"

    items = faq.find_all("div", class_="faq-item")
    assert len(items) >= 5, f"Expected at least 5 FAQ items, found {len(items)}"

    for item in items:
        question = item.find("button", class_="faq-question")
        answer = item.find("div", class_="faq-answer")
        assert question is not None, "FAQ item missing question button"
        assert answer is not None, "FAQ item missing answer div"
        assert question.get("aria-expanded") is not None, "FAQ question missing aria-expanded"


# ── Test: Mobile Responsive Layout ────────────────────────────────


def test_mobile_responsive_layout(soup):
    """Verify the page has viewport meta tag for responsive design."""
    viewport = soup.find("meta", attrs={"name": "viewport"})
    assert viewport is not None, "Viewport meta tag not found"
    assert "width=device-width" in viewport.get("content", ""), "Viewport missing width=device-width"
    assert "initial-scale=1" in viewport.get("content", ""), "Viewport missing initial-scale"


# ── Test: CTA Buttons Link to /login ──────────────────────────────


def test_cta_buttons_link_to_login(soup):
    """Verify CTA buttons link to /login."""
    # Hero CTA
    hero = soup.find("section", class_="hero")
    hero_cta = hero.find("a", string="Start Free Trial")
    assert hero_cta is not None, "Hero CTA 'Start Free Trial' not found"
    assert hero_cta.get("href") == "/login", f"Hero CTA links to {hero_cta.get('href')}, expected /login"

    # Pricing CTAs
    pricing = soup.find("section", class_="pricing")
    pricing_ctas = pricing.find_all("a", string="Start Free Trial")
    assert len(pricing_ctas) == 3, f"Expected 3 pricing CTAs, found {len(pricing_ctas)}"
    for cta in pricing_ctas:
        assert cta.get("href") == "/login", f"Pricing CTA links to {cta.get('href')}, expected /login"

    # Bottom CTA
    cta_section = soup.find("section", class_="cta-section")
    bottom_cta = cta_section.find("a", string="Start Free Trial")
    assert bottom_cta is not None, "Bottom CTA not found"
    assert bottom_cta.get("href") == "/login", f"Bottom CTA links to {bottom_cta.get('href')}, expected /login"


# ── Test: SEO Meta Tags Present ───────────────────────────────────


def test_seo_meta_tags_present(soup):
    """Verify SEO meta tags are present."""
    # Description
    desc = soup.find("meta", attrs={"name": "description"})
    assert desc is not None, "Meta description not found"
    assert len(desc.get("content", "")) > 10, "Meta description too short"

    # Keywords
    keywords = soup.find("meta", attrs={"name": "keywords"})
    assert keywords is not None, "Meta keywords not found"

    # OG tags
    og_title = soup.find("meta", attrs={"property": "og:title"})
    assert og_title is not None, "OG title not found"

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    assert og_desc is not None, "OG description not found"

    # Twitter card
    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    assert twitter_card is not None, "Twitter card not found"

    # Canonical
    canonical = soup.find("link", rel="canonical")
    assert canonical is not None, "Canonical link not found"


# ── Test: Fast Load Time (Static Page) ────────────────────────────


def test_fast_load_time(landing_html):
    """Verify the page is static HTML (no heavy dependencies)."""
    # No external scripts except our own
    assert "landing.js" in landing_html, "landing.js not included"
    assert "landing.css" in landing_html, "landing.css not included"

    # No heavy external libraries
    assert "chart.js" not in landing_html.lower(), "Chart.js should not be on landing page"
    assert "jquery" not in landing_html.lower(), "jQuery should not be on landing page"


# ── Test: Navigation ──────────────────────────────────────────────


def test_navigation_has_all_links(soup):
    """Verify the navigation has all expected links."""
    nav = soup.find("nav", class_="landing-nav")
    assert nav is not None, "Navigation not found"

    links = nav.find_all("a")
    link_texts = [a.get_text().strip() for a in links]

    assert "Features" in link_texts, "Features nav link missing"
    assert "How It Works" in link_texts, "How It Works nav link missing"
    assert "Pricing" in link_texts, "Pricing nav link missing"
    assert "FAQ" in link_texts, "FAQ nav link missing"
    assert "Sign In" in link_texts, "Sign In nav link missing"


# ── Test: Testimonials ────────────────────────────────────────────


def test_testimonials_section_has_cards(soup):
    """Verify the testimonials section has testimonial cards."""
    testimonials = soup.find("section", class_="testimonials")
    assert testimonials is not None, "Testimonials section not found"

    cards = testimonials.find_all("div", class_="testimonial-card")
    assert len(cards) >= 2, f"Expected at least 2 testimonials, found {len(cards)}"

    for card in cards:
        stars = card.find("div", class_="testimonial-stars")
        text = card.find("p", class_="testimonial-text")
        author = card.find("div", class_="testimonial-author")
        assert stars is not None, "Testimonial missing stars"
        assert text is not None, "Testimonial missing text"
        assert author is not None, "Testimonial missing author"


# ── Test: Footer ──────────────────────────────────────────────────


def test_footer_has_all_sections(soup):
    """Verify the footer has brand info, links, and copyright."""
    footer = soup.find("footer", class_="landing-footer")
    assert footer is not None, "Footer not found"

    # Brand
    brand = footer.find("div", class_="footer-brand")
    assert brand is not None, "Footer brand section missing"

    # Quick links
    links_sections = footer.find_all("div", class_="footer-links")
    assert len(links_sections) >= 2, f"Expected at least 2 footer link sections, found {len(links_sections)}"

    # Copyright
    bottom = footer.find("div", class_="footer-bottom")
    assert bottom is not None, "Footer bottom missing"
    assert "Vision OS" in bottom.get_text(), "Copyright missing company name"


# ── Test: CSS and JS Files Exist ──────────────────────────────────


def test_css_file_exists():
    """Verify the landing CSS file exists."""
    path = Path("backend/dashboard/static/landing.css")
    assert path.exists(), "landing.css not found"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 500, "landing.css seems too short"


def test_js_file_exists():
    """Verify the landing JS file exists."""
    path = Path("backend/dashboard/static/landing.js")
    assert path.exists(), "landing.js not found"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 500, "landing.js seems too short"
