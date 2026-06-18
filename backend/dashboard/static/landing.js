/**
 * landing.js — Vision OS Public Landing Page
 *
 * Features:
 * - Mobile navigation toggle
 * - Smooth scroll for anchor links
 * - FAQ accordion
 * - Sticky nav on scroll
 * - Intersection Observer for animations
 */

// ═══════════════════════════════════════════════════════════════
// DOM Ready
// ═══════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", function () {
  initNavToggle();
  initSmoothScroll();
  initFaqAccordion();
  initStickyNav();
  initScrollAnimations();
});

// ═══════════════════════════════════════════════════════════════
// Mobile Navigation Toggle
// ═══════════════════════════════════════════════════════════════

function initNavToggle() {
  const toggle = document.getElementById("nav-toggle");
  const menu = document.getElementById("nav-menu");

  if (!toggle || !menu) return;

  toggle.addEventListener("click", function () {
    menu.classList.toggle("open");
    toggle.setAttribute("aria-label",
      menu.classList.contains("open") ? "Close navigation" : "Toggle navigation"
    );
  });

  // Close menu when clicking a link
  menu.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      menu.classList.remove("open");
      toggle.setAttribute("aria-label", "Toggle navigation");
    });
  });

  // Close menu when clicking outside
  document.addEventListener("click", function (event) {
    if (window.innerWidth < 768 &&
        menu.classList.contains("open") &&
        !menu.contains(event.target) &&
        !toggle.contains(event.target)) {
      menu.classList.remove("open");
      toggle.setAttribute("aria-label", "Toggle navigation");
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// Smooth Scroll for Anchor Links
// ═══════════════════════════════════════════════════════════════

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener("click", function (event) {
      const targetId = this.getAttribute("href");
      if (targetId === "#") return;

      const target = document.querySelector(targetId);
      if (target) {
        event.preventDefault();
        const navHeight = document.querySelector(".landing-nav").offsetHeight || 70;
        const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;

        window.scrollTo({
          top: targetPosition,
          behavior: "smooth"
        });
      }
    });
  });
}

// ═══════════════════════════════════════════════════════════════
// FAQ Accordion
// ═══════════════════════════════════════════════════════════════

function initFaqAccordion() {
  const faqItems = document.querySelectorAll(".faq-item");

  faqItems.forEach(function (item) {
    const question = item.querySelector(".faq-question");

    question.addEventListener("click", function () {
      const isExpanded = this.getAttribute("aria-expanded") === "true";

      // Close all other items
      faqItems.forEach(function (other) {
        if (other !== item) {
          other.querySelector(".faq-question").setAttribute("aria-expanded", "false");
          other.querySelector(".faq-answer").style.maxHeight = "0";
          other.querySelector(".faq-icon").textContent = "+";
        }
      });

      // Toggle current item
      this.setAttribute("aria-expanded", !isExpanded);
      const answer = this.nextElementSibling;
      const icon = this.querySelector(".faq-icon");

      if (!isExpanded) {
        answer.style.maxHeight = answer.scrollHeight + "px";
        icon.textContent = "−";
      } else {
        answer.style.maxHeight = "0";
        icon.textContent = "+";
      }
    });
  });
}

// ═══════════════════════════════════════════════════════════════
// Sticky Navigation
// ═══════════════════════════════════════════════════════════════

function initStickyNav() {
  const nav = document.getElementById("landing-nav");
  let lastScrollY = 0;

  window.addEventListener("scroll", function () {
    const scrollY = window.pageYOffset;

    if (scrollY > 100) {
      nav.classList.add("nav-scrolled");
    } else {
      nav.classList.remove("nav-scrolled");
    }

    lastScrollY = scrollY;
  }, { passive: true });
}

// ═══════════════════════════════════════════════════════════════
// Scroll Animations with Intersection Observer
// ═══════════════════════════════════════════════════════════════

function initScrollAnimations() {
  // Only run if IntersectionObserver is supported
  if (!("IntersectionObserver" in window)) return;

  const animateElements = document.querySelectorAll(
    ".feature-card, .step-card, .pricing-card, .testimonial-card, .faq-item"
  );

  const observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("animate-in");
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.1,
      rootMargin: "0px 0px -50px 0px"
    }
  );

  animateElements.forEach(function (el) {
    el.classList.add("animate-ready");
    observer.observe(el);
  });
}
