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
// Login — POST to backend /login endpoint
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

  // Submit the form to the backend login endpoint
  const formData = new URLSearchParams();
  formData.append('email', email.value);
  formData.append('password', password.value);

  fetch('/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData.toString(),
  })
    .then(function (response) {
      if (response.redirected) {
        // Successful login — follow the redirect to /dashboard
        window.location.href = response.url;
      } else {
        // Error — show the error message
        response.text().then(function (html) {
          // Parse the error from the returned HTML page
          var parser = new DOMParser();
          var doc = parser.parseFromString(html, 'text/html');
          var errEl = doc.getElementById('login-error');
          if (errEl && errEl.textContent) {
            if (errorEl) errorEl.textContent = errEl.textContent;
          } else {
            if (errorEl) errorEl.textContent = 'Login failed. Please try again.';
          }
        });
      }
    })
    .catch(function (err) {
      if (errorEl) errorEl.textContent = 'Network error: ' + err.message;
    });
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
// Camera Management (Settings Page)
// ═══════════════════════════════════════════════════════════════


function editCamera(cameraId, cameraName) {
  const newName = prompt('Edit camera name:', cameraName);
  if (!newName || newName === cameraName) return;

  fetch('/api/cameras/' + cameraId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ camera_name: newName }),
  })
    .then(function (resp) {
      if (resp.ok) {
        alert('Camera renamed to "' + newName + '"');
        location.reload();
      } else {
        return resp.json().then(function (data) {
          alert('Error: ' + (data.detail || 'Failed to rename camera.'));
        });
      }
    })
    .catch(function (err) {
      alert('Network error: ' + err.message);
    });
}

function deleteCamera(cameraId, cameraName) {
  if (!confirm('Delete camera "' + cameraName + '"? This cannot be undone.')) return;

  fetch('/api/cameras/' + cameraId, {
    method: 'DELETE',
  })
    .then(function (resp) {
      if (resp.ok) {
        alert('Camera "' + cameraName + '" deleted.');
        location.reload();
      } else {
        return resp.json().then(function (data) {
          alert('Error: ' + (data.detail || 'Failed to delete camera.'));
        });
      }
    })
    .catch(function (err) {
      alert('Network error: ' + err.message);
    });
}

function addCamera() {
  const modal = document.getElementById('add-camera-modal');
  if (modal) modal.style.display = 'flex';
}

// Wire up add camera modal buttons
document.addEventListener('DOMContentLoaded', function () {
  const addCamSubmit = document.getElementById('add-cam-submit');
  const addCamCancel = document.getElementById('add-cam-cancel');
  const addCamClose = document.getElementById('add-camera-close');

  if (addCamSubmit) {
    addCamSubmit.addEventListener('click', function () {
      const name = document.getElementById('add-cam-name').value.trim();
      const rtsp = document.getElementById('add-cam-rtsp').value.trim();
      const location = document.getElementById('add-cam-location').value.trim();
      const mode = document.getElementById('add-cam-mode').value;
      const errorEl = document.getElementById('add-cam-error');
      const successEl = document.getElementById('add-cam-success');

      if (!name) {
        if (errorEl) { errorEl.textContent = 'Camera name is required.'; errorEl.style.display = 'block'; }
        return;
      }
      if (!rtsp) {
        if (errorEl) { errorEl.textContent = 'RTSP URL is required.'; errorEl.style.display = 'block'; }
        return;
      }

      if (errorEl) errorEl.style.display = 'none';
      if (successEl) successEl.style.display = 'none';

      fetch('/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, rtsp_url: rtsp, location: location, mode: mode }),
      })
        .then(function (resp) {
          if (resp.ok) {
            if (successEl) { successEl.textContent = 'Camera added successfully!'; successEl.style.display = 'block'; }
            setTimeout(function () { location.reload(); }, 1500);
          } else {
            return resp.json().then(function (data) {
              if (errorEl) { errorEl.textContent = data.detail || 'Failed to add camera.'; errorEl.style.display = 'block'; }
            });
          }
        })
        .catch(function (err) {
          if (errorEl) { errorEl.textContent = 'Network error: ' + err.message; errorEl.style.display = 'block'; }
        });
    });
  }

  if (addCamCancel) {
    addCamCancel.addEventListener('click', function () {
      document.getElementById('add-camera-modal').style.display = 'none';
    });
  }

  if (addCamClose) {
    addCamClose.addEventListener('click', function () {
      document.getElementById('add-camera-modal').style.display = 'none';
    });
  }
});

function saveAccountSettings() {

  const nameInput = document.getElementById('account-name');
  if (!nameInput) return;

  const name = nameInput.value.trim();
  if (!name) {
    alert('Please enter a display name.');
    return;
  }

  fetch('/api/users/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: name }),
  })
    .then(function (resp) {
      if (resp.ok) {
        alert('Account settings saved successfully.');
      } else {
        return resp.json().then(function (data) {
          alert('Error: ' + (data.detail || 'Failed to save settings.'));
        });
      }
    })
    .catch(function (err) {
      alert('Network error: ' + err.message);
    });
}

// ═══════════════════════════════════════════════════════════════
// Payment Page
// ═══════════════════════════════════════════════════════════════

function showPaymentInstructions(tier, amount) {
  const instructions = document.getElementById('payment-instructions');
  if (!instructions) return;

  // Set hidden fields
  document.getElementById('payment-tier').value = tier;
  document.getElementById('payment-amount').value = amount || 0;

  // Clear previous status
  const statusEl = document.getElementById('payment-submit-status');
  if (statusEl) statusEl.textContent = '';

  instructions.style.display = 'block';
  instructions.scrollIntoView({ behavior: 'smooth' });
}

function submitTransactionId() {
  const tier = document.getElementById('payment-tier').value;
  const amount = parseInt(document.getElementById('payment-amount').value, 10);
  const trxId = document.getElementById('trx-id').value.trim();
  const method = document.getElementById('payment-method-select').value;
  const statusEl = document.getElementById('payment-submit-status');

  if (!trxId) {
    if (statusEl) { statusEl.textContent = 'Please enter your transaction ID.'; statusEl.style.color = '#ef4444'; }
    return;
  }

  if (!tier || !amount) {
    if (statusEl) { statusEl.textContent = 'Please select a plan first.'; statusEl.style.color = '#ef4444'; }
    return;
  }

  if (statusEl) { statusEl.textContent = 'Submitting...'; statusEl.style.color = '#6b7280'; }

  fetch('/api/payments/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tier: tier,
      amount_bdt: amount,
      transaction_id: trxId,
      payment_method: method,
    }),
  })
    .then(function (resp) {
      if (resp.ok) {
        if (statusEl) {
          statusEl.textContent = 'Transaction ID submitted successfully! We will verify and upgrade your tier within 24 hours.';
          statusEl.style.color = '#10b981';
        }
        document.getElementById('trx-id').value = '';
      } else {
        return resp.json().then(function (data) {
          if (statusEl) {
            statusEl.textContent = 'Error: ' + (data.detail || 'Submission failed. Please try again.');
            statusEl.style.color = '#ef4444';
          }
        });
      }
    })
    .catch(function (err) {
      if (statusEl) { statusEl.textContent = 'Network error: ' + err.message; statusEl.style.color = '#ef4444'; }
    });
}
