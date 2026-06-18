/**
 * admin_analytics.js — Vision OS Admin Analytics Dashboard
 *
 * Features:
 * - Summary cards with trend indicators
 * - Revenue chart (line, stacked by tier)
 * - User growth chart (area + bar overlay)
 * - Camera adoption chart (pie/horizontal bar)
 * - Event trends chart (line)
 * - Top users table (sortable, paginated)
 * - Date range selector (7d, 30d, 90d, custom)
 * - CSV and PDF export
 */

(function () {
  'use strict';

  // ═══════════════════════════════════════════════════════════════
  // Mock Data (replace with API calls in production)
  // ═══════════════════════════════════════════════════════════════

  function generateDateRange(days) {
    const dates = [];
    const now = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      dates.push(d.toISOString().split('T')[0]);
    }
    return dates;
  }

  function generateRandomData(days, min, max) {
    return Array.from({ length: days }, () =>
      Math.floor(Math.random() * (max - min + 1)) + min
    );
  }

  const mockData = {
    summary: {
      totalUsers: 1247,
      usersChange: 12.5,
      activeCameras: 3892,
      camerasChange: 8.3,
      mrr: 485000,
      mrrChange: 15.2,
      trialConversion: 34.7,
      conversionChange: 2.1,
    },
    revenue: {
      dates: generateDateRange(30),
      free: generateRandomData(30, 0, 5000),
      household: generateRandomData(30, 10000, 25000),
      business: generateRandomData(30, 5000, 15000),
    },
    userGrowth: {
      dates: generateDateRange(30),
      cumulative: (function () {
        let count = 800;
        return generateRandomData(30, 5, 30).map(function (n) {
          count += n;
          return count;
        });
      })(),
      newSignups: generateRandomData(30, 3, 25),
      activeUsers: (function () {
        let count = 600;
        return generateRandomData(30, 3, 20).map(function (n) {
          count += n;
          return count;
        });
      })(),
    },
    cameraAdoption: {
      labels: ['1-2 Cameras', '3-5 Cameras', '6-10 Cameras'],
      data: [520, 380, 210],
      average: 3.4,
    },
    eventTrends: {
      dates: generateDateRange(30),
      events: generateRandomData(30, 100, 500),
    },
    topUsers: [
      { email: 'rahim@example.com', tier: 'Business', cameras: 10, events: 1452, revenue: 4990, status: 'active' },
      { email: 'karim@example.com', tier: 'Household', cameras: 8, events: 1123, revenue: 2392, status: 'active' },
      { email: 'fatima@example.com', tier: 'Business', cameras: 7, events: 987, revenue: 3493, status: 'active' },
      { email: 'hasan@example.com', tier: 'Household', cameras: 6, events: 876, revenue: 1794, status: 'active' },
      { email: 'nadia@example.com', tier: 'Free', cameras: 5, events: 654, revenue: 0, status: 'trial' },
      { email: 'tanvir@example.com', tier: 'Household', cameras: 5, events: 543, revenue: 1495, status: 'active' },
      { email: 'shahin@example.com', tier: 'Business', cameras: 4, events: 432, revenue: 1996, status: 'active' },
      { email: 'mim@example.com', tier: 'Free', cameras: 4, events: 321, revenue: 0, status: 'trial' },
      { email: 'arif@example.com', tier: 'Household', cameras: 3, events: 298, revenue: 897, status: 'active' },
      { email: 'sadia@example.com', tier: 'Free', cameras: 3, events: 234, revenue: 0, status: 'trial' },
      { email: 'jamil@example.com', tier: 'Household', cameras: 2, events: 187, revenue: 598, status: 'active' },
      { email: 'farzana@example.com', tier: 'Free', cameras: 2, events: 145, revenue: 0, status: 'trial' },
      { email: 'rakib@example.com', tier: 'Household', cameras: 1, events: 98, revenue: 299, status: 'active' },
      { email: 'sumi@example.com', tier: 'Free', cameras: 1, events: 67, revenue: 0, status: 'trial' },
      { email: 'nayeem@example.com', tier: 'Free', cameras: 1, events: 45, revenue: 0, status: 'expired' },
      { email: 'tania@example.com', tier: 'Household', cameras: 9, events: 1345, revenue: 2691, status: 'active' },
      { email: 'sharif@example.com', tier: 'Business', cameras: 6, events: 876, revenue: 2994, status: 'active' },
      { email: 'mohua@example.com', tier: 'Free', cameras: 3, events: 234, revenue: 0, status: 'trial' },
      { email: 'babul@example.com', tier: 'Household', cameras: 4, events: 456, revenue: 1196, status: 'active' },
      { email: 'runa@example.com', tier: 'Free', cameras: 2, events: 123, revenue: 0, status: 'trial' },
      { email: 'kamal@example.com', tier: 'Business', cameras: 8, events: 1098, revenue: 3992, status: 'active' },
      { email: 'shamim@example.com', tier: 'Household', cameras: 5, events: 654, revenue: 1495, status: 'active' },
      { email: 'parvin@example.com', tier: 'Free', cameras: 2, events: 89, revenue: 0, status: 'expired' },
      { email: 'jahid@example.com', tier: 'Household', cameras: 7, events: 765, revenue: 2093, status: 'active' },
      { email: 'morshed@example.com', tier: 'Business', cameras: 10, events: 1567, revenue: 4990, status: 'active' },
    ],
  };

  // ═══════════════════════════════════════════════════════════════
  // State
  // ═══════════════════════════════════════════════════════════════

  let currentRange = '30d';
  let currentSort = 'events';
  let currentPage = 1;
  const pageSize = 10;
  let charts = {};

  // ═══════════════════════════════════════════════════════════════
  // Summary Cards
  // ═══════════════════════════════════════════════════════════════

  function updateSummaryCards() {
    const s = mockData.summary;
    document.getElementById('totalUsers').textContent = s.totalUsers.toLocaleString();
    document.getElementById('usersChange').textContent = (s.usersChange >= 0 ? '+' : '') + s.usersChange + '%';
    document.getElementById('activeCameras').textContent = s.activeCameras.toLocaleString();
    document.getElementById('camerasChange').textContent = (s.camerasChange >= 0 ? '+' : '') + s.camerasChange + '%';
    document.getElementById('mrr').textContent = s.mrr.toLocaleString();
    document.getElementById('mrrChange').textContent = (s.mrrChange >= 0 ? '+' : '') + s.mrrChange + '%';
    document.getElementById('trialConversion').textContent = s.trialConversion + '%';
    document.getElementById('conversionChange').textContent = (s.conversionChange >= 0 ? '+' : '') + s.conversionChange + '%';
  }

  // ═══════════════════════════════════════════════════════════════
  // Revenue Chart
  // ═══════════════════════════════════════════════════════════════

  function createRevenueChart() {
    const ctx = document.getElementById('revenueChart').getContext('2d');
    const data = mockData.revenue;

    charts.revenue = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.dates,
        datasets: [
          {
            label: 'Free',
            data: data.free,
            borderColor: '#94a3b8',
            backgroundColor: 'rgba(148, 163, 184, 0.1)',
            fill: false,
            tension: 0.3,
          },
          {
            label: 'Household',
            data: data.household,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: false,
            tension: 0.3,
          },
          {
            label: 'Business',
            data: data.business,
            borderColor: '#22c55e',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            fill: false,
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              label: function (context) {
                return context.dataset.label + ': ' + context.parsed.y.toLocaleString() + ' BDT';
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { callback: function (v) { return v.toLocaleString(); } },
          },
        },
      },
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // User Growth Chart
  // ═══════════════════════════════════════════════════════════════

  function createUserGrowthChart() {
    const ctx = document.getElementById('userGrowthChart').getContext('2d');
    const data = mockData.userGrowth;

    charts.userGrowth = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.dates,
        datasets: [
          {
            label: 'Cumulative Users',
            data: data.cumulative,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: true,
            tension: 0.3,
            yAxisID: 'y',
          },
          {
            label: 'New Signups',
            data: data.newSignups,
            type: 'bar',
            backgroundColor: 'rgba(59, 130, 246, 0.3)',
            borderColor: '#3b82f6',
            borderWidth: 1,
            yAxisID: 'y1',
          },
          {
            label: 'Active Users',
            data: data.activeUsers,
            borderColor: '#22c55e',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            fill: true,
            tension: 0.3,
            yAxisID: 'y',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: { legend: { position: 'top' } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, position: 'left' },
          y1: { beginAtZero: true, position: 'right', grid: { display: false } },
        },
      },
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Camera Adoption Chart
  // ═══════════════════════════════════════════════════════════════

  function createCameraAdoptionChart() {
    const ctx = document.getElementById('cameraAdoptionChart').getContext('2d');
    const data = mockData.cameraAdoption;

    charts.cameraAdoption = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.labels,
        datasets: [{
          data: data.data,
          backgroundColor: ['#3b82f6', '#22c55e', '#f59e0b'],
          borderWidth: 2,
          borderColor: '#ffffff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: function (context) {
                var total = context.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                var pct = ((context.parsed / total) * 100).toFixed(1);
                return context.label + ': ' + context.parsed + ' users (' + pct + '%)';
              },
            },
          },
        },
      },
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Event Trends Chart
  // ═══════════════════════════════════════════════════════════════

  function createEventTrendsChart() {
    const ctx = document.getElementById('eventTrendsChart').getContext('2d');
    const data = mockData.eventTrends;

    charts.eventTrends = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.dates,
        datasets: [{
          label: 'Events per Day',
          data: data.events,
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139, 92, 246, 0.1)',
          fill: true,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: { legend: { position: 'top' } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true },
        },
      },
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Top Users Table
  // ═══════════════════════════════════════════════════════════════

  function renderTable() {
    const tbody = document.getElementById('usersTableBody');
    const pagination = document.getElementById('tablePagination');

    // Sort users
    var sorted = [].concat(mockData.topUsers).sort(function (a, b) {
      if (currentSort === 'events') return b.events - a.events;
      if (currentSort === 'revenue') return b.revenue - a.revenue;
      if (currentSort === 'cameras') return b.cameras - a.cameras;
      return 0;
    });

    // Paginate
    var totalPages = Math.ceil(sorted.length / pageSize);
    currentPage = Math.min(currentPage, totalPages);
    var start = (currentPage - 1) * pageSize;
    var pageUsers = sorted.slice(start, start + pageSize);

    // Render rows
    tbody.innerHTML = '';
    pageUsers.forEach(function (u) {
      var statusClass = u.status === 'active' ? 'status-active' : u.status === 'trial' ? 'status-trial' : 'status-expired';
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + u.email + '</td>' +
        '<td><span class="tier-badge tier-' + u.tier.toLowerCase() + '">' + u.tier + '</span></td>' +
        '<td>' + u.cameras + '</td>' +
        '<td>' + u.events.toLocaleString() + '</td>' +
        '<td>' + (u.revenue > 0 ? u.revenue.toLocaleString() + ' BDT' : '--') + '</td>' +
        '<td><span class="status-badge ' + statusClass + '">' + u.status + '</span></td>';
      tbody.appendChild(tr);
    });

    // Render pagination
    pagination.innerHTML = '';
    for (var i = 1; i <= totalPages; i++) {
      var btn = document.createElement('button');
      btn.className = 'page-btn' + (i === currentPage ? ' active' : '');
      btn.textContent = i;
      btn.addEventListener('click', function (page) {
        return function () {
          currentPage = page;
          renderTable();
        };
      }(i));
      pagination.appendChild(btn);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // Date Range Selector
  // ═══════════════════════════════════════════════════════════════

  function initDateRangeSelector() {
    const buttons = document.querySelectorAll('.date-btn');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        buttons.forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
        currentRange = this.getAttribute('data-range');
        refreshData();
      });
    });
  }

  function refreshData() {
    // In production, fetch new data from API based on currentRange
    // For now, just re-render with existing mock data
    updateSummaryCards();
    renderTable();
  }

  // ═══════════════════════════════════════════════════════════════
  // Table Sorting
  // ═══════════════════════════════════════════════════════════════

  function initTableSorting() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('active'); });
        this.classList.add('active');
        currentSort = this.getAttribute('data-sort');
        currentPage = 1;
        renderTable();
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // CSV Export
  // ═══════════════════════════════════════════════════════════════

  function exportCSV() {
    var headers = ['Email', 'Tier', 'Cameras', 'Events (30d)', 'Revenue', 'Status'];
    var rows = mockData.topUsers.map(function (u) {
      return [u.email, u.tier, u.cameras, u.events, u.revenue, u.status];
    });

    var csv = headers.join(',') + '\n';
    rows.forEach(function (row) {
      csv += row.join(',') + '\n';
    });

    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'visionos_analytics_' + new Date().toISOString().split('T')[0] + '.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  }

  // ═══════════════════════════════════════════════════════════════
  // PDF Export
  // ═══════════════════════════════════════════════════════════════

  function exportPDF() {
    var element = document.querySelector('.summary-cards');
    if (!element) return;

    html2canvas(element, { scale: 2 }).then(function (canvas) {
      var imgData = canvas.toDataURL('image/png');
      var pdf = new jspdf.jsPDF('l', 'mm', 'a4');
      var imgWidth = 280;
      var imgHeight = (canvas.height * imgWidth) / canvas.width;

      pdf.addImage(imgData, 'PNG', 10, 10, imgWidth, imgHeight);
      pdf.save('visionos_analytics_' + new Date().toISOString().split('T')[0] + '.pdf');
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Initialize
  // ═══════════════════════════════════════════════════════════════

  document.addEventListener('DOMContentLoaded', function () {
    updateSummaryCards();
    createRevenueChart();
    createUserGrowthChart();
    createCameraAdoptionChart();
    createEventTrendsChart();
    renderTable();
    initDateRangeSelector();
    initTableSorting();

    document.getElementById('exportCsv').addEventListener('click', exportCSV);
    document.getElementById('exportPdf').addEventListener('click', exportPDF);
  });

})();
