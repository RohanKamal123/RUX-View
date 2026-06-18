/**
 * onboarding.js — Vision OS Multi-Step Onboarding Wizard
 *
 * Handles step navigation, form validation, API calls,
 * progress tracking, and camera management.
 */

// ── State ──────────────────────────────────────────────────────

let currentStep = 1;
const TOTAL_STEPS = 6;
const STEP_NAMES = ["Account", "Location", "Camera", "Mode", "Notifications", "Payment"];
let cameras = [{}]; // array of camera data objects
let selectedTier = "free";
let couponDiscount = 0;
let onboardingComplete = false;

// ── Initialization ─────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async function () {
  // Check if onboarding already in progress
  try {
    const res = await fetch("/api/onboarding/state");
    if (res.ok) {
      const data = await res.json();
      if (data.current_step && !data.is_complete) {
        goToStep(data.current_step);
        restoreStepData(data.step_data || {});
      }
    }
  } catch (e) {
    // No existing session — start fresh
  }

  // Location type toggle
  document.querySelectorAll('input[name="loc-type"]').forEach((radio) => {
    radio.addEventListener("change", function () {
      const bizGroup = document.getElementById("business-hours-group");
      bizGroup.style.display =
        this.value === "shop" || this.value === "office" ? "block" : "none";
    });
  });
});

// ── Step Navigation ────────────────────────────────────────────

function goToStep(step) {
  // Hide all steps
  document.querySelectorAll(".onboarding-step").forEach((el) => {
    el.classList.remove("active");
    el.style.display = "none";
  });

  // Show target step
  const target = document.getElementById(`step-${step}`);
  if (target) {
    target.classList.add("active");
    target.style.display = "block";
  }

  currentStep = step;
  updateProgressBar();
  updateProgressSteps();
}

function updateProgressBar() {
  const pct = ((currentStep - 1) / (TOTAL_STEPS - 1)) * 100;
  const fill = document.getElementById("progress-fill");
  if (fill) fill.style.width = `${Math.min(pct, 100)}%`;
}

function updateProgressSteps() {
  for (let i = 1; i <= TOTAL_STEPS; i++) {
    const el = document.getElementById(`progress-step-${i}`);
    if (!el) continue;
    el.classList.remove("active", "completed");
    if (i === currentStep) el.classList.add("active");
    else if (i < currentStep) el.classList.add("completed");
  }
}

// ── Step Actions ───────────────────────────────────────────────

async function saveStep(step) {
  const data = collectStepData(step);
  if (!data) return; // validation failed

  try {
    const res = await fetch("/api/onboarding/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step: step, data: data }),
    });

    if (!res.ok) {
      const err = await res.json();
      showError(err.detail || "Failed to save step");
      return;
    }

    if (step < TOTAL_STEPS) {
      goToStep(step + 1);
    } else {
      await completeOnboarding();
    }
  } catch (e) {
    showError("Network error. Please try again.");
  }
}

async function skipStep(step) {
  try {
    const res = await fetch("/api/onboarding/skip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step: step }),
    });

    if (!res.ok) {
      const err = await res.json();
      showError(err.detail || "Failed to skip step");
      return;
    }

    if (step < TOTAL_STEPS) {
      goToStep(step + 1);
    } else {
      await completeOnboarding();
    }
  } catch (e) {
    showError("Network error. Please try again.");
  }
}

async function goBack() {
  if (currentStep > 1) {
    try {
      await fetch("/api/onboarding/go-back", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step: currentStep - 1 }),
      });
    } catch (e) {
      // Continue even if API fails
    }
    goToStep(currentStep - 1);
  }
}

async function completeOnboarding() {
  try {
    const res = await fetch("/api/onboarding/complete", { method: "POST" });
    if (!res.ok) throw new Error("Failed to complete onboarding");

    const summary = await res.json();

    // Show completion screen
    document.querySelectorAll(".onboarding-step").forEach((el) => {
      el.classList.remove("active");
      el.style.display = "none";
    });
    const completeEl = document.getElementById("step-complete");
    if (completeEl) {
      completeEl.style.display = "block";
      completeEl.classList.add("active");
    }

    document.getElementById("complete-steps").textContent =
      summary.total_steps_completed || 6;
    document.getElementById("complete-cameras").textContent =
      cameras.length || 0;
    document.getElementById("complete-tier").textContent =
      selectedTier.charAt(0).toUpperCase() + selectedTier.slice(1);

    onboardingComplete = true;
  } catch (e) {
    showError("Failed to complete setup. Please try again.");
  }
}

function finishOnboarding() {
  window.location.href = "/";
}

// ── Data Collection ────────────────────────────────────────────

function collectStepData(step) {
  switch (step) {
    case 1:
      return collectAccountData();
    case 2:
      return collectLocationData();
    case 3:
      return collectCameraData();
    case 4:
      return collectModeData();
    case 5:
      return collectNotificationData();
    case 6:
      return collectPaymentData();
    default:
      return {};
  }
}

function collectAccountData() {
  const email = document.getElementById("account-email").value.trim();
  const name = document.getElementById("account-name").value.trim();
  const phone = document.getElementById("account-phone").value.trim();
  const company = document.getElementById("account-company").value.trim();
  const timezone = document.getElementById("account-timezone").value;

  if (!email) {
    showError("Please enter your email address.");
    return null;
  }
  if (!name) {
    showError("Please enter your name.");
    return null;
  }
  if (!phone) {
    showError("Please enter your phone number.");
    return null;
  }

  return { email, name, phone, company, timezone };
}

function collectLocationData() {
  const name = document.getElementById("location-name").value.trim();
  const address = document.getElementById("location-address").value.trim();
  const type = document.querySelector('input[name="loc-type"]:checked')?.value || "home";
  const bizOpen = document.getElementById("biz-open")?.value;
  const bizClose = document.getElementById("biz-close")?.value;

  if (!name) {
    showError("Please enter a location name.");
    return null;
  }

  const data = { name, address, type };
  if ((type === "shop" || type === "office") && bizOpen && bizClose) {
    data.business_hours = { open: bizOpen, close: bizClose };
  }
  return data;
}

function collectCameraData() {
  const cameraEntries = document.querySelectorAll(".camera-entry");
  const camerasData = [];

  cameraEntries.forEach((entry) => {
    const name = entry.querySelector(".cam-name")?.value?.trim();
    const rtsp = entry.querySelector(".cam-rtsp")?.value?.trim();
    const user = entry.querySelector(".cam-user")?.value?.trim();
    const pass = entry.querySelector(".cam-pass")?.value;
    const type = entry.querySelector(".cam-type")?.value || "indoor";

    if (name && rtsp) {
      camerasData.push({ name, rtsp, username: user, password: pass, type });
    }
  });

  return { cameras: camerasData };
}

function collectModeData() {
  const modeSelections = [];
  document.querySelectorAll(".mode-entry").forEach((entry) => {
    const camIndex = entry.dataset.camIndex;
    const mode = entry.querySelector(".cam-mode-select")?.value || "indoor";
    const ignoreZones = entry.querySelector(".ignore-zones")?.value?.trim() || "";
    modeSelections.push({ camera_index: parseInt(camIndex), mode, ignore_zones: ignoreZones });
  });

  const bizOpen = document.getElementById("mode-biz-open")?.value;
  const bizClose = document.getElementById("mode-biz-close")?.value;

  const data = { modes: modeSelections };
  if (bizOpen && bizClose) {
    data.business_hours = { open: bizOpen, close: bizClose };
  }
  return data;
}

function collectNotificationData() {
  const alertLevels = [];
  document.querySelectorAll(".alert-level:checked").forEach((cb) => {
    alertLevels.push(cb.value);
  });

  const quietStart = document.getElementById("quiet-start")?.value;
  const quietEnd = document.getElementById("quiet-end")?.value;
  const smsPhone = document.getElementById("sms-phone")?.value?.trim();

  return {
    alert_levels: alertLevels,
    quiet_hours: { start: quietStart, end: quietEnd },
    sms_fallback: smsPhone || null,
  };
}

function collectPaymentData() {
  const paymentNumber = document.getElementById("payment-number")?.value?.trim();
  const couponCode = document.getElementById("coupon-code")?.value?.trim();

  return {
    tier: selectedTier,
    payment_number: paymentNumber || null,
    coupon_code: couponCode || null,
    discount: couponDiscount,
  };
}

// ── Camera Management ──────────────────────────────────────────

let cameraCount = 1;
const MAX_CAMERAS = 10;

function addCameraEntry() {
  if (cameraCount >= MAX_CAMERAS) {
    showError(`Maximum ${MAX_CAMERAS} cameras allowed during onboarding.`);
    return;
  }

  const container = document.getElementById("cameras-container");
  const index = cameraCount;
  const div = document.createElement("div");
  div.className = "camera-entry";
  div.dataset.camIndex = index;
  div.innerHTML = `
    <div class="cam-header">
      <h4>Camera #${index + 1}</h4>
      <button class="btn btn-sm btn-danger" onclick="removeCameraEntry(this)">Remove</button>
    </div>
    <div class="form-group">
      <label>Camera Name</label>
      <input type="text" class="form-input cam-name" placeholder="e.g. Back Door" />
    </div>
    <div class="form-group">
      <label>RTSP URL</label>
      <input type="text" class="form-input cam-rtsp" placeholder="rtsp://192.168.1.101:554/stream1" />
    </div>
    <div class="form-row">
      <div class="form-group half">
        <label>Username</label>
        <input type="text" class="form-input cam-user" placeholder="admin" />
      </div>
      <div class="form-group half">
        <label>Password</label>
        <input type="password" class="form-input cam-pass" placeholder="••••••••" />
      </div>
    </div>
    <div class="form-group">
      <label>Camera Type</label>
      <select class="form-input cam-type">
        <option value="indoor">Indoor</option>
        <option value="outdoor">Outdoor</option>
        <option value="doorbell">Doorbell</option>
        <option value="PTZ">PTZ</option>
      </select>
    </div>
    <div class="cam-actions">
      <button class="btn btn-sm btn-outline test-connection-btn" onclick="testCameraConnection(${index})">Test Connection</button>
      <span class="cam-test-result" id="cam-test-${index}"></span>
    </div>
  `;
  container.appendChild(div);
  cameraCount++;
}

function removeCameraEntry(btn) {
  const entry = btn.closest(".camera-entry");
  if (entry) {
    entry.remove();
    cameraCount--;
    // Renumber remaining cameras
    document.querySelectorAll(".camera-entry").forEach((el, i) => {
      el.querySelector("h4").textContent = `Camera #${i + 1}`;
      el.dataset.camIndex = i;
    });
  }
}

async function testCameraConnection(index) {
  const entry = document.querySelector(`.camera-entry[data-cam-index="${index}"]`);
  if (!entry) return;

  const rtsp = entry.querySelector(".cam-rtsp")?.value?.trim();
  const resultEl = document.getElementById(`cam-test-${index}`);
  if (!resultEl) return;

  if (!rtsp) {
    resultEl.textContent = "❌ Please enter RTSP URL first";
    resultEl.className = "cam-test-result error";
    return;
  }

  resultEl.textContent = "⏳ Testing connection...";
  resultEl.className = "cam-test-result";

  try {
    const res = await fetch("/api/cameras/test-connection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rtsp_url: rtsp,
        username: entry.querySelector(".cam-user")?.value?.trim() || "",
        password: entry.querySelector(".cam-pass")?.value || "",
      }),
    });

    const data = await res.json();
    if (data.connected) {
      resultEl.textContent = "✅ Connection successful";
      resultEl.className = "cam-test-result success";
    } else {
      resultEl.textContent = `❌ ${data.error || "Connection failed"}`;
      resultEl.className = "cam-test-result error";
    }
  } catch (e) {
    resultEl.textContent = "❌ Network error";
    resultEl.className = "cam-test-result error";
  }
}

// ── Mode Step — Populate Cameras ───────────────────────────────

function populateModeCameras(camerasData) {
  const container = document.getElementById("mode-cameras-container");
  if (!container) return;

  if (!camerasData || camerasData.length === 0) {
    container.innerHTML = '<p class="no-cameras-msg">No cameras added yet. You can configure modes later.</p>';
    return;
  }

  container.innerHTML = "";
  camerasData.forEach((cam, i) => {
    const div = document.createElement("div");
    div.className = "mode-entry";
    div.dataset.camIndex = i;
    div.innerHTML = `
      <div class="mode-cam-header">
        <h4>${cam.name || `Camera #${i + 1}`}</h4>
      </div>
      <div class="form-group">
        <label>Mode</label>
        <select class="form-input cam-mode-select">
          <option value="indoor" ${cam.type === "indoor" ? "selected" : ""}>Indoor</option>
          <option value="outdoor" ${cam.type === "outdoor" ? "selected" : ""}>Outdoor</option>
          <option value="parking" ${cam.type === "parking" ? "selected" : ""}>Parking</option>
          <option value="mixed" ${cam.type === "mixed" ? "selected" : ""}>Mixed</option>
          <option value="shop" ${cam.type === "shop" ? "selected" : ""}>Shop</option>
        </select>
      </div>
      <div class="form-group">
        <label>Ignore Zones <span class="optional">(optional)</span></label>
        <textarea class="form-input ignore-zones" placeholder="e.g. [[0,0,100,100], [200,200,300,300]]" rows="2"></textarea>
      </div>
    `;
    container.appendChild(div);
  });
}

// ── Payment / Tier Selection ───────────────────────────────────

function selectTier(tier) {
  selectedTier = tier;
  document.querySelectorAll(".tier-card").forEach((card) => {
    card.classList.toggle("selected", card.dataset.tier === tier);
  });
  updateSummary();
}

async function applyCoupon() {
  const code = document.getElementById("coupon-code")?.value?.trim();
  const resultEl = document.getElementById("coupon-result");
  if (!code) {
    resultEl.textContent = "Please enter a coupon code.";
    return;
  }

  try {
    const res = await fetch("/api/payments/validate-coupon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code }),
    });

    const data = await res.json();
    if (data.valid) {
      couponDiscount = data.discount_amount || 0;
      resultEl.textContent = `✅ Coupon applied! Discount: ${couponDiscount} BDT`;
      resultEl.className = "field-hint success";
    } else {
      couponDiscount = 0;
      resultEl.textContent = `❌ ${data.message || "Invalid coupon"}`;
      resultEl.className = "field-hint error";
    }
    updateSummary();
  } catch (e) {
    resultEl.textContent = "❌ Network error";
    resultEl.className = "field-hint error";
  }
}

function updateSummary() {
  const tierNames = { free: "Free Trial", household: "Household", business: "Business" };
  const tierPrices = { free: 0, household: 299, business: 499 };
  const cameraCount = document.querySelectorAll(".camera-entry").length || 0;

  document.getElementById("summary-tier").textContent = tierNames[selectedTier] || "Free Trial";
  document.getElementById("summary-cameras").textContent = cameraCount;

  let total = cameraCount * (tierPrices[selectedTier] || 0);
  total = Math.max(0, total - couponDiscount);
  document.getElementById("summary-total").textContent = `${total} BDT`;
}

// ── Error Display ──────────────────────────────────────────────

function showError(message) {
  // Remove existing error
  const existing = document.querySelector(".onboarding-error");
  if (existing) existing.remove();

  const errorDiv = document.createElement("div");
  errorDiv.className = "onboarding-error";
  errorDiv.textContent = message;
  errorDiv.style.cssText =
    "background: #d32f2f; color: white; padding: 12px 20px; border-radius: 8px; margin-bottom: 16px; text-align: center; animation: fadeIn 0.3s;";

  const activeStep = document.querySelector(".onboarding-step.active");
  if (activeStep) {
    activeStep.insertBefore(errorDiv, activeStep.firstChild);
  }

  setTimeout(() => {
    if (errorDiv.parentNode) errorDiv.remove();
  }, 5000);
}

// ── Restore Step Data (for resume) ─────────────────────────────

function restoreStepData(stepData) {
  if (!stepData) return;

  // Restore account data
  const step1 = stepData[1];
  if (step1) {
    setVal("account-email", step1.email);
    setVal("account-name", step1.name);
    setVal("account-phone", step1.phone);
    setVal("account-company", step1.company);
    if (step1.timezone) setVal("account-timezone", step1.timezone);
  }

  // Restore location data
  const step2 = stepData[2];
  if (step2) {
    setVal("location-name", step2.name);
    setVal("location-address", step2.address);
    if (step2.type) {
      const radio = document.querySelector(`input[name="loc-type"][value="${step2.type}"]`);
      if (radio) radio.checked = true;
    }
    if (step2.business_hours) {
      setVal("biz-open", step2.business_hours.open);
      setVal("biz-close", step2.business_hours.close);
    }
  }

  // Restore camera data
  const step3 = stepData[3];
  if (step3 && step3.cameras && step3.cameras.length > 0) {
    // Remove default empty camera entry
    const container = document.getElementById("cameras-container");
    container.innerHTML = "";
    cameraCount = 0;
    step3.cameras.forEach((cam, i) => {
      if (i > 0) addCameraEntry();
      const entries = document.querySelectorAll(".camera-entry");
      const entry = entries[entries.length - 1];
      if (entry) {
        const inputs = entry.querySelectorAll("input");
        if (inputs[0]) inputs[0].value = cam.name || "";
        if (inputs[1]) inputs[1].value = cam.rtsp || "";
        if (inputs[2]) inputs[2].value = cam.username || "";
        if (inputs[3]) inputs[3].value = cam.password || "";
        const typeSelect = entry.querySelector(".cam-type");
        if (typeSelect && cam.type) typeSelect.value = cam.type;
      }
    });
  }

  // Restore notification data
  const step5 = stepData[5];
  if (step5) {
    if (step5.alert_levels) {
      document.querySelectorAll(".alert-level").forEach((cb) => {
        cb.checked = step5.alert_levels.includes(cb.value);
      });
    }
    if (step5.quiet_hours) {
      setVal("quiet-start", step5.quiet_hours.start);
      setVal("quiet-end", step5.quiet_hours.end);
    }
    if (step5.sms_fallback) setVal("sms-phone", step5.sms_fallback);
  }

  // Restore payment data
  const step6 = stepData[6];
  if (step6) {
    if (step6.tier) selectTier(step6.tier);
    if (step6.payment_number) setVal("payment-number", step6.payment_number);
    if (step6.coupon_code) setVal("coupon-code", step6.coupon_code);
  }
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el && val !== undefined && val !== null) el.value = val;
}

// ── Keyboard Navigation ────────────────────────────────────────

document.addEventListener("keydown", function (e) {
  if (e.key === "Enter") {
    const activeStep = document.querySelector(".onboarding-step.active");
    if (activeStep) {
      const stepNum = parseInt(activeStep.id.replace("step-", ""));
      if (!isNaN(stepNum) && stepNum >= 1 && stepNum <= TOTAL_STEPS) {
        e.preventDefault();
        saveStep(stepNum);
      }
    }
  }
});
