# Vision OS V9 — DeepSeek Coding Prompts
# Launch Features & Polish
# Copy-paste these prompts into DeepSeek to generate each sprint's code
# Each prompt includes: context + function signatures + test cases

---

## How to Use

1. Open DeepSeek (chat.deepseek.com)
2. Copy the entire prompt block for the sprint you want
3. Paste into DeepSeek
4. DeepSeek will generate: code + tests + docstring
5. Save the generated files to the correct paths
6. Run `pytest` to verify tests pass
7. Commit with `git commit -m "feat: [module] what it does"`

---

## SPRINT 11.1 — Public Landing Page
### Files: backend/dashboard/templates/landing.html, backend/dashboard/static/landing.js, backend/dashboard/static/landing.css
### Tests: backend/tests/unit/test_landing.py

```
You are building the public landing page for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Jinja2 + JavaScript + CSS (standalone, no auth required)
- Public-facing marketing page for customer acquisition
- Sections: Hero, Features, Pricing, How It Works, Testimonials, FAQ, Contact
- Mobile-first responsive design
- SEO-optimized with meta tags
- Fast loading (no heavy dependencies)
- Bangladesh market focus (Bengali + English support)
- Pricing: Free trial (30 days), Household (299 BDT/camera/month), Business (499 BDT/camera/month)
- No camera limit — supports up to 10 cameras

KEY DECISIONS:
- D012: Firebase Auth for login (sign-up button links to /login)
- D014: Three pricing tiers displayed
- Static page (no SSR needed, can be served from CDN)

SECTIONS TO BUILD:

1. Hero Section:
   - Tagline: "AI-Powered Security for Your Home & Business"
   - Subtitle: "Plug into any camera. Get AI alerts, audio intelligence, and natural language search — starting at 299 BDT/month."
   - CTA buttons: "Start Free Trial" → /login, "See How It Works" → scroll to features
   - Background: animated gradient or hero image of dashboard

2. Features Section:
   - Feature cards (6 features):
     1. Real-time AI Detection — "Gemini-powered analysis of every event"
     2. Audio Intelligence — "Detect glass breaking, shouting, gunshots"
     3. Cross-Camera Tracking — "Follow persons across all your cameras"
     4. Natural Language Search — "Ask 'who came yesterday at 2pm?'"
     5. Multi-Platform — "Web dashboard, Android, iOS, Telegram alerts"
     6. Bangladesh Payments — "Pay via bKash, Nagad, or Rocket"

3. How It Works Section:
   - 3-step process:
     1. "Connect Your Camera" — Enter RTSP URL
     2. "AI Takes Over" — Automatic detection and alerts
     3. "Stay Informed" — Real-time dashboard + Telegram

4. Pricing Section:
   - 3 pricing cards:
     - Free Trial: 0 BDT, 30 days full access, 1-2 cameras
     - Household: 299 BDT/camera/month, up to 10 cameras, 30-day history
     - Business: 499 BDT/camera/month, up to 10 cameras, 90-day history + analytics
   - Highlight "Most Popular" on Household tier
   - CTA: "Start Free Trial" button on each

5. Testimonials Section:
   - Placeholder testimonials (can be updated later)
   - Star ratings
   - User name + location

6. FAQ Section:
   - Accordion-style FAQ
   - Questions: "How do I connect my camera?", "What cameras are supported?",
     "Is my data secure?", "Can I cancel anytime?", "How does billing work?",
     "Do I need a powerful computer?"

7. Footer:
   - Company info
   - Quick links
   - Social media (placeholder)
   - Copyright

TEST CASES:
test_landing_page_loads, test_hero_section_visible, test_features_section_has_6_cards, test_pricing_section_has_3_tiers, test_how_it_works_3_steps, test_faq_accordion_works, test_mobile_responsive_layout, test_cta_buttons_link_to_login, test_seo_meta_tags_present, test_fast_load_time

OUTPUT: Generate landing.html, landing.js, landing.css, and test_landing.py.
```

---

## SPRINT 11.2 — Self-Service Signup
### Files: backend/api/public_signup.py
### Tests: backend/tests/unit/test_public_signup.py

```
You are building the self-service signup flow for Vision OS.

CONTEXT:
- Stack: FastAPI + Python asyncio + Firebase Auth + SQLAlchemy async
- Public signup endpoint (no admin approval needed)
- Firebase Auth account creation
- Automatic trial start (30 days)
- Email verification required
- Rate limiting: 5 signups per IP per hour
- Welcome email/Telegram message on signup
- Supports up to 10 cameras after signup

KEY DECISIONS:
- D012: Firebase Auth for authentication
- D026: All calls async
- Self-service: instant account creation

FUNCTIONS TO IMPLEMENT:

1. PublicSignupHandler class:
   - signup(email: str, password: str, name: str, phone: str) -> SignupResult
   - verify_email(email: str, code: str) -> dict
   - resend_verification(email: str) -> dict
   - check_email_available(email: str) -> bool
   - initiate_password_reset(email: str) -> dict
   - reset_password(code: str, new_password: str) -> dict
   - get_signup_stats(since: datetime) -> SignupStats

2. SignupResult dataclass:
   - user_id: str
   - email: str
   - name: str
   - tier: str = "free"
   - trial_ends_at: datetime
   - email_verified: bool = False
   - firebase_uid: str
   - created_at: datetime
   - message: str

3. SignupStats dataclass:
   - total_signups: int
   - verified_emails: int
   - unverified_emails: int
   - trial_active: int
   - trial_converted: int
   - signups_today: int
   - signups_this_week: int
   - signups_this_month: int

4. Signup Flow:
   - Step 1: User submits email + password + name + phone
   - Step 2: Firebase Auth account created
   - Step 3: User record created in database
   - Step 4: Trial subscription started (30 days)
   - Step 5: Verification email sent
   - Step 6: Welcome Telegram message sent (if Telegram connected)
   - Step 7: Redirect to onboarding wizard

5. Validation Rules:
   - Email: valid format, not already registered
   - Password: min 8 chars, 1 uppercase, 1 number
   - Name: min 2 chars, max 100 chars
   - Phone: valid Bangladesh number (01XXXXXXXXX)
   - Rate limit: 5 signups/IP/hour

TEST CASES:
test_signup_creates_firebase_user, test_signup_creates_database_record, test_signup_starts_trial, test_signup_sends_verification_email, test_verify_email_marks_verified, test_resend_verification_returns_success, test_check_email_available_true, test_check_email_available_false, test_initiate_password_reset, test_reset_password_with_valid_code, test_signup_invalid_email_returns_error, test_signup_weak_password_returns_error, test_signup_rate_limit_exceeded, test_get_signup_stats, test_duplicate_email_returns_error

OUTPUT: Generate public_signup.py and test_public_signup.py. Use async/await throughout.
```

---

## SPRINT 11.3 — Email Notifications
### Files: backend/notifications/email_service.py
### Tests: backend/tests/unit/test_email_service.py

```
You are building the email notification service for Vision OS.

CONTEXT:
- Stack: Python asyncio + SendGrid (or SMTP) + Jinja2 templates
- Email types: welcome, verification, password reset, payment receipt, trial expiry, weekly digest
- HTML email templates with responsive design
- Bangla + English support
- SendGrid API for reliable delivery
- Email tracking: open rate, click rate (optional)
- Rate limiting: 100 emails/hour per user

KEY DECISIONS:
- D026: All calls async
- SendGrid for email delivery (or SMTP fallback)
- Jinja2 templates for HTML emails

FUNCTIONS TO IMPLEMENT:

1. EmailService class:
   - send_welcome_email(user_id: str, email: str, name: str) -> bool
   - send_verification_email(email: str, code: str) -> bool
   - send_password_reset_email(email: str, code: str) -> bool
   - send_payment_receipt(user_id: str, payment_id: str) -> bool
   - send_trial_expiry_warning(user_id: str, days_remaining: int) -> bool
   - send_trial_expired(user_id: str) -> bool
   - send_weekly_digest(user_id: str, digest_data: dict) -> bool
   - send_custom_email(email: str, subject: str, template: str, data: dict) -> bool
   - get_email_history(user_id: str, limit: int = 20) -> list[EmailRecord]
   - get_email_stats(since: datetime) -> EmailStats

2. EmailRecord dataclass:
   - email_id: str
   - user_id: str
   - to_email: str
   - subject: str
   - template: str
   - status: str (sent/delivered/bounced/opened/clicked)
   - sent_at: datetime
   - delivered_at: Optional[datetime]
   - opened_at: Optional[datetime]
   - error: Optional[str]

3. EmailStats dataclass:
   - total_sent: int
   - delivered: int
   - bounced: int
   - opened: int
   - clicked: int
   - delivery_rate: float
   - open_rate: float
   - click_rate: float

4. Email Templates:
   - welcome.html: "Welcome to Vision OS!" with getting started guide
   - verification.html: "Verify your email" with verification link
   - password_reset.html: "Reset your password" with reset link
   - payment_receipt.html: "Payment Receipt" with amount, date, receipt number
   - trial_warning.html: "Your trial ends in X days" with upgrade CTA
   - trial_expired.html: "Your trial has ended" with grace period info
   - weekly_digest.html: Weekly security summary with stats

TEST CASES:
test_send_welcome_email_returns_true, test_send_verification_email_contains_code, test_send_password_reset_email, test_send_payment_receipt, test_send_trial_expiry_warning, test_send_trial_expired, test_send_weekly_digest, test_send_custom_email, test_get_email_history_returns_list, test_get_email_stats, test_email_bounce_handling, test_rate_limit_enforced, test_html_template_renders_correctly

OUTPUT: Generate email_service.py and test_email_service.py. Use async/await throughout.
```

---

## SPRINT 11.4 — Help Center & Documentation
### Files: backend/dashboard/templates/help.html, backend/dashboard/templates/help_article.html, backend/dashboard/static/help.js, backend/dashboard/static/help.css
### Tests: backend/tests/unit/test_help.py

```
You are building the help center and documentation pages for Vision OS.

CONTEXT:
- Stack: Jinja2 + JavaScript + CSS
- Help center with search functionality
- Article categories: Getting Started, Cameras, Alerts, Billing, Troubleshooting, FAQ
- Search across all articles
- Article view with table of contents
- Feedback on articles (helpful/not helpful)
- Mobile-first responsive design matching dark navy theme
- Bangla + English support

KEY DECISIONS:
- D012: Firebase Auth for login (help is public, but some articles require auth)
- Static articles stored as Markdown (rendered to HTML)

PAGES/COMPONENTS TO BUILD:

1. help.html — Help Center Home:
   - Search bar at top
   - Category cards (6 categories)
   - Popular articles section
   - Contact support button

2. help_article.html — Individual Article:
   - Breadcrumb navigation
   - Table of contents (auto-generated from headings)
   - Article content with formatting
   - "Was this helpful?" feedback buttons
   - Related articles section

3. Article Categories:
   - Getting Started: "How to connect your first camera", "Understanding the dashboard",
     "Setting up Telegram alerts", "Adding multiple cameras"
   - Cameras: "Camera modes explained", "RTSP URL format", "Troubleshooting connection",
     "Camera placement tips", "Managing 10 cameras"
   - Alerts: "Alert levels explained", "Customizing alert preferences",
     "Emergency alerts", "Quiet hours setup"
   - Billing: "Pricing plans", "How to pay via bKash", "Understanding your bill",
     "Cancelling your subscription", "Trial period FAQ"
   - Troubleshooting: "Camera offline", "No alerts received", "Login issues",
     "Slow dashboard", "Audio not working"
   - FAQ: "What cameras are supported?", "Is my data secure?",
     "Can I use multiple locations?", "What happens after trial?",
     "Do I need internet for cameras?"

4. Search Functionality:
   - Real-time search as user types
   - Search across article titles and content
   - Highlight matching terms in results
   - Category filter

TEST CASES:
test_help_page_loads, test_search_returns_relevant_articles, test_search_empty_returns_no_results, test_article_page_loads_with_content, test_table_of_contents_generated, test_feedback_submission, test_category_filter_works, test_mobile_responsive_layout, test_breadcrumb_navigation, test_related_articles_shown

OUTPUT: Generate help.html, help_article.html, help.js, help.css, and test_help.py.
```

---

## SPRINT 11.5 — Admin Analytics Dashboard
### Files: backend/dashboard/templates/admin_analytics.html, backend/dashboard/static/admin_analytics.js, backend/dashboard/static/admin_analytics.css
### Tests: backend/tests/unit/test_admin_analytics.py

```
You are building the admin analytics dashboard for Vision OS.

CONTEXT:
- Stack: Jinja2 + JavaScript (Chart.js) + CSS
- Admin-only analytics dashboard with real-time metrics
- Charts: revenue over time, user growth, camera adoption, event trends
- Tables: top users by usage, top users by revenue, recent signups
- Date range selector (7d, 30d, 90d, custom)
- Export to CSV/PDF
- Mobile-first responsive design matching dark navy theme
- Supports up to 10 cameras per user, aggregated across all users

KEY DECISIONS:
- D012: Firebase Auth for login (admin role required)
- Chart.js for interactive charts (lightweight, no server rendering)

PAGES/COMPONENTS TO BUILD:

1. admin_analytics.html — Main analytics page:
   - Summary cards row: Total Users, Active Cameras, MRR (Monthly Recurring Revenue), Trial Conversion Rate
   - Revenue chart (line chart, daily revenue over selected period)
   - User growth chart (area chart, cumulative users)
   - Camera adoption chart (bar chart, cameras per user distribution)
   - Event trends chart (line chart, events per day)
   - Top users table (by events, by revenue, by cameras)
   - Date range selector
   - Export buttons (CSV, PDF)

2. Summary Cards:
   - Total Users: count + change from previous period
   - Active Cameras: count + change
   - MRR: BDT amount + change
   - Trial Conversion: percentage + change
   - Each card has icon and trend indicator (up/down arrow)

3. Revenue Chart:
   - Daily revenue for selected period
   - Breakdown by tier (free/household/business) — stacked
   - Tooltip on hover showing exact values
   - Zoom and pan support

4. User Growth Chart:
   - Cumulative user count over time
   - New signups per day (bar overlay)
   - Total active users line

5. Camera Adoption Chart:
   - Distribution: users with 1-2 cameras, 3-5 cameras, 6-10 cameras
   - Pie chart or horizontal bar chart
   - Average cameras per user stat

6. Top Users Table:
   - Columns: Email, Tier, Cameras, Events (30d), Revenue, Status
   - Sortable by any column
   - Click to view user detail
   - Pagination (20 per page)

7. Export Functionality:
   - CSV export: all table data
   - PDF export: charts + summary (using html2canvas + jsPDF)
   - Date range in filename

TEST CASES:
test_admin_analytics_page_loads, test_summary_cards_display_correct_values, test_revenue_chart_renders, test_user_growth_chart_renders, test_camera_adoption_chart_renders, test_event_trends_chart_renders, test_top_users_table_sorted, test_date_range_filter_works, test_csv_export_generates_file, test_pdf_export_generates_file, test_non_admin_gets_403, test_mobile_responsive_layout

OUTPUT: Generate admin_analytics.html, admin_analytics.js, admin_analytics.css, and test_admin_analytics.py.
```

---

## Quick Reference: V9 File Paths

| Sprint | File Path |
|--------|-----------|
| 11.1 | `backend/dashboard/templates/landing.html` |
| 11.1 | `backend/dashboard/static/landing.js` |
| 11.1 | `backend/dashboard/static/landing.css` |
| 11.1 | `backend/tests/unit/test_landing.py` |
| 11.2 | `backend/api/public_signup.py` |
| 11.2 | `backend/tests/unit/test_public_signup.py` |
| 11.3 | `backend/notifications/email_service.py` |
| 11.3 | `backend/tests/unit/test_email_service.py` |
| 11.4 | `backend/dashboard/templates/help.html` |
| 11.4 | `backend/dashboard/templates/help_article.html` |
| 11.4 | `backend/dashboard/static/help.js` |
| 11.4 | `backend/dashboard/static/help.css` |
| 11.4 | `backend/tests/unit/test_help.py` |
| 11.5 | `backend/dashboard/templates/admin_analytics.html` |
| 11.5 | `backend/dashboard/static/admin_analytics.js` |
| 11.5 | `backend/dashboard/static/admin_analytics.css` |
| 11.5 | `backend/tests/unit/test_admin_analytics.py` |

---

*Vision OS V9 — Launch Features & Polish*

*Copy, paste, generate, test, commit. Repeat.*
