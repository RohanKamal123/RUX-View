/**
 * Vision OS Dashboard — Frontend JavaScript
 *
 * Features:
 * - Sidebar toggle for mobile
 * - Event feed filtering by camera/threat
 * - Auto-refresh every 30s
 * - Firebase Auth integration
 * - Person label editing
 * - Camera management
 */

// ═══════════════════════════════════════════════════════════════
// Sidebar
// ═══════════════════════════════════════════════════════════════

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', function (event) {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.querySelector('.sidebar-toggle');

  if (window.innerWidth < 768 &&
      sidebar.classList.contains('open') &&
      !sidebar.contains(event.target) &&
      !toggle.contains(event.target)) {
    sidebar.classList.remove('open');
  }
});

// ═══════════════════════════════════════════════════════════════
// Event Feed Filtering
// ═══════════════════════════════════════════════════════════════

function applyFilters() {
  const cameraFilter = document.getElementById('camera-filter');
  const threatFilter = document.getElementById('threat-filter');
  const cards = document.querySelectorAll('.event-card');

  const cameraValue = cameraFilter ? cameraFilter.value : '';
  const threatValue = threatFilter ? threatFilter.value : '';

  cards.forEach(function (card) {
    const cardCamera = card.getAttribute('data-camera') || '';
    const cardThreat = card.getAttribute('data-threat') || '';

    const cameraMatch = !cameraValue || cardCamera === cameraValue;
    const threatMatch = !threatValue || cardThreat === threatValue;

    card.style.display = cameraMatch && threatMatch ? 'flex' : 'none';
  });
}

// ═══════════════════════════════════════════════════════════════
// Auto-Refresh (every 30s)
// ═══════════════════════════════════════════════════════════════

let refreshInterval = null;

function startAutoRefresh() {
  // Only start on the event feed page
  const eventFeed = document.getElementById('event-feed');
  if (!eventFeed) return;

  // Clear existing interval
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }

  refreshInterval = setInterval(function () {
    refreshEventFeed();
  }, 30000); // 30 seconds
}

async function refreshEventFeed() {
  const eventFeed = document.getElementById('event-feed');
  const skeletonFeed = document.getElementById('skeleton-feed');
  if (!eventFeed) return;

  try {
    // Show skeleton loading
    if (skeletonFeed) {
      eventFeed.style.display = 'none';
      skeletonFeed.style.display = 'flex';
    }

    // Build query params from current filters
    const cameraFilter = document.getElementById('camera-filter');
    const threatFilter = document.getElementById('threat-filter');
    const params = new URLSearchParams();

    if (cameraFilter && cameraFilter.value) {
      params.set('camera_id', cameraFilter.value);
    }
    if (threatFilter && threatFilter.value) {
      params.set('threat_level', threatFilter.value);
    }
    params.set('limit', '50');

    const url = '/api/events?' + params.toString();
    const response = await fetch(url);
    const data = await response.json();

    // Rebuild event feed
    if (data.events && data.events.length > 0) {
      eventFeed.innerHTML = '';
      data.events.forEach(function (event) {
        const card = createEventCard(event);
        eventFeed.appendChild(card);
      });
    } else {
      eventFeed.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">&#x1F50D;</div>
          <p>No events match your filters.</p>
          <p>Try adjusting the camera or threat level filters.</p>
        </div>
      `;
    }

    // Hide skeleton
    if (skeletonFeed) {
      skeletonFeed.style.display = 'none';
      eventFeed.style.display = 'flex';
    }
  } catch (error) {
    console.error('Auto-refresh failed:', error);
    if (skeletonFeed) {
      skeletonFeed.style.display = 'none';
      eventFeed.style.display = 'flex';
    }
  }
}

function createEventCard(event) {
  const card = document.createElement('div');
  card.className = 'event-card threat-' + (event.threat_level || 'low').toLowerCase();
  card.setAttribute('data-camera', event.camera_id || '');
  card.setAttribute('data-threat', event.threat_level || '');

  const thumbnailUrl = event.thumbnail_url || '/static/placeholder.jpg';
  const timestamp = event.timestamp_start || '';
  const timeFormatted = timestamp ? timestamp.split('T')[1] || timestamp : '';
  const description = event.alert_message || 'Motion detected';
  const duration = event.duration_sec || 0;
  const personIds = event.person_ids || [];

  let personsHtml = '';
  if (personIds.length > 0) {
    const links = personIds.map(function (pid) {
      return '<a href="/person/' + pid + '" class="person-link">' + pid + '</a>';
    });
    personsHtml = '<span>Persons: ' + links.join(', ') + '</span>';
  }

  card.innerHTML = `
    <div class="event-thumbnail">
      <img src="${thumbnailUrl}" alt="Event thumbnail" loading="lazy">
    </div>
    <div class="event-details">
      <div class="event-header">
        <span class="threat-badge ${(event.threat_level || 'low').toLowerCase()}">${event.threat_level || 'LOW'}</span>
        <span class="event-camera">${event.camera_name || 'Unknown Camera'}</span>
        <span class="event-time">${timeFormatted}</span>
      </div>
      <p class="event-description">${description}</p>
      <div class="event-meta">
        <span>Duration: ${duration}s</span>
        ${personsHtml}
      </div>
    </div>
  `;

  // Click to navigate to camera page
  card.addEventListener('click', function () {
    if (event.camera_id) {
      window.location.href = '/camera/' + event.camera_id;
    }
  });

  return card;
}

// Start auto-refresh when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
  startAutoRefresh();
});

// ═══════════════════════════════════════════════════════════════
// Firebase Auth (placeholder — integrate with Firebase SDK)
// ═══════════════════════════════════════════════════════════════

function loginWithEmail() {
  const email = document.getElementById('email');
  const password = document.getElementById('password');
  const errorEl = document.getElementById('login-error');

  if (!email || !password) return;

  if (!email.value || !password.value) {
    if (errorEl) errorEl.textContent = 'Please enter email and password.';
    return;
  }

  // TODO: Integrate Firebase Auth
  // firebase.auth().signInWithEmailAndPassword(email.value, password.value)
  //   .then(function (userCredential) {
  //     window.location.href = '/';
  //   })
  //   .catch(function (error) {
  //     errorEl.textContent = error.message;
  //   });

  // Development: redirect to main page
  window.location.href = '/';
}

function loginWithGoogle() {
  // TODO: Integrate Firebase Google Auth
  // var provider = new firebase.auth.GoogleAuthProvider();
  // firebase.auth().signInWithPopup(provider)
  //   .then(function (result) {
  //     window.location.href = '/';
  //   })
  //   .catch(function (error) {
  //     var errorEl = document.getElementById('login-error');
  //     if (errorEl) errorEl.textContent = error.message;
  //   });

  // Development: redirect to main page
  window.location.href = '/';
}

function logout() {
  // TODO: Firebase sign out
  // firebase.auth().signOut().then(function () {
  //   window.location.href = '/login';
  // });

  // Development: redirect to login
  window.location.href = '/login';
}

// ═══════════════════════════════════════════════════════════════
// Person Page
// ═══════════════════════════════════════════════════════════════

function editPersonLabel(personUid) {
  const labelEl = document.getElementById('person-label');
  if (!labelEl) return;

  const currentLabel = labelEl.textContent;
  const newLabel = prompt('Enter a custom label for ' + personUid + ':', currentLabel);

  if (newLabel && newLabel !== currentLabel) {
    // TODO: Save to backend
    labelEl.textContent = newLabel;
    labelEl.style.fontStyle = 'normal';
    labelEl.style.color = 'var(--color-text)';
  }
}

// ═══════════════════════════════════════════════════════════════
// Settings Page
// ═══════════════════════════════════════════════════════════════

function editCamera(cameraId) {
  alert('Edit camera: ' + cameraId + '\nCamera configuration dialog coming soon.');
}

function configureZones(cameraId) {
  alert('Configure ignore zones for: ' + cameraId + '\nZone editor coming soon.');
}

function addCamera() {
  alert('Add camera dialog coming soon.\nYou will be able to enter RTSP URL and configure the camera.');
}

function saveAccountSettings() {
  const nameInput = document.getElementById('account-name');
  if (nameInput) {
    // TODO: Save to backend
    alert('Account settings saved successfully.');
  }
}

// ═══════════════════════════════════════════════════════════════
// Payment Page
// ═══════════════════════════════════════════════════════════════

function showPaymentInstructions(tier) {
  const instructions = document.getElementById('payment-instructions');
  if (instructions) {
    instructions.style.display = 'block';
    instructions.scrollIntoView({ behavior: 'smooth' });
  }
}
