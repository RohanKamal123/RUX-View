/**
 * help.js — Vision OS Help Center & Documentation
 *
 * Features:
 * - Real-time search across articles
 * - Category filtering
 * - Auto-generated table of contents
 * - Article feedback (helpful/not helpful)
 * - Mobile-responsive navigation
 */

(function () {
  'use strict';

  // ═══════════════════════════════════════════════════════════════
  // Article Database (for search)
  // ═══════════════════════════════════════════════════════════════

  const articles = [
    // Getting Started
    { title: 'How to connect your first camera', category: 'getting-started', slug: 'how-to-connect-first-camera', content: 'Connect your camera by entering the RTSP URL in the dashboard. Go to Cameras > Add Camera and paste your RTSP URL.' },
    { title: 'Understanding the dashboard', category: 'getting-started', slug: 'understanding-the-dashboard', content: 'The dashboard shows your camera feeds, recent events, and alerts. Use the sidebar to navigate between sections.' },
    { title: 'Setting up Telegram alerts', category: 'getting-started', slug: 'setting-up-telegram-alerts', content: 'Go to Settings > Notifications > Telegram. Enter your bot token and chat ID to receive real-time alerts.' },
    { title: 'Adding multiple cameras', category: 'getting-started', slug: 'adding-multiple-cameras', content: 'You can add up to 10 cameras. Repeat the connection process for each camera from the Cameras page.' },

    // Cameras
    { title: 'Camera modes explained', category: 'cameras', slug: 'camera-modes-explained', content: 'Vision OS supports Indoor, Outdoor, Parking, Shop, and Mixed modes. Each mode optimizes detection settings.' },
    { title: 'RTSP URL format', category: 'cameras', slug: 'rtsp-url-format', content: 'RTSP URLs follow the format: rtsp://username:password@ip:port/path. Check your camera manual for the exact URL.' },
    { title: 'Troubleshooting connection', category: 'cameras', slug: 'troubleshooting-connection', content: 'If your camera won\'t connect, check: network connectivity, RTSP URL format, username/password, and firewall settings.' },
    { title: 'Camera placement tips', category: 'cameras', slug: 'camera-placement-tips', content: 'Place cameras at entry points, avoid direct sunlight, ensure good lighting, and keep lenses clean for best results.' },
    { title: 'Managing 10 cameras', category: 'cameras', slug: 'managing-10-cameras', content: 'Organize cameras by location, use descriptive names, and group them for easier monitoring across all feeds.' },

    // Alerts
    { title: 'Alert levels explained', category: 'alerts', slug: 'alert-levels-explained', content: 'Alerts are categorized: Info (low priority), Warning (medium), Critical (high), and Emergency (immediate action required).' },
    { title: 'Customizing alert preferences', category: 'alerts', slug: 'customizing-alert-preferences', content: 'Go to Settings > Alerts to choose which events trigger notifications and their delivery method (Telegram, email, push).' },
    { title: 'Emergency alerts', category: 'alerts', slug: 'emergency-alerts', content: 'Emergency alerts are triggered by glass breaking, gunshots, or shouting. These are sent immediately via all channels.' },
    { title: 'Quiet hours setup', category: 'alerts', slug: 'quiet-hours-setup', content: 'Set quiet hours in Settings > Alerts > Quiet Hours to suppress non-critical notifications during specific times.' },

    // Billing
    { title: 'Pricing plans', category: 'billing', slug: 'pricing-plans', content: 'Vision OS offers Free Trial (30 days), Household (299 BDT/camera/month), and Business (499 BDT/camera/month) plans.' },
    { title: 'How to pay via bKash', category: 'billing', slug: 'how-to-pay-via-bkash', content: 'Go to Billing > Payment Methods, select bKash, enter your bKash number, and confirm the payment via your bKash app.' },
    { title: 'Understanding your bill', category: 'billing', slug: 'understanding-your-bill', content: 'Your bill is calculated based on the number of active cameras and your plan tier. Bills are generated monthly.' },
    { title: 'Cancelling your subscription', category: 'billing', slug: 'cancelling-your-subscription', content: 'Go to Settings > Subscription > Cancel. Your service will continue until the end of the current billing period.' },
    { title: 'Trial period FAQ', category: 'billing', slug: 'trial-period-faq', content: 'Your 30-day free trial includes full access to all features. No payment method is required to start.' },

    // Troubleshooting
    { title: 'Camera offline', category: 'troubleshooting', slug: 'camera-offline', content: 'If your camera shows offline: check power, network connection, RTSP URL, and restart the camera. Contact support if the issue persists.' },
    { title: 'No alerts received', category: 'troubleshooting', slug: 'no-alerts-received', content: 'Check your notification settings, ensure Telegram/email is configured, and verify that alerts are enabled for the camera.' },
    { title: 'Login issues', category: 'troubleshooting', slug: 'login-issues', content: 'If you can\'t log in: reset your password, check your email for verification, or clear your browser cache.' },
    { title: 'Slow dashboard', category: 'troubleshooting', slug: 'slow-dashboard', content: 'If the dashboard is slow: reduce the number of visible cameras, check your internet speed, or try a different browser.' },
    { title: 'Audio not working', category: 'troubleshooting', slug: 'audio-not-working', content: 'Ensure your camera has a microphone, check audio settings in the dashboard, and verify browser permissions for audio.' },

    // FAQ
    { title: 'What cameras are supported?', category: 'faq', slug: 'what-cameras-are-supported', content: 'Vision OS supports any IP camera that provides an RTSP stream. This includes brands like Hikvision, Dahua, TP-Link, and more.' },
    { title: 'Is my data secure?', category: 'faq', slug: 'is-my-data-secure', content: 'Yes. All video streams are encrypted in transit and at rest. We use industry-standard security practices to protect your data.' },
    { title: 'Can I use multiple locations?', category: 'faq', slug: 'can-i-use-multiple-locations', content: 'Yes, you can group cameras by location. This helps organize cameras across different properties or areas.' },
    { title: 'What happens after trial?', category: 'faq', slug: 'what-happens-after-trial', content: 'After your 30-day trial, you can choose a paid plan. You have a 7-day grace period before features are limited.' },
    { title: 'Do I need internet for cameras?', category: 'faq', slug: 'do-i-need-internet-for-cameras', content: 'Yes, an internet connection is required for AI processing and remote access. Local recording may work without internet.' },
  ];

  // ═══════════════════════════════════════════════════════════════
  // Search Functionality
  // ═══════════════════════════════════════════════════════════════

  const searchInput = document.getElementById('helpSearch');
  const searchResults = document.getElementById('searchResults');
  const searchClear = document.getElementById('searchClear');

  if (searchInput && searchResults) {
    searchInput.addEventListener('input', function () {
      const query = this.value.trim().toLowerCase();
      performSearch(query);
    });

    searchInput.addEventListener('focus', function () {
      if (this.value.trim().length > 0) {
        searchResults.classList.add('visible');
      }
    });

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.help-search-container')) {
        searchResults.classList.remove('visible');
      }
    });

    if (searchClear) {
      searchClear.addEventListener('click', function () {
        searchInput.value = '';
        searchResults.classList.remove('visible');
        searchInput.focus();
        showAllCategories();
      });
    }
  }

  function performSearch(query) {
    if (query.length < 1) {
      searchResults.classList.remove('visible');
      showAllCategories();
      return;
    }

    const results = articles.filter(function (article) {
      const titleMatch = article.title.toLowerCase().includes(query);
      const contentMatch = article.content.toLowerCase().includes(query);
      const categoryMatch = article.category.toLowerCase().includes(query);
      return titleMatch || contentMatch || categoryMatch;
    });

    displaySearchResults(results, query);
  }

  function displaySearchResults(results, query) {
    if (results.length === 0) {
      searchResults.innerHTML = '<div class="search-no-results">No articles found. Try a different search term.</div>';
    } else {
      var html = '';
      results.forEach(function (article) {
        var highlightedTitle = highlightMatch(article.title, query);
        var highlightedContent = highlightMatch(article.content.substring(0, 120), query);
        html += '<a href="/help/article/' + article.slug + '" class="search-result-item" role="option">';
        html += '<div class="search-result-title">' + highlightedTitle + '</div>';
        html += '<div class="search-result-category">' + article.category + '</div>';
        html += '<div class="search-result-preview">' + highlightedContent + '...</div>';
        html += '</a>';
      });
      searchResults.innerHTML = html;
    }
    searchResults.classList.add('visible');
  }

  function highlightMatch(text, query) {
    var regex = new RegExp('(' + escapeRegExp(query) + ')', 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }

  function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function showAllCategories() {
    var cards = document.querySelectorAll('.category-card');
    cards.forEach(function (card) {
      card.style.display = 'block';
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Category Filtering
  // ═══════════════════════════════════════════════════════════════

  const filterButtons = document.querySelectorAll('.filter-btn');
  const categoryCards = document.querySelectorAll('.category-card');

  filterButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      // Update active state
      filterButtons.forEach(function (b) { b.classList.remove('active'); });
      this.classList.add('active');

      var category = this.getAttribute('data-category');

      categoryCards.forEach(function (card) {
        if (category === 'all') {
          card.style.display = 'block';
        } else {
          var cardCategory = card.getAttribute('data-category');
          card.style.display = cardCategory === category ? 'block' : 'none';
        }
      });
    });
  });

  // ═══════════════════════════════════════════════════════════════
  // Table of Contents (Article Page)
  // ═══════════════════════════════════════════════════════════════

  function generateTOC() {
    var tocList = document.getElementById('tocList');
    var articleBody = document.querySelector('.article-body');

    if (!tocList || !articleBody) return;

    var headings = articleBody.querySelectorAll('h2, h3');
    if (headings.length === 0) {
      document.getElementById('articleToc').style.display = 'none';
      return;
    }

    headings.forEach(function (heading, index) {
      var id = 'section-' + index;
      heading.setAttribute('id', id);

      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + id;
      a.textContent = heading.textContent;

      if (heading.tagName === 'H3') {
        li.classList.add('toc-subitem');
      }

      li.appendChild(a);
      tocList.appendChild(li);
    });

    // Smooth scroll for TOC links
    tocList.addEventListener('click', function (e) {
      var target = e.target;
      if (target.tagName === 'A') {
        e.preventDefault();
        var href = target.getAttribute('href');
        if (href && href.startsWith('#')) {
          var el = document.getElementById(href.substring(1));
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }
      }
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Article Feedback
  // ═══════════════════════════════════════════════════════════════

  const feedbackButtons = document.querySelectorAll('.feedback-btn');
  const feedbackThanks = document.getElementById('feedbackThanks');

  feedbackButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var feedback = this.getAttribute('data-feedback');

      // Disable buttons after feedback
      feedbackButtons.forEach(function (b) {
        b.disabled = true;
        b.classList.add('feedback-submitted');
      });

      // Show thank you message
      if (feedbackThanks) {
        feedbackThanks.style.display = 'block';
      }

      // Store feedback (could send to server)
      try {
        localStorage.setItem('article_feedback_' + window.location.pathname, feedback);
      } catch (e) {
        // localStorage not available
      }
    });
  });

  // ═══════════════════════════════════════════════════════════════
  // Initialize
  // ═══════════════════════════════════════════════════════════════

  document.addEventListener('DOMContentLoaded', function () {
    generateTOC();
  });

})();
