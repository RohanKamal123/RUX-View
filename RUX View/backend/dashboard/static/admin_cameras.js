/**
 * admin_cameras.js — Admin Camera Management Dashboard UI
 * 
 * Features:
 * - Camera grid with status cards
 * - Filter by status and search
 * - Bulk operations (select, enable, disable, delete, reset)
 * - Camera detail modal with health, metrics, config, cost tabs
 * - Pagination
 * - Auto-refresh every 30 seconds
 */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────
  const state = {
    cameras: [],
    selected: new Set(),
    currentPage: 1,
    perPage: 20,
    totalPages: 1,
    statusFilter: 'all',
    searchQuery: '',
    currentCameraId: null,
    refreshInterval: null,
  };

  // ── DOM References ─────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const dom = {
    grid: $('camera-grid'),
    refreshBtn: $('refresh-btn'),
    lastUpdated: $('last-updated'),
    statusFilter: $('status-filter'),
    searchInput: $('search-input'),
    bulkToolbar: $('bulk-toolbar'),
    bulkCount: $('bulk-count'),
    bulkDeselect: $('bulk-deselect-all'),
    prevPage: $('prev-page'),
    nextPage: $('next-page'),
    pageInfo: $('page-info'),
    // Stats
    statTotal: $('stat-total'),
    statOnline: $('stat-online'),
    statOffline: $('stat-offline'),
    statError: $('stat-error'),
    statUptime: $('stat-uptime'),
    statTriggers: $('stat-triggers'),
    // Modal
    cameraModal: $('camera-modal'),
    modalClose: $('modal-close'),
    modalCameraName: $('modal-camera-name'),
    modalStatus: $('modal-status'),
    modalLastHb: $('modal-last-hb'),
    modalUptime24h: $('modal-uptime-24h'),
    modalUptime7d: $('modal-uptime-7d'),
    modalErrors24h: $('modal-errors-24h'),
    modalErrors7d: $('modal-errors-7d'),
    modalTriggers: $('modal-triggers'),
    modalAiCalls: $('modal-ai-calls'),
    modalBandwidth: $('modal-bandwidth'),
    modalEvents: $('modal-events'),
    modalAiCost: $('modal-ai-cost'),
    modalStorageCost: $('modal-storage-cost'),
    modalBandwidthCost: $('modal-bandwidth-cost'),
    modalTotalCost: $('modal-total-cost'),
    modalCostPerDay: $('modal-cost-per-day'),
    modalCostPerTrigger: $('modal-cost-per-trigger'),
    configName: $('config-name'),
    configMode: $('config-mode'),
    configLocation: $('config-location'),
    configSave: $('config-save'),
    // Confirm modal
    confirmModal: $('confirm-modal'),
    confirmClose: $('confirm-close'),
    confirmCancel: $('confirm-cancel'),
    confirmProceed: $('confirm-proceed'),
    confirmMessage: $('confirm-message'),
    confirmDetail: $('confirm-detail'),
  };

  // ── API Calls ──────────────────────────────────────────────
  const API = {
    async listCameras(page, perPage, status, search) {
      const params = new URLSearchParams({ page, per_page: perPage });
      if (status && status !== 'all') params.set('status', status);
      if (search) params.set('search', search);
      const res = await fetch(`/admin/cameras?${params}`);
      if (!res.ok) throw new Error('Failed to fetch cameras');
      return res.json();
    },

    async getCameraDetails(cameraId) {
      const res = await fetch(`/admin/cameras/${cameraId}`);
      if (!res.ok) throw new Error('Failed to fetch camera details');
      return res.json();
    },

    async getCameraHealth(cameraId, days = 7) {
      const res = await fetch(`/admin/cameras/${cameraId}/health?days=${days}`);
      if (!res.ok) throw new Error('Failed to fetch health');
      return res.json();
    },

    async getCameraMetrics(cameraId, days = 7) {
      const res = await fetch(`/admin/cameras/${cameraId}/metrics?days=${days}`);
      if (!res.ok) throw new Error('Failed to fetch metrics');
      return res.json();
    },

    async getHealthSummary() {
      const res = await fetch('/admin/cameras/health');
      if (!res.ok) throw new Error('Failed to fetch health summary');
      return res.json();
    },

    async getCameraStats() {
      const res = await fetch('/admin/cameras/stats');
      if (!res.ok) throw new Error('Failed to fetch stats');
      return res.json();
    },

    async bulkOperation(cameraIds, operation, reason) {
      const res = await fetch('/admin/cameras/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_ids: cameraIds, operation, reason }),
      });
      if (!res.ok) throw new Error('Bulk operation failed');
      return res.json();
    },

    async updateConfig(cameraId, config) {
      const res = await fetch(`/admin/cameras/${cameraId}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error('Failed to update config');
      return res.json();
    },

    async resetCamera(cameraId) {
      const res = await fetch(`/admin/cameras/${cameraId}/reset`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to reset camera');
      return res.json();
    },
  };

  // ── Render Functions ───────────────────────────────────────

  function renderCameraCard(camera) {
    const statusClass = camera.status || 'unknown';
    const lastHb = camera.last_heartbeat
      ? new Date(camera.last_heartbeat).toLocaleTimeString()
      : 'Never';
    const isSelected = state.selected.has(camera.camera_id);

    return `
      <div class="camera-card ${statusClass} ${isSelected ? 'selected' : ''}"
           data-camera-id="${camera.camera_id}">
        <div class="card-select">
          <input type="checkbox" class="camera-checkbox"
                 data-id="${camera.camera_id}"
                 ${isSelected ? 'checked' : ''} />
        </div>
        <div class="card-status-dot ${statusClass}"></div>
        <div class="card-body" data-action="view-details">
          <h4 class="card-name">${escapeHtml(camera.camera_name)}</h4>
          <p class="card-location">${escapeHtml(camera.location_name || 'No location')}</p>
          <div class="card-metrics">
            <span class="card-metric">
              <span class="metric-icon">&#x23F1;</span>
              ${lastHb}
            </span>
            <span class="card-metric">
              <span class="metric-icon">&#x2B06;</span>
              ${camera.uptime_pct_24h || 100}%
            </span>
            <span class="card-metric error-count">
              <span class="metric-icon">&#x26A0;</span>
              ${camera.error_count_24h || 0} errors
            </span>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-card" data-action="view-details" title="View Details">&#x1F50D;</button>
          <button class="btn-card" data-action="reset" title="Reset">&#x21BB;</button>
          <button class="btn-card" data-action="disable" title="Disable">&#x23F9;</button>
        </div>
      </div>
    `;
  }

  async function renderCameraGrid() {
    try {
      dom.grid.innerHTML = '<div class="loading-state">Loading cameras...</div>';

      const data = await API.listCameras(
        state.currentPage,
        state.perPage,
        state.statusFilter,
        state.searchQuery
      );

      state.cameras = data.cameras || [];
      state.totalPages = data.total_pages || 1;

      if (state.cameras.length === 0) {
        dom.grid.innerHTML = '<div class="empty-state">No cameras found.</div>';
      } else {
        dom.grid.innerHTML = state.cameras.map(renderCameraCard).join('');
      }

      updatePagination();
      updateStats();
      updateBulkToolbar();
      attachCardEvents();
    } catch (err) {
      dom.grid.innerHTML = `<div class="error-state">Failed to load cameras: ${err.message}</div>`;
    }
  }

  async function updateStats() {
    try {
      const [summary, stats] = await Promise.all([
        API.getHealthSummary(),
        API.getCameraStats(),
      ]);

      dom.statTotal.textContent = summary.total_cameras || 0;
      dom.statOnline.textContent = summary.online_cameras || 0;
      dom.statOffline.textContent = summary.offline_cameras || 0;
      dom.statError.textContent = summary.error_cameras || 0;
      dom.statUptime.textContent = (summary.avg_uptime_pct || 100).toFixed(1) + '%';
      dom.statTriggers.textContent = stats.total_triggers_24h || 0;

      dom.lastUpdated.textContent = 'Updated: ' + new Date().toLocaleTimeString();
    } catch (err) {
      console.warn('Failed to update stats:', err);
    }
  }

  function updatePagination() {
    dom.pageInfo.textContent = `Page ${state.currentPage} of ${state.totalPages}`;
    dom.prevPage.disabled = state.currentPage <= 1;
    dom.nextPage.disabled = state.currentPage >= state.totalPages;
  }

  function updateBulkToolbar() {
    const count = state.selected.size;
    if (count > 0) {
      dom.bulkToolbar.style.display = 'flex';
      dom.bulkCount.textContent = `${count} selected`;
    } else {
      dom.bulkToolbar.style.display = 'none';
    }
  }

  function attachCardEvents() {
    document.querySelectorAll('.camera-card').forEach((card) => {
      const cameraId = card.dataset.cameraId;

      // Checkbox
      const checkbox = card.querySelector('.camera-checkbox');
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) {
          state.selected.add(cameraId);
          card.classList.add('selected');
        } else {
          state.selected.delete(cameraId);
          card.classList.remove('selected');
        }
        updateBulkToolbar();
      });

      // Action buttons
      card.querySelectorAll('[data-action]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const action = btn.dataset.action;
          if (action === 'view-details') {
            await openCameraModal(cameraId);
          } else if (action === 'reset') {
            await handleReset(cameraId);
          } else if (action === 'disable') {
            await handleDisable(cameraId);
          }
        });
      });
    });
  }

  // ── Modal ──────────────────────────────────────────────────

  async function openCameraModal(cameraId) {
    state.currentCameraId = cameraId;
    dom.cameraModal.style.display = 'flex';

    try {
      const [details, health, metrics] = await Promise.all([
        API.getCameraDetails(cameraId),
        API.getCameraHealth(cameraId),
        API.getCameraMetrics(cameraId),
      ]);

      // Camera info
      dom.modalCameraName.textContent = details.camera_name || cameraId;

      // Health tab
      const h = details.health || {};
      dom.modalStatus.textContent = h.status || 'unknown';
      dom.modalStatus.className = 'metric-value status-' + (h.status || 'unknown');
      dom.modalLastHb.textContent = h.last_heartbeat
        ? new Date(h.last_heartbeat).toLocaleString()
        : 'Never';
      dom.modalUptime24h.textContent = (h.uptime_pct_24h || 0).toFixed(1) + '%';
      dom.modalUptime7d.textContent = (h.uptime_pct_7d || 0).toFixed(1) + '%';
      dom.modalErrors24h.textContent = h.error_count_24h || 0;
      dom.modalErrors7d.textContent = h.error_count_7d || 0;

      // Metrics tab
      const dm = metrics.daily_metrics || [];
      const totalTriggers = dm.reduce((s, m) => s + m.total_triggers, 0);
      const totalAiCalls = dm.reduce((s, m) => s + m.ai_calls, 0);
      const totalBandwidth = dm.reduce((s, m) => s + m.bandwidth_bytes, 0);
      const totalEvents = dm.reduce((s, m) => s + m.events_generated, 0);

      dom.modalTriggers.textContent = totalTriggers;
      dom.modalAiCalls.textContent = totalAiCalls;
      dom.modalBandwidth.textContent = formatBytes(totalBandwidth);
      dom.modalEvents.textContent = totalEvents;

      // Cost tab
      const cost = metrics.cost_breakdown || {};
      dom.modalAiCost.textContent = '$' + (cost.total_ai_cost || 0).toFixed(6);
      dom.modalStorageCost.textContent = '$' + (cost.total_storage_cost || 0).toFixed(6);
      dom.modalBandwidthCost.textContent = '$' + (cost.total_bandwidth_cost || 0).toFixed(6);
      dom.modalTotalCost.textContent = '$' + (cost.total_cost || 0).toFixed(6);
      dom.modalCostPerDay.textContent = '$' + (cost.cost_per_day || 0).toFixed(6);
      dom.modalCostPerTrigger.textContent = '$' + (cost.cost_per_trigger || 0).toFixed(6);

      // Config tab
      dom.configName.value = details.camera_name || '';
      dom.configMode.value = details.mode || 'indoor';
      dom.configLocation.value = details.location_id || '';

      // Render health history chart
      renderUptimeChart(health.snapshots || []);
      renderTriggerTrendChart(dm);

    } catch (err) {
      console.error('Failed to load camera details:', err);
    }
  }

  function closeCameraModal() {
    dom.cameraModal.style.display = 'none';
    state.currentCameraId = null;
  }

  // ── Charts (simple canvas drawing) ─────────────────────────

  function renderUptimeChart(snapshots) {
    const canvas = document.getElementById('uptime-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width || 400;
    canvas.height = 200;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (snapshots.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No health data available', canvas.width / 2, canvas.height / 2);
      return;
    }

    const padding = 40;
    const w = canvas.width - padding * 2;
    const h = canvas.height - padding * 2;
    const points = snapshots.slice(-20); // Last 20 snapshots

    ctx.strokeStyle = '#22c55e';
    ctx.lineWidth = 2;
    ctx.beginPath();

    points.forEach((p, i) => {
      const x = padding + (i / Math.max(points.length - 1, 1)) * w;
      const y = padding + h * (1 - (p.status === 'online' ? 1 : p.status === 'error' ? 0.3 : 0));
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#64748b';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Time →', canvas.width / 2, canvas.height - 5);
    ctx.textAlign = 'right';
    ctx.fillText('Online', padding - 5, padding + 5);
    ctx.fillText('Offline', padding - 5, padding + h);
  }

  function renderTriggerTrendChart(metrics) {
    const canvas = document.getElementById('trigger-trend-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width || 400;
    canvas.height = 200;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (metrics.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No trigger data available', canvas.width / 2, canvas.height / 2);
      return;
    }

    const padding = 40;
    const w = canvas.width - padding * 2;
    const h = canvas.height - padding * 2;
    const maxTriggers = Math.max(...metrics.map((m) => m.total_triggers), 1);

    ctx.fillStyle = '#3b82f6';
    metrics.forEach((m, i) => {
      const barW = Math.max(w / metrics.length - 4, 4);
      const barH = (m.total_triggers / maxTriggers) * h;
      const x = padding + (i / metrics.length) * w;
      const y = padding + h - barH;
      ctx.fillRect(x, y, barW, barH);
    });

    ctx.fillStyle = '#64748b';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Days →', canvas.width / 2, canvas.height - 5);
  }

  // ── Bulk Operations ────────────────────────────────────────

  async function handleBulkOperation(action) {
    if (state.selected.size === 0) return;

    if (action === 'delete') {
      showConfirmModal(
        `Delete ${state.selected.size} camera(s)?`,
        'This action cannot be undone.',
        async () => {
          await executeBulk(action);
        }
      );
      return;
    }

    await executeBulk(action);
  }

  async function executeBulk(action) {
    const cameraIds = Array.from(state.selected);
    try {
      const result = await API.bulkOperation(cameraIds, action);
      state.selected.clear();
      updateBulkToolbar();
      await renderCameraGrid();
      showToast(`${action}: ${result.succeeded} succeeded, ${result.failed} failed`);
    } catch (err) {
      showToast(`Bulk ${action} failed: ${err.message}`, 'error');
    }
  }

  // ── Single Camera Actions ──────────────────────────────────

  async function handleReset(cameraId) {
    try {
      await API.resetCamera(cameraId);
      showToast(`Camera ${cameraId} reset successfully`);
      await renderCameraGrid();
    } catch (err) {
      showToast(`Reset failed: ${err.message}`, 'error');
    }
  }

  async function handleDisable(cameraId) {
    try {
      await API.bulkOperation([cameraId], 'disable', 'Admin action');
      showToast(`Camera ${cameraId} disabled`);
      await renderCameraGrid();
    } catch (err) {
      showToast(`Disable failed: ${err.message}`, 'error');
    }
  }

  // ── Confirm Modal ──────────────────────────────────────────

  function showConfirmModal(message, detail, onConfirm) {
    dom.confirmMessage.textContent = message;
    dom.confirmDetail.textContent = detail || '';
    dom.confirmModal.style.display = 'flex';

    const cleanup = () => {
      dom.confirmModal.style.display = 'none';
      dom.confirmProceed.removeEventListener('click', handleConfirm);
      dom.confirmCancel.removeEventListener('click', cleanup);
      dom.confirmClose.removeEventListener('click', cleanup);
    };

    const handleConfirm = async () => {
      cleanup();
      if (onConfirm) await onConfirm();
    };

    dom.confirmProceed.addEventListener('click', handleConfirm);
    dom.confirmCancel.addEventListener('click', cleanup);
    dom.confirmClose.addEventListener('click', cleanup);
  }

  // ── Toast Notifications ────────────────────────────────────

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-fadeout');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ── Utility ────────────────────────────────────────────────

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // ── Event Listeners ────────────────────────────────────────

  // Refresh
  dom.refreshBtn.addEventListener('click', () => {
    renderCameraGrid();
  });

  // Status filter
  dom.statusFilter.addEventListener('change', (e) => {
    state.statusFilter = e.target.value;
    state.currentPage = 1;
    renderCameraGrid();
  });

  // Search (debounced)
  let searchTimeout;
  dom.searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.searchQuery = e.target.value;
      state.currentPage = 1;
      renderCameraGrid();
    }, 300);
  });

  // Pagination
  dom.prevPage.addEventListener('click', () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      renderCameraGrid();
    }
  });

  dom.nextPage.addEventListener('click', () => {
    if (state.currentPage < state.totalPages) {
      state.currentPage++;
      renderCameraGrid();
    }
  });

  // Bulk actions
  document.querySelectorAll('.btn-bulk[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      handleBulkOperation(btn.dataset.action);
    });
  });

  dom.bulkDeselect.addEventListener('click', () => {
    state.selected.clear();
    updateBulkToolbar();
    document.querySelectorAll('.camera-checkbox').forEach((cb) => {
      cb.checked = false;
    });
    document.querySelectorAll('.camera-card').forEach((card) => {
      card.classList.remove('selected');
    });
  });

  // Modal close
  dom.modalClose.addEventListener('click', closeCameraModal);
  dom.cameraModal.addEventListener('click', (e) => {
    if (e.target === dom.cameraModal) closeCameraModal();
  });

  // Modal tabs
  document.querySelectorAll('.modal-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.modal-tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      tab.classList.add('active');
      const panel = document.getElementById('tab-' + tab.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });

  // Config save
  dom.configSave.addEventListener('click', async () => {
    if (!state.currentCameraId) return;
    const config = {
      camera_name: dom.configName.value,
      mode: dom.configMode.value,
      location_id: dom.configLocation.value,
    };
    try {
      await API.updateConfig(state.currentCameraId, config);
      showToast('Configuration saved');
      await renderCameraGrid();
    } catch (err) {
      showToast(`Failed to save config: ${err.message}`, 'error');
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeCameraModal();
      dom.confirmModal.style.display = 'none';
    }
  });

  // ── Auto-refresh ───────────────────────────────────────────
  function startAutoRefresh() {
    if (state.refreshInterval) clearInterval(state.refreshInterval);
    state.refreshInterval = setInterval(() => {
      renderCameraGrid();
    }, 30000); // Every 30 seconds
  }

  // ── Init ───────────────────────────────────────────────────
  function init() {
    renderCameraGrid();
    startAutoRefresh();
  }

  // Wait for DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
