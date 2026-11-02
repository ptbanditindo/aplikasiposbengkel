/* ==========================================================================
   BengkelPOS Radiator - logika antarmuka kasir
   ========================================================================== */
(function () {
  'use strict';

  /* ----------------------------- Helpers --------------------------------- */
  const $ = (selector, root) => (root || document).querySelector(selector);
  const $$ = (selector, root) =>
    Array.from((root || document).querySelectorAll(selector));

  const HTML_ESCAPES = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };

  function esc(value) {
    return String(value == null ? '' : value).replace(
      /[&<>"']/g,
      (char) => HTML_ESCAPES[char]
    );
  }

  // Uang kasir selalu rupiah bulat. Pemisah ribuan (titik/koma/spasi) boleh,
  // tetapi format desimal ditolak agar angka yang dikirim tidak ambigu.
  const MONEY_INPUT_RE = /^\d{1,3}(?:[.,\s]\d{3})*$|^\d+$/;

  function moneyInputValid(value) {
    const raw = String(value == null ? '' : value).trim();
    return raw === '' || MONEY_INPUT_RE.test(raw);
  }

  function parseMoney(value) {
    const raw = String(value == null ? '' : value).trim();
    if (!raw || !MONEY_INPUT_RE.test(raw)) return 0;
    const digits = raw.replace(/\D/g, '');
    return digits ? Number(digits) : 0;
  }

  function formatMoneyValue(value) {
    const digits = String(value == null ? '' : value)
      .replace(/\D/g, '')
      .replace(/^0+(?=\d)/, '');
    if (!digits) return '';
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function setMoneyValue(input, value) {
    if (!input) return;
    input.value = value == null || value === '' ? '' : formatMoneyValue(value);
  }

  function formatMoneyField(input) {
    if (!input) return;
    const raw = input.value;
    const caret =
      typeof input.selectionStart === 'number'
        ? input.selectionStart
        : raw.length;
    const digitsBefore = raw.slice(0, caret).replace(/\D/g, '').length;
    const formatted = formatMoneyValue(raw);
    if (input.value === formatted) return;
    input.value = formatted;
    if (document.activeElement !== input) return;
    let position = 0;
    let seen = 0;
    while (position < formatted.length && seen < digitsBefore) {
      if (/\d/.test(formatted[position])) seen += 1;
      position += 1;
    }
    try {
      input.setSelectionRange(position, position);
    } catch (err) {
      /* Input tanpa dukungan seleksi caret tetap memakai nilai baru. */
    }
  }

  function isMoneyField(target) {
    if (!target) return false;
    if (target.classList.contains('money-input')) return true;
    return (
      target.matches('[data-kind][data-field]') &&
      /^(harga|harga_satuan|harga_modal)$/.test(target.dataset.field)
    );
  }

  function readMoneyInput(input, label) {
    const raw = input ? input.value : '';
    if (!moneyInputValid(raw)) {
      toast(
        label + ' harus berupa rupiah bulat tanpa desimal. Contoh: 150.000.',
        'warning'
      );
      if (input) input.focus();
      return null;
    }
    return parseMoney(raw);
  }

  // Nilai uang dari API berupa string desimal dua tempat; penjumlahan untuk
  // tampilan dilakukan dalam sen agar tidak ada galat floating point.
  function moneyToCents(value) {
    const text = String(value == null ? '' : value).trim();
    if (!text) return 0;
    const negative = text.charAt(0) === '-';
    const [whole, fraction] = text.replace('-', '').split('.');
    const cents =
      Number(whole || 0) * 100 + Number(((fraction || '') + '00').slice(0, 2));
    return negative ? -cents : cents;
  }

  function centsToRp(cents) {
    return fmtRp(Math.round(cents) / 100);
  }

  function intValue(value, fallback) {
    const parsed = parseInt(String(value == null ? '' : value), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function fmtRp(value) {
    const number = Number(value);
    const safe = Number.isFinite(number) ? Math.round(number) : 0;
    return 'Rp ' + safe.toLocaleString('id-ID');
  }

  function toISODate(date) {
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 10);
  }

  function todayISO() {
    return toISODate(new Date());
  }

  function followupWindow() {
    const ops = (state.config && state.config.ops) || {};
    const start = ops.followup_jam_mulai || '08:00';
    const end = ops.followup_jam_selesai || '20:00';
    return {
      start,
      end,
      label: start.replace(':', '.') + '-' + end.replace(':', '.'),
    };
  }

  function isFollowupWindowOpen(now) {
    const windowInfo = followupWindow();
    const toMinutes = (value) => {
      const parts = String(value || '').split(':');
      return intValue(parts[0], 0) * 60 + intValue(parts[1], 0);
    };
    const start = toMinutes(windowInfo.start);
    const end = toMinutes(windowInfo.end);
    if (start === end) return true;
    const current = now || new Date();
    const minutes = current.getHours() * 60 + current.getMinutes();
    return start < end
      ? minutes >= start && minutes < end
      : minutes >= start || minutes < end;
  }

  function fmtDate(dateString) {
    if (!dateString) return '-';
    const value = String(dateString).slice(0, 10);
    const date = new Date(value + 'T00:00:00');
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }

  function fmtDateTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function debounce(fn, delay) {
    let timer = null;
    return function debounced() {
      const args = arguments;
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(null, args), delay);
    };
  }

  function describeUnit(unit) {
    if (!unit) return '-';
    if (unit.unit_type === 'SPAREPART') {
      return unit.keterangan || 'Pembelian sparepart';
    }
    if (unit.unit_type === 'MOBIL') {
      let text = unit.nopol || '-';
      if (unit.jenis_mobil) text += ' (' + unit.jenis_mobil + ')';
      return text;
    }
    let text = 'Radiator saja · ' + (unit.label_radiator || 'belum berlabel');
    if (unit.tipe_radiator) text += ' (' + unit.tipe_radiator + ')';
    return text;
  }

  /* ------------------------------ State ---------------------------------- */
  const state = {
    config: null,
    selectedCustomer: null,
    customerResults: [],
    units: [],
    selectedUnit: null,
    posMode: 'SERVICE',
    newUnitFormOpen: false,
    unitType: 'MOBIL',
    jobs: [],
    parts: [],
    stock: [],
    stockFilter: 'all',
    suppliers: [],
    archivedSuppliers: [],
    supplierGroups: [],
    resellerItems: [],
    supplierItemSelection: [],
    employees: [],
    archivedEmployees: [],
    salaryPayments: [],
    salaryPaymentsLoaded: false,
    employeeDebts: [],
    payrollSummary: null,
    payrollPayItem: null,
    salaryPendingPhone: '',
    employeePerfId: null,
    employeePerfHistory: [],
    employeePerfName: '',
    employeePerfMode: 'unpaid',
    followupTab: 'customer',
    reportTab: 'kas',
    partsOutToday: 0,
    employeeTab: 'list',
    navEdit: false,
    jasa: [],
    history: [],
    customerDirectory: [],
    customerWarrantyRecords: [],
    dashboardToday: [],
    reportRows: [],
    reportLabel: 'Hari ini',
    notaList: [],
    detailRecord: null,
    detailReturns: [],
    detailCustomer: null,
    customerHistory: [],
    customerHistorySeq: 0,
    receipt: null,
    receiptWidth: 58,
    customerReturnToPos: false,
    editingStock: null,
    editingJasa: null,
    searchTimer: null,
    saving: false,
    pendingRequest: null,
    backupFolder: { configured: false, name: '' },    preview: null,
    previewSeq: 0,
    previewTimer: null,
    previewError: null,
    printerSettingsBound: false,
    printerActionId: null,
    printerDiscovery: [],
    printerDiscoveryType: null,
    printing: false,
    printPrinterId: null,
    printFailure: null,
    printJobTimer: null,
    printJobSeen: new Set(),
    jenisBayar: 'LUNAS',
    complaintConfirmed: false,
    notaReviewed: false,
    detailPayments: [],
    pendingPengerjaan: null,
    followupList: null,
    followupDetail: null,
    followupReceipt: null,
    receivables: null,
    receivablesCustomerId: null,
    receivablesExpanded: new Set(),
    rescheduleTarget: null,
    pengerjaan: null,
    waPreview: null,
  };

  /* ------------------------------ UI utils -------------------------------- */
  function toast(message, type, timeout) {
    const container = $('#toastContainer');
    if (!container) return;
    const element = document.createElement('div');
    element.className = 'toast ' + (type || 'info');
    element.textContent = message;
    container.appendChild(element);
    const life = timeout || 4500;
    setTimeout(() => {
      element.style.opacity = '0';
      element.style.transform = 'translateY(6px)';
      setTimeout(() => element.remove(), 220);
    }, life);
  }

  let modalLayer = 100;
  const modalHistory = [];

  function openModal(selector) {
    const modal = $(selector);
    if (!modal) return;
    const wasOpen = !modal.classList.contains('hidden');
    modalLayer += 1;
    modal.style.zIndex = String(modalLayer);
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    if (wasOpen) return;
    modalHistory.push(selector);
    try {
      window.history.pushState({ bengkelModal: selector }, '');
    } catch (err) {
      /* Riwayat tidak tersedia; modal tetap bisa ditutup lewat tombol. */
    }
  }

  function hideModal(selector) {
    const modal = $(selector);
    if (!modal) return;
    if (selector === '#recordModal') {
      state.pendingPengerjaan = null;
    }
    modal.classList.add('hidden');
    if (!$$('.modal-backdrop:not(.hidden)').length) {
      document.body.style.overflow = '';
      modalLayer = 100;
    }
  }

  function closeModal(selector) {
    hideModal(selector);
    const index = modalHistory.lastIndexOf(selector);
    if (index >= 0) modalHistory.splice(index, 1);
    if (
      window.history.state &&
      window.history.state.bengkelModal === selector
    ) {
      try {
        window.history.back();
      } catch (err) {
        /* noop */
      }
    }
  }

  function dismissModalStack(selectors) {
    selectors.forEach((selector) => {
      hideModal(selector);
      const index = modalHistory.lastIndexOf(selector);
      if (index >= 0) modalHistory.splice(index, 1);
    });
  }

  function closeAllModals() {
    $$('.modal-backdrop').forEach((modal) => modal.classList.add('hidden'));
    document.body.style.overflow = '';
    modalLayer = 100;
    const steps = modalHistory.length;
    modalHistory.length = 0;
    if (steps > 0 && window.history.state && window.history.state.bengkelModal) {
      try {
        window.history.go(-steps);
      } catch (err) {
        /* noop */
      }
    }
  }

  window.addEventListener('popstate', () => {
    const active =
      window.history.state && window.history.state.bengkelModal;
    while (modalHistory.length) {
      const top = modalHistory[modalHistory.length - 1];
      if (top === active) break;
      modalHistory.pop();
      hideModal(top);
    }
  });

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalHtml) {
        button.dataset.originalHtml = button.innerHTML;
      }
      button.classList.add('is-busy');
      button.disabled = true;
      button.innerHTML =
        '<span class="spin"></span>' + esc(label || 'Memproses...');
    } else {
      button.classList.remove('is-busy');
      button.disabled = false;
      if (button.dataset.originalHtml) {
        button.innerHTML = button.dataset.originalHtml;
        delete button.dataset.originalHtml;
      }
    }
  }

  function metodeBadge(metode) {
    if (metode === 'TRANSFER') {
      return '<span class="badge blue">Transfer</span>';
    }
    return '<span class="badge green">Tunai</span>';
  }

  function warrantyBadge(record) {
    if (record.status === 'VOID') {
      return '<span class="badge red">Dibatalkan</span>';
    }
    if (!record.bergaransi) {
      return '<span class="badge gray">Tanpa garansi</span>';
    }
    if (record.status_klaim === 'Sudah claim') {
      return '<span class="badge blue">Sudah diklaim</span>';
    }
    if (record.garansi_aktif) {
      return (
        '<span class="badge green">Aktif s/d ' +
        fmtDate(record.garansi_sampai) +
        '</span>'
      );
    }
    return '<span class="badge red">Kedaluwarsa</span>';
  }

  function statusBadge(record) {
    if (record.status === 'VOID') {
      return '<span class="badge red">Dibatalkan</span>';
    }
    return '';
  }

  function paymentBadge(record) {
    if (!record || record.status === 'VOID') return '';
    if (record.status_bayar === 'LUNAS') {
      return '<span class="badge green">Lunas</span>';
    }
    if (record.status_bayar === 'BELUM_LUNAS') {
      return '<span class="badge amber">Kredit</span>';
    }
    return '';
  }

  function dueLabel(item) {
    if (item.pengingat) return item.pengingat;
    if (item.status === 'AKAN_DATANG' && item.tanggal_service) {
      return 'Service ' + fmtDate(item.tanggal_service);
    }
    if (item.sisa_hari == null) return '-';
    if (item.sisa_hari < 0) return 'Lewat ' + Math.abs(item.sisa_hari) + ' hari';
    if (item.sisa_hari === 0) return 'Hari ini';
    return 'H-' + item.sisa_hari;
  }

  function jenisTone(jenis) {
    if (jenis === 'piutang') return 'red';
    if (jenis === 'garansi') return 'amber';
    if (jenis === 'servis_berkala') return 'blue';
    return 'gray';
  }

  function netTotal(record) {
    // Selalu pakai total_neto dari server; frontend tidak menghitung ulang.
    return record && record.total_neto != null ? record.total_neto : '0.00';
  }

  /* ------------------------------- Clock ---------------------------------- */
  function startClock() {
    const dateEl = $('#clockDate');
    const timeEl = $('#clockTime');
    const tick = () => {
      const now = new Date();
      if (dateEl) {
        dateEl.textContent = now.toLocaleDateString('id-ID', {
          weekday: 'long',
          day: '2-digit',
          month: 'long',
          year: 'numeric',
        });
      }
      if (timeEl) {
        timeEl.textContent = now.toLocaleTimeString('id-ID', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
      }
    };
    tick();
    setInterval(tick, 1000);
  }

  /* ----------------------------- Navigation ------------------------------- */
  const NAV_ORDER_KEY = 'bengkel.navOrder';
  const NAV_FIXED_VIEWS = ['dashboard', 'pos'];

  function navReorderableTabs() {
    return $$('.nav-tab').filter(
      (tab) => !NAV_FIXED_VIEWS.includes(tab.dataset.view)
    );
  }

  function navMoveUnits() {
    return navReorderableTabs().map(
      (tab) => tab.closest('.nav-order-row') || tab
    );
  }

  function applyNavOrder() {
    const nav = $('#navTabs');
    if (!nav) return;
    let saved = [];
    try {
      saved = JSON.parse(window.localStorage.getItem(NAV_ORDER_KEY) || '[]');
    } catch (err) {
      saved = [];
    }
    const byView = new Map(
      navReorderableTabs().map((tab) => [tab.dataset.view, tab])
    );
    saved.forEach((view) => {
      const tab = byView.get(view);
      if (!tab) return;
      nav.appendChild(tab);
      byView.delete(view);
    });
    byView.forEach((tab) => nav.appendChild(tab));
  }

  function saveNavOrder() {
    const order = navReorderableTabs().map((tab) => tab.dataset.view);
    try {
      window.localStorage.setItem(NAV_ORDER_KEY, JSON.stringify(order));
    } catch (err) {
      /* penyimpanan lokal tidak tersedia */
    }
  }

  function refreshNavMoveButtons() {
    const units = navMoveUnits();
    units.forEach((unit, index) => {
      unit.querySelectorAll('[data-nav-move="-1"]').forEach((button) => {
        button.disabled = index === 0;
      });
      unit.querySelectorAll('[data-nav-move="1"]').forEach((button) => {
        button.disabled = index === units.length - 1;
      });
    });
  }

  function moveNavTab(view, delta) {
    const tabs = navReorderableTabs();
    const index = tabs.findIndex((tab) => tab.dataset.view === view);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= tabs.length) return;
    const units = navMoveUnits();
    const unit = units[index];
    const other = units[target];
    if (delta < 0) {
      other.parentNode.insertBefore(unit, other);
    } else {
      other.parentNode.insertBefore(other, unit);
    }
    saveNavOrder();
    refreshNavMoveButtons();
  }

  function setNavEdit(enabled) {
    state.navEdit = enabled;
    const nav = $('#navTabs');
    const toggle = $('#navOrderToggle');
    if (!nav) return;
    nav.classList.toggle('is-editing', enabled);
    if (enabled) {
      navReorderableTabs().forEach((tab) => {
        if (tab.closest('.nav-order-row')) return;
        const row = document.createElement('div');
        row.className = 'nav-order-row';
        tab.parentNode.insertBefore(row, tab);
        row.appendChild(tab);
        const move = document.createElement('span');
        move.className = 'nav-move';
        move.innerHTML =
          '<span class="nav-move-group nav-move-v">' +
          '<button type="button" data-nav-move="-1" aria-label="Geser naik">\u2191</button>' +
          '<button type="button" data-nav-move="1" aria-label="Geser turun">\u2193</button>' +
          '</span>' +
          '<span class="nav-move-group nav-move-h">' +
          '<button type="button" data-nav-move="-1" aria-label="Geser ke kiri">\u2190</button>' +
          '<button type="button" data-nav-move="1" aria-label="Geser ke kanan">\u2192</button>' +
          '</span>';
        row.appendChild(move);
      });
      refreshNavMoveButtons();
    } else {
      $$('.nav-order-row').forEach((row) => {
        const tab = row.querySelector('.nav-tab');
        if (tab) row.parentNode.insertBefore(tab, row);
        row.remove();
      });
    }
    if (toggle) {
      toggle.textContent = enabled ? 'Selesai atur menu' : 'Atur urutan menu';
      toggle.classList.toggle('btn-primary', enabled);
      toggle.classList.toggle('btn-outline', !enabled);
    }
  }

  /* ------------------------- Tampil / sembunyi menu ------------------------ */
  const MENU_HIDDEN_KEY = 'bengkel.menuHidden';

  const MENU_TOGGLE_FIELDS = [
    ['history', 'Riwayat servis'],
    ['customers', 'Pelanggan'],
    ['employees', 'Karyawan'],
    ['suppliers', 'Supplier'],
    ['followup', 'Follow up'],
    ['reseller', 'Tab Follow up Reseller'],
    ['stock', 'Stok'],
    ['jasa', 'Jasa'],
    ['report', 'Laporan'],
  ];

  function hiddenMenus() {
    try {
      const raw = JSON.parse(window.localStorage.getItem(MENU_HIDDEN_KEY) || '[]');
      return Array.isArray(raw) ? raw : [];
    } catch (err) {
      return [];
    }
  }

  function isMenuHidden(key) {
    return hiddenMenus().includes(key);
  }

  function saveHiddenMenus(list) {
    try {
      window.localStorage.setItem(MENU_HIDDEN_KEY, JSON.stringify(list));
    } catch (err) {
      /* penyimpanan lokal tidak tersedia */
    }
  }

  function applyMenuVisibility() {
    const hidden = hiddenMenus();
    $$('.nav-tab').forEach((tab) => {
      const view = tab.dataset.view;
      if (NAV_FIXED_VIEWS.includes(view) || view === 'settings') {
        tab.classList.remove('menu-hidden');
        return;
      }
      tab.classList.toggle('menu-hidden', hidden.includes(view));
    });
    const supplierAktif =
      !state.config ||
      !state.config.ops ||
      state.config.ops.supplier_aktif !== false;
    const resellerTab = $('#followupTabSwitch [data-followup-tab="reseller"]');
    if (resellerTab) {
      resellerTab.classList.toggle(
        'hidden',
        !supplierAktif || hidden.includes('reseller')
      );
    }
    if (hidden.includes('reseller') && state.followupTab === 'reseller') {
      state.followupTab = 'customer';
    }
    const active = $('.nav-tab.active');
    if (active && active.classList.contains('menu-hidden')) {
      navigate('dashboard');
    }
  }

  function fillMenuSettings() {
    const grid = $('#menuToggleGrid');
    if (!grid) return;
    const hidden = hiddenMenus();
    grid.innerHTML = MENU_TOGGLE_FIELDS.map(
      ([key, label]) =>
        '<label class="switch-row"><span>' +
        esc(label) +
        '</span><input type="checkbox" data-menu-toggle="' +
        key +
        '"' +
        (hidden.includes(key) ? '' : ' checked') +
        '><span class="switch-ui" aria-hidden="true"></span></label>'
    ).join('');
  }

  function handleMenuToggleChange(event) {
    const input = event.target.closest('[data-menu-toggle]');
    if (!input) return;
    const key = input.dataset.menuToggle;
    const hidden = hiddenMenus().filter((row) => row !== key);
    if (!input.checked) hidden.push(key);
    saveHiddenMenus(hidden);
    applyMenuVisibility();
  }

  function navigate(view) {
    $$('.nav-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.view === view);
    });
    $$('.view').forEach((section) => section.classList.add('hidden'));
    const target = $('#view-' + view);
    if (target) target.classList.remove('hidden');
    const activeTab = $('.nav-tab.active');
    if (activeTab && activeTab.scrollIntoView) {
      activeTab.scrollIntoView({
        block: 'nearest',
        inline: 'center',
        behavior: 'smooth',
      });
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (view === 'dashboard') loadDashboard();
    if (view === 'followup') loadFollowupPage();
    if (view === 'suppliers') loadSuppliers();
    if (view === 'employees') {
      loadEmployees();
      loadSalaryPayments();
      loadEmployeeDebts();
    }
    if (view === 'history') loadHistory($('#historySearch').value.trim());
    if (view === 'stock') renderStock();
    if (view === 'jasa') renderJasa();
    if (view === 'customers') {
      loadCustomerDirectory($('#customerDirectorySearch').value.trim());
    }
    if (view === 'report') loadReport();
    if (view === 'settings') {
      fillSettingsForm();
      fillOpsForm();
      fillReceiptForm();
      fillTelegramForm();
      initPrinterSettings();
    }
    if (view === 'pos') {
      loadPartsOutToday();
      if (!state.selectedCustomer) {
        const search = $('#customerSearch');
        if (search) search.focus();
      }
    }
  }

  /* ------------------------------ Config ---------------------------------- */
  function applyConfig() {
    const config = state.config;
    if (!config) return;

    syncFeatureToggles();
    document.title = config.bengkel.nama + ' - Kasir Bengkel';
    $('#bengkelNama').textContent = config.bengkel.nama;
    $('#bengkelTagline').textContent = config.bengkel.tagline;
    $('#bankAccount').textContent =
      config.bengkel.bank_nama + ': ' + config.bengkel.no_rekening;
    $('#bankOwner').textContent = 'a/n ' + config.bengkel.atas_nama;
    setGaransiBulan(config.default_garansi_bulan || 1);
    $('#garansiCatatan').value = config.garansi_syarat || '';
    state.receiptWidth = preferredReceiptWidth();
    syncReceiptWidthUI();
    renderComplaintChips();
    refreshReceiptPrinterUI();
    fillSettingsForm();
    fillOpsForm();
    fillTelegramForm();
  }

  function renderComplaintChips() {
    const container = $('#complaintChips');
    if (!container) return;
    container.innerHTML = '';
    const presets = (state.config && state.config.keluhan_presets) || [];
    presets.forEach((text) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.textContent = text;
      chip.addEventListener('click', () => {
        const textarea = $('#keluhanInput');
        const current = textarea.value.trim();
        if (current.toLowerCase().indexOf(text.toLowerCase()) !== -1) {
          textarea.focus();
          return;
        }
        textarea.value = current ? current + ', ' + text : text;
        textarea.focus();
      });
      container.appendChild(chip);
    });
  }

  /* --------------------------- Customer flow ------------------------------ */
  function renderSelectedCustomer() {
    const box = $('#selectedCustomer');
    if (!box) return;

    if (!state.selectedCustomer) {
      box.classList.add('hidden');
      box.innerHTML = '';
      updateSummaryCustomer();
      return;
    }

    const customer = state.selectedCustomer;
    box.classList.remove('hidden');
    box.innerHTML =
      '<div class="customer-info">' +
      '<strong>' +
      esc(customer.nama) +
      '</strong>' +
      '<span>' +
      esc(customer.nomor_hp) +
      (customer.alamat ? ' &middot; ' + esc(customer.alamat) : '') +
      '</span>' +
      '</div>' +
      '<div class="customer-actions">' +
      '<button type="button" class="btn btn-ghost btn-sm" id="btnChangeCustomer">Ganti pelanggan</button>' +
      '</div>';

    const changeButton = $('#btnChangeCustomer');
    if (changeButton) changeButton.addEventListener('click', clearCustomerSelection);
    updateSummaryCustomer();
  }

  function updateSummaryCustomer() {
    const label = $('#summaryCustomer');
    if (!label) return;
    if (state.posMode === 'PART') {
      label.textContent = state.selectedCustomer
        ? state.selectedCustomer.nama + ' - pembelian sparepart'
        : 'Pelanggan Umum - pembelian sparepart';
      return;
    }
    if (!state.selectedCustomer) {
      label.textContent = 'Belum ada pelanggan dipilih.';
      return;
    }
    if (!state.selectedUnit) {
      label.textContent = state.selectedCustomer.nama + ' - pilih unit servis';
      return;
    }
    label.textContent =
      state.selectedCustomer.nama + ' - ' + describeUnit(state.selectedUnit);
  }

  function detachCustomer() {
    state.selectedCustomer = null;
    state.units = [];
    state.selectedUnit = null;
    state.jobs = [];
    state.parts = [];
    state.complaintConfirmed = false;
    $('#unitList').innerHTML = '';
    renderSelectedCustomer();
    renderItems();
    applyPosMode();
  }

  function clearCustomerSelection() {
    detachCustomer();
    $('#customerSearch').value = '';
    $('#customerSearch').focus();
    hideCustomerResults();
  }

  async function runCustomerSearch(query) {
    try {
      const results = await API.searchCustomers(query);
      state.customerResults = results;
      renderCustomerResults(results);
    } catch (err) {
      toast('Pencarian pelanggan gagal. Coba lagi.', 'error');
    }
  }

  function onCustomerSearchInput() {
    const input = $('#customerSearch');
    const value = input.value;
    if (state.selectedCustomer && value.trim() !== state.selectedCustomer.nama) {
      detachCustomer();
    }
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => runCustomerSearch(value.trim()), 220);
  }

  function renderCustomerResults(results) {
    const list = $('#customerResults');
    if (!list) return;
    list.classList.remove('hidden');
    if (!results.length) {
      list.innerHTML =
        '<div class="autocomplete-empty">Pelanggan tidak ditemukan. Tambahkan lewat tombol Pelanggan baru.</div>';
      return;
    }
    list.innerHTML = results
      .map(
        (customer) =>
          '<button type="button" class="autocomplete-item" data-customer-id="' +
          customer.id +
          '">' +
          '<span><strong>' +
          esc(customer.nama) +
          '</strong><small>' +
          esc(customer.nomor_hp) +
          (customer.alamat ? ' &middot; ' + esc(customer.alamat) : '') +
          '</small></span>' +
          '<span class="badge gray">Pilih</span>' +
          '</button>'
      )
      .join('');
  }

  function hideCustomerResults() {
    const list = $('#customerResults');
    if (list) list.classList.add('hidden');
  }

  async function chooseCustomer(customer) {
    invalidateNotaReview();
    state.selectedCustomer = customer;
    state.selectedUnit = null;
    state.jobs = [];
    state.parts = [];
    state.units = [];
    state.complaintConfirmed = false;
    state.newUnitFormOpen = false;

    $('#customerSearch').value = customer.nama;
    hideCustomerResults();
    renderSelectedCustomer();
    renderItems();
    if (state.posMode === 'PART') {
      applyPosMode();
      updateSummary();
      return;
    }
    $('#unitCard').classList.remove('hidden');
    $('#complaintCard').classList.add('hidden');
    $('#itemsCard').classList.add('hidden');

    await loadUnits(customer.id);
    const card = $('#unitCard');
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  async function loadUnits(customerId) {
    try {
      state.units = await API.customerUnits(customerId);
      renderUnits();
    } catch (err) {
      toast('Gagal memuat unit pelanggan. Coba pilih pelanggan lagi.', 'error');
    }
  }

  function renderUnits() {
    const container = $('#unitList');
    if (!container) return;

    if (!state.units.length) {
      container.innerHTML =
        '<div class="empty-state sm">Belum ada unit terdaftar. Daftarkan mobil atau radiator baru di bawah.</div>';
      syncNewUnitForm();
      return;
    }

    container.innerHTML = state.units
      .map((unit) => {
        const selected =
          state.selectedUnit && state.selectedUnit.id === unit.id;
        const isCar = unit.unit_type === 'MOBIL';
        const title = isCar
          ? unit.nopol || '-'
          : unit.label_radiator || 'Belum berlabel';
        const subtitle = isCar
          ? [unit.jenis_mobil, unit.tahun_mobil].filter(Boolean).join(' · ') ||
            'Mobil lengkap'
          : unit.tipe_radiator || 'Radiator copotan';
        const tag = isCar
          ? ''
          : '<span class="unit-label">Tanpa nopol</span>';
        return (
          '<div class="unit-card-wrap">' +
          '<button type="button" class="unit-card' +
          (selected ? ' selected' : '') +
          '" data-unit-id="' +
          unit.id +
          '">' +
          '<span class="unit-icon">' +
          (isCar ? 'MOBIL' : 'RAD') +
          '</span>' +
          '<span class="unit-info">' +
          '<span class="unit-title">' +
          esc(title) +
          '</span>' +
          '<span class="unit-sub">' +
          esc(subtitle) +
          '</span>' +
          '<span class="unit-pick">Pilih</span>' +
          tag +
          '</span>' +
          '</button>' +
          '<button type="button" class="unit-delete" data-delete-unit="' +
          unit.id +
          '" aria-label="Hapus unit ' +
          esc(title) +
          '">Hapus</button>' +
          '</div>'
        );
      })
      .join('');
    syncNewUnitForm();
  }

  function syncNewUnitForm() {
    const form = $('#newUnitForm');
    const toggle = $('#btnToggleNewUnit');
    if (!form || !toggle) return;
    const hasUnits = state.units.length > 0;
    const open = !hasUnits || state.newUnitFormOpen;
    form.classList.toggle('hidden', !open);
    toggle.classList.toggle('hidden', !hasUnits);
    toggle.textContent = state.newUnitFormOpen
      ? 'Tutup formulir unit baru'
      : 'Daftarkan unit baru';
  }

  async function deleteUnit(unitId) {
    const unit = state.units.find((item) => item.id === unitId);
    if (!unit) return;
    const title =
      unit.unit_type === 'MOBIL'
        ? unit.nopol || 'unit mobil'
        : unit.tipe_radiator || unit.label_radiator || 'unit radiator';
    if (
      !window.confirm(
        'Hapus unit ' +
          title +
          '? Riwayat servis yang sudah ada tetap tersimpan.'
      )
    ) {
      return;
    }

    try {
      await API.deleteUnit(unitId);
      const wasSelected =
        state.selectedUnit && state.selectedUnit.id === unitId;
      state.units = state.units.filter((item) => item.id !== unitId);
      if (wasSelected) {
        invalidateNotaReview();
        state.selectedUnit = null;
        state.jobs = [];
        state.parts = [];
        $('#complaintCard').classList.add('hidden');
        $('#itemsCard').classList.add('hidden');
        renderItems();
        updateSummary();
      }
      renderUnits();
      updateSummaryCustomer();
      toast('Unit dihapus dari daftar. Riwayat servis tetap tersimpan.', 'success');
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  function selectUnit(unitId) {
    const unit = state.units.find((item) => item.id === unitId);
    if (!unit) return;
    invalidateNotaReview();
    state.selectedUnit = unit;
    state.complaintConfirmed = false;
    state.newUnitFormOpen = false;
    renderUnits();
    $('#complaintCard').classList.remove('hidden');
    $('#itemsCard').classList.remove('hidden');
    applyPosMode();
    updateSummaryCustomer();
    updateSummary();
  }

  function saveComplaint() {
    if (!$('#keluhanInput').value.trim()) {
      toast('Keluhan awal wajib diisi.', 'warning');
      $('#keluhanInput').focus();
      return;
    }
    state.complaintConfirmed = true;
    $('#itemsCard').classList.remove('hidden');
    $('#itemsCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    toast('Keluhan disimpan.', 'success');
  }

  function setUnitType(type) {
    state.unitType = type;
    $$('#unitTypeSwitch button').forEach((button) => {
      button.classList.toggle('active', button.dataset.type === type);
    });
    $('#mobilFields').classList.toggle('hidden', type !== 'MOBIL');
    $('#radiatorFields').classList.toggle('hidden', type !== 'RADIATOR_ONLY');
  }

  function resetUnitForm() {
    $('#unitNopol').value = '';
    $('#unitJenis').value = '';
    $('#unitTahun').value = '';
    $('#unitTipe').value = '';
    $('#unitKondisi').value = '';
    $('#unitKeterangan').value = '';
  }

  async function handleAddUnit() {
    if (!state.selectedCustomer) {
      toast('Pilih pelanggan terlebih dahulu.', 'warning');
      return;
    }

    const payload = {
      customer_id: state.selectedCustomer.id,
      unit_type: state.unitType,
      keterangan: $('#unitKeterangan').value.trim() || null,
    };

    if (state.unitType === 'MOBIL') {
      const nopol = $('#unitNopol').value.trim();
      if (!nopol) {
        toast('Nomor polisi wajib diisi untuk mobil.', 'warning');
        $('#unitNopol').focus();
        return;
      }
      payload.nopol = nopol;
      payload.jenis_mobil = $('#unitJenis').value.trim() || null;
      const tahun = intValue($('#unitTahun').value, null);
      payload.tahun_mobil = tahun && tahun >= 1900 && tahun <= 2100 ? tahun : null;
    } else {
      payload.tipe_radiator = $('#unitTipe').value.trim() || null;
      const kondisi = $('#unitKondisi').value.trim();
      if (kondisi) {
        payload.keterangan = payload.keterangan
          ? kondisi + ' - ' + payload.keterangan
          : kondisi;
      }
    }

    const button = $('#btnAddUnit');
    setBusy(button, true, 'Menyimpan...');
    try {
      const unit = await API.createUnit(payload);
      state.units = [unit].concat(state.units);
      state.newUnitFormOpen = false;
      renderUnits();
      selectUnit(unit.id);
      resetUnitForm();
      toast(
        unit.unit_type === 'RADIATOR_ONLY'
          ? 'Unit radiator tersimpan. Label dibuat saat transaksi pertama.'
          : 'Unit mobil ' + unit.nopol + ' tersimpan.',
        'success',
        5000
      );
    } catch (err) {
      toast(err.message, 'error', 6000);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleCustomerSubmit(event) {
    event.preventDefault();
    const button = $('#customerSubmit');
    const payload = {
      nama: $('#custNama').value.trim(),
      nomor_hp: $('#custHp').value.trim(),
      alamat: $('#custAlamat').value.trim() || null,
    };

    setBusy(button, true, 'Menyimpan...');
    try {
      const customer = await API.createCustomer(payload);
      $('#customerForm').reset();
      closeModal('#customerModal');
      toast('Pelanggan ' + customer.nama + ' tersimpan.', 'success');

      if (state.customerReturnToPos) {
        navigate('pos');
        await chooseCustomer(customer);
      }
      if (!$('#view-customers').classList.contains('hidden')) {
        await loadCustomerDirectory($('#customerDirectorySearch').value.trim());
      }
      loadDashboard();
    } catch (err) {
      toast(err.message, 'error', 6000);
    } finally {
      setBusy(button, false);
    }
  }

  function openCustomerModal(fromPos) {
    state.customerReturnToPos = !!fromPos;
    $('#customerForm').reset();
    $('#customerModalTitle').textContent = 'Tambah pelanggan';
    openModal('#customerModal');
    setTimeout(() => $('#custNama').focus(), 60);
  }

  /* --------------------------- Customer Directory -------------------------- */
  function customerInitials(name) {
    const parts = String(name || '')
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return '?';
    return (
      parts[0].charAt(0) + (parts.length > 1 ? parts[1].charAt(0) : '')
    ).toUpperCase();
  }

  function customerUnitHtml(unit) {
    const isCar = unit.unit_type === 'MOBIL';
    const title = isCar
      ? unit.nopol || '-'
      : unit.label_radiator || 'Belum berlabel';
    const subtitle = isCar
      ? [unit.jenis_mobil, unit.tahun_mobil].filter(Boolean).join(' · ') ||
        'Mobil lengkap'
      : unit.tipe_radiator || 'Radiator copotan';
    return (
      '<div class="customer-unit">' +
      '<span class="unit-icon">' +
      (isCar ? 'MOBIL' : 'RAD') +
      '</span>' +
      '<span class="customer-unit-info">' +
      '<span class="customer-unit-title">' +
      esc(title) +
      '</span>' +
      '<span class="customer-unit-sub">' +
      esc(subtitle) +
      '</span>' +
      '</span>' +
      '<span class="unit-tag' +
      (isCar ? '' : ' radiator') +
      '">' +
      (isCar ? 'Mobil' : 'Radiator') +
      '</span>' +
      '</div>'
    );
  }

  function customerCardHtml(customer) {
    const units = customer.units || [];
    const unitCounts = [];
    if (customer.total_mobil) {
      unitCounts.push(
        '<span class="unit-count">' + customer.total_mobil + ' mobil</span>'
      );
    }
    if (customer.total_radiator) {
      unitCounts.push(
        '<span class="unit-count radiator">' +
          customer.total_radiator +
          ' radiator</span>'
      );
    }
    if (!unitCounts.length) {
      unitCounts.push('<span class="unit-count muted">Belum ada unit</span>');
    }

    const unitList = units.length
      ? units.map(customerUnitHtml).join('')
      : '<div class="customer-unit-empty">Belum ada unit terdaftar untuk pelanggan ini.</div>';

    return (
      '<article class="customer-card">' +
      '<div class="customer-card-head is-clickable" role="button" tabindex="0" title="Lihat detail pelanggan" data-action="customer-detail" data-id="' +
      customer.id +
      '">' +
      '<span class="customer-avatar">' +
      esc(customerInitials(customer.nama)) +
      '</span>' +
      '<div class="customer-main">' +
      '<h3 class="customer-name">' +
      esc(customer.nama) +
      '</h3>' +
      '<p class="customer-meta">' +
      esc(customer.nomor_hp) +
      (customer.alamat ? ' · ' + esc(customer.alamat) : '') +
      '</p>' +
      '<div class="customer-unit-counts">' +
      unitCounts.join('') +
      '</div>' +
      '</div>' +
      '</div>' +
      '<div class="customer-units">' +
      unitList +
      '</div>' +
      '<div class="customer-card-actions">' +
      '<span class="customer-since">Terdaftar ' +
      esc(fmtDate(customer.created_at)) +
      '</span>' +
      '<button type="button" class="btn btn-outline btn-xs" data-action="service-customer" data-id="' +
      customer.id +
      '">Buat servis</button>' +
      '</div>' +
      '</article>'
    );
  }

  async function loadCustomerDirectory(query) {
    try {
      const results = await Promise.all([
        API.customerOverview(query || ''),
        API.records(''),
      ]);
      state.customerDirectory = results[0];
      state.customerWarrantyRecords = (results[1] || []).filter(
        (record) => record.garansi_aktif
      );
      renderCustomerDirectory();
    } catch (err) {
      toast('Gagal memuat data pelanggan. Coba muat ulang.', 'error', 6000);
    }
  }

  function renderCustomerDirectory() {
    const grid = $('#customerDirectoryGrid');
    if (!grid) return;

    const customers = state.customerDirectory || [];
    const totals = customers.reduce(
      function (acc, customer) {
        acc.units += Number(customer.total_unit) || 0;
        acc.mobil += Number(customer.total_mobil) || 0;
        acc.radiator += Number(customer.total_radiator) || 0;
        return acc;
      },
      { units: 0, mobil: 0, radiator: 0 }
    );

    $('#customerStatTotal').textContent = customers.length;
    $('#customerStatUnits').textContent = totals.units;
    $('#customerStatMobil').textContent = totals.mobil;
    $('#customerStatRadiator').textContent = totals.radiator;
    $('#customerStatWarranty').textContent = (
      state.customerWarrantyRecords || []
    ).length;
    $('#customerDirectoryCount').textContent = customers.length + ' pelanggan';

    if (!customers.length) {
      grid.innerHTML = '';
      const query = $('#customerDirectorySearch').value.trim();
      $('#customerDirectoryEmpty').textContent = query
        ? 'Tidak ada pelanggan yang cocok dengan pencarian "' + query + '".'
        : 'Belum ada pelanggan terdaftar. Tambahkan pelanggan baru untuk mulai mencatat unit servis.';
      $('#customerDirectoryEmpty').classList.remove('hidden');
      return;
    }

    $('#customerDirectoryEmpty').classList.add('hidden');
    grid.innerHTML = customers.map(customerCardHtml).join('');
  }

  function openCustomerStatList(kind) {
    const customers = state.customerDirectory || [];
    const units = [];
    customers.forEach((customer) => {
      (customer.units || []).forEach((unit) => {
        units.push({ unit: unit, customer: customer });
      });
    });

    const config = {
      customers: {
        title: 'Total pelanggan',
        subtitle: customers.length + ' pelanggan terdaftar',
        empty: 'Belum ada pelanggan terdaftar.',
        head: '<tr><th>Nama</th><th>No. HP</th><th class="text-right">Unit</th></tr>',
      },
      units: {
        title: 'Total unit terdaftar',
        subtitle: units.length + ' unit dari ' + customers.length + ' pelanggan',
        empty: 'Belum ada unit terdaftar.',
        head: '<tr><th>Pelanggan</th><th>Unit</th><th>Jenis</th></tr>',
      },
      mobil: {
        title: 'Unit mobil',
        subtitle:
          units.filter((row) => row.unit.unit_type === 'MOBIL').length +
          ' unit mobil terdaftar',
        empty: 'Belum ada unit mobil terdaftar.',
        head: '<tr><th>Pelanggan</th><th>Unit</th><th>Jenis</th></tr>',
      },
      radiator: {
        title: 'Radiator copotan',
        subtitle:
          units.filter((row) => row.unit.unit_type === 'RADIATOR_ONLY').length +
          ' radiator terdaftar',
        empty: 'Belum ada radiator terdaftar.',
        head: '<tr><th>Pelanggan</th><th>Unit</th><th>Jenis</th></tr>',
      },
    }[kind];
    if (!config) return;

    let rows = [];
    if (kind === 'customers') {
      rows = customers.map(
        (customer) =>
          '<tr>' +
          '<td><button type="button" class="cell-link" data-action="customer-detail" data-id="' +
          customer.id + '">' + esc(customer.nama) + '</button></td>' +
          '<td>' + esc(customer.nomor_hp || '-') + '</td>' +
          '<td class="text-right">' + customer.total_unit + '</td>' +
          '</tr>'
      );
    } else {
      const filtered = units.filter((row) => {
        if (kind === 'mobil') return row.unit.unit_type === 'MOBIL';
        if (kind === 'radiator') return row.unit.unit_type === 'RADIATOR_ONLY';
        return true;
      });
      rows = filtered.map((row) => {
        const isCar = row.unit.unit_type === 'MOBIL';
        return (
          '<tr>' +
          '<td><button type="button" class="cell-link" data-action="customer-detail" data-id="' +
          row.customer.id + '">' + esc(row.customer.nama) + '</button>' +
          '<span class="cell-sub">' + esc(row.customer.nomor_hp || '-') + '</span></td>' +
          '<td>' + esc(describeUnit(row.unit)) + '</td>' +
          '<td><span class="unit-tag' + (isCar ? '' : ' radiator') + '">' +
          (isCar ? 'Mobil' : 'Radiator') + '</span></td>' +
          '</tr>'
        );
      });
    }

    openStatListModal({
      title: config.title,
      subtitle: config.subtitle,
      head: config.head,
      rows,
      empty: config.empty,
    });
  }

  function openStatListModal(config) {
    $('#customerStatTitle').textContent = config.title;
    $('#customerStatSubtitle').textContent = config.subtitle;
    $('#customerStatHead').innerHTML = config.head;
    const body = $('#customerStatBody');
    const empty = $('#customerStatEmpty');
    if (!config.rows.length) {
      body.innerHTML = '';
      empty.textContent = config.empty;
      empty.classList.remove('hidden');
    } else {
      empty.classList.add('hidden');
      body.innerHTML = config.rows.join('');
    }
    openModal('#customerStatModal');
  }

  /* ------------------------------- Items ---------------------------------- */
  function populatePickers() {
    const jasaPicker = $('#jasaPicker');
    if (jasaPicker) {
      jasaPicker.innerHTML =
        '<option value="">Pilih tarif jasa (opsional)</option>' +
        state.jasa
          .map(
            (jasa) =>
              '<option value="' +
              jasa.id +
              '">' +
              esc(jasa.nama) +
              ' · ' +
              fmtRp(jasa.harga_standar) +
              '</option>'
          )
          .join('');
    }

    const partPicker = $('#partPicker');
    if (partPicker) {
      partPicker.innerHTML =
        '<option value="">Pilih sparepart (opsional)</option>' +
        state.stock
          .map(
            (item) =>
              '<option value="' +
              item.id +
              '">' +
              esc(item.nama) +
              ' (stok ' +
              item.jumlah +
              ') · ' +
              fmtRp(item.harga_jual) +
              '</option>'
          )
          .join('');
    }
  }

  function clampInterval(value) {
    return Math.min(120, Math.max(0, intValue(value, 0)));
  }

  function onJasaPickerChange() {
    const id = intValue($('#jasaPicker').value, 0);
    const master = state.jasa.find((jasa) => jasa.id === id);
    const hint = $('#jasaIntervalHint');
    if (!master) {
      if (hint) hint.classList.add('hidden');
      return;
    }
    $('#jasaNama').value = master.nama;
    setMoneyValue($('#jasaHarga'), Math.round(Number(master.harga_standar) || 0));
    $('#jasaQty').value = '1';
    if (hint) {
      const interval = clampInterval(master.interval_servis_bulan);
      hint.textContent =
        interval > 0
          ? 'Servis berkala: ' +
            interval +
            ' bulan. Nilai di baris nota boleh diubah untuk nota ini saja.'
          : 'Jasa ini tanpa interval servis berkala.';
      hint.classList.remove('hidden');
    }
  }

  function onPartPickerChange() {
    const id = intValue($('#partPicker').value, 0);
    const stock = state.stock.find((item) => item.id === id);
    const hint = $('#partStockHint');
    const intervalHint = $('#partIntervalHint');
    if (!stock) {
      if (hint) hint.textContent = 'Stok gudang berkurang otomatis.';
      $('#partInterval').value = '0';
      if (intervalHint) intervalHint.classList.add('hidden');
      return;
    }
    $('#partNama').value = stock.nama;
    setMoneyValue($('#partHarga'), Math.round(Number(stock.harga_jual) || 0));
    $('#partQty').value = '1';
    $('#partInterval').value = String(
      clampInterval(stock.interval_servis_bulan)
    );
    if (hint) {
      hint.textContent =
        'Stok tersedia ' +
        stock.jumlah +
        '. Harga patokan ' +
        fmtRp(stock.harga_jual);
    }
    if (intervalHint) {
      if (state.posMode === 'PART') {
        intervalHint.classList.add('hidden');
      } else {
        const interval = clampInterval(stock.interval_servis_bulan);
        intervalHint.textContent =
          interval > 0
            ? 'Servis berkala: ' +
              interval +
              ' bulan. Nilai di baris nota boleh diubah untuk nota ini saja.'
            : 'Sparepart ini tanpa interval servis berkala.';
        intervalHint.classList.remove('hidden');
      }
    }
  }

  function addJob() {
    const jasaId = intValue($('#jasaPicker').value, 0);
    const master = state.jasa.find((jasa) => jasa.id === jasaId);
    const description = $('#jasaNama').value.trim() || (master ? master.nama : '');
    if (!description) {
      toast('Nama jasa wajib diisi.', 'warning');
      $('#jasaNama').focus();
      return;
    }

    const quantity = Math.max(1, intValue($('#jasaQty').value, 1));
    const price = readMoneyInput($('#jasaHarga'), 'Harga jasa');
    if (price === null) return;

    invalidateNotaReview();
    state.jobs.push({
      harga_jasa_id: master ? master.id : null,
      deskripsi: description,
      jumlah: quantity,
      harga: String(price),
      interval_servis_bulan: master
        ? clampInterval(master.interval_servis_bulan)
        : 0,
    });

    $('#jasaPicker').value = '';
    $('#jasaNama').value = '';
    $('#jasaQty').value = '1';
    $('#jasaHarga').value = '';
    $('#jasaIntervalHint').classList.add('hidden');
    renderItems();
  }

  function addPart() {
    const stockId = intValue($('#partPicker').value, 0);
    const stock = state.stock.find((item) => item.id === stockId);
    const name = $('#partNama').value.trim() || (stock ? stock.nama : '');
    if (!name) {
      toast('Nama sparepart wajib diisi.', 'warning');
      $('#partNama').focus();
      return;
    }

    const quantity = Math.max(1, intValue($('#partQty').value, 1));
    const price = readMoneyInput($('#partHarga'), 'Harga sparepart');
    if (price === null) return;
    const modalInput = $('#partModal').value.trim();
    const modal = modalInput
      ? readMoneyInput($('#partModal'), 'Harga modal')
      : null;
    if (modalInput && modal === null) return;

    invalidateNotaReview();
    state.parts.push({
      stock_item_id: stock ? stock.id : null,
      nama_part: name,
      jumlah: quantity,
      harga_satuan: String(price),
      harga_modal: stock ? null : modal,
      interval_servis_bulan: clampInterval($('#partInterval').value),
    });

    if (state.posMode === 'PART') {
      state.parts[state.parts.length - 1].interval_servis_bulan = 0;
    }

    $('#partPicker').value = '';
    $('#partNama').value = '';
    $('#partQty').value = '1';
    $('#partHarga').value = '';
    $('#partModal').value = '';
    $('#partInterval').value = '0';
    $('#partStockHint').textContent = 'Stok gudang berkurang otomatis.';
    $('#partIntervalHint').classList.add('hidden');
    renderItems();
  }

  function renderItems() {
    const jobsBody = $('#jobsBody');
    const partsBody = $('#partsBody');
    if (!jobsBody || !partsBody) return;

    jobsBody.innerHTML = state.jobs
      .map((job, index) => {
        return (
          '<tr>' +
          '<td><input class="table-input" data-kind="job" data-index="' +
          index +
          '" data-field="deskripsi" value="' +
          esc(job.deskripsi) +
          '" maxlength="255"></td>' +
          '<td><input type="number" min="1" class="table-input qty" data-kind="job" data-index="' +
          index +
          '" data-field="jumlah" value="' +
          esc(job.jumlah) +
          '"></td>' +
          '<td><input class="table-input price" inputmode="numeric" data-kind="job" data-index="' +
          index +
          '" data-field="harga" value="' +
          esc(formatMoneyValue(job.harga)) +
          '"></td>' +
          '<td><input type="number" min="0" max="120" class="table-input interval" data-kind="job" data-index="' +
          index +
          '" data-field="interval_servis_bulan" value="' +
          esc(clampInterval(job.interval_servis_bulan)) +
          '" title="Interval servis berkala (bulan). 0 = nonaktif."></td>' +
          '<td class="text-right item-subtotal" data-subtotal-kind="job" data-subtotal-index="' +
          index +
          '">&mdash;</td>' +
          '<td class="text-right"><button type="button" class="icon-btn danger" data-remove-kind="job" data-index="' +
          index +
          '" aria-label="Hapus jasa">&times;</button></td>' +
          '</tr>'
        );
      })
      .join('');

    partsBody.innerHTML = state.parts
      .map((part, index) => {
        const stock = state.stock.find(
          (item) => item.id === part.stock_item_id
        );
        const warning =
          stock && intValue(part.jumlah, 0) > stock.jumlah
            ? '<span class="stock-warn">stok ' + stock.jumlah + '</span>'
            : '';
        const modalCell = stock
          ? '<span class="cell-sub">' + fmtRp(stock.harga_modal) + '</span>'
          : '<input class="table-input price" inputmode="numeric" data-kind="part" data-index="' +
            index +
            '" data-field="harga_modal" value="' +
            esc(formatMoneyValue(part.harga_modal)) +
            '" placeholder="Modal">' +
            (part.harga_modal == null || part.harga_modal === ''
              ? '<span class="stock-warn">belum diisi</span>'
              : '');
        return (
          '<tr>' +
          '<td><input class="table-input" data-kind="part" data-index="' +
          index +
          '" data-field="nama_part" value="' +
          esc(part.nama_part) +
          '" maxlength="255">' +
          warning +
          '</td>' +
          '<td><input type="number" min="1" class="table-input qty" data-kind="part" data-index="' +
          index +
          '" data-field="jumlah" value="' +
          esc(part.jumlah) +
          '"></td>' +
          '<td><input class="table-input price" inputmode="numeric" data-kind="part" data-index="' +
          index +
          '" data-field="harga_satuan" value="' +
          esc(formatMoneyValue(part.harga_satuan)) +
          '"></td>' +
          '<td>' +
          modalCell +
          '</td>' +
          '<td><input type="number" min="0" max="120" class="table-input interval" data-kind="part" data-index="' +
          index +
          '" data-field="interval_servis_bulan" value="' +
          esc(clampInterval(part.interval_servis_bulan)) +
          '" title="Interval servis berkala (bulan). 0 = nonaktif."></td>' +
          '<td class="text-right item-subtotal" data-subtotal-kind="part" data-subtotal-index="' +
          index +
          '">&mdash;</td>' +
          '<td class="text-right"><button type="button" class="icon-btn danger" data-remove-kind="part" data-index="' +
          index +
          '" aria-label="Hapus sparepart">&times;</button></td>' +
          '</tr>'
        );
      })
      .join('');

    $('#jobsEmpty').classList.toggle('hidden', state.jobs.length > 0);
    $('#partsEmpty').classList.toggle('hidden', state.parts.length > 0);
    updateSummary();
  }

  function removeItem(kind, index) {
    invalidateNotaReview();
    if (kind === 'job') state.jobs.splice(index, 1);
    if (kind === 'part') state.parts.splice(index, 1);
    renderItems();
  }

  function handleItemInput(target) {
    const kind = target.dataset.kind;
    const field = target.dataset.field;
    const index = intValue(target.dataset.index, -1);
    const list = kind === 'job' ? state.jobs : state.parts;
    const item = list[index];
    if (!item) return;

    invalidateNotaReview();
    item[field] = target.value;

    if (field === 'jumlah' || field === 'harga' || field === 'harga_satuan') {
      const row = target.closest('tr');
      const cell = row ? row.querySelector('.item-subtotal') : null;
      if (cell) cell.textContent = '\u2014';
    }
    updateSummary();
  }

  /* ------------------------------ Summary --------------------------------- */
  // Semua angka ringkasan berasal dari backend lewat /api/pos/preview yang
  // memakai mesin harga yang sama dengan penyimpanan transaksi.
  function getMetode() {
    const checked = $('input[name="metode"]:checked');
    return checked ? checked.value : 'CASH';
  }

  function getJenisBayar() {
    return state.jenisBayar === 'KREDIT' ? 'KREDIT' : 'LUNAS';
  }

  function isKreditMode() {
    return getJenisBayar() === 'KREDIT';
  }

  function kreditUangMukaAktif() {
    const toggle = $('#kreditUangMukaAktif');
    return isKreditMode() && !!(toggle && toggle.checked);
  }

  function buildPreviewPayload() {
    const metode = getMetode();
    const kreditMode = isKreditMode();
    const uangMuka = kreditUangMukaAktif()
      ? String(parseMoney($('#kreditUangMukaInput').value))
      : '0';
    return {
      diskon: String(parseMoney($('#diskonInput').value)),
      metode_bayar: metode,
      bayar:
        !kreditMode && metode === 'CASH'
          ? String(parseMoney($('#bayarInput').value))
          : '0',
      jenis_bayar: getJenisBayar(),
      dp: uangMuka,
      rencana_bayar: kreditMode
        ? String(parseMoney($('#rencanaBayarInput').value))
        : '0',
      jobs: state.jobs.map((job) => ({
        deskripsi: job.deskripsi || 'Jasa',
        jumlah: Math.max(1, intValue(job.jumlah, 1)),
        harga: String(parseMoney(job.harga)),
      })),
      parts: state.parts.map((part) => ({
        nama_part: part.nama_part || '',
        jumlah: Math.max(1, intValue(part.jumlah, 1)),
        harga_satuan: String(parseMoney(part.harga_satuan)),
      })),
    };
  }

  function setLineSubtotals(kind, lines) {
    $$('.item-subtotal[data-subtotal-kind="' + kind + '"]').forEach((cell) => {
      const index = intValue(cell.dataset.subtotalIndex, -1);
      const line = lines ? lines[index] : null;
      cell.textContent = line ? fmtRp(line.subtotal) : '\u2014';
    });
  }

  function setSummaryNote(message) {
    const note = $('#summaryPreviewNote');
    if (!note) return;
    note.textContent = message || '';
    note.classList.toggle('hidden', !message);
  }

  function renderPreview(preview, error) {
    const transfer = getMetode() === 'TRANSFER';
    const kreditMode = isKreditMode();
    const installment = kreditMode;
    const paidInput = $('#bayarInput');
    paidInput.disabled = transfer || installment;
    $('#bankInfo').classList.toggle('hidden', !transfer);
    $('#dpSummaryRow').classList.toggle('hidden', !installment);

    if (error) {
      $('#jobSubtotal').textContent = '\u2014';
      $('#partSubtotal').textContent = '\u2014';
      $('#grandTotalValue').textContent = '\u2014';
      $('#kembalianValue').textContent = '\u2014';
      $('#dpSisaValue').textContent = '\u2014';
      setLineSubtotals('job', null);
      setLineSubtotals('part', null);
      setSummaryNote(error);
      return;
    }

    if (!preview) {
      $('#jobSubtotal').textContent = 'Rp 0';
      $('#partSubtotal').textContent = 'Rp 0';
      $('#grandTotalValue').textContent = 'Rp 0';
      const zeroChange = $('#kembalianValue');
      zeroChange.textContent = 'Rp 0';
      if (zeroChange.parentElement) {
        zeroChange.parentElement.classList.remove('short');
      }
      $('#dpSisaValue').textContent = 'Rp 0';
      setLineSubtotals('job', null);
      setLineSubtotals('part', null);
      setSummaryNote('Perkiraan sementara. Nilai final dicatat saat nota disimpan.');
      return;
    }

    if (transfer && !installment) {
      setMoneyValue(paidInput, moneyToCents(preview.total_servis) / 100);
    }

    setLineSubtotals('job', preview.jobs);
    setLineSubtotals('part', preview.parts);
    $('#jobSubtotal').textContent = fmtRp(preview.biaya_jasa);
    $('#partSubtotal').textContent = fmtRp(preview.total_part);
    $('#grandTotalValue').textContent = fmtRp(preview.total_servis);
    $('#dpSisaValue').textContent = fmtRp(preview.sisa_bayar);

    const kurang = Number(preview.kekurangan) > 0;
    const changeEl = $('#kembalianValue');
    changeEl.textContent = kurang
      ? 'Kurang ' + fmtRp(preview.kekurangan)
      : fmtRp(preview.kembalian);
    const changeRow = changeEl.parentElement;
    if (changeRow) changeRow.classList.toggle('short', kurang);
    setSummaryNote('Perkiraan sementara. Nilai final dicatat saat nota disimpan.');
  }

  async function refreshPreview() {
    state.previewTimer = null;
    const seq = (state.previewSeq += 1);
    try {
      const preview = await API.previewTransaction(buildPreviewPayload());
      if (seq !== state.previewSeq) return;
      state.preview = preview;
      state.previewError = null;
      renderPreview(preview, null);
    } catch (err) {
      if (seq !== state.previewSeq) return;
      state.preview = null;
      state.previewError = err.message;
      renderPreview(null, err.message);
    }
  }

  function updateSummary() {
    const diskonInput = $('#diskonInput');
    const bayarInput = $('#bayarInput');
    const cash = getMetode() === 'CASH';
    const kreditMode = isKreditMode();
    const uangMukaAktif = kreditUangMukaAktif();
    if (
      !moneyInputValid(diskonInput.value) ||
      (cash && !kreditMode && !moneyInputValid(bayarInput.value)) ||
      (kreditMode && !moneyInputValid($('#rencanaBayarInput').value)) ||
      (uangMukaAktif && !moneyInputValid($('#kreditUangMukaInput').value))
    ) {
      renderPreview(
        null,
        'Format angka tidak valid. Gunakan rupiah bulat. Contoh: 150.000.'
      );
      return;
    }
    if (state.previewTimer) clearTimeout(state.previewTimer);
    state.previewTimer = setTimeout(refreshPreview, 180);
  }

  function handlePaymentModeChange() {
    invalidateNotaReview();
    const transfer = getMetode() === 'TRANSFER';
    const installment = getJenisBayar() !== 'LUNAS';
    $('#bayarInput').disabled = transfer || installment;
    $('#bankInfo').classList.toggle('hidden', !transfer);
    updateSummary();
  }

  function updateKreditUangMuka() {
    invalidateNotaReview();
    const aktif = kreditUangMukaAktif();
    $('#kreditUangMukaFields').classList.toggle('hidden', !aktif);
    updateSummary();
  }

  function updateJenisBayar() {
    invalidateNotaReview();
    const kreditMode = isKreditMode();
    $('#lunasFields').classList.toggle('hidden', kreditMode);
    $('#kreditFields').classList.toggle('hidden', !kreditMode);
    $('#dpSummaryRow').classList.toggle('hidden', !kreditMode);
    $('#bayarInput').disabled = getMetode() === 'TRANSFER' || kreditMode;
    $$('#jenisBayarSwitch button').forEach((button) => {
      button.classList.toggle('active', button.dataset.jenis === getJenisBayar());
    });
    updateKreditUangMuka();
  }

  function updateGaransiFields() {
    const enabled = $('#garansiAktif').checked;
    $('#garansiFields').classList.toggle('off', !enabled);
    $('#garansiBulanCustomField').classList.toggle(
      'hidden',
      $('#garansiBulan').value !== 'custom'
    );
  }

  function garansiBulanValue() {
    const selected = $('#garansiBulan').value;
    const raw = selected === 'custom' ? $('#garansiBulanCustom').value : selected;
    return Math.min(120, Math.max(1, intValue(raw, 1) || 1));
  }

  function setGaransiBulan(months) {
    const value = Math.min(120, Math.max(1, intValue(months, 1) || 1));
    const isPreset = Array.from($('#garansiBulan').options).some(
      (option) => option.value === String(value)
    );
    $('#garansiBulan').value = isPreset ? String(value) : 'custom';
    $('#garansiBulanCustom').value = isPreset ? '' : String(value);
    updateGaransiFields();
  }

  function makeRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    const bytes = new Uint8Array(16);
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      window.crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < bytes.length; i += 1) {
        bytes[i] = Math.floor(Math.random() * 256);
      }
    }
    let value = '';
    for (let i = 0; i < bytes.length; i += 1) {
      value += bytes[i].toString(16).padStart(2, '0');
    }
    return value;
  }

  // Idempotency key dipakai ulang hanya bila isi transaksi tidak berubah.
  function ensureRequestId(payload) {
    const signature = JSON.stringify(payload);
    if (!state.pendingRequest || state.pendingRequest.signature !== signature) {
      state.pendingRequest = { signature, id: makeRequestId() };
    }
    return state.pendingRequest.id;
  }

  function updatePartWarrantyFields() {
    $('#garansiTukarFields')?.classList.toggle(
      'hidden',
      !$('#garansiTukarAktif')?.checked
    );
    $('#garansiBarangFields')?.classList.toggle(
      'hidden',
      !$('#garansiBarangAktif')?.checked
    );
  }

  function applyPosMode() {
    const partMode = state.posMode === 'PART';
    $('#view-pos')?.classList.toggle('pos-part-mode', partMode);
    $('#unitDitinggalField')?.classList.toggle('hidden', partMode);
    $('#serviceWarrantyBox')?.classList.toggle('hidden', partMode);
    $('#partWarrantyBox')?.classList.toggle('hidden', !partMode);
    $('#unitCard')?.classList.toggle(
      'hidden',
      partMode || !state.selectedCustomer
    );
    $('#complaintCard')?.classList.toggle(
      'hidden',
      partMode || !state.selectedCustomer || !state.selectedUnit
    );
    $('#itemsCard')?.classList.toggle(
      'hidden',
      partMode ? false : !(state.selectedCustomer && state.selectedUnit)
    );
    $$('.line-form--jasa, .items-block--jasa').forEach((element) => {
      element.classList.toggle('hidden', partMode);
    });
    $('#jobSubtotalRow')?.classList.toggle('hidden', partMode);
    if (partMode) $('#partIntervalHint')?.classList.add('hidden');
    if ($('#customerSearch')) {
      $('#customerSearch').placeholder = partMode
        ? 'Cari pelanggan (opsional)'
        : 'Cari nama atau no. HP';
    }
    updateSummaryCustomer();
    updatePartWarrantyFields();
  }

  function setPosMode(mode) {
    const next = mode === 'PART' ? 'PART' : 'SERVICE';
    if (state.posMode === next) return;
    state.posMode = next;
    $$('#posModeSwitch button').forEach((button) => {
      button.classList.toggle('active', button.dataset.posMode === next);
    });
    resetPosState();
    applyPosMode();
  }

  function resetPosState() {
    state.pendingRequest = null;
    state.selectedCustomer = null;
    state.customerResults = [];
    state.units = [];
    state.selectedUnit = null;
    state.jobs = [];
    state.parts = [];
    state.unitType = 'MOBIL';
    state.complaintConfirmed = false;
    state.newUnitFormOpen = false;
    state.notaReviewed = false;
    showSaveActions(false);

    if ($('#customerSearch')) $('#customerSearch').value = '';
    hideCustomerResults();
    $('#unitCard').classList.add('hidden');
    $('#complaintCard').classList.add('hidden');
    $('#itemsCard').classList.add('hidden');
    $('#unitList').innerHTML = '';
    $('#keluhanInput').value = '';
    $('#catatanPengerjaan').value = '';
    $('#diskonInput').value = '0';
    $('#bayarInput').value = '';
    $('#rencanaBayarInput').value = '';
    $('#rencanaTanggalInput').value = '';
    $('#kreditUangMukaAktif').checked = false;
    $('#kreditUangMukaInput').value = '';
    $('#unitDitinggalAktif').checked = false;
    if ($('#posCashier')) $('#posCashier').value = '';
    $$('#posMechanics input').forEach((input) => {
      input.checked = false;
    });
    $('#metodeCash').checked = true;
    $('#metodeTransfer').checked = false;
    state.jenisBayar = 'LUNAS';
    $('#garansiAktif').checked = true;
    $('#partInterval').value = '0';
    $('#partIntervalHint').classList.add('hidden');
    if ($('#garansiTukarAktif')) {
      $('#garansiTukarAktif').checked = false;
      $('#garansiTukarHari').value = '7';
    }
    if ($('#garansiBarangAktif')) {
      $('#garansiBarangAktif').checked = false;
      $('#garansiBarangNilai').value = '1';
      $('#garansiBarangSatuan').value = 'BULAN';
    }

    if (state.config) {
      setGaransiBulan(state.config.default_garansi_bulan || 1);
      $('#garansiCatatan').value = state.config.garansi_syarat || '';
    }

    setUnitType('MOBIL');
    resetUnitForm();
    updateGaransiFields();
    updateJenisBayar();
    state.preview = null;
    state.previewError = null;
    state.previewSeq += 1;
    if (state.previewTimer) {
      clearTimeout(state.previewTimer);
      state.previewTimer = null;
    }
    renderPreview(null, null);
    renderSelectedCustomer();
    renderItems();
    updateSummary();
    applyPosMode();
  }

  /* ---------------------------- Transaction ------------------------------- */
  function buildTransactionPayload() {
    const metode = getMetode();
    const kreditMode = isKreditMode();
    const partMode = state.posMode === 'PART';
    // Server menghitung nilai final; frontend hanya mengirim angka mentah.
    const paid =
      !kreditMode && metode === 'CASH'
        ? parseMoney($('#bayarInput').value)
        : 0;
    const uangMuka = kreditUangMukaAktif()
      ? String(parseMoney($('#kreditUangMukaInput').value))
      : '0';
    const tukarAktif = partMode && Boolean($('#garansiTukarAktif')?.checked);
    const barangAktif = partMode && Boolean($('#garansiBarangAktif')?.checked);

    return {
      unit_id: partMode
        ? state.selectedUnit
          ? state.selectedUnit.id
          : null
        : state.selectedUnit.id,
      customer_id:
        partMode && state.selectedCustomer ? state.selectedCustomer.id : null,
      sparepart_only: partMode,
      keluhan_awal: partMode ? '' : $('#keluhanInput').value.trim(),
      catatan_pengerjaan: $('#catatanPengerjaan').value.trim() || null,
      diskon: String(parseMoney($('#diskonInput').value)),
      metode_bayar: metode,
      bayar: String(paid),
      jenis_bayar: getJenisBayar(),
      dp: uangMuka,
      rencana_bayar: kreditMode
        ? String(parseMoney($('#rencanaBayarInput').value))
        : '0',
      jatuh_tempo: kreditMode
        ? $('#rencanaTanggalInput').value || null
        : null,
      unit_ditinggal: partMode ? false : $('#unitDitinggalAktif').checked,
      cashier_employee_id:
        state.config && state.config.ops && state.config.ops.karyawan_aktif === false
          ? null
          : intValue($('#posCashier').value, 0) || null,
      mechanic_ids:
        state.config && state.config.ops && state.config.ops.karyawan_aktif === false
          ? []
          : $$('#posMechanics input:checked').map((input) => Number(input.value)),
      bergaransi: partMode ? false : $('#garansiAktif').checked,
      garansi_bulan: partMode ? 1 : garansiBulanValue(),
      catatan_garansi: partMode
        ? null
        : $('#garansiCatatan').value.trim() || null,
      garansi_tukar_aktif: tukarAktif,
      garansi_tukar_hari: tukarAktif
        ? Math.max(1, intValue($('#garansiTukarHari').value, 1))
        : 0,
      garansi_barang_aktif: barangAktif,
      garansi_barang_nilai: barangAktif
        ? Math.max(1, intValue($('#garansiBarangNilai').value, 1))
        : 0,
      garansi_barang_satuan: barangAktif
        ? $('#garansiBarangSatuan').value
        : 'HARI',
      jobs: partMode
        ? []
        : state.jobs.map((job) => ({
            harga_jasa_id: job.harga_jasa_id || null,
            deskripsi: job.deskripsi,
            jumlah: Math.max(1, intValue(job.jumlah, 1)),
            harga: String(parseMoney(job.harga)),
            interval_servis_bulan: clampInterval(job.interval_servis_bulan),
          })),
      parts: state.parts.map((part) => ({
        stock_item_id: part.stock_item_id || null,
        nama_part: part.nama_part,
        jumlah: Math.max(1, intValue(part.jumlah, 1)),
        harga_satuan: String(parseMoney(part.harga_satuan)),
        harga_modal:
          part.stock_item_id || part.harga_modal === '' || part.harga_modal == null
            ? null
            : String(parseMoney(part.harga_modal)),
        interval_servis_bulan: partMode
          ? 0
          : clampInterval(part.interval_servis_bulan),
      })),
    };
  }

  function showSaveActions(visible) {
    ['#btnSavePrint', '#btnSaveOnly'].forEach((selector) => {
      const button = $(selector);
      if (button) button.classList.toggle('hidden', !visible);
    });
  }

  function invalidateNotaReview() {
    state.notaReviewed = false;
    showSaveActions(false);
  }

  function validatePosForm() {
    if (state.posMode === 'PART') {
      if (state.jobs.length) {
        toast('Mode beli sparepart hanya menerima sparepart.', 'warning');
        return false;
      }
      if (!state.parts.length) {
        toast('Tambahkan minimal satu sparepart.', 'warning');
        return false;
      }
      if ($('#garansiTukarAktif')?.checked) {
        const hari = intValue($('#garansiTukarHari').value, 0);
        if (hari < 1) {
          toast('Isi durasi garansi penukaran minimal 1 hari.', 'warning');
          $('#garansiTukarHari').focus();
          return false;
        }
      }
      if ($('#garansiBarangAktif')?.checked) {
        const nilai = intValue($('#garansiBarangNilai').value, 0);
        if (nilai < 1) {
          toast('Isi durasi garansi barang minimal 1.', 'warning');
          $('#garansiBarangNilai').focus();
          return false;
        }
      }
    } else {
      if (!state.selectedCustomer) {
        toast('Pilih pelanggan terlebih dahulu.', 'warning');
        return false;
      }
      if (!state.selectedUnit) {
        toast('Pilih unit servis terlebih dahulu.', 'warning');
        return false;
      }
      if (!$('#keluhanInput').value.trim()) {
        toast('Keluhan awal wajib diisi.', 'warning');
        $('#keluhanInput').focus();
        return false;
      }
      if (!state.complaintConfirmed) {
        toast('Simpan keluhan awal terlebih dahulu.', 'warning');
        $('#btnSaveComplaint').focus();
        return false;
      }
    }
    if (!state.jobs.length && !state.parts.length) {
      toast('Tambahkan minimal satu jasa atau sparepart.', 'warning');
      return false;
    }
    if (
      !moneyInputValid($('#diskonInput').value) ||
      (getMetode() === 'CASH' &&
        getJenisBayar() === 'LUNAS' &&
        !moneyInputValid($('#bayarInput').value)) ||
      (isKreditMode() &&
        (!moneyInputValid($('#rencanaBayarInput').value) ||
          (kreditUangMukaAktif() &&
            !moneyInputValid($('#kreditUangMukaInput').value)))) ||
      state.jobs.some((job) => !moneyInputValid(job.harga)) ||
      state.parts.some((part) => !moneyInputValid(part.harga_satuan))
    ) {
      toast('Angka uang harus rupiah bulat tanpa desimal.', 'warning');
      return false;
    }
    if (kreditUangMukaAktif() && parseMoney($('#kreditUangMukaInput').value) <= 0) {
      toast('Isi uang muka lebih dari Rp 0 atau matikan opsi penambahan uang.', 'warning');
      $('#kreditUangMukaInput').focus();
      return false;
    }
    return true;
  }

  function reviewLineHtml(item, line, name) {
    const qty = Math.max(1, intValue(item.jumlah, 1));
    const price = name === 'job' ? item.harga : item.harga_satuan;
    const interval = clampInterval(item.interval_servis_bulan);
    return (
      '<div class="review-line">' +
      '<div class="review-line-main"><strong>' +
      esc(item.deskripsi || item.nama_part || '-') +
      '</strong><span>x' +
      qty +
      ' · ' +
      fmtRp(price) +
      (interval > 0 ? ' · servis tiap ' + interval + ' bulan' : '') +
      '</span></div>' +
      '<span class="review-line-total">' +
      (line ? fmtRp(line.subtotal) : '\u2014') +
      '</span></div>'
    );
  }

  function buildNotaReviewHtml(preview) {
    const customer = state.selectedCustomer || {};
    const unit = state.selectedUnit || {};
    const partMode = state.posMode === 'PART';
    const kreditMode = isKreditMode();
    const kreditTanggal = $('#rencanaTanggalInput').value;
    const jenisLabel = kreditMode ? 'Kredit' : 'Lunas';
    const tukarAktif = partMode && Boolean($('#garansiTukarAktif')?.checked);
    const barangAktif = partMode && Boolean($('#garansiBarangAktif')?.checked);
    const tukarHari = Math.max(1, intValue($('#garansiTukarHari').value, 1));
    const barangNilai = Math.max(1, intValue($('#garansiBarangNilai').value, 1));
    const barangSatuan =
      $('#garansiBarangSatuan').value === 'BULAN' ? 'bulan' : 'hari';
    const customerNama = customer.nama || 'Pelanggan Umum';
    const unitLabel = partMode ? 'Pembelian sparepart' : describeUnit(unit);
    const jobs = state.jobs.length
      ? state.jobs
          .map((job, index) =>
            reviewLineHtml(job, (preview.jobs || [])[index], 'job')
          )
          .join('')
      : '<div class="empty-state sm">Belum ada jasa.</div>';
    const parts = state.parts.length
      ? state.parts
          .map((part, index) =>
            reviewLineHtml(part, (preview.parts || [])[index], 'part')
          )
          .join('')
      : '<div class="empty-state sm">Belum ada sparepart.</div>';
    const garansiAktif = $('#garansiAktif').checked;
    const unitDitinggal = $('#unitDitinggalAktif').checked;

    return (
      '<div class="nota-review">' +
      '<div class="review-block"><h4 class="detail-section-title">Pelanggan &amp; unit</h4>' +
      '<div class="detail-grid">' +
      detailItem('Nama', esc(customerNama)) +
      detailItem('No. HP', esc(customer.nomor_hp || '-')) +
      detailItem('Unit', esc(unitLabel)) +
      '</div></div>' +
      '<div class="review-block"><h4 class="detail-section-title">Keluhan &amp; catatan</h4>' +
      '<p class="detail-text">' +
      esc(partMode ? 'Pembelian sparepart saja.' : $('#keluhanInput').value.trim()) +
      '</p>' +
      ($('#catatanPengerjaan').value.trim()
        ? '<p class="tiny muted">Catatan: ' +
          esc($('#catatanPengerjaan').value.trim()) +
          '</p>'
        : '') +
      '</div>' +
      (partMode
        ? ''
        : '<div class="review-block"><h4 class="detail-section-title">Jasa</h4>' +
          jobs +
          '</div>') +
      '<div class="review-block"><h4 class="detail-section-title">Sparepart</h4>' +
      parts +
      '</div>' +
      '<div class="review-block"><h4 class="detail-section-title">Total</h4>' +
      (partMode
        ? ''
        : '<div class="review-total-row"><span>Total jasa</span><strong>' +
          fmtRp(preview.biaya_jasa) +
          '</strong></div>') +
      '<div class="review-total-row"><span>Total part</span><strong>' +
      fmtRp(preview.total_part) +
      '</strong></div>' +
      '<div class="review-total-row"><span>Diskon</span><strong>' +
      fmtRp(preview.diskon) +
      '</strong></div>' +
      '<div class="review-total-row is-grand"><span>Grand total</span><strong>' +
      fmtRp(preview.total_servis) +
      '</strong></div></div>' +
      '<div class="review-block"><h4 class="detail-section-title">Pembayaran &amp; garansi</h4>' +
      '<div class="detail-grid">' +
      detailItem(
        'Metode',
        esc(getMetode() === 'TRANSFER' ? 'Transfer' : 'Tunai')
      ) +
      detailItem('Jenis', esc(jenisLabel)) +
      (kreditMode
        ? detailItem(
            'Rencana pembayaran',
            fmtRp(parseMoney($('#rencanaBayarInput').value))
          ) +
          detailItem(
            'Tanggal rencana',
            esc(kreditTanggal ? fmtDate(kreditTanggal) : 'Tidak ditentukan')
          ) +
          detailItem(
            'Uang muka',
            fmtRp(
              kreditUangMukaAktif()
                ? parseMoney($('#kreditUangMukaInput').value)
                : 0
            )
          ) +
          detailItem('Sisa tagihan', fmtRp(preview.sisa_bayar))
        : detailItem('Uang diterima', fmtRp(parseMoney($('#bayarInput').value))) +
          detailItem('Kembalian', fmtRp(preview.kembalian))) +
      (partMode
        ? (tukarAktif
            ? detailItem('Garansi tukar', esc(tukarHari + ' hari'))
            : '') +
          (barangAktif
            ? detailItem(
                'Garansi barang',
                esc(barangNilai + ' ' + barangSatuan)
              )
            : '') +
          (!tukarAktif && !barangAktif
            ? detailItem('Garansi', 'Tidak aktif')
            : '')
        : detailItem('Unit ditinggal', unitDitinggal ? 'Ya' : 'Tidak') +
          detailItem('Garansi', esc(garansiAktif ? 'Aktif' : 'Tidak aktif')) +
          (garansiAktif
            ? detailItem('Durasi', esc(garansiBulanValue() + ' bulan'))
            : '')) +
      '</div>' +
      (garansiAktif && !partMode && $('#garansiCatatan').value.trim()
        ? '<p class="tiny muted">Catatan garansi: ' +
          esc($('#garansiCatatan').value.trim()) +
          '</p>'
        : '') +
      '</div></div>'
    );
  }

  async function reviewNota() {
    if (!validatePosForm()) return false;
    await refreshPreview();
    if (state.previewError) {
      toast(state.previewError, 'warning');
      return false;
    }
    if (!state.preview) {
      toast('Ringkasan nota belum siap. Coba lagi.', 'warning');
      return false;
    }
    $('#notaReviewBody').innerHTML = buildNotaReviewHtml(state.preview);
    openModal('#notaReviewModal');
    return true;
  }

  function editNotaReview() {
    closeModal('#notaReviewModal');
    const target = $('#keluhanInput');
    if (target) target.focus();
  }

  function confirmNotaReview() {
    closeModal('#notaReviewModal');
    state.notaReviewed = true;
    showSaveActions(true);
    const button = $('#btnSavePrint');
    if (button) button.focus();
  }

  async function saveTransaction(printAfter) {
    if (state.saving) return;
    if (!validatePosForm()) return;
    if (!state.notaReviewed) {
      toast('Periksa nota dan tekan Benar sebelum menyimpan.', 'warning');
      await reviewNota();
      return;
    }
    if (state.previewError) {
      toast(state.previewError, 'warning');
      return;
    }

    const payload = buildTransactionPayload();
    const requestId = ensureRequestId(payload);
    const button = printAfter ? $('#btnSavePrint') : $('#btnSaveOnly');
    state.saving = true;
    setBusy(button, true, 'Menyimpan...');

    let allowNegative = false;
    let result = null;

    try {
      for (;;) {
        try {
          result = await API.createTransaction(
            Object.assign({}, payload, {
              izinkan_stok_minus: allowNegative,
              request_id: requestId,
            })
          );
          break;
        } catch (err) {
          const stockConflict =
            err.status === 409 &&
            err.detail &&
            Array.isArray(err.detail.items) &&
            !allowNegative;
          if (!stockConflict) throw err;

          const proceed = window.confirm(
            err.message + '\n\nTetap simpan transaksi dengan stok minus?'
          );
          if (!proceed) return;
          allowNegative = true;
        }
      }

      toast('Nota ' + result.record.no_nota + ' berhasil disimpan.', 'success', 5000);
      (result.warnings || []).forEach((warning) =>
        toast(warning, 'warning', 8000)
      );

      if (printAfter) showReceipt(result.receipt);
      resetPosState();

      await Promise.all([loadDashboard(), loadStock(), loadPartsOutToday()]);
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      state.saving = false;
      setBusy(button, false);
    }
  }

  async function loadPartsOutToday() {
    try {
      const sold = await API.soldParts(todayISO(), todayISO());
      state.partsOutToday = intValue(sold && sold.total_qty, 0);
    } catch (err) {
      state.partsOutToday = 0;
    }
    const el = $('#partsOutToday');
    if (el) el.textContent = String(state.partsOutToday);
  }

  /* ------------------------------ Receipt --------------------------------- */
  const RECEIPT_WIDTH_KEY = 'bengkel.receiptWidth';

  function normalizeReceiptWidth(value) {
    if (String(value) === 'A4') return 'A4';
    return intValue(value, 58) === 80 ? 80 : 58;
  }

  function preferredReceiptWidth() {
    const stored = window.localStorage.getItem(RECEIPT_WIDTH_KEY);
    if (stored) return normalizeReceiptWidth(stored);
    const primary = activePrimaryPrinter();
    if (primary) return normalizeReceiptWidth(primary.paper_width);
    return normalizeReceiptWidth(
      state.config && state.config.printer.paper_width
    );
  }

  function showReceipt(receipt) {
    state.receipt = receipt;
    state.printPrinterId = null;
    state.printFailure = null;
    clearPrintJobTimer();
    const primary = activePrimaryPrinter();
    state.receiptWidth = primary
      ? normalizeReceiptWidth(primary.paper_width)
      : preferredReceiptWidth();
    if (hasNativeBridge() && state.receiptWidth === 'A4') {
      state.receiptWidth = 58;
    }
    syncReceiptWidthUI();
    $('#receiptTitle').textContent = 'Struk ' + receipt.no_nota;
    $('#receiptSubtitle').textContent =
      receipt.customer_nama + ' - ' + receipt.unit_deskripsi;
    renderReceiptPreview();
    refreshReceiptPrinterUI();
    setReceiptPrintStatus('', '');
    showWhatsappFallback(false);
    openModal('#receiptModal');
  }

  function currentReceiptLines() {
    if (!state.receipt) return [];
    return state.receiptWidth === 58
      ? state.receipt.struk_58
      : state.receipt.struk_80;
  }

  function renderReceiptPreview() {
    const preview = $('#receiptPreview');
    if (!preview || !state.receipt) return;
    preview.textContent = currentReceiptLines().join('\n');
    preview.classList.toggle('w80', state.receiptWidth === 80);
    preview.classList.toggle('w-a4', state.receiptWidth === 'A4');
  }

  function syncReceiptWidthUI() {
    $$('#receiptWidthSwitch button').forEach((button) => {
      button.classList.toggle(
        'active',
        String(button.dataset.width) === String(state.receiptWidth)
      );
    });
  }

  function onReceiptWidthClick(event) {
    const button = event.target.closest('button[data-width]');
    if (!button) return;
    state.receiptWidth = normalizeReceiptWidth(button.dataset.width);
    window.localStorage.setItem(
      RECEIPT_WIDTH_KEY,
      String(state.receiptWidth)
    );
    syncReceiptWidthUI();
    renderReceiptPreview();
  }

  /* ------------------------------ WhatsApp -------------------------------- */
  function waDigits(value) {
    return String(value == null ? '' : value).replace(/\D/g, '');
  }

  function waLink(number, text) {
    let target = waDigits(number);
    if (!target) return '';
    if (target.charAt(0) === '0') {
      target = '62' + target.slice(1);
    } else if (target.charAt(0) === '8') {
      target = '62' + target;
    }
    const suffix = text ? '?text=' + encodeURIComponent(text) : '';
    return 'https://wa.me/' + target + suffix;
  }

  async function openExternalLink(url) {
    const target = String(url || '').trim();
    if (!target) return false;
    if (
      hasNativeBridge() &&
      window.BengkelBridge &&
      typeof window.BengkelBridge.call === 'function'
    ) {
      try {
        await window.BengkelBridge.call('openExternal', { url: target }, 15000);
        return true;
      } catch (err) {
        toast(err.message || 'Tautan tidak dapat dibuka.', 'error', 6000);
        return false;
      }
    }
    const opened = window.open(target, '_blank');
    if (!opened) {
      toast('Tautan tidak dapat dibuka. Izinkan pop-up lalu coba lagi.', 'warning');
      return false;
    }
    opened.opener = null;
    return true;
  }

  async function copyText(value, successMessage) {
    const text = String(value == null ? '' : value);
    if (!text.trim()) {
      toast('Tidak ada teks untuk disalin.', 'warning');
      return false;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const area = document.createElement('textarea');
        area.value = text;
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
      }
      toast(successMessage || 'Teks disalin.', 'success');
      return true;
    } catch (err) {
      toast('Gagal menyalin. Salin manual dari kotak teks.', 'warning');
      return false;
    }
  }

  function openWaPreview(options) {
    const opts = options || {};
    const link = opts.link || waLink(opts.nomor, opts.text);
    state.waPreview = {
      link: link,
      nomor: opts.nomor || '',
      disabled: Boolean(opts.disabled),
      onOpen: typeof opts.onOpen === 'function' ? opts.onOpen : null,
    };
    $('#waModalTitle').textContent = opts.judul || 'Pesan WhatsApp';
    $('#waModalSubtitle').textContent =
      opts.subtitle || 'Periksa pesan sebelum dibuka di WhatsApp.';
    $('#waModalNumber').value = opts.masked || opts.nomor || '-';
    $('#waModalText').value = opts.text || '';
    $('#waModalNote').textContent =
      opts.note ||
      'Pesan hanya dibuka di WhatsApp, tidak dikirim otomatis. Upaya dicatat saat tombol dibuka.';
    const open = $('#waModalOpen');
    if (!link || opts.disabled) {
      open.classList.add('hidden');
    } else {
      open.classList.remove('hidden');
      open.href = link;
    }
    openModal('#waModal');
  }

  async function handleWaOpen(event) {
    event.preventDefault();
    const preview = state.waPreview;
    if (!preview || preview.disabled) return;
    const text = ($('#waModalText').value || '').trim();
    const link = preview.nomor ? waLink(preview.nomor, text) : preview.link;
    if (!link) {
      toast('Nomor WhatsApp pelanggan belum valid.', 'warning');
      return;
    }
    const onOpen = preview.onOpen;
    state.waPreview = null;
    closeModal('#waModal');
    const opening = openExternalLink(link);
    if (!onOpen) {
      await opening;
      return;
    }
    try {
      await onOpen(text);
    } catch (err) {
      toast(err.message, 'error', 7000);
    }
    await opening;
  }

  function receiptWaNumber(receipt) {
    return receipt.customer_wa || receipt.customer_hp || '';
  }

  async function openRecordForPayment(id) {
    await openRecordDetail(id);
    const input = $('#paymentNominal');
    if (!input) return;
    input.focus();
    if (input.scrollIntoView) {
      input.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  async function openCompletionWhatsapp(id) {
    try {
      let receipt = state.detailRecord;
      if (!receipt || receipt.id !== id) {
        receipt = await API.receipt(id);
      }
      if (!waDigits(receiptWaNumber(receipt))) {
        toast('Nomor WhatsApp pelanggan belum valid.', 'warning');
        return;
      }
      if (!(receipt.completion_wa_text || '').trim()) {
        toast('Pesan kendaraan selesai belum tersedia.', 'warning');
        return;
      }
      const gate = await API.recordWaGate(id, 'pengerjaan');
      if (!gate.allowed) {
        toast(gate.alasan, 'warning', 7000);
        return;
      }
      if (gate.peringatan) toast(gate.peringatan, 'warning', 7000);
      openWaPreview({
        judul: 'Kendaraan selesai · ' + receipt.no_nota,
        subtitle: 'Periksa pesan untuk ' + receipt.customer_nama + '.',
        nomor: receiptWaNumber(receipt),
        text: receipt.completion_wa_text,
        note: 'Membuka WhatsApp akan mencatat upaya pemberitahuan. Kasir tetap menekan kirim di WhatsApp.',
        onOpen: async (text) => {
          await API.recordWhatsapp(receipt.id, {
            status: 'DIBUKA',
            jenis: 'pengerjaan',
            pesan: text,
          });
          toast('Pemberitahuan kendaraan selesai tercatat.', 'success');
          if (state.detailRecord && state.detailRecord.id === receipt.id) {
            await loadRecordExtras(receipt.id);
          }
          if (!$('#pengerjaanModal').classList.contains('hidden')) {
            await loadPengerjaan();
          }
        },
      });
    } catch (err) {
      toast('Pesan kendaraan selesai gagal dimuat.', 'error', 6000);
    }
  }

  function showWhatsappFallback(visible) {
    const button = $('#btnReceiptWhatsappFallback');
    if (button) button.classList.toggle('hidden', !visible);
  }

  async function sendReceiptToWhatsapp(receipt) {
    if (!receipt) return false;
    if (!waDigits(receiptWaNumber(receipt))) return false;
    const text = String(receipt.wa_text || '').trim();
    if (!text) return false;
    try {
      const gate = await API.recordWaGate(receipt.id, 'struk');
      if (!gate.allowed) {
        toast(gate.alasan, 'warning', 7000);
        return false;
      }
    } catch (err) {
      toast(err.message, 'error', 7000);
      return false;
    }
    const link = waLink(receiptWaNumber(receipt), text);
    if (!link) return false;

    showWhatsappFallback(false);
    if (
      hasNativeBridge() &&
      window.BengkelBridge &&
      typeof window.BengkelBridge.call === 'function'
    ) {
      try {
        await window.BengkelBridge.call('openExternal', { url: link }, 15000);
      } catch (err) {
        try {
          await API.recordWhatsapp(receipt.id, {
            status: 'TIDAK_TERSEDIA',
            jenis: 'struk',
          });
        } catch (logErr) {
          /* Kegagalan mencatat tidak boleh menyembunyikan pesan utama. */
        }
        toast(
          (err && err.message) ||
            'WhatsApp tidak tersedia di perangkat ini. Gunakan Salin teks.',
          'error',
          8000
        );
        return false;
      }
    } else {
      const opened = window.open(link, '_blank');
      if (!opened) {
        showWhatsappFallback(true);
        toast(
          'WhatsApp tidak dapat dibuka otomatis karena pop-up diblokir. ' +
            'Tekan "Buka WhatsApp" atau salin teks struk.',
          'warning',
          9000
        );
        return false;
      }
      opened.opener = null;
    }

    try {
      await API.recordWhatsapp(receipt.id, {
        status: 'DIBUKA',
        jenis: 'struk',
      });
      toast(
        'WhatsApp nota ' + receipt.no_nota + ' dibuka. Tekan kirim di WhatsApp.',
        'success',
        6000
      );
      if (state.detailRecord && state.detailRecord.id === receipt.id) {
        await loadRecordExtras(receipt.id);
      }
    } catch (err) {
      toast(err.message, 'error', 7000);
    }
    return true;
  }

  function hasNativeBridge() {
    return Boolean(
      window.BengkelBridge && window.BengkelBridge.available()
    );
  }

  function activePrimaryPrinter() {
    const manager = window.printerManager;
    return manager ? manager.primaryPrinter() : null;
  }

  function selectedPrintPrinter() {
    const manager = window.printerManager;
    if (!manager) return null;
    if (state.printPrinterId) {
      return manager.printerSnapshot(state.printPrinterId);
    }
    return manager.primaryPrinter();
  }

  function printerStatusLabel(printer) {
    if (!printer) return { label: 'Belum diatur', tone: 'gray' };
    if (printer.supported === false) {
      return { label: 'Tidak didukung', tone: 'red' };
    }
    if (printer.status === 'CONNECTED') {
      return { label: 'Terhubung', tone: 'green' };
    }
    if (printer.status === 'CONNECTING') {
      return { label: 'Menghubungkan...', tone: 'amber' };
    }
    if (printer.status === 'UNAVAILABLE') {
      return { label: 'Tidak tersedia', tone: 'red' };
    }
    if (printer.status === 'ERROR') {
      return { label: 'Gagal', tone: 'red' };
    }
    const manager = window.printerManager;
    const adapter = manager && manager.adapterFor(printer.connection_type);
    if (adapter && adapter.connectionless) {
      return { label: 'Siap dipakai', tone: 'gray' };
    }
    return { label: 'Tersimpan', tone: 'gray' };
  }

  function refreshReceiptPrinterUI() {
    const note = $('#receiptNotice');
    const target = selectedPrintPrinter();
    if (note) {
      if (!window.printerManager) {
        note.textContent = 'Fitur printer tidak tersedia di perangkat ini.';
      } else if (!target) {
        note.textContent =
          'Belum ada printer utama. Tambahkan printer di Pengaturan > Printer.';
      } else {
        note.textContent =
          'Printer: ' +
          target.name +
          ' (' +
          target.paper_width +
          ' mm, ' +
          printerTypeLabel(target.connection_type).toLowerCase() +
          ')';
      }
    }

    const nameEl = $('#receiptPrinterName');
    const statusEl = $('#receiptPrinterStatus');
    if (nameEl) {
      nameEl.textContent = target ? target.name : 'Belum ada printer utama';
    }
    if (statusEl) {
      const badge = printerStatusLabel(target);
      statusEl.textContent = badge.label;
      statusEl.className = 'badge ' + badge.tone;
    }

    const native = hasNativeBridge();
    const browserButton = $('#btnBrowserPrint');
    if (browserButton) browserButton.classList.toggle('hidden', native);
    const a4Button = $('#receiptWidthA4');
    if (a4Button) a4Button.classList.toggle('hidden', native);
    const printButton = $('#btnReceiptPrint');
    if (printButton) printButton.disabled = state.printing;
  }

  function setReceiptPrintStatus(kind, message, options) {
    const box = $('#receiptPrintStatus');
    const text = $('#receiptPrintMessage');
    if (!box || !text) return;
    if (!message) {
      box.classList.add('hidden');
      box.classList.remove('info', 'success', 'error');
      text.textContent = '';
      return;
    }
    box.classList.remove('hidden', 'info', 'success', 'error');
    box.classList.add(kind || 'info');
    text.textContent = message;

    const opts = options || {};
    const retry = $('#btnReceiptRetry');
    const choose = $('#btnReceiptChooseOther');
    const settings = $('#btnReceiptOpenSettings');
    if (retry) retry.classList.toggle('hidden', !opts.retry);
    if (choose) choose.classList.toggle('hidden', !opts.chooseOther);
    if (settings) settings.classList.toggle('hidden', !opts.settings);
  }

  function clearPrintJobTimer() {
    if (state.printJobTimer) {
      clearTimeout(state.printJobTimer);
      state.printJobTimer = null;
    }
  }

  function describeJobState(status) {
    const stateName = String(status && status.state ? status.state : 'UNKNOWN');
    if (stateName === 'COMPLETED') return 'Selesai dilaporkan layanan cetak';
    if (stateName === 'PRINTING') return 'Sedang dikirim ke layanan cetak';
    if (stateName === 'QUEUED') return 'Menunggu antrean layanan cetak';
    if (stateName === 'BLOCKED') return 'Tertahan, periksa dialog Android';
    if (stateName === 'CANCELLED') return 'Dibatalkan dari dialog Android';
    if (stateName === 'FAILED') return 'Gagal menurut layanan cetak';
    if (stateName === 'IDLE') return 'Belum ada pekerjaan';
    if (stateName === 'UNAVAILABLE') return 'Layanan cetak tidak tersedia';
    return 'Status belum tersedia';
  }

  function monitorSystemPrintJob(printer, jobId, receipt) {
    const manager = window.printerManager;
    const adapter = manager && manager.adapterFor('SYSTEM');
    if (!adapter || typeof adapter.jobStatus !== 'function') return;
    const key = String(printer.id) + ':' + String(jobId);
    if (state.printJobSeen.has(key)) return;
    state.printJobSeen.add(key);
    clearPrintJobTimer();

    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      let status = null;
      try {
        status = await adapter.jobStatus(jobId);
      } catch (err) {
        status = { state: 'UNKNOWN', message: err.message };
      }
      const stateName = String((status && status.state) || 'UNKNOWN');
      const message =
        'Status pekerjaan Android: ' + describeJobState(status) + '.';
      if (!$('#receiptModal').classList.contains('hidden')) {
        const final = ['COMPLETED', 'CANCELLED', 'FAILED', 'UNAVAILABLE'];
        setReceiptPrintStatus(
          stateName === 'COMPLETED'
            ? 'success'
            : stateName === 'FAILED' || stateName === 'UNAVAILABLE'
              ? 'error'
              : 'info',
          message,
          {}
        );
      }
      if (stateName === 'COMPLETED') {
        toast('Layanan cetak melaporkan pekerjaan selesai.', 'success');
        if (receipt) await sendReceiptToWhatsapp(receipt);
        return;
      }
      if (stateName === 'FAILED' || stateName === 'UNAVAILABLE') {
        toast('Pekerjaan cetak Android gagal. Periksa printer.', 'error', 7000);
        return;
      }
      if (stateName === 'CANCELLED') {
        toast('Pekerjaan cetak dibatalkan dari dialog Android.', 'info');
        return;
      }
      if (attempts >= 80) return;
      state.printJobTimer = setTimeout(poll, 1500);
    };
    state.printJobTimer = setTimeout(poll, 1200);
  }

  async function printReceipt(receipt, silent) {
    if (!receipt) {
      toast('Tidak ada struk untuk dicetak.', 'warning');
      return false;
    }
    if (state.printing) return false;

    const width = state.receiptWidth;
    if (width === 'A4') {
      if (hasNativeBridge()) {
        setReceiptPrintStatus(
          'error',
          'Pilih lebar 58 mm atau 80 mm untuk printer utama. Cetak A4 hanya bisa lewat browser di komputer.',
          {}
        );
        toast('Struk memakai lebar kertas printer utama, 58 atau 80 mm.', 'warning');
        return false;
      }
      browserPrint(currentReceiptLines(), 'A4');
      setReceiptPrintStatus(
        'info',
        'Dialog cetak browser dibuka. Pilih printer lalu konfirmasi.',
        {}
      );
      await sendReceiptToWhatsapp(receipt);
      return true;
    }

    const manager = window.printerManager;
    if (!manager) {
      setReceiptPrintStatus(
        'error',
        'Fitur printer tidak tersedia. Muat ulang aplikasi.',
        {}
      );
      await sendReceiptToWhatsapp(receipt);
      return false;
    }

    const target = selectedPrintPrinter();
    if (!target) {
      setReceiptPrintStatus(
        'error',
        'Belum ada printer utama. Transaksi tetap tersimpan; pilih printer untuk mencetak struk ini.',
        { chooseOther: true, settings: true }
      );
      toast('Belum ada printer utama. Pilih printer di Pengaturan.', 'warning');
      await sendReceiptToWhatsapp(receipt);
      return false;
    }
    if (target.supported === false) {
      setReceiptPrintStatus(
        'error',
        'Printer ' +
          printerTypeLabel(target.connection_type) +
          ' tidak didukung di perangkat ini. Pilih printer lain.',
        { chooseOther: true, settings: true }
      );
      await sendReceiptToWhatsapp(receipt);
      return false;
    }
    // Pratinjau harus sama dengan lebar kertas printer tujuan; pengelola
    // printer memilih payload berdasarkan paper_width perangkat.
    const targetWidth = normalizeReceiptWidth(target.paper_width);
    if (state.receiptWidth !== targetWidth) {
      state.receiptWidth = targetWidth;
      window.localStorage.setItem(RECEIPT_WIDTH_KEY, String(targetWidth));
      syncReceiptWidthUI();
      renderReceiptPreview();
    }

    state.printing = true;
    state.printFailure = null;
    showWhatsappFallback(false);
    refreshReceiptPrinterUI();
    const button = $('#btnReceiptPrint');
    setBusy(button, true, 'Mengirim...');
    setReceiptPrintStatus(
      'info',
      'Mengirim struk ke ' + target.name + '...',
      {}
    );

    try {
      const result = await manager.printReceipt(receipt, {
        printerId: target.id,
      });
      const adapterResult = result && result.adapter_result;
      const systemJob =
        target.connection_type === 'SYSTEM' &&
        adapterResult &&
        adapterResult.job_id != null;
      if (systemJob) {
        setReceiptPrintStatus(
          'info',
          'Dialog Android dibuka. ' +
            'Pekerjaan #' +
            adapterResult.job_id +
            ': ' +
            describeJobState(adapterResult) +
            '.',
          {}
        );
        monitorSystemPrintJob(target, adapterResult.job_id, receipt);
      } else if (target.connection_type === 'WEB') {
        setReceiptPrintStatus(
          'info',
          'Dialog browser dibuka. Pilih printer lalu konfirmasi.',
          {}
        );
      } else {
        setReceiptPrintStatus(
          'success',
          'Struk ' +
            (receipt.no_nota || '') +
            ' dikirim ke ' +
            target.name +
            '. Status printer: ' +
            printerStatusLabel(manager.printerSnapshot(target.id)).label +
            '.',
          {}
        );
      }
      toast('Perintah cetak dikirim ke ' + target.name + '.', 'success');
      if (!systemJob) await sendReceiptToWhatsapp(receipt);
      return true;
    } catch (err) {
      const message = err && err.message ? err.message : String(err);
      state.printFailure = {
        receipt: receipt,
        printerId: target.id,
        message: message,
      };
      setReceiptPrintStatus(
        'error',
        message +
          ' Transaksi sudah tersimpan; mencetak ulang tidak membuat transaksi baru. ' +
          'Periksa kertas sebelum mencoba lagi karena sebagian struk mungkin sudah terkirim.',
        {
          retry: true,
          chooseOther: true,
          settings: true,
        }
      );
      toast('Cetak gagal: ' + message, 'error', 8000);
      await sendReceiptToWhatsapp(receipt);
      return false;
    } finally {
      state.printing = false;
      setBusy(button, false);
      refreshReceiptPrinterUI();
    }
  }

  function browserPrint(lines, width) {
    const text = (lines || []).join('\n');
    const isA4 = width === 'A4';
    const style = isA4
      ? '@page{size:A4;margin:15mm}' +
        'body{margin:0;font-family:"Courier New",monospace;font-size:12.5px;line-height:1.5;color:#000}' +
        'pre{margin:0 auto;width:120mm;white-space:pre;font-family:inherit}'
      : '@page{size:' +
        (width === 80 ? '80mm' : '58mm') +
        ' auto;margin:4mm}' +
        'body{margin:0;padding:6px;font-family:"Courier New",monospace;font-size:' +
        (width === 80 ? '11px' : '10.5px') +
        ';line-height:1.35;color:#000}' +
        'pre{margin:0;white-space:pre;font-family:inherit}';
    const html =
      '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Struk Servis</title>' +
      '<style>' +
      style +
      '</style></head><body><pre>' +
      esc(text) +
      '</pre><script>window.onload=function(){setTimeout(function(){window.print();},180);};<\/script>' +
      '</body></html>';

    const win = window.open(
      '',
      '_blank',
      isA4 ? 'width=900,height=1000' : 'width=420,height=760'
    );
    if (win && win.document) {
      win.document.open();
      win.document.write(html);
      win.document.close();
      return;
    }

    const frame = document.createElement('iframe');
    frame.style.cssText =
      'position:fixed;right:0;bottom:0;width:380px;height:600px;border:0;opacity:0;pointer-events:none';
    document.body.appendChild(frame);
    const doc = frame.contentDocument;
    if (!doc) {
      toast('Popup diblokir browser. Izinkan popup untuk mencetak.', 'error');
      frame.remove();
      return;
    }
    doc.open();
    doc.write(html);
    doc.close();
    setTimeout(() => {
      try {
        frame.contentWindow.focus();
        frame.contentWindow.print();
      } catch (err) {
        toast('Cetak browser gagal.', 'error');
      }
      setTimeout(() => frame.remove(), 1500);
    }, 350);
  }

  // Adapter WEB desktop memakai jalur cetak browser yang sama dengan tombol lama.
  window.BengkelWebPrint = { print: browserPrint };

  /* ------------------------------- Printer -------------------------------- */
  const PRINTER_TYPE_LABELS = Object.freeze({
    BLUETOOTH: 'Bluetooth',
    NETWORK: 'Wi-Fi / LAN',
    USB: 'USB OTG',
    SYSTEM: 'Cetak Android',
    WEB: 'Cetak browser',
  });

  const PRINTER_MODES = Object.freeze({
    BLUETOOTH: ['ESCPOS', 'TEXT'],
    NETWORK: ['ESCPOS', 'TEXT'],
    USB: ['ESCPOS', 'TEXT'],
    SYSTEM: ['SYSTEM', 'TEXT'],
    WEB: ['BROWSER', 'SYSTEM', 'TEXT'],
  });

  const PRINTER_DEFAULT_MODES = Object.freeze({
    BLUETOOTH: 'ESCPOS',
    NETWORK: 'ESCPOS',
    USB: 'ESCPOS',
    SYSTEM: 'SYSTEM',
    WEB: 'BROWSER',
  });

  function printerTypeLabel(type) {
    return PRINTER_TYPE_LABELS[String(type || '').toUpperCase()] || type || '-';
  }

  function printerModeLabel(mode) {
    const value = String(mode || '').toUpperCase();
    if (value === 'ESCPOS') return 'Printer thermal';
    if (value === 'TEXT') return 'Teks';
    if (value === 'SYSTEM') return 'Cetak Android';
    if (value === 'BROWSER') return 'Cetak browser';
    return value || '-';
  }

  function printerTargetLabel(printer) {
    if (!printer) return '-';
    if (printer.connection_type === 'BLUETOOTH') {
      return printer.address || 'Bluetooth';
    }
    if (printer.connection_type === 'NETWORK') {
      return (printer.ip || '-') + ':' + (printer.port || '-');
    }
    if (printer.connection_type === 'USB') {
      return 'USB';
    }
    if (printer.connection_type === 'SYSTEM') {
      return 'Dialog cetak Android';
    }
    if (printer.connection_type === 'WEB') {
      return 'Dialog cetak browser';
    }
    return '-';
  }

  function renderPrinterToolbar(snapshot) {
    const button = $('#printerBtn');
    const label = $('#printerLabel');
    if (!button || !label) return;
    const data = snapshot || (window.printerManager && window.printerManager.snapshot());
    const printers = (data && data.printers) || [];
    const primary = printers.find((item) => item.is_primary) || null;

    button.classList.toggle(
      'connected',
      Boolean(primary && primary.status === 'CONNECTED')
    );
    button.classList.toggle(
      'connecting',
      Boolean(primary && primary.status === 'CONNECTING')
    );

    if (!window.printerManager) {
      label.textContent = 'Printer tidak tersedia';
    } else if (!printers.length) {
      label.textContent = 'Printer belum diatur';
    } else if (!primary) {
      label.textContent = 'Printer: pilih printer utama';
    } else {
      label.textContent = 'Printer: ' + primary.name;
    }

    button.title = primary
      ? 'Printer utama: ' +
        primary.name +
        ' (' +
        printerTargetLabel(primary) +
        ', ' +
        primary.paper_width +
        ' mm). Buka pengaturan printer.'
      : 'Atur printer di pengaturan.';
  }

  async function loadPrinterSettings(force) {
    const manager = window.printerManager;
    if (!manager) return null;
    try {
      const snapshot = await manager.load(force === true);
      renderPrinterSettings(snapshot);
      renderPrinterToolbar(snapshot);
      return snapshot;
    } catch (err) {
      if (err && err.status === 401) return null;
      showPrinterWarning('Pengaturan printer gagal dimuat. Coba muat ulang.');
      return null;
    }
  }

  function showPrinterWarning(message) {
    const box = $('#printerWarning');
    if (!box) return;
    box.textContent = message || '';
    box.classList.toggle('hidden', !message);
  }

  async function refreshPrinterStatuses() {
    const manager = window.printerManager;
    if (!manager) return;
    const snapshot = manager.snapshot();
    for (const printer of snapshot.printers) {
      if (printer.supported === false) continue;
      try {
        await manager.refreshStatus(printer.id);
      } catch (err) {
        /* Status satu printer tidak boleh menghentikan printer lain. */
      }
    }
  }

  function initPrinterSettings() {
    bindPrinterSettingsEvents();
    return loadPrinterSettings(true).then((snapshot) => {
      if (snapshot) return refreshPrinterStatuses();
      return null;
    });
  }

  function bindPrinterSettingsEvents() {
    if (state.printerSettingsBound) return;
    state.printerSettingsBound = true;

    const addButton = $('#btnAddPrinter');
    if (addButton) {
      addButton.addEventListener('click', () => openPrinterModal(null));
    }
    const list = $('#printerList');
    if (list) list.addEventListener('click', handlePrinterListClick);
    const form = $('#printerForm');
    if (form) form.addEventListener('submit', handlePrinterSubmit);
    const cancel = $('#printerCancel');
    if (cancel) cancel.addEventListener('click', () => closeModal('#printerModal'));
    const modalClose = $('#printerModalClose');
    if (modalClose) {
      modalClose.addEventListener('click', () => closeModal('#printerModal'));
    }
    const typeSelect = $('#printerConnectionType');
    if (typeSelect) {
      typeSelect.addEventListener('change', () => syncPrinterFormType());
    }
    const discover = $('#btnPrinterDiscover');
    if (discover) discover.addEventListener('click', handlePrinterDiscover);
    const results = $('#printerDiscoveryResults');
    if (results) results.addEventListener('click', handlePrinterDiscoveryPick);

    const pickerClose = $('#printerPickerClose');
    if (pickerClose) {
      pickerClose.addEventListener('click', () => closeModal('#printerPickerModal'));
    }
    const pickerDismiss = $('#printerPickerDismiss');
    if (pickerDismiss) {
      pickerDismiss.addEventListener('click', () => closeModal('#printerPickerModal'));
    }
    const pickerList = $('#printerPickerList');
    if (pickerList) pickerList.addEventListener('click', handlePrinterPickerClick);

    const choose = $('#btnReceiptChoosePrinter');
    if (choose) choose.addEventListener('click', openPrinterPicker);
    const chooseOther = $('#btnReceiptChooseOther');
    if (chooseOther) chooseOther.addEventListener('click', openPrinterPicker);
    const printButton = $('#btnReceiptPrint');
    if (printButton) {
      printButton.addEventListener('click', () => {
        if (state.receipt) printReceipt(state.receipt, false);
      });
    }
    const retry = $('#btnReceiptRetry');
    if (retry) retry.addEventListener('click', retryFailedPrint);
    const settings = $('#btnReceiptOpenSettings');
    if (settings) settings.addEventListener('click', openPrinterSettingsFromReceipt);

    const toolbar = $('#printerBtn');
    if (toolbar) toolbar.addEventListener('click', handlePrinterToolbarClick);

    const manager = window.printerManager;
    if (manager) {
      manager.onChange((snapshot) => {
        renderPrinterToolbar(snapshot);
        renderPrinterSettings(snapshot);
        if (state.receipt) refreshReceiptPrinterUI();
      });
    }
    renderPrinterToolbar();
  }

  function handlePrinterToolbarClick() {
    closeAllModals();
    navigate('settings');
    const card = $('#printerSettingsCard');
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderPrinterSettings(snapshot) {
    const list = $('#printerList');
    if (!list) return;
    const manager = window.printerManager;
    const data =
      snapshot || (manager ? manager.snapshot() : { printers: [] });
    const printers = data.printers || [];
    const summary = $('#printerSummary');
    const empty = $('#printerEmpty');
    const warning = data.warning || data.storage_warning || '';

    showPrinterWarning(warning);

    if (summary) {
      if (!printers.length) {
        summary.textContent = 'Belum ada printer tersimpan.';
      } else {
        const primary = printers.find((item) => item.is_primary);
        summary.textContent =
          printers.length +
          ' printer tersimpan' +
          (primary ? ' · Utama: ' + primary.name : ' · Belum ada printer utama');
      }
    }

    if (!printers.length) {
      list.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');

    const busy = state.printerActionId;
    list.innerHTML = printers
      .map((printer) => {
        const badge = printerStatusLabel(printer);
        const disabled =
          printer.supported === false ||
          printer.status === 'CONNECTING' ||
          Boolean(busy);
        const connectionless = Boolean(
          manager &&
            manager.adapterFor(printer.connection_type) &&
            manager.adapterFor(printer.connection_type).connectionless
        );
        const actions = [];

        if (!connectionless) {
          if (printer.status === 'CONNECTED') {
            actions.push(
              '<button type="button" class="btn btn-outline btn-sm" ' +
                'data-printer-action="disconnect" data-printer-id="' +
                esc(printer.id) +
                '"' +
                (disabled ? ' disabled' : '') +
                '>Putuskan</button>'
            );
          } else {
            actions.push(
              '<button type="button" class="btn btn-outline btn-sm" ' +
                'data-printer-action="connect" data-printer-id="' +
                esc(printer.id) +
                '"' +
                (disabled ? ' disabled' : '') +
                '>Hubungkan</button>'
            );
          }
          actions.push(
            '<button type="button" class="btn btn-outline btn-sm" ' +
              'data-printer-action="reconnect" data-printer-id="' +
              esc(printer.id) +
              '"' +
              (disabled ? ' disabled' : '') +
              '>Hubungkan ulang</button>'
          );
        }

        actions.push(
          '<button type="button" class="btn btn-outline btn-sm" ' +
            'data-printer-action="primary" data-printer-id="' +
            esc(printer.id) +
            '"' +
            (printer.is_primary || disabled ? ' disabled' : '') +
            '>' +
            (printer.is_primary ? 'Printer utama' : 'Jadikan utama') +
            '</button>'
        );
        actions.push(
          '<button type="button" class="btn btn-outline btn-sm" ' +
            'data-printer-action="test" data-printer-id="' +
            esc(printer.id) +
            '"' +
            (disabled ? ' disabled' : '') +
            '>Tes cetak</button>'
        );
        actions.push(
          '<button type="button" class="btn btn-ghost btn-sm" ' +
            'data-printer-action="edit" data-printer-id="' +
            esc(printer.id) +
            '">Ubah</button>'
        );
        actions.push(
          '<button type="button" class="btn btn-danger btn-sm" ' +
            'data-printer-action="delete" data-printer-id="' +
            esc(printer.id) +
            '"' +
            (busy ? ' disabled' : '') +
            '>Hapus</button>'
        );

        const lastUsed = printer.connected_at
          ? (connectionless ? 'Terakhir dipakai: ' : 'Terakhir terhubung: ') +
            fmtDateTime(printer.connected_at)
          : 'Belum pernah ' +
            (connectionless ? 'dipakai' : 'terhubung');
        const metaParts = [
          printerTargetLabel(printer),
          printer.paper_width + ' mm',
          printerModeLabel(printer.print_mode),
          lastUsed,
        ];
        const errorText =
          printer.error || (printer.supported === false
            ? 'Jenis printer ini belum didukung di perangkat ini.'
            : '');

        return (
          '<div class="printer-row' +
          (printer.is_primary ? ' is-primary' : '') +
          (busy === printer.id ? ' is-busy' : '') +
          '">' +
          '<div class="printer-row-head">' +
          '<div class="printer-identity">' +
          '<strong>' +
          esc(printer.name) +
          '</strong>' +
          '<span class="printer-meta">' +
          esc(metaParts.join(' · ')) +
          '</span>' +
          (errorText
            ? '<span class="printer-error">' + esc(errorText) + '</span>'
            : '') +
          '</div>' +
          '<div class="printer-badges">' +
          (printer.is_primary ? '<span class="badge blue">Utama</span>' : '') +
          '<span class="badge gray">' +
          esc(printerTypeLabel(printer.connection_type)) +
          '</span>' +
          '<span class="badge ' +
          badge.tone +
          '">' +
          esc(badge.label) +
          '</span>' +
          '</div>' +
          '</div>' +
          '<div class="printer-actions">' +
          actions.join('') +
          '</div>' +
          '</div>'
        );
      })
      .join('');
  }

  async function handlePrinterListClick(event) {
    const button = event.target.closest('[data-printer-action]');
    if (!button) return;
    const id = button.dataset.printerId;
    const action = button.dataset.printerAction;
    const manager = window.printerManager;
    if (!manager || !id) return;

    if (action === 'edit') {
      openPrinterModal(id);
      return;
    }
    if (action === 'delete') {
      const printer = manager.printerSnapshot(id);
      if (!printer) return;
      const ok = window.confirm(
        'Hapus printer "' +
          printer.name +
          '" dari daftar? Data transaksi, pelanggan, dan stok tidak dihapus.'
      );
      if (!ok) return;
    }
    if (action === 'primary') {
      const printer = manager.printerSnapshot(id);
      if (!printer || printer.is_primary) return;
      if (state.printerActionId) return;
      state.printerActionId = id;
      renderPrinterSettings();
      try {
        await manager.selectPrimary(id, { allowDisconnected: true });
        toast(
          'Printer utama diganti ke ' +
            printer.name +
            '. Printer sebelumnya tetap tersimpan.',
          'success'
        );
      } catch (err) {
        toast(err.message, 'error', 7000);
      } finally {
        state.printerActionId = null;
        renderPrinterSettings();
      }
      return;
    }

    if (state.printerActionId) return;
    state.printerActionId = id;
    renderPrinterSettings();

    try {
      if (action === 'connect') {
        await manager.connect(id);
        toast('Printer berhasil terhubung.', 'success');
      } else if (action === 'disconnect') {
        const result = await manager.disconnect(id);
        if (result && result.warning) {
          toast(
            'Koneksi printer diputus. Printer tetap tersimpan. ' +
              result.warning,
            'warning',
            7000
          );
        } else {
          toast(
            'Koneksi printer diputus. Printer tetap tersimpan.',
            'info'
          );
        }
      } else if (action === 'reconnect') {
        await manager.reconnect(id);
        toast('Printer berhasil dihubungkan ulang.', 'success');
      } else if (action === 'test') {
        const printer = manager.printerSnapshot(id);
        const result = await manager.testPrint(id);
        const adapterResult = result && result.adapter_result;
        if (
          printer &&
          printer.connection_type === 'SYSTEM' &&
          adapterResult &&
          adapterResult.job_id != null
        ) {
          toast(
            'Dialog Android dibuka untuk tes cetak. Status: ' +
              describeJobState({ state: 'QUEUED' }) +
              '.',
            'info',
            7000
          );
          pollPrinterJobStatus(
            manager.adapterFor('SYSTEM'),
            adapterResult.job_id,
            printer.name
          );
        } else if (printer && printer.connection_type === 'WEB') {
          toast('Dialog cetak browser dibuka.', 'info', 6000);
        } else {
          toast('Tes cetak dikirim ke ' + (printer ? printer.name : 'printer') + '.', 'success');
        }
      } else if (action === 'delete') {
        const printer = manager.printerSnapshot(id);
        await manager.removePrinter(id);
        toast(
          'Printer ' +
            (printer ? printer.name : '') +
            ' dihapus. Data transaksi tidak berubah.',
          'success'
        );
      }
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      state.printerActionId = null;
      renderPrinterSettings();
    }
  }

  function pollPrinterJobStatus(adapter, jobId, printerName) {
    if (!adapter || typeof adapter.jobStatus !== 'function') return;
    let attempts = 0;
    const tick = async () => {
      attempts += 1;
      let status;
      try {
        status = await adapter.jobStatus(jobId);
      } catch (err) {
        return;
      }
      const stateName = String((status && status.state) || 'UNKNOWN');
      if (stateName === 'COMPLETED') {
        toast('Cetak untuk ' + printerName + ' selesai.', 'success');
        return;
      }
      if (stateName === 'FAILED' || stateName === 'UNAVAILABLE') {
        toast('Pekerjaan cetak Android gagal. Periksa printer.', 'error', 7000);
        return;
      }
      if (stateName === 'CANCELLED') {
        toast('Pekerjaan cetak dibatalkan dari dialog Android.', 'info');
        return;
      }
      if (attempts < 80) setTimeout(tick, 1500);
    };
    setTimeout(tick, 1200);
  }

  function openPrinterModal(id) {
    const manager = window.printerManager;
    if (!manager) {
      toast('Fitur printer tidak tersedia di perangkat ini.', 'error');
      return;
    }
    const printer = id ? manager.printerSnapshot(id) : null;
    const isEdit = Boolean(printer);
    state.printerDiscovery = [];
    state.printerDiscoveryType = null;
    const results = $('#printerDiscoveryResults');
    if (results) {
      results.innerHTML = '';
      results.classList.add('hidden');
    }

    const typeSelect = $('#printerConnectionType');
    if (!typeSelect) return;
    syncPrinterTypeOptions(isEdit ? printer.connection_type : null);

    $('#printerId').value = isEdit ? printer.id : '';
    $('#printerName').value = isEdit ? printer.name : '';
    typeSelect.value = isEdit
      ? printer.connection_type
      : firstSupportedPrinterType();
    const width = isEdit ? printer.paper_width : preferredReceiptWidth();
    $('#printerPaperWidth').value = String(width === 80 ? 80 : 58);
    $('#printerEncoding').value = isEdit ? printer.encoding : 'CP437';
    $('#printerAddress').value =
      isEdit && printer.connection_type === 'BLUETOOTH' ? printer.address : '';
    $('#printerIp').value =
      isEdit && printer.connection_type === 'NETWORK' ? printer.ip : '';
    $('#printerPort').value = String(
      isEdit && printer.connection_type === 'NETWORK' ? printer.port : 9100
    );
    $('#printerUsbIdentity').value =
      isEdit && printer.connection_type === 'USB' ? printer.address : '';

    const makePrimary = $('#printerMakePrimary');
    makePrimary.checked = isEdit
      ? printer.is_primary
      : manager.snapshot().printers.length === 0;

    $('#printerModalTitle').textContent = isEdit
      ? 'Ubah printer'
      : 'Tambah printer';
    $('#printerModalSubtitle').textContent = isEdit
      ? 'Perubahan alamat atau jenis koneksi akan memutus sesi printer ini.'
      : 'Simpan perangkat sekali, lalu sambungkan saat dibutuhkan.';
    const submit = $('#printerSubmit');
    if (submit) submit.textContent = isEdit ? 'Simpan perubahan' : 'Simpan printer';

    syncPrinterFormType(isEdit ? printer.print_mode : null);
    openModal('#printerModal');
  }

  function firstSupportedPrinterType() {
    const manager = window.printerManager;
    const order = ['BLUETOOTH', 'NETWORK', 'USB', 'SYSTEM', 'WEB'];
    if (!manager) return 'WEB';
    const found = order.find((type) => manager.adapterFor(type));
    return found || 'WEB';
  }

  function syncPrinterTypeOptions(preferredType) {
    const select = $('#printerConnectionType');
    if (!select) return;
    const manager = window.printerManager;
    const selected = preferredType || select.value;
    Array.from(select.options).forEach((option) => {
      const type = option.value;
      const supported = Boolean(manager && manager.adapterFor(type));
      option.disabled = !supported && type !== selected;
      option.textContent =
        PRINTER_TYPE_LABELS[type] + (supported ? '' : ' (tidak tersedia)');
    });
    if (selected) select.value = selected;
  }

  function syncPrinterFormType(preferredMode) {
    const typeSelect = $('#printerConnectionType');
    if (!typeSelect) return;
    const type = typeSelect.value;
    const manager = window.printerManager;
    const supported = Boolean(manager && manager.adapterFor(type));

    const toggle = (selector, visible) => {
      const element = $(selector);
      if (element) element.classList.toggle('hidden', !visible);
    };
    toggle('#printerBluetoothFields', type === 'BLUETOOTH');
    toggle('#printerNetworkFields', type === 'NETWORK');
    toggle('#printerUsbFields', type === 'USB');
    toggle('#printerSystemInfo', type === 'SYSTEM');
    toggle('#printerWebInfo', type === 'WEB');
    toggle(
      '#printerDiscoveryRow',
      type === 'BLUETOOTH' || type === 'NETWORK' || type === 'USB'
    );

    const supportedText = $('#printerSupportedText');
    if (supportedText) {
      supportedText.textContent = supported
        ? 'Tersedia di perangkat ini.'
        : 'Belum didukung di perangkat ini; konfigurasi tetap dapat disimpan.';
    }

    const modes = PRINTER_MODES[type] || [];
    const modeSelect = $('#printerPrintMode');
    if (modeSelect) {
      const current = preferredMode || modeSelect.value;
      modeSelect.innerHTML = modes
        .map(
          (mode) =>
            '<option value="' +
            esc(mode) +
            '">' +
            esc(printerModeLabel(mode)) +
            '</option>'
        )
        .join('');
      modeSelect.value = modes.includes(current)
        ? current
        : PRINTER_DEFAULT_MODES[type] || modes[0] || '';
    }

    const discover = $('#btnPrinterDiscover');
    const hint = $('#printerDiscoveryHint');
    if (discover) {
      discover.textContent =
        type === 'BLUETOOTH'
          ? 'Cari printer Bluetooth'
          : type === 'NETWORK'
            ? 'Cari printer jaringan'
            : 'Cari printer USB';
      discover.disabled = !supported;
    }
    if (hint) {
      hint.textContent =
        type === 'BLUETOOTH'
          ? 'Pastikan Bluetooth aktif dan printer siap dipasangkan.'
          : type === 'NETWORK'
            ? 'Pastikan printer dan perangkat berada di jaringan yang sama.'
            : 'Hubungkan kabel OTG lalu izinkan akses USB saat diminta.';
    }
  }

  async function handlePrinterDiscover() {
    const manager = window.printerManager;
    const type = $('#printerConnectionType').value;
    const button = $('#btnPrinterDiscover');
    const results = $('#printerDiscoveryResults');
    if (!manager || !results) return;
    if (!manager.adapterFor(type)) {
      toast('Pencarian printer ini tidak tersedia di perangkat.', 'warning');
      return;
    }
    setBusy(button, true, 'Mencari...');
    results.innerHTML = '';
    results.classList.remove('hidden');
    results.textContent = 'Mencari printer...';
    try {
      const devices = await manager.discover(type);
      state.printerDiscovery = devices;
      state.printerDiscoveryType = type;
      renderPrinterDiscovery(devices, type);
    } catch (err) {
      results.innerHTML =
        '<p class="tiny muted">' + esc(err.message) + '</p>';
    } finally {
      setBusy(button, false);
    }
  }

  function renderPrinterDiscovery(devices, type) {
    const results = $('#printerDiscoveryResults');
    if (!results) return;
    if (!devices.length) {
      results.innerHTML =
        '<p class="tiny muted">Tidak ada printer ditemukan. Masukkan data printer secara manual.</p>';
      return;
    }
    results.innerHTML = devices
      .map((device, index) => {
        let detail = '';
        if (type === 'BLUETOOTH') {
          detail =
            (device.address || '-') +
            (device.paired ? ' · sudah dipasangkan' : ' · belum dipasangkan');
        } else if (type === 'NETWORK') {
          detail = (device.ip || '-') + ':' + (device.port || '-');
        } else if (type === 'USB') {
          detail =
            (device.identity || device.address || '-') +
            (device.supported === false ? ' · tidak didukung' : '');
        }
        return (
          '<div class="printer-discovery-item">' +
          '<div><strong>' +
          esc(device.name || 'Printer') +
          '</strong><span class="tiny muted">' +
          esc(detail) +
          '</span></div>' +
          '<button type="button" class="btn btn-outline btn-sm" ' +
          'data-printer-discovery-index="' +
          index +
          '"' +
          (device.supported === false ? ' disabled' : '') +
          '>Gunakan</button>' +
          '</div>'
        );
      })
      .join('');
  }

  function handlePrinterDiscoveryPick(event) {
    const button = event.target.closest('[data-printer-discovery-index]');
    if (!button) return;
    const index = intValue(button.dataset.printerDiscoveryIndex, -1);
    const device = state.printerDiscovery[index];
    if (!device) return;
    const type = state.printerDiscoveryType;
    const nameInput = $('#printerName');
    if (nameInput && !nameInput.value.trim() && device.name) {
      nameInput.value = device.name;
    }
    if (type === 'BLUETOOTH') {
      $('#printerAddress').value = device.address || '';
    } else if (type === 'NETWORK') {
      $('#printerIp').value = device.ip || '';
      if (device.port) $('#printerPort').value = String(device.port);
    } else if (type === 'USB') {
      $('#printerUsbIdentity').value = device.identity || device.address || '';
    }
    const results = $('#printerDiscoveryResults');
    if (results) results.classList.add('hidden');
    toast('Data printer dimasukkan. Periksa lalu simpan.', 'info');
  }

  async function handlePrinterSubmit(event) {
    event.preventDefault();
    const manager = window.printerManager;
    if (!manager) return;
    const id = $('#printerId').value.trim();
    const isEdit = Boolean(id);
    const type = $('#printerConnectionType').value;
    const name = $('#printerName').value.trim();
    const paperWidth = intValue($('#printerPaperWidth').value, 58) === 80 ? 80 : 58;
    const printMode = $('#printerPrintMode').value;
    const encoding = $('#printerEncoding').value.trim() || 'CP437';
    const makePrimary = $('#printerMakePrimary').checked;

    if (!name) {
      toast('Nama printer wajib diisi.', 'warning');
      $('#printerName').focus();
      return;
    }

    const draft = {
      name: name,
      connection_type: type,
      paper_width: paperWidth,
      print_mode: printMode,
      encoding: encoding,
      address: '',
      ip: '',
      port: null,
    };

    if (type === 'BLUETOOTH') {
      const address = $('#printerAddress').value.trim().toUpperCase();
      if (!/^([0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(address)) {
        toast('Alamat Bluetooth harus berbentuk AA:BB:CC:DD:EE:FF.', 'warning');
        $('#printerAddress').focus();
        return;
      }
      draft.address = address;
    } else if (type === 'NETWORK') {
      const ip = $('#printerIp').value.trim();
      const port = intValue($('#printerPort').value, 0);
      if (!ip) {
        toast('Alamat IP printer wajib diisi.', 'warning');
        $('#printerIp').focus();
        return;
      }
      if (port < 1 || port > 65535) {
        toast('Port harus antara 1 dan 65535.', 'warning');
        $('#printerPort').focus();
        return;
      }
      draft.ip = ip;
      draft.port = port;
    } else if (type === 'USB') {
      const identity = $('#printerUsbIdentity').value.trim();
      if (!identity) {
        toast('Identitas perangkat USB wajib diisi.', 'warning');
        $('#printerUsbIdentity').focus();
        return;
      }
      draft.address = identity;
    }

    const submit = $('#printerSubmit');
    setBusy(submit, true, 'Menyimpan...');
    try {
      if (isEdit) {
        const updated = await manager.updatePrinter(id, draft);
        if (makePrimary && !updated.is_primary) {
          await manager.selectPrimary(id, { allowDisconnected: true });
        }
        toast('Perubahan printer disimpan.', 'success');
      } else {
        const created = await manager.addPrinter(draft, {
          makePrimary: makePrimary,
          allowDisconnected: true,
        });
        if (makePrimary && !created.is_primary) {
          await manager.selectPrimary(created.id, { allowDisconnected: true });
        }
        toast('Printer ' + created.name + ' disimpan.', 'success');
      }
      closeModal('#printerModal');
    } catch (err) {
      toast(err.message, 'error', 8000);
    } finally {
      setBusy(submit, false);
    }
  }

  async function openPrinterPicker() {
    const manager = window.printerManager;
    if (!manager) return;
    try {
      await manager.load();
    } catch (err) {
      toast('Gagal memuat daftar printer. Coba lagi.', 'error', 7000);
      return;
    }
    const snapshot = manager.snapshot();
    const list = $('#printerPickerList');
    if (!list) return;
    if (!snapshot.printers.length) {
      list.innerHTML =
        '<div class="empty-state sm">Belum ada printer tersimpan. ' +
        'Tambahkan printer di pengaturan.</div>';
    } else {
      list.innerHTML = snapshot.printers
        .map((printer) => {
          const badge = printerStatusLabel(printer);
          const selected = printer.id === state.printPrinterId;
          return (
            '<div class="printer-picker-item' +
            (selected ? ' is-selected' : '') +
            '">' +
            '<div><strong>' +
            esc(printer.name) +
            '</strong><span class="tiny muted">' +
            esc(
              printerTypeLabel(printer.connection_type) +
                ' · ' +
                printerTargetLabel(printer) +
                ' · ' +
                printer.paper_width +
                ' mm'
            ) +
            '</span></div>' +
            '<div class="printer-badges">' +
            (printer.is_primary ? '<span class="badge blue">Utama</span>' : '') +
            '<span class="badge ' +
            badge.tone +
            '">' +
            esc(badge.label) +
            '</span>' +
            '<button type="button" class="btn btn-outline btn-sm" ' +
            'data-printer-picker-id="' +
            esc(printer.id) +
            '"' +
            (printer.supported === false ? ' disabled' : '') +
            '>Pilih</button>' +
            '</div></div>'
          );
        })
        .join('');
    }
    openModal('#printerPickerModal');
  }

  function handlePrinterPickerClick(event) {
    const button = event.target.closest('[data-printer-picker-id]');
    if (!button) return;
    const manager = window.printerManager;
    const printer = manager
      ? manager.printerSnapshot(button.dataset.printerPickerId)
      : null;
    if (!printer) return;
    state.printPrinterId = printer.id;
    state.receiptWidth = normalizeReceiptWidth(printer.paper_width);
    window.localStorage.setItem(
      RECEIPT_WIDTH_KEY,
      String(state.receiptWidth)
    );
    syncReceiptWidthUI();
    renderReceiptPreview();
    refreshReceiptPrinterUI();
    state.printFailure = null;
    setReceiptPrintStatus(
      'info',
      'Printer tujuan: ' + printer.name + '. Tekan Cetak untuk mengirim struk.',
      {}
    );
    closeModal('#printerPickerModal');
  }

  function retryFailedPrint() {
    if (!state.printFailure || state.printing) return;
    const ok = window.confirm(
      'Cetak sebelumnya gagal dan sebagian struk mungkin sudah tercetak. ' +
        'Cetak ulang struk yang sama? Tidak ada transaksi baru yang dibuat.'
    );
    if (!ok) return;
    const failure = state.printFailure;
    if (failure.printerId) state.printPrinterId = failure.printerId;
    printReceipt(state.receipt || failure.receipt, false);
  }

  function openPrinterSettingsFromReceipt() {
    if (!$('#printerPickerModal').classList.contains('hidden')) {
      closeModal('#printerPickerModal');
    }
    if (!$('#receiptModal').classList.contains('hidden')) {
      closeModal('#receiptModal');
    }
    navigate('settings');
    const card = $('#printerSettingsCard');
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function initPrinter() {
    bindPrinterSettingsEvents();
    renderPrinterToolbar();
  }

  /* ------------------------------ Dashboard ------------------------------- */
  async function loadDashboard() {
    try {
      const employeeAktif =
        !state.config ||
        !state.config.ops ||
        state.config.ops.karyawan_aktif !== false;
      const results = await Promise.all([
        API.daily(todayISO()),
        employeeAktif ? API.payrollSummary(todayISO()) : Promise.resolve(null),
        API.soldParts(todayISO(), todayISO()),
      ]);
      const daily = results[0];
      state.payrollSummary = results[1];
      const soldToday = results[2];
      renderPayrollCard();

      state.dashboardToday = daily.transaksi || [];

      $('#statUnit').textContent = daily.jumlah_unit_servis;
      $('#statPartsOut').textContent = intValue(
        soldToday && soldToday.total_qty,
        0
      );
      $('#statCash').textContent = fmtRp(daily.total_cash);
      $('#statTransfer').textContent = fmtRp(daily.total_transfer);
      $('#statTotalDebt').textContent = fmtRp(daily.piutang_total || 0);
      $('#statTotalDebtSub').textContent =
        intValue(daily.piutang_count, 0) +
        ' nota · ' +
        intValue(daily.piutang_customers, 0) +
        ' pelanggan';
      $('#statEmployeeDebt').textContent = fmtRp(
        daily.piutang_karyawan_total || 0
      );
      $('#statEmployeeDebtSub').textContent =
        intValue(daily.piutang_karyawan_count, 0) + ' hutang berjalan';
      $('#statLowStock').textContent = intValue(daily.stok_menipis, 0);
      $('#statStockOut').textContent = intValue(daily.stok_habis, 0);
    } catch (err) {
      toast('Ringkasan hari ini gagal dimuat. Coba muat ulang.', 'error', 6000);
    }
  }

  function renderPayrollCard() {
    const card = $('#dashboardPayrollCard');
    if (!card) return;
    const data = state.payrollSummary;
    if (!data) {
      card.classList.add('hidden');
      $('#payrollAlert')?.classList.add('hidden');
      return;
    }
    card.classList.remove('hidden');
    $('#statPayroll').textContent = fmtRp(data.total_due || 0);
    const dueCount = intValue(data.due_count, 0);
    $('#statPayrollSub').textContent = dueCount
      ? dueCount +
        ' karyawan jatuh tempo · ' +
        fmtRp(data.due_total || 0)
      : intValue(data.count, 0)
        ? data.count +
          ' karyawan · berikutnya ' +
          (data.next_date ? fmtDate(data.next_date) : '-')
        : 'Tidak ada tagihan gaji';
    const alert = $('#payrollAlert');
    if (alert) {
      alert.classList.toggle('hidden', !dueCount);
      if (dueCount) {
        const names = (data.items || [])
          .filter(
            (row) =>
              Number(row.total_due) > 0 &&
              ['JATUH_TEMPO', 'SEGERA'].includes(row.status)
          )
          .map((row) => row.nama);
        $('#payrollAlertText').textContent =
          names.join(', ') +
          ' · total ' +
          fmtRp(data.due_total || 0) +
          '.';
      }
    }
  }

  function openPayrollModal() {
    const data = state.payrollSummary;
    if (!data) {
      toast('Data gaji belum dimuat.', 'warning');
      return;
    }
    const body = $('#payrollBody');
    const empty = $('#payrollEmpty');
    const items = data.items || [];
    $('#payrollModalSubtitle').textContent =
      'Total perlu dibayar ' +
      fmtRp(data.total_due || 0) +
      (data.next_date ? ' · berikutnya ' + fmtDate(data.next_date) : '');
    if (!items.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
    } else {
      if (empty) empty.classList.add('hidden');
      body.innerHTML = items
        .map((row) => {
          const due = Number(row.total_due) > 0;
          const debt = Number(row.debt_total) > 0;
          const payable = due && row.status === 'JATUH_TEMPO';
          let action;
          if (payable) {
            action =
              '<button type="button" class="btn btn-primary btn-xs" data-action="payroll-mark-paid" data-id="' +
              row.employee_id +
              '">Bayar</button>';
          } else {
            const notes = [];
            if (due) notes.push('Jadwal ' + fmtDate(row.next_date));
            if (debt) notes.push('Sisa hutang ' + fmtRp(row.debt_total));
            action =
              '<span class="cell-sub">' +
              (notes.length ? notes.join(' · ') : 'Lunas') +
              '</span>';
          }
          return (
            '<tr><td><span class="cell-primary">' +
            esc(row.nama) +
            '</span></td>' +
            '<td class="text-right"><strong>' +
            fmtRp(row.total_due) +
            '</strong></td>' +
            '<td class="row-actions">' +
            action +
            '</td></tr>'
          );
        })
        .join('');
    }
    openModal('#payrollModal');
  }

  function openPayrollPayModal(item) {
    state.payrollPayItem = item;
    $('#payrollPayTitle').textContent = 'Bayar ' + item.nama;
    $('#payrollPaySubtitle').textContent =
      'Pilih cara pembayaran gaji dan komisi.';
    const hasDebt = Number(item.debt_total) > 0;
    $('#payrollCicilToggle')?.classList.toggle('hidden', !hasDebt);
    $('#payrollFullDebtToggle')?.classList.toggle('hidden', !hasDebt);
    if ($('#payrollCicilAktif')) $('#payrollCicilAktif').checked = false;
    if ($('#payrollFullDebtAktif')) $('#payrollFullDebtAktif').checked = false;
    $('#payrollCicilRow')?.classList.add('hidden');
    if ($('#payrollCicilNominal')) $('#payrollCicilNominal').value = '';
    if ($('#payrollBonusAktif')) $('#payrollBonusAktif').checked = false;
    $('#payrollBonusRow')?.classList.add('hidden');
    if ($('#payrollBonusNominal')) $('#payrollBonusNominal').value = '';
    if ($('#payrollBonusKeterangan')) $('#payrollBonusKeterangan').value = '';
    renderPayrollPaySummary();
    openModal('#payrollPayModal');
  }

  function payrollPayValues() {
    const item = state.payrollPayItem || {};
    const gross = Number(item.gross_due || 0);
    const fullDebt = Boolean($('#payrollFullDebtAktif')?.checked);
    let potongan = 0;
    if (fullDebt) {
      potongan = Number(item.debt_used || 0);
    } else if ($('#payrollCicilAktif')?.checked) {
      potongan = Number($('#payrollCicilNominal').value || 0);
    }
    const bonus = $('#payrollBonusAktif')?.checked
      ? Number($('#payrollBonusNominal').value || 0)
      : 0;
    return {
      gross,
      potongan,
      bonus,
      fullDebt,
      nominal: Math.max(0, gross - potongan + bonus),
    };
  }

  function renderPayrollPaySummary() {
    const values = payrollPayValues();
    const item = state.payrollPayItem || {};
    $('#payrollPayGross').textContent = fmtRp(values.gross);
    const debtTotal = Number(item.debt_total || 0);
    const debtTotalRow = $('#payrollPayDebtTotalRow');
    if (debtTotalRow) {
      debtTotalRow.classList.toggle('hidden', debtTotal <= 0);
      $('#payrollPayDebtTotal').textContent = fmtRp(debtTotal);
    }
    const debtRow = $('#payrollPayDebtRow');
    if (debtRow) {
      debtRow.classList.toggle('hidden', values.potongan <= 0);
      $('#payrollPayDebtLabel').textContent = values.fullDebt
        ? 'Full bayar hutang'
        : 'Cicil hutang';
      $('#payrollPayDebt').textContent = fmtRp(values.potongan);
    }
    const bonusRow = $('#payrollPayBonusRow');
    if (bonusRow) {
      bonusRow.classList.toggle(
        'hidden',
        !$('#payrollBonusAktif')?.checked
      );
      $('#payrollPayBonus').textContent = fmtRp(values.bonus);
    }
    $('#payrollPayNet').textContent = fmtRp(values.nominal);
  }

  function submitPayrollPayment() {
    const item = state.payrollPayItem;
    if (!item) return;
    let bonus = 0;
    let bonusKeterangan = '';
    if ($('#payrollBonusAktif')?.checked) {
      bonus = Number($('#payrollBonusNominal').value || 0);
      bonusKeterangan = $('#payrollBonusKeterangan').value.trim();
      if (bonus <= 0) {
        toast('Isi nominal bonus lebih dari 0.', 'warning');
        $('#payrollBonusNominal').focus();
        return;
      }
      if (!bonusKeterangan) {
        toast('Isi keterangan bonus.', 'warning');
        $('#payrollBonusKeterangan').focus();
        return;
      }
    }
    const gross = Number(item.gross_due || 0);
    const debtUsed = Number(item.debt_used || 0);
    const debtTotal = Number(item.debt_total || 0);
    let potongan = 0;
    let fullDebt = false;
    if ($('#payrollFullDebtAktif')?.checked) {
      potongan = debtUsed;
      fullDebt = true;
    } else if ($('#payrollCicilAktif')?.checked) {
      potongan = Number($('#payrollCicilNominal').value || 0);
      if (potongan <= 0) {
        toast('Isi nominal cicilan hutang lebih dari 0.', 'warning');
        $('#payrollCicilNominal').focus();
        return;
      }
      if (potongan > debtTotal) {
        toast('Cicilan melebihi sisa hutang karyawan.', 'warning');
        return;
      }
      if (potongan > gross) {
        toast('Cicilan melebihi gaji dan komisi.', 'warning');
        return;
      }
    }
    const nominal = gross - potongan + bonus;
    if (nominal <= 0) {
      toast('Tidak ada nominal yang perlu dibayar.', 'warning');
      return;
    }
    const catatan =
      (fullDebt
        ? 'Gaji dipotong hutang penuh'
        : potongan > 0
          ? 'Gaji penuh · cicil hutang ' + fmtRp(potongan)
          : 'Gaji penuh') +
      (bonus > 0
        ? ' · bonus ' + fmtRp(bonus) + ' (' + bonusKeterangan + ')'
        : '');
    openSalaryModal({
      employee_id: item.employee_id,
      nama_karyawan: item.nama,
      periode: String(item.cycle_start || todayISO()).slice(0, 7),
      tanggal: todayISO(),
      nominal,
      potongan_hutang: potongan,
      bonus,
      bonus_keterangan: bonusKeterangan,
      cicilan_hutang: 0,
      metode: 'CASH',
      catatan,
      bank_nama: item.bank_nama || '',
      bank_nomor: item.bank_nomor || '',
      bank_atas_nama: item.bank_atas_nama || '',
      nomor_hp: item.nomor_hp || '',
    });
  }

  /* ------------------------------- History -------------------------------- */
  async function loadHistory(query) {
    try {
      state.history = await API.records(query || '');
      renderHistory();
    } catch (err) {
      toast('Riwayat servis gagal dimuat. Coba muat ulang.', 'error', 6000);
    }
  }

  function renderHistory() {
    const body = $('#historyBody');
    if (!body) return;

    $('#historyCount').textContent = state.history.length + ' nota';

    if (!state.history.length) {
      body.innerHTML = '';
      $('#historyEmpty').classList.remove('hidden');
      return;
    }

    $('#historyEmpty').classList.add('hidden');
    body.innerHTML = state.history
      .map((record) => {
        const claimable =
          record.status !== 'VOID' &&
          record.bergaransi &&
          record.status_klaim !== 'Sudah claim';
        return (
          '<tr class="is-clickable" data-action="record-detail" data-id="' +
          record.id +
          '">' +
          '<td>' +
          esc(fmtDateTime(record.waktu_service)) +
          '</td>' +
          '<td><button type="button" class="cell-link" data-action="record-detail" data-id="' +
          record.id +
          '">' +
          esc(record.no_nota) +
          '</button>' +
          statusBadge(record) +
          '</td>' +
          '<td><button type="button" class="cell-link" data-action="customer-detail" data-id="' +
          record.customer_id +
          '">' +
          esc(record.customer_nama) +
          '</button><span class="cell-sub">' +
          esc(record.customer_hp) +
          '</span></td>' +
          '<td><span class="cell-primary">' +
          esc(record.unit_deskripsi) +
          '</span><span class="cell-sub">' +
          esc((record.keluhan_awal || '').slice(0, 56)) +
          '</span></td>' +
          '<td class="text-right money">' +
          fmtRp(netTotal(record)) +
          (Number(record.total_retur) > 0
            ? '<span class="cell-sub">Retur -' +
              fmtRp(record.total_retur) +
              '</span>'
            : '') +
          '</td>' +
          '<td>' +
          metodeBadge(record.metode_bayar) +
          paymentBadge(record) +
          '</td>' +
          '<td>' +
          warrantyBadge(record) +
          '</td>' +
          '<td>' +
          (Number(record.retur_count) > 0
            ? '<span class="badge amber">Retur/Ganti</span>' +
              '<span class="cell-sub">' +
              fmtRp(record.total_retur) +
              '</span>'
            : '-') +
          '</td>' +
          '<td class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="reprint" data-id="' +
          record.id +
          '">Cetak ulang</button>' +
          (claimable
            ? '<button type="button" class="btn btn-ghost btn-xs" data-action="claim" data-id="' +
              record.id +
              '">Klaim</button>'
            : '') +
          '</td>' +
          '</tr>'
        );
      })
      .join('');
  }

  /* --------------------------- Detail & drilldown ------------------------- */
  function findRecordByCustomerId(customerId) {
    const lists = [
      state.history,
      state.reportRows,
      state.dashboardToday,
      state.notaList,
    ];
    for (let i = 0; i < lists.length; i += 1) {
      const found = (lists[i] || []).find(
        (record) => record.customer_id === customerId
      );
      if (found) return found;
    }
    return null;
  }

  function openNotaList(title, records, options) {
    const list = records || [];
    const opts = options || {};
    state.notaList = list;

    const totals = list.reduce(
      (acc, record) => {
        acc.omsetCents += moneyToCents(netTotal(record));
        acc.profitCents += moneyToCents(record.laba_kotor);
        return acc;
      },
      { omsetCents: 0, profitCents: 0 }
    );

    $('#notaListTitle').textContent = title;
    const meta = [list.length + ' nota', 'total ' + centsToRp(totals.omsetCents)];
    if (opts.note) meta.push(opts.note);
    if (opts.showProfit) {
      meta.push('laba bersih ' + centsToRp(totals.profitCents));
    }
    $('#notaListSubtitle').textContent = meta.join(' · ');

    const body = $('#notaListBody');
    if (!list.length) {
      body.innerHTML = '';
      $('#notaListEmpty').classList.remove('hidden');
    } else {
      $('#notaListEmpty').classList.add('hidden');
      body.innerHTML = list
        .map(
          (record) =>
            '<tr class="is-clickable" data-action="record-detail" data-id="' +
            record.id +
            '">' +
            '<td>' +
            esc(fmtDateTime(record.waktu_service)) +
            '</td>' +
            '<td><button type="button" class="cell-link" data-action="record-detail" data-id="' +
            record.id +
            '">' +
            esc(record.no_nota) +
            '</button>' +
            statusBadge(record) +
            '</td>' +
            '<td><button type="button" class="cell-link" data-action="customer-detail" data-id="' +
            record.customer_id +
            '">' +
            esc(record.customer_nama) +
            '</button><span class="cell-sub">' +
            esc(record.customer_hp) +
            '</span></td>' +
            '<td class="text-right money">' +
            fmtRp(netTotal(record)) +
            (Number(record.total_retur) > 0
              ? '<span class="cell-sub">Retur -' +
                fmtRp(record.total_retur) +
                '</span>'
              : '') +
            (opts.showProfit
              ? '<span class="cell-sub">Laba ' +
                fmtRp(record.laba_kotor) +
                (record.modal_tidak_diketahui ? ' · modal belum diisi' : '') +
                (record.modal_estimasi ? ' · modal estimasi' : '') +
                '</span>'
              : '') +
            '</td>' +
            '<td>' +
            metodeBadge(record.metode_bayar) +
            paymentBadge(record) +
            '</td>' +
            '</tr>'
        )
        .join('');
    }

    openModal('#notaListModal');
  }

  function detailItem(label, valueHtml) {
    return (
      '<div class="detail-item"><span class="detail-label">' +
      esc(label) +
      '</span><div class="detail-value">' +
      valueHtml +
      '</div></div>'
    );
  }

  function qtyCell(item) {
    const returned = intValue(item.jumlah_retur, 0);
    return (
      intValue(item.jumlah, 0) +
      (returned > 0
        ? '<span class="cell-sub">retur ' + returned + '</span>'
        : '')
    );
  }

  function returnHistoryHtml(returns) {
    if (!returns.length) return '';
    const entries = returns
      .map((retur) => {
        const items = (retur.items || [])
          .map(
            (item) =>
              '<div class="cell-sub">' +
              esc(item.nama_item) +
              ' x' +
              intValue(item.jumlah, 0) +
              ' · ' +
              fmtRp(item.subtotal) +
              '</div>'
          )
          .join('');
        return (
          '<div class="return-entry"><div class="return-entry-head"><strong>' +
          fmtRp(retur.total_nilai) +
          '</strong><span class="cell-sub">' +
          esc(fmtDateTime(retur.created_at)) +
          ' · ' +
          esc(retur.oleh || '-') +
          '</span></div>' +
          '<div class="detail-text">' +
          esc(retur.alasan) +
          '</div>' +
          items +
          (retur.ganti_nama
            ? '<div class="cell-sub">Diganti dengan: ' +
              esc(retur.ganti_nama) +
              ' x' +
              intValue(retur.ganti_jumlah, 0) +
              '</div>'
            : '') +
          '</div>'
        );
      })
      .join('');
    return (
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Riwayat retur / tukar (' +
      returns.length +
      ')</h4>' +
      '<div class="return-history">' +
      entries +
      '</div></div>'
    );
  }

  function paymentSectionHtml(receipt) {
    if (receipt.status === 'VOID') return '';
    const payments = state.detailPayments || [];
    const rows = payments
      .map((payment) => {
        const label =
          payment.jenis === 'TUKAR_TAMBAHAN'
            ? 'Tambahan tukar'
            : payment.jenis === 'REFUND'
              ? 'Kembalian / refund'
              : payment.jenis || 'Pembayaran';
        return (
          '<div class="payment-row"><div><small>' +
          esc(fmtDateTime(payment.waktu)) +
          ' · ' +
          esc(payment.operator || '-') +
          '</small><div>' +
          esc(label) +
          ' · ' +
          esc(payment.metode || '-') +
          (payment.catatan ? ' · ' + esc(payment.catatan) : '') +
          '</div></div><strong>' +
          fmtRp(payment.nominal) +
          '</strong></div>'
        );
      })
      .join('');
    const sisa = moneyToCents(receipt.sisa_bayar);
    const canPay = receipt.status_bayar === 'BELUM_LUNAS' && sisa > 0;
    const form = canPay
      ? '<div class="payment-form">' +
        '<label class="switch-row"><span>Kredit (bayar sebagian)</span>' +
        '<input type="checkbox" id="paymentKreditAktif"' +
        (receipt.jenis_bayar === 'KREDIT' ? ' checked' : '') +
        '><span class="switch-ui" aria-hidden="true"></span></label>' +
        '<p class="tiny muted" id="paymentKreditHint">' +
        (receipt.jenis_bayar === 'KREDIT'
          ? 'Kredit aktif: boleh membayar sebagian, sisa tetap di Piutang.'
          : 'Kredit nonaktif: pembayaran harus penuh.') +
        '</p>' +
        '<div class="form-grid">' +
        '<label class="field"><span>Nominal pembayaran</span>' +
        '<input type="text" class="input money-input" id="paymentNominal" inputmode="numeric" placeholder="0"></label>' +
        '<label class="field"><span>Metode</span>' +
        '<select class="input" id="paymentMetode">' +
        '<option value="CASH">Tunai</option>' +
        '<option value="TRANSFER">Transfer</option>' +
        '</select></label>' +
        '</div>' +
        '<label class="field"><span>Catatan (opsional)</span>' +
        '<input type="text" class="input" id="paymentCatatan" maxlength="500" placeholder="Contoh: pelunasan transfer"></label>' +
        '<div class="payment-form-actions">' +
        '<button type="button" class="btn btn-ghost btn-sm' +
        (receipt.jenis_bayar === 'KREDIT' ? '' : ' hidden') +
        '" id="paymentSetengahBtn" data-action="payment-fill-setengah">Setengah</button>' +
        '<button type="button" class="btn btn-ghost btn-sm" data-action="payment-fill-sisa">Isi sisa</button>' +
        '<button type="button" class="btn btn-primary btn-sm" data-action="payment-submit" data-id="' +
        receipt.id +
        '">Catat pembayaran</button>' +
        '</div></div>'
      : '';
    return (
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Pembayaran</h4>' +
      '<div class="detail-grid">' +
      detailItem('Status bayar', paymentBadge(receipt) || '-') +
      detailItem('Total dibayar', fmtRp(receipt.total_dibayar)) +
      detailItem('Sisa bayar', fmtRp(receipt.sisa_bayar)) +
      detailItem(
        'Jatuh tempo',
        esc(receipt.jatuh_tempo ? fmtDate(receipt.jatuh_tempo) : '-')
      ) +
      (Number(receipt.rencana_bayar) > 0
        ? detailItem('Rencana pembayaran', fmtRp(receipt.rencana_bayar))
        : '') +
      '</div>' +
      (payments.length
        ? '<div class="payment-list">' + rows + '</div>'
        : '<div class="empty-state sm">Belum ada pembayaran tercatat.</div>') +
      form +
      '</div>'
    );
  }


  function recordPengerjaanSection(receipt) {
    if (!receipt || (receipt.status || 'NORMAL') === 'VOID') return '';
    const marker = state.detailPengerjaan;
    if (marker) {
      const closed = marker.status_pengerjaan === 'SUDAH_DIAMBIL';
      return (
        '<div class="detail-section">' +
        '<h4 class="detail-section-title">Pengerjaan unit</h4>' +
        '<p class="detail-text">Status: <strong>' +
        esc(PENGERJAAN_STATUS_LABELS[marker.status_pengerjaan] || marker.status_pengerjaan) +
        '</strong> · ' +
        intValue(marker.hari_di_bengkel, 0) +
        ' hari di bengkel</p>' +
        (closed
          ? ''
          : '<button type="button" class="btn btn-outline btn-sm" data-action="pengerjaan-status" data-id="' +
            marker.id +
            '">Ubah status pengerjaan</button>') +
        '</div>'
      );
    }
    return (
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Pengerjaan unit</h4>' +
      '<p class="detail-text">Unit belum ditandai masih di bengkel.</p>' +
      '<button type="button" class="btn btn-outline btn-sm" data-action="record-mark-workshop" data-id="' +
      receipt.id +
      '">Tandai unit di bengkel</button>' +
      '</div>'
    );
  }

  function renderRecordDetail(receipt) {
    const jobs = receipt.jobs || [];
    const parts = receipt.parts || [];
    const isVoid = receipt.status === 'VOID';
    const jobsHtml = jobs.length
      ? jobs
          .map(
            (job) =>
              '<tr><td>' +
              esc(job.deskripsi) +
              '</td><td class="text-center">' +
              qtyCell(job) +
              '</td><td class="text-right money">' +
              fmtRp(job.harga) +
              '</td><td class="text-right money">' +
              fmtRp(job.subtotal) +
              '</td></tr>'
          )
          .join('')
      : '<tr><td colspan="4" class="muted">Tidak ada rincian jasa.</td></tr>';
    const partsHtml = parts.length
      ? parts
          .map(
            (part) =>
              '<tr><td>' +
              esc(part.nama_part) +
              '</td><td class="text-center">' +
              qtyCell(part) +
              '</td><td class="text-right money">' +
              fmtRp(part.harga_satuan) +
              '</td><td class="text-right money">' +
              fmtRp(part.subtotal) +
              '</td></tr>'
          )
          .join('')
      : '<tr><td colspan="4" class="muted">Tidak ada sparepart.</td></tr>';

    const voidBanner = isVoid
      ? '<div class="void-banner"><strong>Nota dibatalkan</strong>' +
        '<span>' +
        esc(receipt.void_reason || '-') +
        '</span><span class="cell-sub">' +
        esc(fmtDateTime(receipt.voided_at)) +
        ' · ' +
        esc(receipt.voided_by || '-') +
        '</span></div>'
      : '';

    const returTotal =
      '<div class="detail-total-row is-grand"><span>Total servis</span><strong>' +
      fmtRp(receipt.total_servis) +
      '</strong></div>' +
      (Number(receipt.total_retur) > 0
        ? '<div class="detail-total-row"><span>Retur</span><strong>-' +
          fmtRp(receipt.total_retur) +
          '</strong></div>' +
          '<div class="detail-total-row is-grand"><span>Total neto</span><strong>' +
          fmtRp(netTotal(receipt)) +
          '</strong></div>'
        : '');

    $('#recordTitle').textContent = 'Nota ' + receipt.no_nota;
    $('#recordSubtitle').textContent =
      receipt.customer_nama + ' · ' + receipt.unit_deskripsi;

    $('#recordDetail').innerHTML =
      voidBanner +
      '<div class="detail-grid">' +
      detailItem('Waktu servis', esc(fmtDateTime(receipt.waktu_service))) +
      detailItem('Metode bayar', metodeBadge(receipt.metode_bayar)) +
      (receipt.sparepart_only
        ? detailItem(
            'Garansi tukar',
            esc(
              receipt.garansi_tukar_aktif
                ? receipt.garansi_tukar_hari + ' hari'
                : 'Tidak aktif'
            )
          ) +
          detailItem(
            'Garansi barang',
            esc(
              receipt.garansi_barang_aktif
                ? receipt.garansi_barang_nilai +
                    ' ' +
                    (receipt.garansi_barang_satuan === 'BULAN'
                      ? 'bulan'
                      : 'hari') +
                    (receipt.garansi_barang_sampai
                      ? ' · sampai ' + fmtDate(receipt.garansi_barang_sampai)
                      : '')
                : 'Tidak aktif'
            )
          )
        : detailItem('Status garansi', warrantyBadge(receipt)) +
          detailItem(
            'Garansi sampai',
            esc(receipt.garansi_sampai ? fmtDate(receipt.garansi_sampai) : '-')
          )) +
      '</div>' +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Pelanggan &amp; unit</h4>' +
      '<p class="detail-text"><strong>' +
      esc(receipt.customer_nama) +
      '</strong> · ' +
      esc(receipt.customer_hp) +
      '<br>' +
      esc(receipt.unit_deskripsi) +
      '</p></div>' +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Keluhan awal</h4>' +
      '<p class="detail-text">' +
      esc(receipt.keluhan_awal) +
      '</p></div>' +
      (receipt.catatan_pengerjaan
        ? '<div class="detail-section">' +
          '<h4 class="detail-section-title">Catatan pengerjaan</h4>' +
          '<p class="detail-text">' +
          esc(receipt.catatan_pengerjaan) +
          '</p></div>'
        : '') +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Rincian jasa</h4>' +
      '<div class="table-wrap"><table class="table detail-table">' +
      '<thead><tr><th>Jasa</th><th class="text-center">Qty</th><th class="text-right">Harga</th><th class="text-right">Subtotal</th></tr></thead>' +
      '<tbody>' +
      jobsHtml +
      '</tbody></table></div></div>' +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Sparepart</h4>' +
      '<div class="table-wrap"><table class="table detail-table">' +
      '<thead><tr><th>Barang</th><th class="text-center">Qty</th><th class="text-right">Harga deal</th><th class="text-right">Subtotal</th></tr></thead>' +
      '<tbody>' +
      partsHtml +
      '</tbody></table></div></div>' +
      '<div class="detail-totals">' +
      '<div class="detail-total-row"><span>Total jasa</span><strong>' +
      fmtRp(receipt.biaya_jasa) +
      '</strong></div>' +
      '<div class="detail-total-row"><span>Total part</span><strong>' +
      fmtRp(receipt.total_part) +
      '</strong></div>' +
      '<div class="detail-total-row"><span>Diskon</span><strong>' +
      fmtRp(receipt.diskon) +
      '</strong></div>' +
      returTotal +
      '<div class="detail-total-row"><span>Bayar</span><strong>' +
      fmtRp(receipt.bayar) +
      '</strong></div>' +
      '<div class="detail-total-row"><span>Kembalian</span><strong>' +
      fmtRp(receipt.kembalian) +
      '</strong></div>' +
      '</div>' +
      (receipt.catatan_garansi
        ? '<div class="detail-section">' +
          '<h4 class="detail-section-title">Catatan garansi</h4>' +
          '<p class="detail-text">' +
          esc(receipt.catatan_garansi) +
          '</p></div>'
        : '') +
      recordPengerjaanSection(receipt) +
      paymentSectionHtml(receipt) +
      returnHistoryHtml(state.detailReturns);
  }

  async function openRecordDetail(id) {
    if (!id) return;
    try {
      const results = await Promise.all([
        API.receipt(id),
        API.returns(id),
        API.payments(id),
        API.pengerjaanByRecord(id),
      ]);
      const receipt = results[0];
      state.detailRecord = receipt;
      state.detailReturns = results[1] || [];
      state.detailPayments = results[2] || [];
      state.detailPengerjaan = results[3] || null;
      renderRecordDetail(receipt);
      $('#btnExchangePart').classList.toggle(
        'hidden',
        !(
          receipt.sparepart_only &&
          (receipt.parts || []).some(
            (part) =>
              intValue(part.jumlah, 0) - intValue(part.jumlah_retur, 0) > 0
          )
        )
      );
      openModal('#recordModal');
    } catch (err) {
      toast('Detail nota gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function syncExchangeQtyMax() {
    const select = $('#exchangePart');
    const option = select?.options?.[select.selectedIndex];
    const max = option ? intValue(option.dataset.max, 1) : 1;
    const input = $('#exchangeQty');
    if (!input) return;
    input.max = String(Math.max(1, max));
    if (intValue(input.value, 1) > max) input.value = String(max);
    syncExchangeSummary();
  }

  function syncExchangeSummary() {
    const partSelect = $('#exchangePart');
    const partOption = partSelect?.options?.[partSelect.selectedIndex];
    const originalPrice = partOption
      ? parseMoney(partOption.dataset.price || 0)
      : 0;
    const qty = Math.max(1, intValue($('#exchangeQty').value, 1));
    const replacementPrice = parseMoney($('#exchangePrice').value);
    const originalValue = originalPrice * qty;
    const replacementValue = replacementPrice * qty;
    const diff = replacementValue - originalValue;
    $('#exchangeOriginalValue').textContent = fmtRp(originalValue);
    $('#exchangeReplacementValue').textContent = fmtRp(replacementValue);
    $('#exchangeDiffLabel').textContent =
      diff > 0 ? 'Tambahan dibayar' : diff < 0 ? 'Kembalian' : 'Selisih';
    $('#exchangeDiffValue').textContent = fmtRp(Math.abs(diff));
    $('#exchangeMethodRow').classList.toggle('hidden', diff <= 0);
  }

  function openExchangeModal() {
    const receipt = state.detailRecord;
    if (!receipt || !receipt.sparepart_only) return;
    const parts = (receipt.parts || []).filter(
      (part) =>
        intValue(part.jumlah, 0) - intValue(part.jumlah_retur, 0) > 0
    );
    if (!parts.length) {
      toast('Tidak ada sparepart yang bisa ditukar.', 'warning');
      return;
    }
    const stock = (state.stock || []).filter(
      (item) => intValue(item.jumlah, 0) > 0
    );
    if (!stock.length) {
      toast('Stok pengganti tidak tersedia.', 'warning');
      return;
    }
    $('#exchangePart').innerHTML = parts
      .map((part) => {
        const remaining =
          intValue(part.jumlah, 0) - intValue(part.jumlah_retur, 0);
        return (
          '<option value="' +
          part.id +
          '" data-max="' +
          remaining +
          '" data-price="' +
          Number(part.harga_satuan || 0) +
          '">' +
          esc(part.nama_part) +
          ' · sisa ' +
          remaining +
          '</option>'
        );
      })
      .join('');
    $('#exchangeStock').innerHTML = stock
      .map(
        (item) =>
          '<option value="' +
          item.id +
          '" data-price="' +
          Number(item.harga_jual || 0) +
          '">' +
          esc(item.nama) +
          ' · stok ' +
          intValue(item.jumlah, 0) +
          ' · ' +
          fmtRp(item.harga_jual) +
          '</option>'
      )
      .join('');
    $('#exchangeQty').value = '1';
    $('#exchangeReason').value = '';
    $('#exchangeMetode').value = 'CASH';
    const firstStock = stock[0];
    $('#exchangePrice').value = String(
      Math.round(Number(firstStock.harga_jual || 0))
    );
    syncExchangeQtyMax();
    openModal('#exchangeModal');
  }

  async function submitExchange() {
    const receipt = state.detailRecord;
    if (!receipt) return;
    const partId = intValue($('#exchangePart').value, 0);
    const stockId = intValue($('#exchangeStock').value, 0);
    const jumlah = intValue($('#exchangeQty').value, 0);
    const hargaGanti = parseMoney($('#exchangePrice').value);
    const alasan = $('#exchangeReason').value.trim();
    if (!partId || !stockId || jumlah < 1) {
      toast('Lengkapi barang dan jumlah tukar.', 'warning');
      return;
    }
    if (alasan.length < 3) {
      toast('Isi alasan tukar minimal 3 karakter.', 'warning');
      $('#exchangeReason').focus();
      return;
    }
    try {
      await API.exchangePart(receipt.id, {
        service_part_id: partId,
        stock_item_id: stockId,
        jumlah,
        harga_ganti: String(hargaGanti),
        bayar_tambahan: true,
        metode: $('#exchangeMetode').value,
        alasan,
      });
      closeModal('#exchangeModal');
      toast('Tukar barang tersimpan. Stok dan selisih sudah dicatat.', 'success');
      const [updated, returns, payments] = await Promise.all([
        API.receipt(receipt.id),
        API.returns(receipt.id),
        API.payments(receipt.id),
      ]);
      state.detailRecord = updated;
      state.detailReturns = returns || [];
      state.detailPayments = payments || [];
      renderRecordDetail(updated);
      await loadStock();
    } catch (err) {
      toast(err.message, 'error', 7000);
    }
  }

  async function loadRecordExtras(recordId) {
    if (!recordId) return;
    state.detailPayments = (await API.payments(recordId)) || [];
    if (state.detailRecord && state.detailRecord.id === recordId) {
      renderRecordDetail(state.detailRecord);
    }
  }

  function paymentRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return (
      'pay-' +
      Date.now().toString(36) +
      '-' +
      Math.random().toString(36).slice(2, 10)
    );
  }

  async function submitPayment(recordId) {
    const record = state.detailRecord;
    if (!record || record.id !== recordId) return;
    const nominal = readMoneyInput($('#paymentNominal'), 'Nominal pembayaran');
    if (nominal === null) return;
    if (nominal <= 0) {
      toast('Nominal pembayaran harus lebih dari nol.', 'warning');
      return;
    }
    const sisaRupiah = Math.round(moneyToCents(record.sisa_bayar) / 100);
    if (nominal > sisaRupiah) {
      toast('Nominal melebihi sisa bayar nota.', 'warning');
      return;
    }
    const kreditEl = $('#paymentKreditAktif');
    const kredit = kreditEl ? kreditEl.checked : false;
    if (!kredit && nominal < sisaRupiah) {
      toast(
        'Kredit nonaktif. Isi pelunasan penuh atau aktifkan Kredit untuk membayar sebagian.',
        'warning'
      );
      return;
    }
    const metodeEl = $('#paymentMetode');
    const noteEl = $('#paymentCatatan');
    const button = $('[data-action="payment-submit"]');
    setBusy(button, true, 'Menyimpan...');
    try {
      const result = await API.createPayment(recordId, {
        nominal: String(nominal),
        metode: metodeEl ? metodeEl.value : 'CASH',
        catatan: noteEl && noteEl.value.trim() ? noteEl.value.trim() : null,
        request_id: paymentRequestId(),
      });
      if (result.status_bayar === 'LUNAS') {
        toast('Nota ' + record.no_nota + ' lunas.', 'success');
      } else if (kredit) {
        toast(
          'Pembayaran kredit tercatat. Sisa ' +
            fmtRp(result.sisa_bayar) +
            ' masuk ke Piutang.',
          'success'
        );
      } else {
        toast(
          'Pembayaran tercatat. Sisa ' + fmtRp(result.sisa_bayar) + '.',
          'success'
        );
      }
      await refreshAfterRecordChange(recordId);
      if (!$('#receivablesModal').classList.contains('hidden')) {
        loadReceivables();
      }
      if (result.receipt) {
        showReceipt(result.receipt);
      }
      const pending = state.pendingPengerjaan;
      const willTake = pending && pending.recordId === recordId;
      if (willTake) {
        state.pendingPengerjaan = null;
        try {
          await API.pengerjaanTaken(pending.markerId);
          toast('Unit ditandai sudah diambil.', 'success');
          await loadPengerjaan();
          loadDashboard();
          if (!$('#view-followup').classList.contains('hidden')) {
            loadFollowupPage();
          }
        } catch (err) {
          toast(
            'Pembayaran tercatat, tetapi unit gagal ditandai diambil: ' +
              err.message,
            'error',
            7000
          );
        }
      } else {
        if (!$('#pengerjaanModal').classList.contains('hidden')) {
          await loadPengerjaan();
        }
        if (!$('#view-followup').classList.contains('hidden')) {
          await loadFollowupPage();
        }
      }
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  function fillPaymentSisa() {
    const record = state.detailRecord;
    if (!record) return;
    const input = $('#paymentNominal');
    if (!input) return;
    setMoneyValue(input, Math.round(moneyToCents(record.sisa_bayar) / 100));
    input.focus();
  }

  function fillPaymentSetengah() {
    const record = state.detailRecord;
    if (!record) return;
    const input = $('#paymentNominal');
    if (!input) return;
    const sisa = Math.round(moneyToCents(record.sisa_bayar) / 100);
    setMoneyValue(input, Math.max(1, Math.floor(sisa / 2)));
    input.focus();
  }

  function syncPaymentKreditUI() {
    const toggle = $('#paymentKreditAktif');
    if (!toggle) return;
    const hint = $('#paymentKreditHint');
    const half = $('#paymentSetengahBtn');
    if (hint) {
      hint.textContent = toggle.checked
        ? 'Kredit aktif: boleh membayar sebagian, sisa tetap di Piutang.'
        : 'Kredit nonaktif: pembayaran harus penuh.';
    }
    if (half) half.classList.toggle('hidden', !toggle.checked);
  }

  function renderCustomerDetail(customer) {
    const units = customer.units || [];
    const unitsHtml = units.length
      ? units
          .map(
            (unit) =>
              '<div class="detail-unit"><div><strong>' +
              esc(describeUnit(unit)) +
              '</strong>' +
              (unit.keterangan
                ? '<span class="muted">' + esc(unit.keterangan) + '</span>'
                : '') +
              '</div><span class="badge ' +
              (unit.unit_type === 'MOBIL' ? 'blue' : 'gray') +
              '">' +
              (unit.unit_type === 'MOBIL' ? 'Mobil' : 'Radiator') +
              '</span></div>'
          )
          .join('')
      : '<div class="empty-state">Belum ada unit terdaftar.</div>';

    $('#customerDetailTitle').textContent = customer.nama;
    $('#customerDetailSubtitle').textContent =
      customer.nomor_hp + (customer.alamat ? ' · ' + customer.alamat : '');
    $('#customerDetailBody').innerHTML =
      '<div class="detail-grid">' +
      detailItem(
        'Total unit',
        esc(String(intValue(customer.total_unit, units.length)))
      ) +
      detailItem('Unit mobil', esc(String(intValue(customer.total_mobil, 0)))) +
      detailItem(
        'Radiator copotan',
        esc(String(intValue(customer.total_radiator, 0)))
      ) +
      detailItem('Terdaftar', esc(fmtDate(customer.created_at))) +
      '</div>' +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Unit terdaftar (' +
      units.length +
      ')</h4>' +
      '<div class="detail-unit-list">' +
      unitsHtml +
      '</div></div>' +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Preferensi pesan</h4>' +
      '<label class="checkbox-row"><input type="checkbox" id="customerWaConsent"' +
      (customer.wa_consent === false ? '' : ' checked') +
      '> Pelanggan memberi izin WhatsApp</label>' +
      '<label class="checkbox-row"><input type="checkbox" id="customerDnc"' +
      (customer.do_not_contact ? ' checked' : '') +
      '> Berhenti dihubungi (DNC)</label>' +
      '<p class="tiny muted">DNC memblokir prospek, garansi, dan servis berkala. Piutang dan pengerjaan tetap bisa dikirim dengan peringatan.</p>' +
      '<button type="button" class="btn btn-outline btn-sm" data-action="customer-contact-save" data-id="' +
      customer.id +
      '">Simpan preferensi</button>' +
      '</div>' +
      '<div class="detail-section" id="customerReceivableSection"></div>' +
      '<div class="detail-section" id="customerFollowupSection"></div>' +
      '<div class="detail-section" id="customerHistorySection"></div>';
  }

  function renderCustomerReceivables(data) {
    const section = $('#customerReceivableSection');
    if (!section) return;
    const count = intValue(data && data.jumlah_nota, 0);
    const total = data ? data.total_sisa : 0;
    if (!count) {
      section.innerHTML =
        '<h4 class="detail-section-title">Piutang</h4>' +
        '<div class="empty-state sm">Tidak ada piutang berjalan.</div>';
      return;
    }
    section.innerHTML =
      '<h4 class="detail-section-title">Piutang</h4>' +
      '<div class="receivable-head"><div><strong>' +
      count +
      ' nota belum lunas</strong><span>Total sisa ' +
      fmtRp(total) +
      '</span></div>' +
      '<button type="button" class="btn btn-outline btn-sm" data-action="customer-receivables" data-id="' +
      intValue(state.detailCustomer && state.detailCustomer.id, 0) +
      '">Lihat rincian</button></div>';
  }

  function renderCustomerFollowups(result) {
    const section = $('#customerFollowupSection');
    if (!section) return;
    const items = (result && result.items) || [];
    section.innerHTML =
      '<h4 class="detail-section-title">Follow-up (' +
      items.length +
      ')</h4>' +
      (items.length
        ? '<div class="detail-history-list">' +
          items
            .map(
              (item) =>
                '<button type="button" class="detail-history-item" data-action="followup-detail" data-id="' +
                item.id +
                '"><span class="detail-history-main"><span class="detail-history-note">' +
                esc(item.jenis_label) +
                '</span><span class="detail-history-unit">' +
                esc(item.judul || '-') +
                '</span></span><span class="detail-history-side"><span class="detail-history-date">' +
                esc(dueLabel(item)) +
                '</span><span class="detail-history-total">' +
                esc(item.status_label) +
                '</span></span></button>'
            )
            .join('') +
          '</div>'
        : '<div class="empty-state sm">Tidak ada follow-up aktif.</div>');
  }

  async function loadCustomerExtras(customer) {
    if (!customer) return;
    const receivableSection = $('#customerReceivableSection');
    if (receivableSection) {
      receivableSection.innerHTML =
        '<h4 class="detail-section-title">Piutang</h4>' +
        '<div class="empty-state sm">Memuat piutang...</div>';
    }
    try {
      const data = await API.customerReceivables(customer.id);
      if (state.detailCustomer && state.detailCustomer.id === customer.id) {
        renderCustomerReceivables(data);
      }
    } catch (err) {
      if (receivableSection) {
        receivableSection.innerHTML =
          '<h4 class="detail-section-title">Piutang</h4>' +
          '<div class="empty-state sm">Piutang gagal dimuat.</div>';
      }
    }
    const followupSection = $('#customerFollowupSection');
    if (followupSection) {
      followupSection.innerHTML =
        '<h4 class="detail-section-title">Follow-up</h4>' +
        '<div class="empty-state sm">Memuat follow-up...</div>';
    }
    try {
      const result = await API.followupItems('semua', null, customer.id);
      if (state.detailCustomer && state.detailCustomer.id === customer.id) {
        renderCustomerFollowups(result);
      }
    } catch (err) {
      if (followupSection) {
        followupSection.innerHTML =
          '<h4 class="detail-section-title">Follow-up</h4>' +
          '<div class="empty-state sm">Follow-up gagal dimuat.</div>';
      }
    }
  }

  function customerHistoryItem(record) {
    return (
      '<button type="button" class="detail-history-item" data-action="record-detail" data-id="' +
      record.id +
      '" title="Buka nota ' +
      esc(record.no_nota) +
      '">' +
      '<span class="detail-history-main">' +
      '<span class="detail-history-note">' +
      esc(record.no_nota) +
      '</span>' +
      '<span class="detail-history-unit">' +
      esc(record.unit_deskripsi || '-') +
      '</span>' +
      '</span>' +
      '<span class="detail-history-side">' +
      '<span class="detail-history-total">' +
      fmtRp(netTotal(record)) +
      '</span>' +
      '<span class="detail-history-date">' +
      esc(fmtDate(record.waktu_service)) +
      '</span>' +
      '</span>' +
      '<span class="detail-history-badges">' +
      metodeBadge(record.metode_bayar) +
          paymentBadge(record) +
      warrantyBadge(record) +
      '</span>' +
      '</button>'
    );
  }

  async function loadCustomerHistory(customer) {
    const section = $('#customerHistorySection');
    if (!section) return;
    const seq = (state.customerHistorySeq += 1);
    state.customerHistory = [];
    section.innerHTML =
      '<h4 class="detail-section-title">Riwayat servis</h4>' +
      '<div class="empty-state sm">Memuat riwayat servis...</div>';

    try {
      const records = await API.records(customer.nomor_hp || '');
      if (seq !== state.customerHistorySeq) return;
      const list = (records || []).filter(
        (record) => record.customer_id === customer.id
      );
      state.customerHistory = list;
      section.innerHTML =
        '<h4 class="detail-section-title">Riwayat servis (' +
        list.length +
        ')</h4>' +
        (list.length
          ? '<div class="detail-history-list">' +
            list.map(customerHistoryItem).join('') +
            '</div>'
          : '<div class="empty-state sm">Belum ada riwayat servis untuk pelanggan ini.</div>');
    } catch (err) {
      if (seq !== state.customerHistorySeq) return;
      section.innerHTML =
        '<h4 class="detail-section-title">Riwayat servis</h4>' +
        '<div class="empty-state sm">Riwayat servis gagal dimuat. Coba lagi.</div>';
    }
  }

  async function openCustomerDetail(id) {
    if (!id) return;
    let customer =
      (state.customerDirectory || []).find((item) => item.id === id) || null;

    if (!customer) {
      const source = findRecordByCustomerId(id);
      try {
        const list = await API.customerOverview(
          source ? source.customer_hp : ''
        );
        customer = list.find((item) => item.id === id) || null;
      } catch (err) {
        toast('Detail pelanggan gagal dimuat. Coba lagi.', 'error', 6000);
        return;
      }
    }

    if (!customer) {
      toast('Data pelanggan tidak ditemukan.', 'warning');
      return;
    }

    state.detailCustomer = customer;
    renderCustomerDetail(customer);
    openModal('#customerDetailModal');
    loadCustomerExtras(customer);
    loadCustomerHistory(customer);
  }

  /* ------------------------------ Follow-up ------------------------------- */
  const FOLLOWUP_STATUS_LABELS = {
    BARU: 'Baru',
    SUDAH_FOLLOWUP: 'Sudah dihubungi',
    JANJI_BAYAR: 'Janji bayar',
    MASIH_KENDALA: 'Masih kendala',
    SELESAI: 'Selesai',
    ARSIP: 'Arsip',
    AKAN_DATANG: 'Akan datang service',
    TIDAK_DATANG: 'Tidak akan datang service',
    SUDAH_BAYAR: 'Sudah bayar',
  };

  const FOLLOWUP_JADWAL_JENIS = ['servis_berkala', 'garansi'];

  const PENGERJAAN_STATUS_LABELS = {
    SEDANG_DIKERJAKAN: 'Sedang dikerjakan',
    MENUNGGU_SPAREPART: 'Menunggu sparepart',
    MENUNGGU_PERSETUJUAN: 'Menunggu persetujuan',
    SELESAI_SIAP_DIAMBIL: 'Selesai, siap diambil',
    SUDAH_DIAMBIL: 'Sudah diambil',
  };

  function followupStatusLabel(status) {
    return FOLLOWUP_STATUS_LABELS[status] || status || '-';
  }

  const FOLLOWUP_LIST_TITLES = {
    servis_berkala: 'Servis berkala',
    garansi: 'Garansi akan habis',
    prospek: 'Prospek pelanggan',
  };

  const FOLLOWUP_AKAN_DATANG_TITLES = {
    garansi: 'Akan datang: Garansi',
    servis_berkala: 'Akan datang: Servis berkala',
    prospek: 'Akan datang: Prospek',
  };

  function followupCardHtml(item, view) {
    const late =
      item.terlambat &&
      item.status !== 'SELESAI' &&
      item.status !== 'ARSIP' &&
      item.status !== 'TIDAK_DATANG';
    const akanDatangView = view === 'AKAN_DATANG';
    const jadwal = FOLLOWUP_JADWAL_JENIS.indexOf(item.jenis) >= 0;
    const remindTitle =
      item.bisa_alasan ||
      (isFollowupWindowOpen()
        ? 'Follow up belum bisa dilakukan sekarang'
        : 'Follow up hanya bisa dilakukan antara pukul ' +
          followupWindow().label +
          '.');
    const remindButton = item.bisa_followup
      ? '<button type="button" class="btn btn-primary btn-xs" data-action="followup-wa" data-id="' +
        item.id +
        '">Ingatkan</button>'
      : '<button type="button" class="btn btn-outline btn-xs" disabled title="' +
        esc(remindTitle) +
        '">Ingatkan</button>';
    const chatButton = waLink(item.nomor_hp)
      ? '<button type="button" class="btn btn-outline btn-xs" data-action="followup-chat" data-id="' +
        item.id +
        '">WA</button>'
      : '<button type="button" class="btn btn-outline btn-xs" disabled title="Nomor WhatsApp pelanggan belum valid">WA</button>';
    const statusLocked =
      (jadwal || item.jenis === 'prospek') && !item.sudah_followup;
    const statusButton =
      '<button type="button" class="btn btn-outline btn-xs" data-action="followup-status-shortcut" data-id="' +
      item.id +
      '"' +
      (statusLocked
        ? ' disabled title="Lakukan Ingatkan dulu sebelum mengubah status"'
        : '') +
      '>Status</button>';
    const detailButton =
      '<button type="button" class="btn btn-outline btn-xs" data-action="followup-detail" data-id="' +
      item.id +
      '">Detail</button>';
    const actions = akanDatangView
      ? statusButton + chatButton
      : remindButton + chatButton + detailButton + statusButton;
    return (
      '<div class="receivable-group' +
      (late ? ' is-late' : '') +
      '"><div class="receivable-head"><div class="pengerjaan-info"><button type="button" class="receivable-name" data-action="followup-detail" data-id="' +
      item.id +
      '">' +
      esc(item.customer_nama) +
      '</button><span>' +
      esc(item.unit_deskripsi || '-') +
      ' · WA ' +
      esc(item.nomor_hp || '-') +
      '</span></div><span class="badge ' +
      (late ? 'red' : 'gray') +
      '">' +
      esc(dueLabel(item)) +
      '</span></div><div class="pengerjaan-row"><div class="pengerjaan-meta">' +
      '<span class="cell-sub">' +
      esc(item.judul) +
      '</span>' +
      (item.no_nota
        ? '<span class="cell-sub">' + esc(item.no_nota) + '</span>'
        : '') +
      '<span class="badge gray">' +
      esc(item.status_label) +
      '</span>' +
      (item.perlu_telepon
        ? '<span class="badge red">Perlu telepon</span>'
        : '') +
      (item.jenis === 'piutang' && item.pengingat_ke
        ? '<span class="badge gray">Pengingat ' +
          intValue(item.pengingat_ke, 0) +
          'x</span>'
        : '') +
      (item.tunda_sampai
        ? '<span class="badge gray">Ditunda s.d. ' +
          esc(fmtDate(item.tunda_sampai)) +
          '</span>'
        : '') +
      '</div><div class="pengerjaan-actions">' +
      actions +
      '</div></div></div>'
    );
  }

  function openFollowupList(jenis, status, excludeStatus) {
    const type = jenis || '';
    const itemStatus = status || '';
    const excluded = excludeStatus || '';
    state.followupList = {
      filter: 'semua',
      jenis: type,
      status: itemStatus,
      excludeStatus: excluded,
      items: [],
    };
    const title = $('#followupListTitle');
    const subtitle = $('#followupListSubtitle');
    const berkendala = itemStatus === 'MASIH_KENDALA' && type === 'prospek';
    if (title) {
      title.textContent = berkendala
        ? 'Berkendala'
        : (itemStatus === 'AKAN_DATANG' && FOLLOWUP_AKAN_DATANG_TITLES[type]) ||
          FOLLOWUP_LIST_TITLES[type] ||
          'Follow-up';
    }
    if (subtitle) {
      subtitle.textContent = berkendala
        ? 'Prospek yang masih terkendala. Pilih item untuk melihat detail.'
        : itemStatus === 'AKAN_DATANG'
          ? 'Jadwal kunjungan yang sudah disepakati. Pilih item untuk melihat detail.'
          : 'Pengingat aktif. Pilih item untuk melihat detail.';
    }
    const body = $('#followupListBody');
    if (body) body.innerHTML = '<div class="empty-state sm">Memuat follow-up...</div>';
    const empty = $('#followupListEmpty');
    if (empty) empty.classList.add('hidden');
    openModal('#followupListModal');
    loadFollowupList();
  }

  async function loadFollowupList() {
    const current = state.followupList;
    if (!current) return;
    const body = $('#followupListBody');
    const empty = $('#followupListEmpty');
    try {
      const result = await API.followupItems(
        current.filter,
        current.jenis || null,
        null,
        current.status || null,
        current.excludeStatus || null
      );
      if (state.followupList !== current) return;
      current.items = result.items || [];
    } catch (err) {
      if (state.followupList !== current) return;
      current.items = [];
      toast('Daftar follow-up gagal dimuat. Coba lagi.', 'error', 6000);
    }
    if (state.followupList !== current || !body) return;
    body.innerHTML = current.items
      .map((item) => followupCardHtml(item, current.status))
      .join('');
    if (empty) empty.classList.toggle('hidden', current.items.length > 0);
  }

  function closeFollowupList() {
    closeModal('#followupListModal');
    state.followupList = null;
  }

  async function loadFollowupPage() {
    const supplierAktif =
      !state.config || !state.config.ops || state.config.ops.supplier_aktif !== false;
    if (state.followupTab === 'reseller' && (!supplierAktif || isMenuHidden('reseller'))) {
      state.followupTab = 'customer';
    }
    const reseller = state.followupTab === 'reseller';
    const statsGrid = $('#followupStatsGrid');
    const resultGrid = $('#followupResultGrid');
    const resellerStats = $('#followupResellerStats');
    const resellerSection = $('#followupResellerSection');
    if (statsGrid) statsGrid.classList.toggle('hidden', reseller);
    if (resultGrid && reseller) resultGrid.classList.add('hidden');
    if (resellerStats) resellerStats.classList.toggle('hidden', !reseller);
    if (resellerSection) resellerSection.classList.toggle('hidden', !reseller);
    $$('#followupTabSwitch [data-followup-tab]').forEach((button) => {
      button.classList.toggle(
        'active',
        button.dataset.followupTab === state.followupTab
      );
    });
    if (reseller) {
      await loadFollowupReseller();
      return;
    }
    try {
      const daily = await API.daily(todayISO());
      const set = (id, value) => {
        const el = $('#' + id);
        if (el) el.textContent = value;
      };
      set('followupStatReceivable', fmtRp(daily.piutang_total));
      set(
        'followupStatReceivableSub',
        (daily.piutang_count || 0) +
          ' nota · ' +
          (daily.piutang_customers || 0) +
          ' pelanggan'
      );
      set('followupStatPengerjaan', daily.kendaraan_selesai || 0);
      set('followupStatProspek', daily.prospek_count || 0);
      set('followupStatBerkendala', daily.berkendala_prospek || 0);
      set('followupStatDueService', daily.servis_berkala_due || 0);
      set('followupStatWarrantyEnding', daily.garansi_akan_habis || 0);
      set('followupStatAkanGaransi', daily.akan_datang_garansi || 0);
      set('followupStatAkanServis', daily.akan_datang_servis || 0);
      set('followupStatAkanProspek', daily.akan_datang_prospek || 0);
      await loadFollowupResults();
    } catch (err) {
      toast('Follow up gagal dimuat. Coba muat ulang.', 'error', 6000);
    }
  }

  async function loadFollowupResults() {
    const grid = $('#followupResultGrid');
    if (!grid) return;
    try {
      const data = await API.followupResults();
      const cards = [
        ['Balik lagi', data.balik_lagi],
        ['Masih bagus', data.masih_bagus],
        ['Bermasalah', data.bermasalah],
        ['Menolak', data.menolak],
      ].filter((row) => intValue(row[1], 0) > 0);
      if (!cards.length) {
        grid.innerHTML = '';
        grid.classList.add('hidden');
        return;
      }
      grid.innerHTML = cards
        .map(
          (row) =>
            '<article class="stat-card"><span class="stat-label">' +
            esc(row[0]) +
            '</span><strong>' +
            intValue(row[1], 0) +
            '</strong></article>'
        )
        .join('');
      grid.classList.remove('hidden');
    } catch (err) {
      grid.classList.add('hidden');
    }
  }

  function refreshFollowupViews() {
    loadDashboard();
    const modal = $('#followupListModal');
    const open = modal && !modal.classList.contains('hidden');
    if (state.followupList && open) loadFollowupList();
    const page = $('#view-followup');
    if (page && !page.classList.contains('hidden')) loadFollowupPage();
  }

  function followupRincianHtml(item) {
    const rows = item.rincian || [];
    if (!rows.length) return '';
    return (
      '<div class="detail-section"><h4 class="detail-section-title">Rincian</h4>' +
      rows
        .map((row) => {
          const bits = [];
          if (row.no_nota) bits.push('Nota ' + row.no_nota);
          if (row.tanggal_servis) bits.push(fmtDate(row.tanggal_servis));
          if (row.pekerjaan) bits.push(row.pekerjaan);
          const money = [];
          if (row.total_servis != null) money.push('Total ' + fmtRp(row.total_servis));
          if (row.sisa_bayar != null && moneyToCents(row.sisa_bayar) > 0) {
            money.push('Sisa ' + fmtRp(row.sisa_bayar));
          }
          return (
            '<div class="detail-text">' +
            esc(bits.join(' · ') || '-') +
            (money.length ? '<br><span class="cell-sub">' + esc(money.join(' · ')) + '</span>' : '') +
            '</div>'
          );
        })
        .join('') +
      '</div>'
    );
  }

  function followupNotaHtml(item) {
    const rows = (item.rincian || []).filter(
      (row) => !item.no_nota || row.no_nota === item.no_nota
    );
    if (!rows.length) return '';
    return (
      '<div class="detail-section"><h4 class="detail-section-title">Nota servis</h4>' +
      rows
        .map((row) => {
          const bits = [];
          if (row.no_nota) bits.push('Nota ' + row.no_nota);
          if (row.tanggal_servis) bits.push(fmtDate(row.tanggal_servis));
          if (row.pekerjaan) bits.push(row.pekerjaan);
          let info = '';
          if (row.garansi_sampai) {
            info = 'Garansi sampai ' + fmtDate(row.garansi_sampai);
            if (row.sisa_hari != null) {
              info +=
                ' (' +
                (row.sisa_hari < 0
                  ? Math.abs(row.sisa_hari) + ' hari lalu'
                  : row.sisa_hari === 0
                    ? 'hari ini'
                    : row.sisa_hari + ' hari lagi') +
                ')';
            }
          } else if (row.jatuh_tempo) {
            info = 'Servis berikutnya ' + fmtDate(row.jatuh_tempo);
            if (row.interval_bulan) {
              info += ' (' + row.interval_bulan + ' bulan)';
            }
          }
          return (
            '<div class="detail-text">' +
            esc(bits.join(' · ') || '-') +
            (info
              ? '<br><span class="cell-sub">' + esc(info) + '</span>'
              : '') +
            '</div>'
          );
        })
        .join('') +
      '</div>'
    );
  }

  function followupFullNotaHtml(receipt, item) {
    if (!receipt) return followupNotaHtml(item);
    const jobs = receipt.jobs || [];
    const parts = receipt.parts || [];
    const jobRows = jobs.length
      ? jobs
          .map(
            (job) =>
              '<tr><td>' +
              esc(job.deskripsi) +
              '</td><td class="text-center">' +
              qtyCell(job) +
              '</td><td class="text-right money">' +
              fmtRp(job.harga) +
              '</td><td class="text-right money">' +
              fmtRp(job.subtotal) +
              '</td></tr>'
          )
          .join('')
      : '<tr><td colspan="4" class="muted">Tidak ada rincian jasa.</td></tr>';
    const partRows = parts.length
      ? parts
          .map(
            (part) =>
              '<tr><td>' +
              esc(part.nama_part) +
              '</td><td class="text-center">' +
              qtyCell(part) +
              '</td><td class="text-right money">' +
              fmtRp(part.harga_satuan) +
              '</td><td class="text-right money">' +
              fmtRp(part.subtotal) +
              '</td></tr>'
          )
          .join('')
      : '<tr><td colspan="4" class="muted">Tidak ada sparepart.</td></tr>';
    return (
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Nota servis · ' +
      esc(receipt.no_nota) +
      '</h4>' +
      '<div class="detail-grid">' +
      detailItem('Waktu servis', esc(fmtDateTime(receipt.waktu_service))) +
      detailItem('Metode bayar', metodeBadge(receipt.metode_bayar)) +
      detailItem('Status bayar', paymentBadge(receipt) || '-') +
      (receipt.sparepart_only
        ? detailItem(
            'Garansi tukar',
            esc(
              receipt.garansi_tukar_aktif
                ? receipt.garansi_tukar_hari + ' hari'
                : 'Tidak aktif'
            )
          ) +
          detailItem(
            'Garansi barang',
            esc(
              receipt.garansi_barang_aktif
                ? receipt.garansi_barang_nilai +
                    ' ' +
                    (receipt.garansi_barang_satuan === 'BULAN'
                      ? 'bulan'
                      : 'hari') +
                    (receipt.garansi_barang_sampai
                      ? ' · sampai ' + fmtDate(receipt.garansi_barang_sampai)
                      : '')
                : 'Tidak aktif'
            )
          )
        : detailItem(
            'Garansi sampai',
            esc(receipt.garansi_sampai ? fmtDate(receipt.garansi_sampai) : '-')
          )) +
      '</div>' +
      '<p class="detail-text"><strong>Keluhan awal</strong><br>' +
      esc(receipt.keluhan_awal || '-') +
      '</p>' +
      (receipt.catatan_pengerjaan
        ? '<p class="detail-text"><strong>Catatan pengerjaan</strong><br>' +
          esc(receipt.catatan_pengerjaan) +
          '</p>'
        : '') +
      '<h4 class="detail-section-title">Rincian jasa</h4>' +
      '<div class="table-wrap"><table class="table detail-table">' +
      '<thead><tr><th>Jasa</th><th class="text-center">Qty</th><th class="text-right">Harga</th><th class="text-right">Subtotal</th></tr></thead>' +
      '<tbody>' +
      jobRows +
      '</tbody></table></div>' +
      '<h4 class="detail-section-title">Sparepart</h4>' +
      '<div class="table-wrap"><table class="table detail-table">' +
      '<thead><tr><th>Barang</th><th class="text-center">Qty</th><th class="text-right">Harga deal</th><th class="text-right">Subtotal</th></tr></thead>' +
      '<tbody>' +
      partRows +
      '</tbody></table></div>' +
      '<div class="detail-totals">' +
      '<div class="detail-total-row"><span>Total jasa</span><strong>' +
      fmtRp(receipt.biaya_jasa) +
      '</strong></div>' +
      '<div class="detail-total-row"><span>Total part</span><strong>' +
      fmtRp(receipt.total_part) +
      '</strong></div>' +
      '<div class="detail-total-row"><span>Diskon</span><strong>' +
      fmtRp(receipt.diskon) +
      '</strong></div>' +
      '<div class="detail-total-row is-grand"><span>Total servis</span><strong>' +
      fmtRp(receipt.total_servis) +
      '</strong></div>' +
      (Number(receipt.total_retur) > 0
        ? '<div class="detail-total-row"><span>Retur</span><strong>-' +
          fmtRp(receipt.total_retur) +
          '</strong></div>' +
          '<div class="detail-total-row is-grand"><span>Total neto</span><strong>' +
          fmtRp(netTotal(receipt)) +
          '</strong></div>'
        : '') +
      '<div class="detail-total-row"><span>Total dibayar</span><strong>' +
      fmtRp(receipt.total_dibayar) +
      '</strong></div>' +
      '<div class="detail-total-row"><span>Sisa bayar</span><strong>' +
      fmtRp(receipt.sisa_bayar) +
      '</strong></div>' +
      '</div>' +
      (receipt.catatan_garansi || item.jenis === 'garansi'
        ? '<div class="detail-section">' +
          '<h4 class="detail-section-title">Catatan garansi</h4>' +
          (receipt.catatan_garansi
            ? '<p class="detail-text">' +
              esc(receipt.catatan_garansi) +
              '</p>'
            : '') +
          (item.jenis === 'garansi'
            ? '<p class="detail-text cell-sub">' +
              esc(item.judul) +
              ' · ' +
              esc(dueLabel(item)) +
              '</p>'
            : '') +
          '</div>'
        : '') +
      '</div>'
    );
  }

  function followupEventsHtml(events) {
    if (!events.length) return '';
    return (
      '<div class="detail-section"><h4 class="detail-section-title">Riwayat tindakan</h4>' +
      '<div class="followup-event-list">' +
      events
        .map(
          (event) =>
            '<div class="followup-event"><div><strong>' +
            esc(followupStatusLabel(event.from_status)) +
            ' → ' +
            esc(followupStatusLabel(event.to_status)) +
            '</strong>' +
            (event.alasan ? '<div>' + esc(event.alasan) + '</div>' : '') +
            '<small>' +
            esc(fmtDateTime(event.created_at)) +
            ' · ' +
            esc(event.operator || '-') +
            '</small></div></div>'
        )
        .join('') +
      '</div></div>'
    );
  }

  function renderFollowupDetail(detail) {
    const item = detail.item;
    const events = detail.events || [];
    $('#followupModalTitle').textContent = item.customer_nama;
    $('#followupModalSubtitle').textContent =
      item.status === 'AKAN_DATANG' && item.jenis === 'garansi'
        ? item.jenis_label
        : item.jenis_label + ' · ' + item.judul + ' · ' + dueLabel(item);
    const jadwal = FOLLOWUP_JADWAL_JENIS.indexOf(item.jenis) >= 0;
    const akanDatang = item.status === 'AKAN_DATANG';
    const simplifiedAkan = akanDatang && jadwal;
    const datangBtn = $('#followupDatang');
    const tidakDatangBtn = $('#followupTidakDatang');
    const rescheduleBtn = $('#followupReschedule');
    if (datangBtn) datangBtn.classList.toggle('hidden', !simplifiedAkan);
    if (tidakDatangBtn) {
      tidakDatangBtn.classList.toggle('hidden', !simplifiedAkan);
    }
    if (rescheduleBtn) {
      rescheduleBtn.classList.toggle('hidden', !simplifiedAkan);
    }
    if (simplifiedAkan) {
      if (datangBtn) datangBtn.dataset.id = String(item.id);
      if (tidakDatangBtn) tidakDatangBtn.dataset.id = String(item.id);
      if (rescheduleBtn) rescheduleBtn.dataset.id = String(item.id);
    } else {
      if (datangBtn) delete datangBtn.dataset.id;
      if (tidakDatangBtn) delete tidakDatangBtn.dataset.id;
      if (rescheduleBtn) delete rescheduleBtn.dataset.id;
    }
    const headHtml =
      '<div class="followup-detail-head">' +
      '<span class="badge ' +
      jenisTone(item.jenis) +
      '">' +
      esc(item.jenis_label) +
      '</span>' +
      '<span class="badge gray">' +
      esc(item.status_label) +
      '</span>' +
      '<span class="badge ' +
      (item.terlambat ? 'red' : 'gray') +
      '">' +
      esc(dueLabel(item)) +
      '</span>' +
      '</div>';
    if (simplifiedAkan) {
      $('#followupDetailBody').innerHTML =
        headHtml +
        '<div class="detail-grid">' +
        detailItem('Pelanggan', esc(item.customer_nama)) +
        detailItem('WhatsApp', esc(item.nomor_hp || '-')) +
        detailItem('Domisili', esc(item.customer_alamat || '-')) +
        detailItem('Unit', esc(item.unit_deskripsi || '-')) +
        detailItem(
          'Tanggal service',
          esc(item.tanggal_service ? fmtDate(item.tanggal_service) : '-')
        ) +
        '</div>' +
        followupFullNotaHtml(state.followupReceipt, item);
      return;
    }
    $('#followupDetailBody').innerHTML =
      headHtml +
      '<div class="detail-grid">' +
      detailItem('Pelanggan', esc(item.customer_nama)) +
      detailItem('Domisili', esc(item.customer_alamat || '-')) +
      detailItem('WhatsApp', esc(item.nomor_hp || '-')) +
      detailItem('Unit', esc(item.unit_deskripsi || '-')) +
      detailItem('Jatuh tempo', esc(item.jatuh_tempo ? fmtDate(item.jatuh_tempo) : '-')) +
      detailItem(
        'Follow up terakhir',
        esc(item.followup_terakhir ? fmtDateTime(item.followup_terakhir) : '-')
      ) +
      (jadwal
        ? detailItem(
            'Tanggal service',
            esc(item.tanggal_service ? fmtDate(item.tanggal_service) : '-')
          )
        : '') +
      '</div>' +
      followupFullNotaHtml(state.followupReceipt, item) +
      followupRincianHtml(item) +
      '<div class="detail-section">' +
      '<h4 class="detail-section-title">Pesan WhatsApp</h4>' +
      '<p class="detail-text">' +
      esc(detail.pesan || '-') +
      '</p></div>' +
      (jadwal || item.jenis === 'prospek'
        ? ''
        : followupEventsHtml(events));
  }

  async function openFollowupDetail(id) {
    if (!id) return;
    try {
      const detail = await API.followupDetail(id);
      state.followupDetail = detail;
      state.followupReceipt = null;
      if (detail.item.service_record_id) {
        try {
          state.followupReceipt = await API.receipt(
            detail.item.service_record_id
          );
        } catch (err) {
          state.followupReceipt = null;
        }
      }
      renderFollowupDetail(detail);
      openModal('#followupModal');
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function followupWhatsapp(id) {
    let detail = state.followupDetail;
    if (!detail || detail.item.id !== id) {
      try {
        detail = await API.followupDetail(id);
        state.followupDetail = detail;
      } catch (err) {
        toast(err.message, 'error', 6000);
        return;
      }
    }
    const item = detail.item;
    if (!item.bisa_followup) {
      toast(
        'Follow up belum bisa dilakukan sekarang. Periksa jeda atau status.',
        'warning'
      );
      return;
    }
    const detailOpen = !$('#followupModal').classList.contains('hidden');
    const listOpen = !$('#followupListModal').classList.contains('hidden');
    openWaPreview({
      judul: 'WhatsApp ' + item.customer_nama,
      subtitle: 'Periksa pesan follow-up sebelum dibuka.',
      nomor: item.nomor_hp,
      masked: item.nomor_masked,
      text: detail.pesan || '',
      note: 'Membuka WhatsApp akan mencatat upaya follow-up. Kasir tetap menekan kirim di WhatsApp.',
      onOpen: async (text) => {
        await API.followupItem(id, { status: 'DIBUKA', pesan: text });
        toast('Follow-up tercatat.', 'success');
        if (detailOpen) await openFollowupDetail(id);
        if (listOpen) await loadFollowupList();
        refreshFollowupViews();
      },
    });
  }

  async function submitFollowupPresence(id, target) {
    const detail = state.followupDetail;
    if (!detail || detail.item.id !== id) return;
    const datang = target === 'SELESAI';
    const konfirmasi = datang
      ? 'Tandai pelanggan datang?'
      : 'Tandai pelanggan tidak datang?';
    if (!window.confirm(konfirmasi)) return;
    try {
      await API.followupStatus(id, {
        status: target,
        alasan: datang
          ? 'Pelanggan datang sesuai jadwal.'
          : 'Pelanggan tidak datang.',
      });
      closeModal('#followupModal');
      toast(datang ? 'Ditandai datang.' : 'Ditandai tidak datang.', 'success');
      refreshFollowupViews();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  function openFollowupReschedule(id) {
    const detail = state.followupDetail;
    if (!detail || detail.item.id !== id) return;
    const item = detail.item;
    $('#followupRescheduleSubtitle').textContent =
      item.customer_nama +
      ' · ' +
      item.jenis_label +
      (item.tanggal_service
        ? ' · Jadwal saat ini ' + fmtDate(item.tanggal_service)
        : '');
    const dateEl = $('#followupRescheduleDate');
    dateEl.value = item.tanggal_service || '';
    $('#followupRescheduleNote').value = '';
    openModal('#followupRescheduleModal');
    setTimeout(() => dateEl.focus(), 80);
  }

  async function submitFollowupReschedule() {
    const detail = state.followupDetail;
    if (!detail) return;
    const item = detail.item;
    const dateEl = $('#followupRescheduleDate');
    const tanggal = dateEl ? dateEl.value : '';
    if (!tanggal) {
      toast('Isi tanggal service baru.', 'warning');
      if (dateEl) dateEl.focus();
      return;
    }
    const noteEl = $('#followupRescheduleNote');
    const note = noteEl ? noteEl.value.trim() : '';
    const button = $('#followupRescheduleSave');
    setBusy(button, true, 'Menyimpan...');
    try {
      await API.followupStatus(item.id, {
        status: 'AKAN_DATANG',
        tanggal_service: tanggal,
        alasan: note || 'Reschedule tanggal service.',
      });
      closeModal('#followupRescheduleModal');
      toast('Jadwal service diperbarui.', 'success');
      await openFollowupDetail(item.id);
      refreshFollowupViews();
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function openWhatsappChat(id) {
    let detail = state.followupDetail;
    if (!detail || detail.item.id !== id) {
      try {
        detail = await API.followupDetail(id);
        state.followupDetail = detail;
      } catch (err) {
        toast(err.message, 'error', 6000);
        return;
      }
    }
    const item = detail.item;
    const jenis =
      item.jenis === 'garansi'
        ? 'garansi'
        : item.jenis === 'piutang'
          ? 'piutang'
          : 'chat';
    try {
      const gate = await API.customerWaLink(item.customer_id, jenis);
      if (gate.peringatan) toast(gate.peringatan, 'warning', 7000);
      await openExternalLink(gate.link);
    } catch (err) {
      toast(err.message, 'warning', 7000);
    }
  }

  function followupStatusShortcutHtml(item) {
    const jadwal = FOLLOWUP_JADWAL_JENIS.indexOf(item.jenis) >= 0;
    const akanDatang = item.status === 'AKAN_DATANG';
    const berkendala =
      item.jenis === 'prospek' && item.status === 'MASIH_KENDALA';
    const piutang = item.jenis === 'piutang';
    const locked =
      (jadwal || item.jenis === 'prospek') && !item.sudah_followup;
    const jadwalOptions =
      '<option value="SELESAI">Datang</option>' +
      '<option value="TIDAK_DATANG">Tidak datang</option>' +
      '<option value="AKAN_DATANG">Akan datang service (wajib tanggal)</option>' +
      '<option value="MASIH_KENDALA">Belum bisa dihubungi lagi</option>' +
      '<option value="ARSIP">Tidak perlu lagi</option>';
    let options;
    if (berkendala) {
      options =
        '<option value="SELESAI">Sudah datang</option>' +
        '<option value="TIDAK_DATANG">Tidak datang</option>' +
        '<option value="AKAN_DATANG">Reschedule (wajib tanggal)</option>';
    } else if (jadwal) {
      options = akanDatang
        ? '<option value="SELESAI">Datang</option>' +
          '<option value="TIDAK_DATANG">Tidak datang</option>' +
          '<option value="AKAN_DATANG">Reschedule (ubah tanggal)</option>'
        : jadwalOptions;
    } else if (piutang) {
      options =
        '<option value="JANJI_BAYAR">Janji bayar (wajib tanggal)</option>' +
        '<option value="MASIH_KENDALA">Belum bisa</option>' +
        '<option value="SUDAH_BAYAR">Sudah bayar (cek sisa)</option>' +
        '<option value="SUDAH_FOLLOWUP">Tidak merespons</option>';
    } else {
      options =
        '<option value="BARU">Masih bagus</option>' +
        '<option value="MASIH_KENDALA">Masih kendala / belum bisa</option>' +
        '<option value="AKAN_DATANG">Akan datang service</option>' +
        '<option value="ARSIP">Tidak perlu lagi</option>';
    }
    const dateField =
      '<label class="field"><span>Tanggal service/kunjungan</span>' +
      '<input type="date" class="input" id="followupShortcutTanggal" value="' +
      esc(item.tanggal_service || '') +
      '"></label>';
    const janjiField =
      '<label class="field"><span>Tanggal janji bayar</span>' +
      '<input type="date" class="input" id="followupShortcutJanji" value="' +
      esc(item.janji_bayar || '') +
      '"></label>';
    const ops = (state.config && state.config.ops) || {};
    const tundaShort = intValue(ops.belum_bisa_hari, 14);
    const tundaLong = intValue(ops.belum_bisa_panjang_hari, 28);
    const tundaField =
      '<label class="field"><span>Hubungi lagi setelah</span>' +
      '<select class="input" id="followupShortcutTunda">' +
      '<option value="' + tundaShort + '">2 minggu (' + tundaShort + ' hari)</option>' +
      '<option value="' + tundaLong + '">4 minggu (' + tundaLong + ' hari)</option>' +
      '</select></label>';
    return (
      '<div class="followup-form">' +
      '<div class="form-grid">' +
      '<label class="field"><span>Status</span><select class="input" id="followupShortcutStatus"' +
      (locked ? ' disabled' : '') +
      '><option value="">Pilih status</option>' +
      options +
      '</select></label>' +
      dateField +
      (piutang ? janjiField : '') +
      tundaField +
      '</div>' +
      '<label class="field"><span>Catatan</span>' +
      '<input type="text" class="input" id="followupShortcutAlasan" maxlength="500" placeholder="Opsional"></label>' +
      (locked
        ? '<p class="tiny muted">Lakukan Ingatkan dulu sebelum mengubah status.</p>'
        : '') +
      '</div>'
    );
  }

  async function openFollowupStatusShortcut(id) {
    let detail;
    try {
      detail = await API.followupDetail(id);
      state.followupDetail = detail;
    } catch (err) {
      toast(err.message, 'error', 6000);
      return;
    }
    const item = detail.item;
    state.followupStatusDetail = detail;
    $('#followupStatusTitle').textContent = item.customer_nama;
    $('#followupStatusSubtitle').textContent =
      item.jenis_label + ' · ' + item.judul + ' · ' + item.status_label;
    $('#followupStatusBody').innerHTML = followupStatusShortcutHtml(item);
    const save = $('#followupStatusSave');
    if (save) {
      save.disabled =
        (FOLLOWUP_JADWAL_JENIS.indexOf(item.jenis) >= 0 ||
          item.jenis === 'prospek') &&
        !item.sudah_followup;
    }
    openModal('#followupStatusModal');
  }

  async function submitFollowupStatusShortcut() {
    const detail = state.followupStatusDetail;
    if (!detail) return;
    const item = detail.item;
    const select = $('#followupShortcutStatus');
    const target = select ? select.value : '';
    if (!target) {
      toast('Pilih status terlebih dahulu.', 'warning');
      if (select) select.focus();
      return;
    }
    const payload = { status: target };
    if (target === 'AKAN_DATANG') {
      const tanggalEl = $('#followupShortcutTanggal');
      const tanggal = tanggalEl ? tanggalEl.value : '';
      if (!tanggal) {
        toast('Isi tanggal service.', 'warning');
        if (tanggalEl) tanggalEl.focus();
        return;
      }
      payload.tanggal_service = tanggal;
    }
    if (target === 'JANJI_BAYAR') {
      const janjiEl = $('#followupShortcutJanji');
      const janji = janjiEl ? janjiEl.value : '';
      if (!janji) {
        toast('Isi tanggal janji bayar.', 'warning');
        if (janjiEl) janjiEl.focus();
        return;
      }
      payload.janji_bayar = janji;
    }
    if (target === 'MASIH_KENDALA') {
      const tundaEl = $('#followupShortcutTunda');
      payload.tunda_hari = parseInt(tundaEl ? tundaEl.value : '14', 10) || 14;
    }
    const reasonEl = $('#followupShortcutAlasan');
    const reason = reasonEl ? reasonEl.value.trim() : '';
    if (reason) {
      payload.alasan = reason;
    } else if (target === 'TIDAK_DATANG') {
      payload.alasan = 'Pelanggan tidak akan datang.';
    } else if (target === 'SELESAI') {
      payload.alasan = 'Pelanggan datang.';
    } else if (target === 'ARSIP') {
      payload.alasan = 'Tidak perlu lagi.';
    }
    const berkendala =
      item.jenis === 'prospek' && item.status === 'MASIH_KENDALA';
    const targetLabel = berkendala
      ? target === 'SELESAI'
        ? 'Sudah datang'
        : target === 'TIDAK_DATANG'
          ? 'Tidak datang'
          : target === 'AKAN_DATANG'
            ? 'Reschedule'
            : target
      : target === 'MASIH_KENDALA'
        ? item.jenis === 'piutang'
          ? 'Belum bisa'
          : 'Masih kendala / belum bisa'
        : target === 'JANJI_BAYAR'
          ? 'Janji bayar'
          : item.jenis === 'prospek'
            ? target === 'BARU'
              ? 'Masih bagus'
              : target === 'AKAN_DATANG'
                ? 'Akan datang service'
                : target === 'ARSIP'
                  ? 'Tidak perlu lagi'
                  : FOLLOWUP_STATUS_LABELS[target] || target
            : FOLLOWUP_STATUS_LABELS[target] || target;
    if (
      !berkendala &&
      item.jenis === 'prospek' &&
      target === item.status &&
      target !== 'AKAN_DATANG'
    ) {
      toast('Status prospek sudah "' + targetLabel + '".', 'warning');
      return;
    }
    if (
      item.jenis === 'prospek' &&
      !window.confirm(
        'Ubah status prospek ' +
          item.customer_nama +
          ' menjadi "' +
          targetLabel +
          '"?'
      )
    ) {
      return;
    }
    const button = $('#followupStatusSave');
    setBusy(button, true, 'Menyimpan...');
    try {
      await API.followupStatus(item.id, payload);
      closeModal('#followupStatusModal');
      state.followupStatusDetail = null;
      toast('Status follow-up diperbarui.', 'success');
      refreshFollowupViews();
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function saveCustomerContact(customerId) {
    const consent = $('#customerWaConsent');
    const dnc = $('#customerDnc');
    if (!consent || !dnc) return;
    try {
      const updated = await API.updateCustomerContact(customerId, {
        wa_consent: Boolean(consent.checked),
        do_not_contact: Boolean(dnc.checked),
      });
      if (state.detailCustomer && state.detailCustomer.id === updated.id) {
        Object.assign(state.detailCustomer, updated);
      }
      const row = (state.customers || []).find((item) => item.id === updated.id);
      if (row) Object.assign(row, updated);
      toast('Preferensi pesan disimpan.', 'success');
      refreshFollowupViews();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  /* ------------------------------- Piutang -------------------------------- */
  function openReceivables(customerId) {
    state.receivablesCustomerId = customerId || null;
    state.receivables = null;
    state.receivablesExpanded = new Set(customerId ? [customerId] : []);
    const subtitle = $('#receivablesSubtitle');
    if (subtitle) {
      subtitle.textContent = customerId
        ? 'Nota belum lunas pelanggan ini.'
        : 'Nota yang belum lunas.';
    }
    const body = $('#receivablesBody');
    if (body) body.innerHTML = '<div class="empty-state sm">Memuat piutang...</div>';
    openModal('#receivablesModal');
    loadReceivables();
  }

  async function loadReceivables() {
    const body = $('#receivablesBody');
    if (!body) return;
    try {
      const data = state.receivablesCustomerId
        ? await API.customerReceivables(state.receivablesCustomerId)
        : await API.receivables();
      state.receivables = data;
      renderReceivables();
    } catch (err) {
      body.innerHTML =
        '<div class="empty-state sm">Piutang gagal dimuat. Coba lagi.</div>';
    }
  }

  function receivableCustomerRemindButton(customer, records) {
    const perluTelepon = records.some((record) => record.perlu_telepon);
    if (perluTelepon) {
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="Pengingat piutang sudah mencapai batas. Hubungi pelanggan lewat telepon.">Perlu telepon</button>'
      );
    }
    const allReminded = records.every((record) => record.sudah_diingatkan);
    if (allReminded) {
      const latest = records.reduce(
        (acc, record) =>
          record.diingatkan_pada && (!acc || record.diingatkan_pada > acc)
            ? record.diingatkan_pada
            : acc,
        null
      );
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="Sudah diingatkan ' +
        esc(fmtDateTime(latest)) +
        '. Ubah jatuh tempo per nota untuk mengingatkan lagi.">Diingatkan</button>'
      );
    }
    const eligible = records.some(
      (record) => !record.sudah_diingatkan && record.bisa_diingatkan
    );
    if (!eligible) {
      const nextTimes = records
        .filter((record) => record.pengingat_berikutnya)
        .map((record) => record.pengingat_berikutnya)
        .sort();
      const pending = records
        .filter((record) => !record.sudah_diingatkan && record.jatuh_tempo)
        .map((record) => record.jatuh_tempo)
        .sort();
      const dueReached = records.some(
        (record) =>
          !record.sudah_diingatkan &&
          (!record.jatuh_tempo || record.jatuh_tempo <= todayISO())
      );
      const title =
        !isFollowupWindowOpen() && dueReached
          ? 'Pengingat hanya bisa dikirim antara pukul ' +
            followupWindow().label +
            '.'
          : nextTimes.length
            ? 'Pengingat berikutnya bisa dikirim setelah ' +
              fmtDateTime(nextTimes[0]) +
              '.'
            : pending.length
              ? 'Pengingat bisa dikirim mulai ' + fmtDate(pending[0]) + '.'
              : 'Pengingat belum bisa dikirim.';
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="' +
        esc(title) +
        '">Ingatkan</button>'
      );
    }
    return (
      '<button type="button" class="btn btn-outline btn-xs" data-action="receivables-remind-customer" data-id="' +
      customer.customer_id +
      '">Ingatkan</button>'
    );
  }

  function receivableRemindButton(record) {
    if (record.perlu_telepon) {
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="Pengingat piutang sudah mencapai batas. Hubungi pelanggan lewat telepon.">Perlu telepon</button>'
      );
    }
    if (record.sudah_diingatkan) {
      const next = record.pengingat_berikutnya
        ? ' Pengingat berikutnya setelah ' +
          fmtDateTime(record.pengingat_berikutnya) +
          '.'
        : '';
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="Sudah diingatkan ' +
        esc(fmtDateTime(record.diingatkan_pada)) +
        '.' +
        esc(next) +
        '">Diingatkan</button>'
      );
    }
    if (record.bisa_diingatkan === false) {
      const dueReached =
        !record.jatuh_tempo || record.jatuh_tempo <= todayISO();
      const title =
        !isFollowupWindowOpen() && dueReached
          ? 'Pengingat hanya bisa dikirim antara pukul ' +
            followupWindow().label +
            '.'
          : record.tunda_sampai
            ? 'Ditunda sampai ' + fmtDateTime(record.tunda_sampai) + '.'
            : record.pengingat_berikutnya
              ? 'Pengingat berikutnya bisa dikirim setelah ' +
                fmtDateTime(record.pengingat_berikutnya) +
                '.'
              : 'Pengingat bisa dikirim mulai ' +
                fmtDate(record.jatuh_tempo) +
                '.';
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="' +
        esc(title) +
        '">Ingatkan</button>'
      );
    }
    return (
      '<button type="button" class="btn btn-outline btn-xs" data-action="receivable-remind" data-id="' +
      record.id +
      '">Ingatkan</button>'
    );
  }

  function receivableChatButton(customer) {
    if (!waLink(customer.nomor_hp)) {
      return (
        '<button type="button" class="btn btn-outline btn-xs" disabled title="Nomor WhatsApp pelanggan belum valid">Chat</button>'
      );
    }
    return (
      '<button type="button" class="btn btn-outline btn-xs" data-action="receivable-chat" data-id="' +
      customer.customer_id +
      '">Chat</button>'
    );
  }

  function receivableDueCell(record) {
    const cadence = record.perlu_telepon
      ? 'Perlu telepon'
      : record.pengingat_ke
        ? 'Pengingat ' + intValue(record.pengingat_ke, 0) + 'x' +
          (record.pengingat_berikutnya
            ? ' · berikut ' + fmtDateTime(record.pengingat_berikutnya)
            : '')
        : '';
    return (
      '<div class="receivable-due"><span class="receivable-due-date">' +
      esc(record.jatuh_tempo ? fmtDate(record.jatuh_tempo) : 'Belum diatur') +
      '</span><button type="button" class="receivable-due-edit" data-action="receivable-reschedule" data-id="' +
      record.id +
      '">' +
      (record.jatuh_tempo ? 'Ubah' : 'Atur') +
      '</button>' +
      (cadence ? '<span class="cell-sub">' + esc(cadence) + '</span>' : '') +
      '</div>'
    );
  }

  function receivableCustomerDueRecord(customer) {
    const records = customer.records || [];
    if (!records.length) return null;
    const nearest = customer.jatuh_tempo_terdekat;
    if (nearest) {
      const match = records.find((row) => row.jatuh_tempo === nearest);
      if (match) return match;
    }
    return records[0];
  }

  function renderReceivables() {
    const body = $('#receivablesBody');
    if (!body) return;
    const data = state.receivables;
    if (!data || !(data.items || []).length) {
      body.innerHTML =
        '<div class="empty-state sm">Tidak ada piutang berjalan.</div>';
      return;
    }
    const summary =
      '<p class="muted">' +
      intValue(data.jumlah_pelanggan, 0) +
      ' pelanggan · ' +
      intValue(data.jumlah_nota, 0) +
      ' nota · total sisa ' +
      fmtRp(data.total_sisa) +
      '</p>';
    const groups = data.items
      .map((customer) => {
        const records = customer.records || [];
        const expanded = state.receivablesExpanded.has(customer.customer_id);
        const dueRecord = receivableCustomerDueRecord(customer);
        const isMulti = records.length > 1;
        const remindButton = isMulti
          ? receivableCustomerRemindButton(customer, records)
          : dueRecord
            ? receivableRemindButton(dueRecord)
            : '';
        const rows = records
          .map(
            (record) =>
              '<tr><td><button type="button" class="btn btn-ghost btn-xs" data-action="record-detail" data-id="' +
              record.id +
              '">' +
              esc(record.no_nota) +
              '</button></td><td>' +
              esc(fmtDate(record.waktu_service)) +
              '</td><td class="num">' +
              fmtRp(record.sisa_bayar) +
              '</td><td>' +
              receivableDueCell(record) +
              '</td><td>' +
              (record.overdue
                ? '<span class="badge red">' +
                  esc(record.umur_bucket) +
                  '</span>'
                : '<span class="badge gray">' +
                  esc(record.umur_bucket) +
                  '</span>') +
              '</td><td class="receivable-actions">' +
              '<button type="button" class="btn btn-primary btn-xs" data-action="record-payment" data-id="' +
              record.id +
              '">Pelunasan</button>' +
              (isMulti ? remindButton : receivableRemindButton(record)) +
              receivableChatButton(customer) +
              '</td></tr>'
          )
          .join('');
        const noteCount =
          records.length > 1
            ? '<button type="button" class="btn btn-ghost btn-xs" data-action="receivable-toggle" data-id="' +
              customer.customer_id +
              '">' +
              records.length +
              ' nota ' +
              (expanded ? '▾' : '▸') +
              '</button>'
            : '';
        const nameHtml = dueRecord
          ? '<button type="button" class="receivable-name" data-action="record-detail" data-id="' +
            dueRecord.id +
            '">' +
            esc(customer.nama) +
            '</button>'
          : '<strong>' + esc(customer.nama) + '</strong>';
        const noteMeta = dueRecord
          ? '<button type="button" class="cell-link pengerjaan-nota" data-action="record-detail" data-id="' +
            dueRecord.id +
            '">' +
            esc(dueRecord.no_nota) +
            '</button><span class="cell-sub">' +
            esc(fmtDate(dueRecord.waktu_service)) +
            '</span>'
          : '';
        return (
          '<div class="receivable-group"><div class="receivable-head"><div class="receivable-title">' +
          nameHtml +
          '<span>' +
          esc(customer.nomor_hp) +
          '</span></div><div class="receivable-head-right">' +
          (dueRecord && !isMulti ? receivableDueCell(dueRecord) : '') +
          noteCount +
          '</div></div>' +
          '<div class="pengerjaan-row"><div class="pengerjaan-meta">' +
          noteMeta +
          '</div><div class="pengerjaan-actions">' +
          remindButton +
          receivableChatButton(customer) +
          (dueRecord
            ? '<button type="button" class="btn btn-primary btn-xs" data-action="record-payment" data-id="' +
              dueRecord.id +
              '">Pelunasan</button>'
            : '') +
          '</div></div>' +
          (expanded
            ? '<div class="receivable-table-wrap"><table class="receivable-records"><thead><tr><th>Nota</th><th>Tanggal</th><th class="num">Sisa</th><th>Jatuh tempo</th><th>Umur</th><th>Aksi</th></tr></thead><tbody>' +
              rows +
              '</tbody></table></div>'
            : '') +
          '</div>'
        );
      })
      .join('');
    body.innerHTML = summary + '<div class="receivable-list">' + groups + '</div>';
  }

  async function remindReceivable(recordId) {
    const button = $(
      '[data-action="receivable-remind"][data-id="' + recordId + '"]'
    );
    setBusy(button, true, 'Membuka...');
    try {
      const result = await API.remindReceivable(recordId);
      const opened = await openExternalLink(result.link);
      if (opened) {
        toast('Pengingat dibuka di WhatsApp. Tekan kirim untuk mengirim pesan.', 'success');
      }
      await loadReceivables();
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function remindCustomerReceivables(customerId) {
    const button = $(
      '[data-action="receivables-remind-customer"][data-id="' +
        customerId +
        '"]'
    );
    setBusy(button, true, 'Membuka...');
    try {
      const result = await API.remindCustomerReceivables(customerId);
      const opened = await openExternalLink(result.link);
      if (opened) {
        toast(
          'Pengingat dibuka di WhatsApp. Tekan kirim untuk mengirim pesan.',
          'success'
        );
      }
      await loadReceivables();
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function chatReceivableCustomer(customerId) {
    try {
      const gate = await API.customerWaLink(customerId, 'piutang');
      if (gate.peringatan) toast(gate.peringatan, 'warning', 7000);
      await openExternalLink(gate.link);
    } catch (err) {
      toast(err.message, 'warning', 7000);
    }
  }

  function findReceivableRecord(recordId) {
    const data = state.receivables;
    if (!data) return null;
    for (const customer of data.items || []) {
      const found = (customer.records || []).find((row) => row.id === recordId);
      if (found) return found;
    }
    return null;
  }

  function openRescheduleModal(recordId) {
    const record = findReceivableRecord(recordId);
    if (!record) return;
    state.rescheduleTarget = record;
    const today = todayISO();
    const input = $('#rescheduleDate');
    input.min = today;
    input.value = record.jatuh_tempo && record.jatuh_tempo >= today
      ? record.jatuh_tempo
      : today;
    $('#rescheduleSubtitle').textContent =
      record.no_nota +
      ' · sisa ' +
      fmtRp(record.sisa_bayar) +
      (record.jatuh_tempo ? ' · tempo ' + fmtDate(record.jatuh_tempo) : ' · belum ada tempo') +
      (record.sudah_diingatkan ? ' · sudah diingatkan' : '');
    openModal('#rescheduleModal');
    input.focus();
  }

  async function submitReschedule(event) {
    if (event) event.preventDefault();
    const record = state.rescheduleTarget;
    if (!record) return;
    const value = ($('#rescheduleDate').value || '').trim();
    if (!value) {
      toast('Tanggal jatuh tempo wajib diisi.', 'warning');
      return;
    }
    const button = $('#rescheduleSave');
    setBusy(button, true, 'Menyimpan...');
    try {
      await API.rescheduleDueDate(record.id, { jatuh_tempo: value });
      closeModal('#rescheduleModal');
      state.rescheduleTarget = null;
      toast(
        'Jatuh tempo diperbarui. Pengingat aktif lagi pada tanggal baru.',
        'success'
      );
      await loadReceivables();
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  /* --------------------------- Kendaraan selesai --------------------------- */
  function openPengerjaanList() {
    state.pengerjaan = null;
    const body = $('#pengerjaanBody');
    if (body) body.innerHTML = '<div class="empty-state sm">Memuat kendaraan...</div>';
    openModal('#pengerjaanModal');
    loadPengerjaan();
  }

  async function loadPengerjaan() {
    const body = $('#pengerjaanBody');
    if (!body) return;
    try {
      const data = await API.pengerjaan();
      state.pengerjaan = data;
      renderPengerjaan();
    } catch (err) {
      body.innerHTML =
        '<div class="empty-state sm">Daftar kendaraan gagal dimuat. Coba lagi.</div>';
    }
  }

  function renderPengerjaan() {
    const body = $('#pengerjaanBody');
    if (!body) return;
    const data = state.pengerjaan;
    const items = (data && data.items) || [];
    if (!items.length) {
      body.innerHTML =
        '<div class="empty-state sm">Tidak ada kendaraan yang menunggu diambil.</div>';
      return;
    }
    const summary = '<p class="muted">' + items.length + ' nota · unit masih di bengkel</p>';
    const rows = items
      .map((item) => {
        const sisaHtml =
          moneyToCents(item.sisa_bayar) > 0
            ? '<span class="receivable-total">' + fmtRp(item.sisa_bayar) + '</span>'
            : '<span class="badge gray">Lunas</span>';
        const waButton = item.sudah_dikabari
          ? '<button type="button" class="btn btn-outline btn-xs" disabled title="Sudah dikabari ' +
            esc(fmtDateTime(item.dikabari_pada)) +
            '.">Sudah dikabari</button>'
          : '<button type="button" class="btn btn-primary btn-xs" data-action="record-completion" data-id="' +
            item.record_id +
            '">Kabari WA</button>';
        const statusBadge =
          '<span class="badge gray">' +
          esc(item.status_label || PENGERJAAN_STATUS_LABELS[item.status_pengerjaan] || item.status_pengerjaan) +
          '</span>';
        const ageLabel =
          '<span class="cell-sub">' +
          intValue(item.hari_di_bengkel, 0) +
          ' hari di bengkel' +
          (item.terlambat ? ' · terlambat' : '') +
          '</span>';
        return (
          '<div class="receivable-group is-clickable" role="button" tabindex="0" title="Buka nota" data-action="record-detail" data-id="' +
          item.record_id +
          '"><div class="receivable-head"><div class="pengerjaan-info"><strong>' +
          esc(item.customer_nama) +
          '</strong><span>' +
          esc(item.unit_deskripsi) +
          ' · ' +
          esc(item.nomor_hp || '-') +
          '</span></div>' +
          sisaHtml +
          '</div><div class="pengerjaan-row"><div class="pengerjaan-meta">' +
          '<strong class="pengerjaan-nota">' +
          esc(item.no_nota) +
          '</strong><span class="cell-sub">' +
          esc(fmtDate(item.waktu_service)) +
          '</span>' + statusBadge + ageLabel + '</div><div class="pengerjaan-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="pengerjaan-status" data-id="' +
          item.id +
          '">Status</button>' +
          waButton +
          '<button type="button" class="btn btn-outline btn-xs" data-action="pengerjaan-taken" data-id="' +
          item.id +
          '">Sudah diambil</button>' +
          '</div></div></div>'
        );
      })
      .join('');
    body.innerHTML = summary + '<div class="receivable-list">' + rows + '</div>';
  }

  function findPengerjaanItem(id) {
    const data = state.pengerjaan;
    if (!data) return null;
    return (data.items || []).find((row) => row.id === id) || null;
  }

  async function markPengerjaanTaken(id) {
    const item = findPengerjaanItem(id);
    const sisa = item ? moneyToCents(item.sisa_bayar) : 0;
    if (item && sisa > 0) {
      if (
        !window.confirm(
          'Nota masih memiliki sisa ' +
            fmtRp(item.sisa_bayar) +
            '. Unit baru ditandai diambil setelah pembayaran dicatat. Buka nota sekarang?'
        )
      ) {
        return;
      }
      state.pendingPengerjaan = { markerId: id, recordId: item.record_id };
      await openRecordForPayment(item.record_id);
      if ($('#recordModal').classList.contains('hidden')) {
        state.pendingPengerjaan = null;
      }
      return;
    }
    if (!window.confirm('Tandai unit sudah diambil pelanggan?')) return;
    const button = $(
      '[data-action="pengerjaan-taken"][data-id="' + id + '"]'
    );
    setBusy(button, true, 'Menyimpan...');
    try {
      await API.pengerjaanTaken(id);
      toast('Unit ditandai sudah diambil.', 'success');
      await loadPengerjaan();
      loadDashboard();
      if (!$('#view-followup').classList.contains('hidden')) {
        loadFollowupPage();
      }
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }


  async function openPengerjaanStatus(id) {
    try {
      const detail = await API.pengerjaanDetail(id);
      const item = detail.item;
      state.pengerjaanStatus = detail;
      $('#pengerjaanStatusTitle').textContent = item.customer_nama;
      $('#pengerjaanStatusSubtitle').textContent =
        item.no_nota + ' · ' + (item.unit_deskripsi || '-');
      const select = $('#pengerjaanStatusSelect');
      select.value = item.status_pengerjaan;
      $('#pengerjaanJanjiAmbil').value = item.janji_ambil || '';
      $('#pengerjaanStatusCatatan').value = '';
      const events = detail.events || [];
      $('#pengerjaanStatusHistory').innerHTML = events.length
        ? '<h4 class="detail-section-title">Riwayat status</h4>' +
          '<div class="followup-event-list">' +
          events
            .map(
              (event) =>
                '<div class="followup-event"><div><strong>' +
                esc(PENGERJAAN_STATUS_LABELS[event.from_status] || event.from_status || '-') +
                ' → ' +
                esc(PENGERJAAN_STATUS_LABELS[event.to_status] || event.to_status) +
                '</strong>' +
                (event.catatan ? '<div>' + esc(event.catatan) + '</div>' : '') +
                '<small>' +
                esc(fmtDateTime(event.created_at)) +
                ' · ' +
                esc(event.operator || '-') +
                '</small></div></div>'
            )
            .join('') +
          '</div>'
        : '';
      openModal('#pengerjaanStatusModal');
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function submitPengerjaanStatus() {
    const detail = state.pengerjaanStatus;
    if (!detail) return;
    const item = detail.item;
    const target = $('#pengerjaanStatusSelect').value;
    const janji = $('#pengerjaanJanjiAmbil').value || null;
    const catatan = $('#pengerjaanStatusCatatan').value.trim();
    const button = $('#pengerjaanStatusSave');
    setBusy(button, true, 'Menyimpan...');
    try {
      const result = await API.pengerjaanStatus(item.id, {
        status: target,
        janji_ambil: janji,
        catatan: catatan || null,
      });
      closeModal('#pengerjaanStatusModal');
      state.pengerjaanStatus = null;
      toast('Status pengerjaan diperbarui.', 'success');
      await loadPengerjaan();
      loadDashboard();
      if (!$('#view-followup').classList.contains('hidden')) {
        loadFollowupPage();
      }
      if (
        state.detailRecord &&
        state.detailRecord.id === item.record_id &&
        !$('#recordModal').classList.contains('hidden')
      ) {
        await openRecordDetail(item.record_id);
      }
      if (target !== item.status_pengerjaan && result.wa_text) {
        openWaPreview({
          judul: 'Status pengerjaan · ' + item.no_nota,
          subtitle: 'Periksa pesan status sebelum dibuka.',
          nomor: item.nomor_hp,
          text: result.wa_text,
          note: 'Membuka WhatsApp akan mencatat pesan pengerjaan. Kasir tetap menekan kirim.',
          onOpen: async (text) => {
            await API.recordWhatsapp(item.record_id, {
              status: 'DIBUKA',
              jenis: 'pengerjaan',
              pesan: text,
            });
            await loadPengerjaan();
          },
        });
      }
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  function openDashboardNotas(filter) {
    const today = state.dashboardToday || [];
    let list = today;
    let title = 'Nota hari ini';
    let note = fmtDate(todayISO());

    if (filter === 'cash') {
      list = today.filter((record) => record.metode_bayar !== 'TRANSFER');
      title = 'Nota tunai hari ini';
    } else if (filter === 'transfer') {
      list = today.filter((record) => record.metode_bayar === 'TRANSFER');
      title = 'Nota transfer hari ini';
    }

    openNotaList(title, list, { note: note });
  }

  function openReportNotas(filter) {
    const rows = state.reportRows || [];
    const period = state.reportLabel;
    let list = rows;
    let title = 'Semua nota · ' + period;

    if (filter === 'cash') {
      list = rows.filter((record) => record.metode_bayar !== 'TRANSFER');
      title = 'Nota tunai · ' + period;
    } else if (filter === 'transfer') {
      list = rows.filter((record) => record.metode_bayar === 'TRANSFER');
      title = 'Nota transfer · ' + period;
    } else if (filter === 'profit') {
      title = 'Laba bersih sparepart · ' + period;
    }

    openNotaList(title, list, { showProfit: true });
  }

  function openDayNotas(date) {
    if (!date) return;
    const list = (state.reportRows || []).filter(
      (record) => String(record.waktu_service || '').slice(0, 10) === date
    );
    openNotaList('Nota ' + fmtDate(date), list, { showProfit: true });
  }

  async function openStockLevelModal(kind) {
    try {
      if (!state.stock.length) await loadStock();
      const low = kind === 'low';
      const rows = state.stock.filter(
        low ? isLowStockItem : isOutOfStockItem
      );
      openStatListModal({
        title: low ? 'Stok menipis' : 'Stok habis',
        subtitle:
          rows.length +
          (low ? ' barang perlu dibeli.' : ' barang tidak tersedia.'),
        head:
          '<tr><th>Barang</th><th class="text-center">Stok</th><th class="text-center">Minimum</th></tr>',
        rows: rows.map(
          (item) =>
            '<tr><td><span class="cell-primary">' +
            esc(item.nama) +
            '</span></td><td class="text-center">' +
            intValue(item.jumlah, 0) +
            '</td><td class="text-center">' +
            effectiveStockMinimum(item) +
            '</td></tr>'
        ),
        empty: low
          ? 'Tidak ada stok menipis.'
          : 'Tidak ada stok habis.',
      });
    } catch (err) {
      toast('Data stok gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  async function openSoldPartsModal() {
    try {
      const sold = await API.soldParts(todayISO(), todayISO());
      const items = sold && Array.isArray(sold.items) ? sold.items : [];
      openStatListModal({
        title: 'Sparepart keluar hari ini',
        subtitle:
          intValue(sold && sold.total_qty, 0) +
          ' sparepart dari nota servis dan pembelian part · ' +
          fmtDate(todayISO()),
        head:
          '<tr><th>Barang</th><th class="text-center">Qty</th><th class="text-right">Harga akhir</th><th class="text-right">Subtotal</th><th>Waktu</th><th>No. nota</th></tr>',
        rows: items.map(
          (item) =>
            '<tr class="is-clickable" data-action="record-detail" data-id="' +
            item.service_record_id +
            '"><td><span class="cell-primary">' +
            esc(item.nama_part || '-') +
            '</span><span class="cell-sub">' +
            esc(item.customer_nama || '-') +
            '</span></td><td class="text-center">' +
            intValue(item.jumlah, 0) +
            '</td><td class="text-right money">' +
            fmtRp(item.harga_satuan) +
            '</td><td class="text-right money">' +
            fmtRp(item.subtotal) +
            '</td><td>' +
            esc(fmtDateTime(item.waktu_service)) +
            '</td><td>' +
            esc(item.no_nota) +
            '</td></tr>'
        ),
        empty: 'Belum ada sparepart keluar hari ini.',
      });
    } catch (err) {
      toast('Sparepart keluar hari ini gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  async function refreshAfterRecordChange(id) {
    await openRecordDetail(id);
    loadHistory($('#historySearch').value.trim());
    loadStock();
    loadDashboard();
    loadReport();
  }

  async function handleAction(action, id, dataset) {
    const data = dataset || {};

    if (action === 'record-detail') {
      openRecordDetail(id);
      return;
    }
    if (action === 'customer-detail') {
      openCustomerDetail(id);
      return;
    }
    if (action === 'dashboard-notas') {
      openDashboardNotas(data.filter);
      return;
    }
    if (action === 'report-notas') {
      openReportNotas(data.filter);
      return;
    }
    if (action === 'day-notas') {
      openDayNotas(data.date);
      return;
    }
    if (action === 'open-followup') {
      openFollowupList(
        data.jenis || '',
        data.status || '',
        data.excludeStatus || ''
      );
      return;
    }
    if (action === 'customer-contact-save') {
      await saveCustomerContact(Number(target.dataset.id));
      return;
    }
    if (action === 'open-receivables') {
      openReceivables(null);
      return;
    }
    if (action === 'open-sold-parts') {
      await openSoldPartsModal();
      return;
    }
    if (action === 'employee-detail') {
      openEmployeeDetail(id);
      return;
    }
    if (action === 'edit-employee') {
      const employee = state.employees.find((row) => row.id === id);
      if (employee) openEmployeeModal(employee);
      return;
    }
    if (action === 'archive-employee') {
      await archiveEmployee(id);
      return;
    }
    if (action === 'reactivate-employee') {
      await reactivateEmployee(id);
      return;
    }
    if (action === 'delete-employee') {
      await deleteEmployee(id);
      return;
    }
    if (action === 'employee-perf') {
      await openEmployeePerformance(id);
      return;
    }
    if (action === 'salary-history-all') {
      openSalaryHistoryModal();
      return;
    }
    if (action === 'debt-detail') {
      openDebtDetail(id);
      return;
    }
    if (action === 'edit-debt') {
      const debt = state.employeeDebts.find((row) => row.id === id);
      if (debt) openDebtModal(debt);
      return;
    }
    if (action === 'delete-debt') {
      await deleteEmployeeDebt(id);
      return;
    }
    if (action === 'employee-perf-load') {
      await loadEmployeePerformance();
      return;
    }
    if (action === 'employee-perf-detail') {
      openEmployeePerfDetail();
      return;
    }
    if (action === 'employee-commission-save') {
      await saveEmployeeCommission(id, Number(data.recordId));
      return;
    }
    if (action === 'edit-supplier') {
      const supplier = state.suppliers.find((row) => row.id === id);
      if (supplier) openSupplierModal(supplier);
      return;
    }
    if (action === 'archive-supplier') {
      await archiveSupplier(id);
      return;
    }
    if (action === 'reactivate-supplier') {
      await reactivateSupplier(id);
      return;
    }
    if (action === 'delete-supplier') {
      await deleteSupplier(id);
      return;
    }
    if (action === 'supplier-item-chat') {
      chatSupplierItem(id);
      return;
    }
    if (action === 'supplier-item-chat-pick') {
      await openSupplierItemChat(
        Number(target.dataset.id),
        Number(target.dataset.itemId)
      );
      return;
    }
    if (action === 'supplier-item-remove') {
      removeSupplierItem(id);
      return;
    }
    if (
      action === 'customer-stat-customers' ||
      action === 'customer-stat-units' ||
      action === 'customer-stat-mobil' ||
      action === 'customer-stat-radiator'
    ) {
      openCustomerStatList(action.replace('customer-stat-', ''));
      return;
    }
    if (action === 'customer-warranties') {
      openNotaList(
        'Nota bergaransi aktif',
        state.customerWarrantyRecords || [],
        { note: 'garansi masih aktif' }
      );
      return;
    }
    if (action === 'open-employee-debts') {
      try {
        const debts = await API.employeeDebts(null, true);
        openDebtHistoryModal(debts, 'Piutang karyawan');
      } catch (err) {
        toast('Piutang karyawan gagal dimuat. Coba lagi.', 'error', 6000);
      }
      return;
    }
    if (action === 'open-payroll') {
      openPayrollModal();
      return;
    }
    if (action === 'payroll-mark-paid') {
      const item = (state.payrollSummary?.items || []).find(
        (row) => row.employee_id === id
      );
      if (!item) return;
      if (!state.salaryPaymentsLoaded) await loadSalaryPayments();
      openPayrollPayModal(item);
      return;
    }
    if (action === 'payroll-pay-confirm') {
      submitPayrollPayment();
      return;
    }
    if (action === 'open-low-stock') {
      await openStockLevelModal('low');
      return;
    }
    if (action === 'open-stock-out') {
      await openStockLevelModal('out');
      return;
    }
    if (action === 'open-pengerjaan') {
      openPengerjaanList();
      return;
    }
    if (action === 'payment-fill-sisa') {
      fillPaymentSisa();
      return;
    }
    if (action === 'payment-fill-setengah') {
      fillPaymentSetengah();
      return;
    }
    if (action === 'record-payment') {
      await openRecordForPayment(id);
      return;
    }
    if (action === 'record-completion') {
      await openCompletionWhatsapp(id);
      return;
    }
    if (action === 'receivable-remind') {
      await remindReceivable(id);
      return;
    }
    if (action === 'receivable-reschedule') {
      openRescheduleModal(id);
      return;
    }
    if (action === 'receivable-chat') {
      await chatReceivableCustomer(id);
      return;
    }
    if (action === 'receivables-remind-customer') {
      await remindCustomerReceivables(id);
      return;
    }
    if (action === 'receivable-toggle') {
      const key = intValue(id, 0);
      if (state.receivablesExpanded.has(key)) {
        state.receivablesExpanded.delete(key);
      } else {
        state.receivablesExpanded.add(key);
      }
      renderReceivables();
      return;
    }

    if (action === 'followup-status-shortcut-save') {
      await submitFollowupStatusShortcut();
      return;
    }

    if (action === 'followup-reschedule-save') {
      await submitFollowupReschedule();
      return;
    }

    if (action === 'pengerjaan-status-save') {
      await submitPengerjaanStatus();
      return;
    }

    if (!id) return;

    if (action === 'pengerjaan-taken') {
      await markPengerjaanTaken(id);
      return;
    }

    if (action === 'pengerjaan-status') {
      await openPengerjaanStatus(id);
      return;
    }

    if (action === 'record-mark-workshop') {
      try {
        await API.pengerjaanCreate(id);
        toast('Unit ditandai masih di bengkel.', 'success');
        await openRecordDetail(id);
        await loadPengerjaan();
      } catch (err) {
        toast(err.message, 'error', 6000);
      }
      return;
    }

    if (action === 'followup-detail') {
      openFollowupDetail(id);
      return;
    }

    if (action === 'followup-wa') {
      await followupWhatsapp(id);
      return;
    }

    if (action === 'followup-chat') {
      openWhatsappChat(id);
      return;
    }

    if (action === 'followup-status-shortcut') {
      await openFollowupStatusShortcut(id);
      return;
    }

    if (action === 'followup-datang') {
      await submitFollowupPresence(id, 'SELESAI');
      return;
    }

    if (action === 'followup-tidak-datang') {
      await submitFollowupPresence(id, 'TIDAK_DATANG');
      return;
    }

    if (action === 'followup-reschedule') {
      openFollowupReschedule(id);
      return;
    }

    if (action === 'customer-receivables') {
      openReceivables(id);
      return;
    }

    if (action === 'payment-submit') {
      await submitPayment(id);
      return;
    }

    if (action === 'reprint') {
      try {
        const receipt = await API.receipt(id);
        showReceipt(receipt);
      } catch (err) {
        toast(err.message, 'error', 6000);
      }
      return;
    }

    if (action === 'claim') {
      if (!window.confirm('Proses klaim garansi untuk nota ini?')) return;
      try {
        await API.claim(id);
        toast('Klaim garansi tercatat.', 'success');
        loadHistory($('#historySearch').value.trim());
        loadDashboard();
      } catch (err) {
        toast(err.message, 'error', 7000);
      }
      return;
    }

    if (action === 'service-customer') {
      const customer = state.customerDirectory.find(
        (item) => item.id === id
      );
      if (customer) {
        navigate('pos');
        await chooseCustomer(customer);
      }
      return;
    }

    if (action === 'edit-stock') {
      const item = state.stock.find((stockItem) => stockItem.id === id);
      if (item) openStockModal(item);
      return;
    }

    if (action === 'delete-stock') {
      await deleteStock(id);
      return;
    }

    if (action === 'edit-jasa') {
      const jasa = state.jasa.find((item) => item.id === id);
      if (jasa) openJasaModal(jasa);
      return;
    }

    if (action === 'delete-jasa') {
      await deleteJasa(id);
    }
  }

  /* -------------------------------- Stock --------------------------------- */
  async function loadStock() {
    try {
      const results = await Promise.all([API.stock(), API.jasa()]);
      state.stock = results[0];
      state.jasa = results[1];
      populatePickers();
      populateEmployeeOptions();
      renderStock();
      renderJasa();
    } catch (err) {
      toast('Data stok gagal dimuat. Coba muat ulang.', 'error', 6000);
    }
  }

  function supplierNamesForStock(stockId) {
    if (state.config && state.config.ops && state.config.ops.supplier_aktif === false) {
      return '-';
    }
    return (
      state.suppliers
        .filter((supplier) =>
          (supplier.items || []).some((item) => item.id === stockId)
        )
        .map((supplier) => supplier.nama)
        .join(', ') || '-'
    );
  }

  function populateStockSuppliers(item) {
    const container = $('#stockSupplierList');
    if (!container) return;
    const selected = new Set(
      state.suppliers
        .filter((supplier) =>
          item && (supplier.items || []).some((row) => row.id === item.id)
        )
        .map((supplier) => supplier.id)
    );
    container.innerHTML =
      state.suppliers
        .filter((supplier) => supplier.aktif)
        .map(
          (supplier) =>
            '<label><input type="checkbox" value="' +
            supplier.id +
            '"' +
            (selected.has(supplier.id) ? ' checked' : '') +
            '> ' +
            esc(supplier.nama) +
            '</label>'
        )
        .join('') ||
      '<span class="tiny muted">Belum ada supplier.</span>';
  }

  function stockMinimumDefault() {
    return intValue(state.config && state.config.ops && state.config.ops.stok_minimum_default, 3);
  }

  function effectiveStockMinimum(item) {
    if (item.stok_minimum === null || item.stok_minimum === undefined) {
      return stockMinimumDefault();
    }
    return intValue(item.stok_minimum, 0);
  }

  function isLowStockItem(item) {
    const minimum = effectiveStockMinimum(item);
    const qty = intValue(item.jumlah, 0);
    return minimum > 0 && qty > 0 && qty <= minimum;
  }

  function isOutOfStockItem(item) {
    return intValue(item.jumlah, 0) <= 0;
  }

  function syncStockFilter() {
    $$('#stockFilterSwitch [data-stock-filter]').forEach((button) => {
      button.classList.toggle(
        'active',
        button.dataset.stockFilter === state.stockFilter
      );
    });
  }

  function renderStock() {
    const stockBody = $('#stockBody');
    if (!stockBody) return;

    const lowItems = state.stock.filter(isLowStockItem);
    const outItems = state.stock.filter(isOutOfStockItem);
    const visible =
      state.stockFilter === 'low'
        ? lowItems
        : state.stockFilter === 'out'
          ? outItems
          : state.stock;
    $('#stockSummary').textContent =
      state.stock.length +
      ' item · ' +
      lowItems.length +
      ' menipis · ' +
      outItems.length +
      ' habis';
    syncStockFilter();

    stockBody.innerHTML = visible
      .map((item) => {
        const out = isOutOfStockItem(item);
        const low = isLowStockItem(item);
        const badgeClass = out ? 'red' : low ? 'amber' : 'gray';
        const minimum = effectiveStockMinimum(item);
        const minimumText =
          item.stok_minimum === null || item.stok_minimum === undefined
            ? 'Bawaan ' + minimum
            : minimum > 0
              ? String(minimum)
              : 'Nonaktif';
        return (
          '<tr>' +
          '<td><span class="cell-sub">' +
          esc(item.kode || '-') +
          '</span></td>' +
          '<td><span class="cell-primary">' +
          esc(item.nama) +
          '</span></td>' +
          '<td class="cell-sub">' +
          esc(supplierNamesForStock(item.id)) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(item.harga_modal) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(item.harga_jual) +
          '</td>' +
          '<td class="text-center"><span class="badge ' +
          badgeClass +
          '">' +
          item.jumlah +
          '</span></td>' +
          '<td class="text-center"><span class="cell-sub">' +
          esc(minimumText) +
          '</span></td>' +
          '<td>' +
          (clampInterval(item.interval_servis_bulan) > 0
            ? '<span class="badge blue">' +
              clampInterval(item.interval_servis_bulan) +
              ' bulan</span>'
            : '<span class="cell-sub">Nonaktif</span>') +
          '</td>' +
          '<td class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="edit-stock" data-id="' +
          item.id +
          '">Edit</button>' +
          '<button type="button" class="btn btn-ghost btn-xs" data-action="delete-stock" data-id="' +
          item.id +
          '">Hapus</button>' +
          '</td>' +
          '</tr>'
        );
      })
      .join('');

    const empty = $('#stockEmpty');
    if (empty) {
      empty.textContent =
        state.stockFilter === 'low'
          ? 'Tidak ada stok menipis.'
          : state.stockFilter === 'out'
            ? 'Tidak ada stok habis.'
            : 'Belum ada data sparepart.';
      empty.classList.toggle('hidden', visible.length > 0);
    }
  }

  function renderJasa() {
    const jasaBody = $('#jasaBody');
    if (!jasaBody) return;

    $('#jasaSummary').textContent = state.jasa.length + ' tarif jasa';

    jasaBody.innerHTML = state.jasa
      .map(
        (jasa) =>
          '<tr>' +
          '<td><span class="cell-primary">' +
          esc(jasa.nama) +
          '</span></td>' +
          '<td class="text-right money">' +
          fmtRp(jasa.harga_standar) +
          '</td>' +
          '<td>' +
          (clampInterval(jasa.interval_servis_bulan) > 0
            ? '<span class="badge blue">' +
              clampInterval(jasa.interval_servis_bulan) +
              ' bulan</span>'
            : '<span class="cell-sub">Nonaktif</span>') +
          '</td>' +
          '<td class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="edit-jasa" data-id="' +
          jasa.id +
          '">Edit</button>' +
          '<button type="button" class="btn btn-ghost btn-xs" data-action="delete-jasa" data-id="' +
          jasa.id +
          '">Hapus</button>' +
          '</td>' +
          '</tr>'
      )
      .join('');

    $('#jasaEmpty').classList.toggle('hidden', state.jasa.length > 0);
  }

  function openStockModal(item) {
    state.editingStock = item || null;
    $('#stockModalTitle').textContent = item ? 'Edit sparepart' : 'Tambah sparepart';
    $('#stockId').value = item ? item.id : '';
    $('#stockKode').value = item ? item.kode || '' : '';
    $('#stockNama').value = item ? item.nama : '';
    setMoneyValue(
      $('#stockModalHarga'),
      item ? Math.round(Number(item.harga_modal) || 0) : 0
    );
    setMoneyValue(
      $('#stockJualHarga'),
      item ? Math.round(Number(item.harga_jual) || 0) : 0
    );
    $('#stockJumlah').value = item ? item.jumlah : '0';
    $('#stockIntervalInput').value = item
      ? clampInterval(item.interval_servis_bulan)
      : '0';
    $('#stockMinimum').value =
      item && item.stok_minimum !== null && item.stok_minimum !== undefined
        ? item.stok_minimum
        : '';
    populateStockSuppliers(item);
    if (!state.suppliers.length) {
      loadSuppliers().then(() => populateStockSuppliers(item));
    }
    openModal('#stockModal');
    setTimeout(() => $('#stockNama').focus(), 60);
  }

  async function handleStockSubmit(event) {
    event.preventDefault();
    const id = intValue($('#stockId').value, 0);
    const minimumRaw = $('#stockMinimum').value.trim();
    const payload = {
      kode: $('#stockKode').value.trim() || null,
      nama: $('#stockNama').value.trim(),
      harga_modal: String(parseMoney($('#stockModalHarga').value)),
      harga_jual: String(parseMoney($('#stockJualHarga').value)),
      jumlah: Math.max(0, intValue($('#stockJumlah').value, 0)),
      interval_servis_bulan: clampInterval($('#stockIntervalInput').value),
      stok_minimum:
        minimumRaw === '' ? null : Math.max(0, intValue(minimumRaw, 0)),
      supplier_ids:
        state.config && state.config.ops && state.config.ops.supplier_aktif === false
          ? undefined
          : $$('#stockSupplierList input:checked').map((input) =>
              Number(input.value)
            ),
    };

    try {
      if (id) await API.updateStock(id, payload);
      else await API.createStock(payload);
      closeModal('#stockModal');
      toast('Data sparepart tersimpan.', 'success');
      await loadStock();
      await loadSuppliers();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function deleteStock(id) {
    const item = state.stock.find((stockItem) => stockItem.id === id);
    if (!item) return;
    if (!window.confirm('Hapus sparepart "' + item.nama + '"?')) return;

    try {
      await API.deleteStock(id);
      toast('Sparepart dihapus.', 'success');
      await loadStock();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  function openJasaModal(jasa) {
    state.editingJasa = jasa || null;
    $('#jasaModalTitle').textContent = jasa ? 'Edit tarif jasa' : 'Tambah tarif jasa';
    $('#jasaId').value = jasa ? jasa.id : '';
    $('#jasaNamaInput').value = jasa ? jasa.nama : '';
    setMoneyValue(
      $('#jasaHargaInput'),
      jasa ? Math.round(Number(jasa.harga_standar) || 0) : 0
    );
    $('#jasaIntervalInput').value = jasa
      ? clampInterval(jasa.interval_servis_bulan)
      : 0;
    openModal('#jasaModal');
    setTimeout(() => $('#jasaNamaInput').focus(), 60);
  }

  async function handleJasaSubmit(event) {
    event.preventDefault();
    const id = intValue($('#jasaId').value, 0);
    const payload = {
      nama: $('#jasaNamaInput').value.trim(),
      harga_standar: String(parseMoney($('#jasaHargaInput').value)),
      interval_servis_bulan: clampInterval($('#jasaIntervalInput').value),
    };

    try {
      if (id) await API.updateJasa(id, payload);
      else await API.createJasa(payload);
      closeModal('#jasaModal');
      toast('Tarif jasa tersimpan.', 'success');
      await loadStock();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function deleteJasa(id) {
    const jasa = state.jasa.find((item) => item.id === id);
    if (!jasa) return;
    if (!window.confirm('Hapus tarif jasa "' + jasa.nama + '"?')) return;

    try {
      await API.deleteJasa(id);
      toast('Tarif jasa dihapus.', 'success');
      await loadStock();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  /* -------------------------------- Report -------------------------------- */
  function reportRangeStart(period) {
    const start = new Date();
    if (period === '7d') start.setDate(start.getDate() - 6);
    else if (period === '30d') start.setDate(start.getDate() - 29);
    else if (period === '1y') start.setFullYear(start.getFullYear() - 1);
    return start;
  }

  function renderPeriodRecap(harian, period, periodLabel) {
    const wrap = $('#periodWrap');
    const activeDays = (harian || []).filter(
      (day) => day.jumlah_transaksi > 0
    );
    if (period === 'today' || !activeDays.length) {
      wrap.classList.add('hidden');
      return;
    }
    $('#periodNote').textContent =
      periodLabel + ' · hanya hari yang memiliki transaksi.';
    $('#periodBody').innerHTML = activeDays
      .map(
        (day) =>
          '<tr class="is-clickable" data-action="day-notas" data-date="' +
          String(day.tanggal).slice(0, 10) +
          '" title="Klik untuk melihat nota hari ini">' +
          '<td><span class="cell-primary">' +
          fmtDate(day.tanggal) +
          '</span></td>' +
          '<td class="text-center">' +
          day.jumlah_transaksi +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(day.total_omset) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(day.total_cash) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(day.total_transfer) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(
            Math.max(
              0,
              Number(day.total_part || 0) - Number(day.laba_kotor || 0)
            )
          ) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(day.laba_kotor) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(day.total_jasa) +
          '</td>' +
          '</tr>'
      )
      .join('');
    wrap.classList.remove('hidden');
  }

  function renderSoldParts(sold, periodLabel) {
    const items = sold && Array.isArray(sold.items) ? sold.items : [];
    if (!items.length) {
      $('#soldPartsBody').innerHTML = '';
      $('#soldPartsEmpty')?.classList.remove('hidden');
      return;
    }
    $('#soldPartsEmpty')?.classList.add('hidden');
    $('#soldPartsNote').textContent =
      periodLabel +
      ' · ' +
      items.length +
      ' penjualan · ' +
      intValue(sold.total_qty, 0) +
      ' unit terjual · harga mengikuti harga deal, diurutkan menurut waktu.';
    $('#soldPartsBody').innerHTML = items
      .map(
        (item) =>
          '<tr class="is-clickable" data-action="record-detail" data-id="' +
          item.service_record_id +
          '">' +
          '<td><span class="cell-primary">' +
          esc(item.nama_part || '-') +
          '</span><span class="cell-sub">' +
          esc(item.customer_nama || '-') +
          ' · ' +
          esc(item.unit_deskripsi || '-') +
          '</span></td>' +
          '<td class="text-center">' +
          intValue(item.jumlah, 0) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(item.harga_satuan) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(item.subtotal) +
          '</td>' +
          '<td>' +
          esc(fmtDateTime(item.waktu_service)) +
          '</td>' +
          '<td><button type="button" class="cell-link" data-action="record-detail" data-id="' +
          item.service_record_id +
          '">' +
          esc(item.no_nota) +
          '</button></td>' +
          '</tr>'
      )
      .join('');
  }

  let reportRequestId = 0;

  function setEmployeeTab(tab) {
    state.employeeTab = tab || 'list';
    $$('#employeeTabSwitch [data-employee-tab]').forEach((button) => {
      button.classList.toggle(
        'active',
        button.dataset.employeeTab === state.employeeTab
      );
    });
    $('#employeePanelList').classList.toggle(
      'hidden',
      state.employeeTab !== 'list'
    );
    $('#employeePanelDebt').classList.toggle(
      'hidden',
      state.employeeTab !== 'debt'
    );
    $('#employeePanelSalary').classList.toggle(
      'hidden',
      state.employeeTab !== 'salary'
    );
  }

  function setReportTab(tab) {
    state.reportTab = tab || 'kas';
    $$('#reportTabSwitch [data-report-tab]').forEach((button) => {
      button.classList.toggle(
        'active',
        button.dataset.reportTab === state.reportTab
      );
    });
    $('#reportPanelKas').classList.toggle('hidden', state.reportTab !== 'kas');
    $('#reportPanelPeriod').classList.toggle(
      'hidden',
      state.reportTab !== 'period'
    );
    $('#reportPanelSold').classList.toggle('hidden', state.reportTab !== 'sold');
  }

  async function loadReport() {
    const requestId = (reportRequestId += 1);
    const select = $('#reportPeriod');
    const period = select.value || 'today';
    const periodLabel = select.selectedOptions.length
      ? select.selectedOptions[0].textContent.trim()
      : 'Hari ini';
    let endISO = todayISO();
    const soldRequest = period === 'all' ? API.soldParts() : null;
    try {
      let data;
      let startISO;
      if (period === 'all') {
        data = await API.allTime();
        startISO = String(data.start).slice(0, 10);
        endISO = String(data.end).slice(0, 10);
      } else {
        startISO = toISODate(reportRangeStart(period));
        data = await API.period(startISO, endISO);
      }

      const soldData = await (soldRequest || API.soldParts(startISO, endISO));
      const rows = data.transaksi || [];

      if (requestId !== reportRequestId) return;

      state.reportRows = rows;
      state.reportLabel = periodLabel;

      $('#reportOmset').textContent = fmtRp(data.total_omset);
      $('#reportCash').textContent = fmtRp(data.total_cash);
      $('#reportTransfer').textContent = fmtRp(data.total_transfer);
      $('#reportProfit').textContent = fmtRp(data.laba_kotor);
      $('#reportProfitJasa').textContent = fmtRp(data.total_jasa);
      $('#reportNetProfit').textContent = fmtRp(
        data.laba_bersih_setelah_komisi_dan_gaji
      );
      $('#reportDateLabel').textContent =
        periodLabel +
        ' · ' +
        (startISO === endISO
          ? fmtDate(startISO)
          : fmtDate(startISO) + ' sampai ' + fmtDate(endISO));

      if ($('#reportMeta')) $('#reportMeta').innerHTML = '';

      const body = $('#reportBody');
      if (!rows.length) {
        body.innerHTML = '';
        $('#reportEmpty').classList.remove('hidden');
      } else {
        $('#reportEmpty').classList.add('hidden');
        body.innerHTML = rows
          .map(
            (record) =>
              '<tr class="is-clickable" data-action="record-detail" data-id="' +
              record.id +
              '">' +
              '<td>' +
              esc(fmtDateTime(record.waktu_service)) +
              '</td>' +
              '<td><button type="button" class="cell-link" data-action="record-detail" data-id="' +
              record.id +
              '">' +
              esc(record.no_nota) +
              '</button></td>' +
              '<td><button type="button" class="cell-link" data-action="customer-detail" data-id="' +
              record.customer_id +
              '">' +
              esc(record.customer_nama) +
              '</button></td>' +
              '<td>' +
              esc(record.unit_deskripsi) +
              '</td>' +
              '<td class="text-right money">' +
              fmtRp(netTotal(record)) +
              '<span class="cell-sub">Laba bersih ' +
              fmtRp(record.laba_kotor) +
              (Number(record.total_retur) > 0
                ? ' · retur -' + fmtRp(record.total_retur)
                : '') +
              (record.modal_tidak_diketahui
                ? ' · modal sparepart belum diisi'
                : '') +
              (record.modal_estimasi ? ' · modal estimasi' : '') +
              '</span></td>' +
              '<td>' +
              metodeBadge(record.metode_bayar) +
          paymentBadge(record) +
              '</td>' +
              '</tr>'
          )
          .join('');
      }

      renderPeriodRecap(data.harian, period, periodLabel);
      renderSoldParts(soldData, periodLabel);
    } catch (err) {
      if (requestId === reportRequestId) {
        toast('Laporan gagal dimuat. Coba lagi.', 'error', 6000);
      }
    }
  }

  /* ---------------------------- Gerbang PIN ------------------------------- */
  const authState = {
    mode: 'session-pin',
    started: false,
  };

  let lastUnauthorizedAt = 0;

  function normalizePin(value) {
    return String(value == null ? '' : value).replace(/[^\d]/g, '').slice(0, 12);
  }

  function setAuthError(element, message) {
    if (!element) return;
    element.textContent = message || '';
    element.classList.toggle('hidden', !message);
  }

  function showAuthGate(screen, message) {
    const gate = $('#authGate');
    if (!gate) return;
    document.body.classList.add('auth-locked');
    gate.classList.remove('hidden');
    $('#authSetup').classList.toggle('hidden', screen !== 'setup');
    $('#authLogin').classList.toggle('hidden', screen !== 'login');
    setAuthError($('#authSetupError'), screen === 'setup' ? message : '');
    setAuthError($('#authLoginError'), screen === 'login' ? message : '');
    const target = screen === 'setup' ? $('#authSetupPin') : $('#authLoginPin');
    if (target) setTimeout(() => target.focus(), 80);
  }

  function hideAuthGate() {
    const gate = $('#authGate');
    if (gate) gate.classList.add('hidden');
    document.body.classList.remove('auth-locked');
  }

  function handleUnauthorized() {
    const now = Date.now();
    if (now - lastUnauthorizedAt < 1500) return;
    lastUnauthorizedAt = now;
    authState.started = false;
    showAuthGate('login', 'Sesi berakhir. Masukkan PIN lagi.');
  }

  async function ensureAuthenticated() {
    let status;
    try {
      status = await API.authStatus();
    } catch (err) {
      const message =
        err.status === 503
          ? 'Aplikasi belum siap. Tutup lalu buka lagi.'
          : err.message;
      showAuthGate('login', message);
      return false;
    }

    authState.mode = status.mode || 'session-pin';
    if (authState.mode !== 'session-pin') {
      // APK memakai token per-instalasi dan PIN native, bukan PIN web.
      hideAuthGate();
      return true;
    }
    if (status.authenticated) {
      hideAuthGate();
      return true;
    }

    const lockMessage =
      Number(status.locked_seconds) > 0
        ? 'Terlalu banyak percobaan. Tunggu ' + status.locked_seconds + ' detik.'
        : '';
    showAuthGate(status.pin_configured ? 'login' : 'setup', lockMessage);
    return false;
  }

  async function handleAuthSetupSubmit(event) {
    event.preventDefault();
    const pin = normalizePin($('#authSetupPin').value);
    const confirmPin = normalizePin($('#authSetupPinConfirm').value);
    const button = $('#authSetupSubmit');

    if (pin.length < 4) {
      setAuthError($('#authSetupError'), 'PIN minimal 4 angka.');
      return;
    }
    if (pin !== confirmPin) {
      setAuthError($('#authSetupError'), 'PIN yang diulang tidak sama.');
      return;
    }

    setAuthError($('#authSetupError'), '');
    setBusy(button, true, 'Menyimpan...');
    try {
      await API.authSetup(pin);
      $('#authSetupPin').value = '';
      $('#authSetupPinConfirm').value = '';
      await startApp();
    } catch (err) {
      setAuthError($('#authSetupError'), err.message);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleAuthLoginSubmit(event) {
    event.preventDefault();
    const input = $('#authLoginPin');
    const pin = normalizePin(input.value);
    const button = $('#authLoginSubmit');

    if (pin.length < 4) {
      setAuthError($('#authLoginError'), 'PIN minimal 4 angka.');
      return;
    }

    setAuthError($('#authLoginError'), '');
    setBusy(button, true, 'Memeriksa...');
    try {
      await API.authLogin(pin);
      input.value = '';
      await startApp();
    } catch (err) {
      input.value = '';
      setAuthError($('#authLoginError'), err.message);
      input.focus();
    } finally {
      setBusy(button, false);
    }
  }

  /* ------------------------------ Karyawan -------------------------------- */
  async function loadEmployees() {
    try {
      state.employees = await API.employees(false);
      renderEmployees();
      populateEmployeeOptions();
    } catch (err) {
      toast('Data karyawan gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function renderEmployees() {
    const body = $('#employeeBody');
    if (!body) return;
    const activeCount = state.employees.filter((row) => row.aktif).length;
    const archivedCount = state.employees.length - activeCount;
    const summary = $('#employeeSummary');
    if (summary) {
      summary.textContent =
        activeCount +
        ' karyawan aktif' +
        (archivedCount ? ' · ' + archivedCount + ' diarsip' : '');
    }
    if (!state.employees.length) {
      body.innerHTML = '';
      $('#employeeEmpty').classList.remove('hidden');
      return;
    }
    $('#employeeEmpty').classList.add('hidden');
    const peranLabel = {
      MEKANIK: 'Mekanik',
      KASIR: 'Kasir',
      KEDUANYA: 'Mekanik dan kasir',
    };
    body.innerHTML = state.employees
      .map(
        (employee) =>
          '<tr><td><button type="button" class="cell-link" data-action="employee-detail" data-id="' +
          employee.id +
          '">' +
          esc(employee.nama) +
          '</button></td><td>' +
          esc(peranLabel[employee.peran] || employee.peran) +
          '</td><td><span class="badge ' +
          (employee.aktif ? 'green' : 'gray') +
          '">' +
          (employee.aktif ? 'Aktif' : 'Nonaktif') +
          '</span></td><td class="row-actions">' +
          (employee.aktif
            ? '<button type="button" class="btn btn-outline btn-xs" data-action="employee-perf" data-id="' +
              employee.id +
              '">Performa</button>'
            : '') +
          '<button type="button" class="btn btn-outline btn-xs" data-action="edit-employee" data-id="' +
          employee.id +
          '">Edit</button>' +
          (employee.aktif
            ? '<button type="button" class="btn btn-ghost btn-xs" data-action="archive-employee" data-id="' +
              employee.id +
              '">Arsipkan</button>'
            : '<button type="button" class="btn btn-outline btn-xs" data-action="reactivate-employee" data-id="' +
              employee.id +
              '">Aktifkan kembali</button>') +
          '<button type="button" class="btn btn-ghost btn-xs" data-action="delete-employee" data-id="' +
          employee.id +
          '">Hapus</button>' +
          '</td></tr>'
      )
      .join('');
  }

  function populateEmployeeOptions() {
    const cashier = $('#posCashier');
    if (cashier) {
      const selected = cashier.value;
      cashier.innerHTML =
        '<option value="">Tanpa kasir</option>' +
        state.employees
          .filter((employee) => employee.aktif && ['KASIR', 'KEDUANYA'].includes(employee.peran))
          .map(
            (employee) =>
              '<option value="' + employee.id + '">' + esc(employee.nama) + '</option>'
          )
          .join('');
      if (selected) cashier.value = selected;
    }
    const mechanics = $('#posMechanics');
    if (mechanics) {
      const checked = new Set(
        $$('#posMechanics input:checked').map((input) => Number(input.value))
      );
      mechanics.innerHTML = state.employees
        .filter((employee) => employee.aktif && ['MEKANIK', 'KEDUANYA'].includes(employee.peran))
        .map(
          (employee) =>
            '<label><input type="checkbox" value="' +
            employee.id +
            '"' +
            (checked.has(employee.id) ? ' checked' : '') +
            '> ' +
            esc(employee.nama) +
            '</label>'
        )
        .join('') || '<span class="tiny muted">Belum ada mekanik.</span>';
    }
  }

  function syncEmployeeImbalanFields() {
    const jenis = $('#employeeJenisImbalan')
      ? $('#employeeJenisImbalan').value
      : 'KOMISI';
    const gajiField = $('#employeeGajiField');
    const komisiFields = $('#employeeKomisiFields');
    const komisiRates = $('#employeeKomisiRateFields');
    if (gajiField) gajiField.classList.toggle('hidden', jenis === 'KOMISI');
    if (komisiFields) komisiFields.classList.toggle('hidden', jenis === 'GAJI');
    if (komisiRates) komisiRates.classList.toggle('hidden', jenis === 'GAJI');
    const mode = $('#employeeKomisiMode')
      ? $('#employeeKomisiMode').value
      : 'PERSEN';
    const suffix = mode === 'PERSEN' ? ' (%)' : ' (Rp/nota)';
    if ($('#employeeKomisiBarangLabel')) {
      $('#employeeKomisiBarangLabel').textContent = 'Komisi barang' + suffix;
    }
    if ($('#employeeKomisiJasaLabel')) {
      $('#employeeKomisiJasaLabel').textContent = 'Komisi jasa' + suffix;
    }
    syncEmployeePayrollFields();
  }

  function syncEmployeePayrollFields() {
    const period = $('#employeePayrollPeriod')
      ? $('#employeePayrollPeriod').value
      : 'BULANAN';
    const weekly = ['MINGGUAN', 'DUA_MINGGUAN', 'TIGA_MINGGUAN'].includes(
      period
    );
    const dateField = $('#employeePayrollTanggalField');
    if (dateField) dateField.classList.toggle('hidden', period !== 'TANGGAL');
    const dayField = $('#employeePayrollHariField');
    if (dayField) dayField.classList.toggle('hidden', !weekly);
  }

  function openEmployeeModal(employee) {
    const current = employee || null;
    $('#employeeModalTitle').textContent = current ? 'Edit karyawan' : 'Tambah karyawan';
    $('#employeeId').value = current ? current.id : '';
    $('#employeeNama').value = current ? current.nama : '';
    $('#employeePeran').value = current ? current.peran : 'MEKANIK';
    $('#employeeAktif').value = current && !current.aktif ? '0' : '1';
    $('#employeeHp').value = current ? current.nomor_hp || '' : '';
    $('#employeeCatatan').value = current ? current.catatan || '' : '';
    $('#employeeJenisImbalan').value = current
      ? current.jenis_imbalan || 'KOMISI'
      : 'KOMISI';
    $('#employeeGajiBulanan').value = current
      ? Number(current.gaji_bulanan || 0)
      : 0;
    $('#employeeKomisiMode').value = current ? current.komisi_mode : 'PERSEN';
    $('#employeeKomisiBarang').value = current
      ? Number(current.komisi_barang_nilai || 0)
      : 0;
    $('#employeeKomisiJasa').value = current
      ? Number(current.komisi_jasa_nilai || 0)
      : 0;
    $('#employeePayrollPeriod').value = current
      ? current.payroll_period || 'BULANAN'
      : 'BULANAN';
    $('#employeePayrollTanggal').value = current
      ? intValue(current.payroll_tanggal, 1)
      : 1;
    $('#employeePayrollHari').value = current
      ? String(intValue(current.payroll_hari, 0))
      : '0';
    $('#employeeTanggalMasuk').value = current
      ? String(current.tanggal_masuk || '').slice(0, 10)
      : todayISO();
    $('#employeeBankNama').value = current ? current.bank_nama || '' : '';
    $('#employeeBankNomor').value = current ? current.bank_nomor || '' : '';
    $('#employeeBankAtasNama').value = current
      ? current.bank_atas_nama || ''
      : '';
    syncEmployeeImbalanFields();
    openModal('#employeeModal');
    setTimeout(() => $('#employeeNama').focus(), 60);
  }

  async function handleEmployeeSubmit(event) {
    event.preventDefault();
    const id = intValue($('#employeeId').value, 0);
    const payload = {
      nama: $('#employeeNama').value.trim(),
      peran: $('#employeePeran').value,
      aktif: $('#employeeAktif').value === '1',
      nomor_hp: $('#employeeHp').value.trim(),
      catatan: $('#employeeCatatan').value.trim() || null,
      jenis_imbalan: $('#employeeJenisImbalan').value,
      gaji_bulanan: String(Number($('#employeeGajiBulanan').value || 0)),
      komisi_mode: $('#employeeKomisiMode').value,
      komisi_barang_nilai: String(
        Number($('#employeeKomisiBarang').value || 0)
      ),
      komisi_jasa_nilai: String(Number($('#employeeKomisiJasa').value || 0)),
      payroll_period: $('#employeePayrollPeriod').value,
      payroll_tanggal: Math.max(
        1,
        Math.min(31, intValue($('#employeePayrollTanggal').value, 1))
      ),
      payroll_hari: Math.max(
        0,
        Math.min(6, intValue($('#employeePayrollHari').value, 0))
      ),
      bank_nama: $('#employeeBankNama').value.trim(),
      bank_nomor: $('#employeeBankNomor').value.trim(),
      bank_atas_nama: $('#employeeBankAtasNama').value.trim(),
      tanggal_masuk: $('#employeeTanggalMasuk').value || null,
    };
    try {
      if (id) await API.updateEmployee(id, payload);
      else await API.createEmployee(payload);
      if (!$('#employeeDetailModal')?.classList.contains('hidden')) {
        dismissModalStack(['#employeeModal', '#employeeDetailModal']);
      } else {
        closeModal('#employeeModal');
      }
      toast('Data karyawan tersimpan.', 'success');
      await loadEmployees();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  function openEmployeeDetail(id) {
    const employee = state.employees.find((row) => row.id === id);
    if (!employee) return;
    const peranLabel = {
      MEKANIK: 'Mekanik',
      KASIR: 'Kasir',
      KEDUANYA: 'Mekanik dan kasir',
    };
    const payrollDays = [
      'Senin',
      'Selasa',
      'Rabu',
      'Kamis',
      'Jumat',
      'Sabtu',
      'Minggu',
    ];
    const weekly = [
      'MINGGUAN',
      'DUA_MINGGUAN',
      'TIGA_MINGGUAN',
    ].includes(employee.payroll_period);
    const jadwal =
      employee.payroll_label +
      (employee.payroll_period === 'TANGGAL'
        ? ' tgl ' + intValue(employee.payroll_tanggal, 1)
        : weekly
          ? ' · ' + payrollDays[intValue(employee.payroll_hari, 0)]
          : '');
    const suffix = employee.komisi_mode === 'PERSEN' ? '%' : ' / nota';
    const row = (label, value) =>
      '<div><span>' + esc(label) + '</span><strong>' +
      esc(value || '-') + '</strong></div>';
    $('#employeeDetailTitle').textContent = employee.nama;
    $('#employeeDetailSubtitle').textContent =
      (peranLabel[employee.peran] || employee.peran) +
      (employee.aktif ? ' · Aktif' : ' · Nonaktif');
    $('#employeeDetailBody').innerHTML =
      '<div class="payroll-pay-summary">' +
      row('Nama', employee.nama) +
      row('Peran', peranLabel[employee.peran] || employee.peran) +
      row('Tanggal masuk', employee.tanggal_masuk ? fmtDate(employee.tanggal_masuk) : '-') +
      row('WhatsApp', employee.nomor_hp || '-') +
      row('Status', employee.aktif ? 'Aktif' : 'Nonaktif') +
      row('Jenis imbalan', employee.jenis_imbalan) +
      row('Gaji bulanan', fmtRp(employee.gaji_bulanan || 0)) +
      row(
        'Komisi barang',
        Number(employee.komisi_barang_nilai || 0) + suffix
      ) +
      row(
        'Komisi jasa',
        Number(employee.komisi_jasa_nilai || 0) + suffix
      ) +
      row('Jadwal gajian', jadwal) +
      row(
        'Rekening',
        [
          employee.bank_nama,
          employee.bank_nomor,
          employee.bank_atas_nama ? 'a.n. ' + employee.bank_atas_nama : '',
        ]
          .filter(Boolean)
          .join(' · ')
      ) +
      row('Catatan', employee.catatan || '-') +
      '</div>' +
      '<div class="row-actions" style="margin-top:14px">' +
      (employee.aktif
        ? '<button type="button" class="btn btn-outline btn-sm" data-action="employee-perf" data-id="' +
          employee.id + '">Performa</button>'
        : '') +
      '<button type="button" class="btn btn-outline btn-sm" data-action="edit-employee" data-id="' +
      employee.id + '">Edit</button>' +
      (employee.aktif
        ? '<button type="button" class="btn btn-ghost btn-sm" data-action="archive-employee" data-id="' +
          employee.id + '">Arsipkan</button>'
        : '<button type="button" class="btn btn-outline btn-sm" data-action="reactivate-employee" data-id="' +
          employee.id + '">Aktifkan kembali</button>') +
      '<button type="button" class="btn btn-ghost btn-sm" data-action="delete-employee" data-id="' +
      employee.id + '">Hapus</button>' +
      '</div>';
    openModal('#employeeDetailModal');
  }

  async function archiveEmployee(id) {
    const employee = state.employees.find((row) => row.id === id);
    if (!employee) return;
    if (
      !window.confirm(
        'Arsipkan ' +
          employee.nama +
          '? Data karyawan tetap tersimpan dan bisa diaktifkan kembali.'
      )
    ) {
      return;
    }
    try {
      await API.updateEmployee(id, { aktif: false });
      dismissModalStack(['#employeeDetailModal']);
      toast('Karyawan dipindahkan ke arsip.', 'success');
      await loadEmployees();
      await loadSalaryPayments();
      await loadEmployeeDebts();
      state.payrollSummary = await API.payrollSummary(todayISO());
      renderPayrollCard();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function openEmployeeArchive() {
    try {
      const all = await API.employees(false);
      state.archivedEmployees = all.filter((employee) => !employee.aktif);
      renderEmployeeArchive();
      openModal('#employeeArchiveModal');
    } catch (err) {
      toast('Arsip karyawan gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function renderEmployeeArchive() {
    const body = $('#employeeArchiveBody');
    const empty = $('#employeeArchiveEmpty');
    if (!body) return;
    const employees = state.archivedEmployees || [];
    $('#employeeArchiveSubtitle').textContent =
      employees.length + ' karyawan di arsip. Data tetap tersimpan.';
    if (!employees.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    const peranLabel = {
      MEKANIK: 'Mekanik',
      KASIR: 'Kasir',
      KEDUANYA: 'Mekanik dan kasir',
    };
    body.innerHTML = employees
      .map(
        (employee) =>
          '<tr><td><span class="cell-primary">' + esc(employee.nama) +
          '</span></td><td>' +
          esc(peranLabel[employee.peran] || employee.peran) + '</td><td>' +
          (employee.tanggal_masuk
            ? esc(fmtDate(employee.tanggal_masuk))
            : '-') +
          '</td><td>' + esc(employee.nomor_hp || '-') + '</td><td>' +
          (employee.jenis_imbalan === 'KOMISI'
            ? '-'
            : fmtRp(employee.gaji_bulanan || 0)) +
          '</td><td class="row-actions">' +
          '<button type="button" class="btn btn-primary btn-xs" data-action="reactivate-employee" data-id="' +
          employee.id + '">Aktifkan kembali</button></td></tr>'
      )
      .join('');
  }

  async function reactivateEmployee(id) {
    const employee =
      (state.archivedEmployees || []).find((row) => row.id === id) ||
      state.employees.find((row) => row.id === id);
    if (!employee) return;
    if (
      !window.confirm(
        'Aktifkan kembali ' +
          employee.nama +
          '? Karyawan akan muncul lagi di daftar aktif.'
      )
    ) {
      return;
    }
    try {
      await API.updateEmployee(id, { aktif: true });
      toast('Karyawan diaktifkan kembali.', 'success');
      await loadEmployees();
      const all = await API.employees(false);
      state.archivedEmployees = all.filter((row) => !row.aktif);
      renderEmployeeArchive();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function deleteEmployee(id) {
    const employee = state.employees.find((row) => row.id === id);
    if (!employee) return;
    if (!window.confirm('Hapus karyawan "' + employee.nama + '"?')) return;
    try {
      await API.deleteEmployee(id);
      dismissModalStack(['#employeeDetailModal']);
      toast('Karyawan dihapus.', 'success');
      await loadEmployees();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function loadSalaryPayments() {
    try {
      state.salaryPayments = await API.salaryPayments();
      state.salaryPaymentsLoaded = true;
      renderSalaryPayments();
    } catch (err) {
      toast('Data pembayaran gaji gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function renderSalaryPayments() {
    const body = $('#salaryBody');
    if (!body) return;
    const summary = $('#salarySummary');
    const total = state.salaryPayments.reduce(
      (sum, row) => sum + Number(row.nominal || 0),
      0
    );
    if (summary) {
      summary.textContent = state.salaryPayments.length
        ? state.salaryPayments.length +
          ' pembayaran · total ' +
          fmtRp(total) +
          '. Menampilkan 2 terbaru per karyawan.'
        : 'Belum ada pembayaran gaji.';
    }
    const empty = $('#salaryEmpty');
    if (!state.salaryPayments.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    const grouped = new Map();
    state.salaryPayments.forEach((payment) => {
      const key = payment.employee_id || 'nama:' + payment.nama_karyawan;
      const rows = grouped.get(key) || [];
      if (rows.length < 2) rows.push(payment);
      grouped.set(key, rows);
    });
    const rows = Array.from(grouped.values()).flat();
    body.innerHTML = rows
      .map(
        (payment) =>
          '<tr>' +
          '<td>' + esc(fmtDate(payment.tanggal)) + '</td>' +
          '<td><span class="cell-primary">' + esc(payment.nama_karyawan) +
          '</span>' +
          (payment.employee_id ? '' : '<span class="cell-sub">Karyawan sudah dihapus</span>') +
          '</td>' +
          '<td>' + esc(payment.periode || '-') + '</td>' +
          '<td>' + esc(payment.metode === 'TRANSFER' ? 'Transfer' : 'Tunai') + '</td>' +
          '<td class="text-right">' + fmtRp(payment.nominal) + '</td>' +
          '<td class="text-right">' + fmtRp(payment.potongan_hutang || 0) + '</td>' +
          '<td>' + esc(payment.catatan || '-') + '</td></tr>'
      )
      .join('');
  }

  function openSalaryHistoryModal() {
    const body = $('#salaryHistoryBody');
    const empty = $('#salaryHistoryEmpty');
    if (!body) return;
    if (!state.salaryPayments.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
    } else {
      if (empty) empty.classList.add('hidden');
      body.innerHTML = state.salaryPayments
        .map(
          (payment) =>
            '<tr>' +
            '<td>' + esc(fmtDate(payment.tanggal)) + '</td>' +
            '<td>' + esc(payment.nama_karyawan) + '</td>' +
            '<td>' + esc(payment.periode || '-') + '</td>' +
            '<td>' + esc(payment.metode === 'TRANSFER' ? 'Transfer' : 'Tunai') + '</td>' +
            '<td class="text-right">' + fmtRp(payment.nominal) + '</td>' +
            '<td class="text-right">' + fmtRp(payment.potongan_hutang || 0) + '</td>' +
              '<td>' + esc(payment.catatan || '-') + '</td></tr>'
        )
        .join('');
    }
    $('#salaryHistorySubtitle').textContent =
      state.salaryPayments.length +
      ' pembayaran gaji tercatat, termasuk potongan hutang.';
    openModal('#salaryHistoryModal');
  }

  async function loadEmployeeDebts() {
    try {
      state.employeeDebts = await API.employeeDebts();
      renderEmployeeDebts();
    } catch (err) {
      toast('Data hutang karyawan gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function renderEmployeeDebts() {
    const body = $('#debtBody');
    if (!body) return;
    const summary = $('#debtSummary');
    const outstanding = state.employeeDebts.reduce(
      (sum, row) => sum + Number(row.sisa || 0),
      0
    );
    if (summary) {
      summary.textContent = state.employeeDebts.length
        ? 'Sisa hutang ' +
          fmtRp(outstanding) +
          '. Sisa hutang otomatis dibawa ke gaji berikutnya dan dipotong saat gajian.'
        : 'Catat uang muka atau kebutuhan karyawan. Sisa hutang otomatis dibawa ke gaji berikutnya dan dipotong saat gajian.';
    }
    const empty = $('#debtEmpty');
    const allButton = $('#btnDebtHistoryAll');
    if (allButton) {
      allButton.classList.toggle(
        'hidden',
        state.employeeDebts.length <= 4
      );
    }
    if (!state.employeeDebts.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    body.innerHTML = state.employeeDebts
      .slice(0, 4)
      .map(
        (debt) =>
          '<tr><td><button type="button" class="cell-link" data-action="debt-detail" data-id="' +
          debt.id + '">' + esc(debt.nama_karyawan) + '</button></td>' +
          '<td class="text-right">' + fmtRp(debt.nominal) + '</td>' +
          '<td><span class="badge ' + (debt.lunas ? 'green' : 'amber') + '">' +
          (debt.lunas ? 'Lunas' : 'Belum lunas') + '</span></td>' +
          '<td class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="edit-debt" data-id="' +
          debt.id + '">Edit</button>' +
          '<button type="button" class="btn btn-ghost btn-xs" data-action="delete-debt" data-id="' +
          debt.id + '">Hapus</button></td></tr>'
      )
      .join('');
  }

  function openDebtDetail(id) {
    const debt = state.employeeDebts.find((row) => row.id === id);
    if (!debt) return;
    const row = (label, value) =>
      '<div><span>' + esc(label) + '</span><strong>' +
      esc(value || '-') + '</strong></div>';
    $('#debtDetailTitle').textContent = debt.nama_karyawan;
    $('#debtDetailSubtitle').textContent =
      fmtDate(debt.tanggal) + ' · ' + (debt.lunas ? 'Lunas' : 'Belum lunas');
    $('#debtDetailBody').innerHTML =
      '<div class="payroll-pay-summary">' +
      row('Nama', debt.nama_karyawan) +
      row('Tanggal', fmtDate(debt.tanggal)) +
      row('Keperluan', debt.keterangan || '-') +
      row('Nominal hutang', fmtRp(debt.nominal)) +
      row('Sudah dipotong', fmtRp(debt.terbayar || 0)) +
      row('Sisa hutang', fmtRp(debt.sisa)) +
      row(
        'Status',
        debt.lunas
          ? 'Lunas'
          : 'Belum lunas · sisa dibawa ke gaji berikutnya'
      ) +
      '</div>' +
      '<div class="row-actions" style="margin-top:14px">' +
      '<button type="button" class="btn btn-outline btn-sm" data-action="edit-debt" data-id="' +
      debt.id + '">Edit</button>' +
      '<button type="button" class="btn btn-ghost btn-sm" data-action="delete-debt" data-id="' +
      debt.id + '">Hapus</button>' +
      '</div>';
    openModal('#debtDetailModal');
  }

  function openDebtHistoryModal(debtRows, title) {
    const body = $('#debtHistoryBody');
    const empty = $('#debtHistoryEmpty');
    if (!body) return;
    const rows = debtRows || state.employeeDebts || [];
    if (!rows.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
    } else {
      if (empty) empty.classList.add('hidden');
      body.innerHTML = rows
        .map(
          (debt) =>
            '<tr><td>' + esc(fmtDate(debt.tanggal)) + '</td>' +
            '<td>' + esc(debt.nama_karyawan) + '</td>' +
            '<td>' + esc(debt.keterangan || '-') + '</td>' +
            '<td class="text-right">' + fmtRp(debt.nominal) + '</td>' +
            '<td class="text-right">' + fmtRp(debt.terbayar || 0) + '</td>' +
            '<td class="text-right">' + fmtRp(debt.sisa) + '</td>' +
            '<td><span class="badge ' + (debt.lunas ? 'green' : 'amber') + '">' +
            (debt.lunas ? 'Lunas' : 'Belum lunas') + '</span></td></tr>'
        )
        .join('');
    }
    $('#debtHistoryTitle').textContent =
      title || 'Seluruh hutang karyawan';
    $('#debtHistorySubtitle').textContent =
      rows.length + ' catatan hutang karyawan.';
    openModal('#debtHistoryModal');
  }

  function debtEmployeeOptions(selectedId, deletedName) {
    const options = state.employees.map(
      (employee) =>
        '<option value="' + employee.id + '"' +
        (employee.id === selectedId ? ' selected' : '') + '>' +
        esc(employee.nama) +
        (employee.aktif ? '' : ' (nonaktif)') +
        '</option>'
    );
    if (selectedId && !state.employees.some((row) => row.id === selectedId)) {
      options.unshift(
        '<option value="" selected>' + esc(deletedName || 'Karyawan') +
        ' (dihapus)</option>'
      );
    }
    return options.join('') || '<option value="">Belum ada karyawan</option>';
  }

  function openDebtModal(debt) {
    const current = debt || null;
    if (!state.employees.length) {
      toast('Tambahkan karyawan lebih dulu.', 'warning');
      return;
    }
    $('#debtModalTitle').textContent = current
      ? 'Edit hutang karyawan'
      : 'Catat hutang karyawan';
    $('#debtId').value = current ? current.id : '';
    $('#debtEmployee').innerHTML = debtEmployeeOptions(
      current ? current.employee_id : state.employees[0].id,
      current ? current.nama_karyawan : ''
    );
    $('#debtEmployee').required = !(current && !current.employee_id);
    $('#debtTanggal').value = current
      ? String(current.tanggal).slice(0, 10)
      : todayISO();
    $('#debtNominal').value = current ? Number(current.nominal || 0) : '';
    $('#debtKeterangan').value = current ? current.keterangan || '' : '';
    openModal('#debtModal');
  }

  async function handleDebtSubmit(event) {
    event.preventDefault();
    const id = intValue($('#debtId').value, 0);
    const employeeId = intValue($('#debtEmployee').value, 0);
    const payload = {
      tanggal: $('#debtTanggal').value || null,
      nominal: String(Number($('#debtNominal').value || 0)),
      keterangan: $('#debtKeterangan').value.trim() || null,
    };
    if (employeeId) payload.employee_id = employeeId;
    try {
      if (id) await API.updateEmployeeDebt(id, payload);
      else await API.createEmployeeDebt(payload);
      if (!$('#debtDetailModal')?.classList.contains('hidden')) {
        dismissModalStack(['#debtModal', '#debtDetailModal']);
      } else {
        closeModal('#debtModal');
      }
      toast('Hutang karyawan tersimpan.', 'success');
      await loadEmployeeDebts();
      state.payrollSummary = await API.payrollSummary(todayISO());
      renderPayrollCard();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function deleteEmployeeDebt(id) {
    const debt = state.employeeDebts.find((row) => row.id === id);
    if (!debt) return;
    if (
      !window.confirm(
        'Hapus hutang ' + debt.nama_karyawan + ' sebesar ' + fmtRp(debt.sisa) + '?'
      )
    ) {
      return;
    }
    try {
      await API.deleteEmployeeDebt(id);
      dismissModalStack(['#debtDetailModal']);
      toast('Hutang karyawan dihapus.', 'success');
      await loadEmployeeDebts();
      state.payrollSummary = await API.payrollSummary(todayISO());
      renderPayrollCard();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  function isoDateLocal(dateObj) {
    return (
      dateObj.getFullYear() +
      '-' +
      String(dateObj.getMonth() + 1).padStart(2, '0') +
      '-' +
      String(dateObj.getDate()).padStart(2, '0')
    );
  }

  function payrollCycleStart(employee, dateISO) {
    const dateObj = new Date((dateISO || todayISO()) + 'T00:00:00');
    if (employee.payroll_period === 'MINGGUAN') {
      dateObj.setDate(dateObj.getDate() - 6);
    } else if (employee.payroll_period === 'DUA_MINGGUAN') {
      dateObj.setDate(dateObj.getDate() - 13);
    } else if (employee.payroll_period === 'TIGA_MINGGUAN') {
      dateObj.setDate(dateObj.getDate() - 20);
    } else {
      dateObj.setDate(1);
    }
    return isoDateLocal(dateObj);
  }

  function salaryAvailableEmployees(dateISO, currentId) {
    return state.employees.filter((employee) => {
      const cycle = payrollCycleStart(employee, dateISO);
      return !state.salaryPayments.some(
        (row) =>
          row.employee_id === employee.id &&
          row.cycle_start === cycle &&
          (!currentId || row.id !== currentId)
      );
    });
  }

  function salaryEmployeeOptions(selectedId, deletedName, dateISO, currentId) {
    const available = salaryAvailableEmployees(dateISO, currentId);
    const options = available.map(
      (employee) =>
        '<option value="' + employee.id + '"' +
        (employee.id === selectedId ? ' selected' : '') + '>' +
        esc(employee.nama) +
        (employee.aktif ? '' : ' (nonaktif)') +
        '</option>'
    );
    if (!selectedId && deletedName) {
      options.unshift(
        '<option value="" selected>' + esc(deletedName) +
        ' (dihapus)</option>'
      );
    }
    return (
      options.join('') ||
      '<option value="">Semua karyawan sudah dicatat untuk siklus ini</option>'
    );
  }

  function refreshSalaryEmployeeOptions() {
    const dateISO = $('#salaryTanggal').value || todayISO();
    const currentId = intValue($('#salaryId').value, 0);
    const current = state.salaryPayments.find((row) => row.id === currentId);
    const available = salaryAvailableEmployees(dateISO, currentId);
    const previous = intValue($('#salaryEmployee').value, 0);
    let selectedId = previous;
    if (!available.some((employee) => employee.id === selectedId)) {
      selectedId = current ? current.employee_id : available[0]?.id || null;
    }
    $('#salaryEmployee').innerHTML = salaryEmployeeOptions(
      selectedId,
      current && !current.employee_id ? current.nama_karyawan : '',
      dateISO,
      currentId
    );
    $('#salaryEmployee').required = Boolean(
      current ? current.employee_id || available.length : available.length
    );
    const submit = $('#salarySubmit');
    if (submit) submit.disabled = !current && !available.length;
    if (!current) {
      const employee = state.employees.find((row) => row.id === selectedId);
      $('#salaryNominal').value = employee ? Number(employee.gaji_bulanan || 0) : '';
    }
  }

  function syncSalaryNominalFromEmployee() {
    const select = $('#salaryEmployee');
    if (!select || $('#salaryId').value) return;
    const employee = state.employees.find(
      (row) => row.id === Number(select.value)
    );
    if (!employee) return;
    const nominal = $('#salaryNominal');
    if (!Number(nominal.value || 0) && Number(employee.gaji_bulanan || 0) > 0) {
      nominal.value = Number(employee.gaji_bulanan);
    }
  }

  function syncSalaryBankRow() {
    const transfer = $('#salaryMetode')?.value === 'TRANSFER';
    $('#salaryBankRow')?.classList.toggle('hidden', !transfer);
  }

  function openSalaryModal(preset) {
    const data = preset || {};
    if (!data.employee_id) {
      toast('Karyawan pembayaran tidak ditemukan.', 'warning');
      return;
    }
    const period = data.periode || todayISO().slice(0, 7);
    $('#salaryModalTitle').textContent =
      'Bayar ' + (data.nama_karyawan || 'karyawan');
    $('#salaryId').value = '';
    $('#salaryEmployee').value = data.employee_id;
    state.salaryPendingPhone = data.nomor_hp || '';
    $('#salaryEmployeeName').textContent = data.nama_karyawan || '-';
    $('#salaryPeriode').value = period;
    $('#salaryPeriodLabel').textContent = period;
    $('#salaryTanggal').value = data.tanggal || todayISO();
    const nominal = Number(data.nominal || 0);
    $('#salaryNominal').value = nominal;
    $('#salaryPayTotal').textContent = fmtRp(nominal);
    $('#salaryPotonganHutang').value = Number(data.potongan_hutang || 0);
    $('#salaryBonus').value = Number(data.bonus || 0);
    $('#salaryBonusKeterangan').value = data.bonus_keterangan || '';
    $('#salaryCicilanHutang').value = Number(data.cicilan_hutang || 0);
    $('#salaryCatatan').value = data.catatan || '';
    $('#salaryMetode').value = data.metode || 'CASH';
    const bankParts = [
      data.bank_nama,
      data.bank_nomor,
      data.bank_atas_nama ? 'a.n. ' + data.bank_atas_nama : '',
    ].filter(Boolean);
    $('#salaryBankInfo').textContent = bankParts.length
      ? bankParts.join(' · ')
      : 'Nomor rekening karyawan belum diisi di menu Karyawan.';
    const bonus = Number(data.bonus || 0);
    $('#salaryBonusInfo').classList.toggle('hidden', bonus <= 0);
    $('#salaryBonusText').textContent =
      bonus > 0
        ? fmtRp(bonus) +
          (data.bonus_keterangan ? ' · ' + data.bonus_keterangan : '')
        : '-';
    syncSalaryBankRow();
    openModal('#salaryModal');
  }

  async function handleSalarySubmit(event) {
    event.preventDefault();
    const id = intValue($('#salaryId').value, 0);
    const employeeId = intValue($('#salaryEmployee').value, 0);
    const employeeName = $('#salaryEmployeeName').textContent.trim();
    const period = $('#salaryPeriode').value;
    const total = Number($('#salaryNominal').value || 0);
    const method = $('#salaryMetode').value;
    const methodLabel = method === 'TRANSFER' ? 'Transfer' : 'Tunai';
    if (
      !window.confirm(
        'Bayar ' +
          employeeName +
          ' sebesar ' +
          fmtRp(total) +
          ' via ' +
          methodLabel +
          '?'
      )
    ) {
      return;
    }
    const payload = {
      periode: period,
      tanggal: $('#salaryTanggal').value || null,
      nominal: String(total),
      potongan_hutang: String(
        Number($('#salaryPotonganHutang').value || 0)
      ),
      bonus: String(Number($('#salaryBonus').value || 0)),
      bonus_keterangan: $('#salaryBonusKeterangan').value.trim() || null,
      cicilan_hutang: String(
        Number($('#salaryCicilanHutang').value || 0)
      ),
      metode: method,
      catatan: $('#salaryCatatan').value.trim() || null,
    };
    if (employeeId) payload.employee_id = employeeId;
    try {
      const saved = id
        ? await API.updateSalaryPayment(id, payload)
        : await API.createSalaryPayment(payload);
      dismissModalStack([
        '#salaryModal',
        '#payrollPayModal',
        '#payrollModal',
      ]);
      toast('Pembayaran gaji tersimpan.', 'success');
      await loadSalaryPayments();
      await loadEmployeeDebts();
      try {
        state.payrollSummary = await API.payrollSummary(todayISO());
        renderPayrollCard();
      } catch (err) {
        // Ringkasan tetap bisa dimuat ulang lewat tombol Muat ulang.
      }
      let receiptText = '';
      try {
        const receipt = await API.salaryReceipt(saved.id);
        receiptText = (receipt.text || '').trim();
      } catch (err) {
        toast('Nota gaji gagal dimuat. Pembayaran tetap tersimpan.', 'warning', 6000);
      }
      const waTarget = receiptText
        ? waLink(state.salaryPendingPhone, receiptText)
        : null;
      if (waTarget) {
        const opened = await openExternalLink(waTarget);
        if (opened) {
          toast('Nota gaji dibuka di WhatsApp karyawan.', 'success');
        }
      } else if (!receiptText) {
        toast('Nota gaji tidak tersedia untuk dibuka.', 'warning');
      } else {
        toast('Nomor WhatsApp karyawan belum diisi.', 'warning');
      }
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function deleteSalaryPayment(id) {
    const payment = state.salaryPayments.find((row) => row.id === id);
    if (!payment) return;
    if (
      !window.confirm(
        'Hapus gaji ' +
          payment.nama_karyawan +
          ' periode ' +
          payment.periode +
          '? Laporan akan dihitung ulang.'
      )
    ) {
      return;
    }
    try {
      await API.deleteSalaryPayment(id);
      toast('Pembayaran gaji dihapus.', 'success');
      await loadSalaryPayments();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  function employeePerfPeriod() {
    const select = $('#employeePerfPeriod');
    const mode = select ? select.value : state.employeePerfMode || 'unpaid';
    state.employeePerfMode = mode;
    if (mode === 'unpaid') return {};
    const today = new Date();
    const end = toISODate(today);
    if (mode === 'weekly') {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 6);
      return { start: toISODate(startDate), end };
    }
    if (mode === 'monthly') {
      return {
        start: toISODate(new Date(today.getFullYear(), today.getMonth(), 1)),
        end,
      };
    }
    if (mode === 'yearly') {
      return { start: toISODate(new Date(today.getFullYear(), 0, 1)), end };
    }
    return { start: '2000-01-01', end };
  }

  async function openEmployeePerformance(id) {
    state.employeePerfId = id;
    state.employeePerfHistory = [];
    state.employeePerfMode = 'unpaid';
    const employee = state.employees.find((row) => row.id === id);
    state.employeePerfName = employee ? employee.nama : '';
    $('#employeePerfTitle').textContent = employee
      ? 'Performa ' + employee.nama
      : 'Performa karyawan';
    $('#employeePerfSubtitle').textContent =
      'Periode dapat diubah. Komisi dihitung per nota di backend.';
    $('#employeePerfBody').innerHTML = '<div class="empty-state sm">Memuat performa...</div>';
    openModal('#employeePerfModal');
    await loadEmployeePerformance();
  }

  async function loadEmployeePerformance() {
    const id = state.employeePerfId;
    if (!id) return;
    const body = $('#employeePerfBody');
    const period = employeePerfPeriod();
    try {
      const data = await API.employeePerformance(id, period.start, period.end);
      renderEmployeePerformance(data);
    } catch (err) {
      if (body) body.innerHTML = '<div class="empty-state sm">Performa gagal dimuat.</div>';
    }
  }

  function renderEmployeePerformance(data) {
    const body = $('#employeePerfBody');
    if (!body) return;
    const employee = data.employee || {};
    const periodLabels = {
      unpaid: 'Belum digaji',
      weekly: 'Mingguan',
      monthly: 'Bulanan',
      yearly: 'Tahunan',
      all: 'Keseluruhan',
    };
    const periodRange = data.start || data.end
      ? (data.start || '-') + ' sampai ' + (data.end || '-')
      : 'Semua waktu';
    const period =
      state.employeePerfMode === 'unpaid' && intValue(data.jumlah_nota, 0) === 0
        ? 'Belum ada pengerjaan setelah gaji'
        : state.employeePerfMode === 'all'
          ? 'Keseluruhan'
          : (periodLabels[state.employeePerfMode] || 'Periode') +
            ' · ' +
            periodRange;
    state.employeePerfHistory = data.riwayat || [];
    state.employeePerfName = employee.nama || state.employeePerfName;
    const periodOptions = [
      ['unpaid', 'Belum digaji'],
      ['weekly', 'Mingguan'],
      ['monthly', 'Bulanan'],
      ['yearly', 'Tahunan'],
      ['all', 'Keseluruhan'],
    ]
      .map(
        ([value, label]) =>
          '<option value="' + value + '"' +
          (state.employeePerfMode === value ? ' selected' : '') + '>' +
          label +
          '</option>'
      )
      .join('');
    body.innerHTML =
      '<label class="field"><span>Periode</span>' +
      '<select class="input" id="employeePerfPeriod">' +
      periodOptions +
      '</select></label>' +
      '<p class="tiny muted">' + esc(period) + '</p>' +
      '<p class="tiny muted">Klik kartu untuk melihat rincian.</p>' +
      '<div class="stats-grid stats-grid--secondary">' +
      '<article class="stat-card is-clickable" role="button" tabindex="0" data-action="employee-perf-detail"><span class="stat-label">Nota</span><strong>' + intValue(data.jumlah_nota, 0) + '</strong></article>' +
      '<article class="stat-card is-clickable" role="button" tabindex="0" data-action="employee-perf-detail"><span class="stat-label">Jasa</span><strong>' + intValue(data.jumlah_jasa, 0) + '</strong></article>' +
      '<article class="stat-card is-clickable" role="button" tabindex="0" data-action="employee-perf-detail"><span class="stat-label">Sparepart</span><strong>' + intValue(data.jumlah_part, 0) + '</strong></article>' +
      '<article class="stat-card is-clickable" role="button" tabindex="0" data-action="employee-perf-detail"><span class="stat-label">Nilai servis</span><strong>' + fmtRp(data.total_nilai) + '</strong></article>' +
      '<article class="stat-card is-clickable" role="button" tabindex="0" data-action="employee-perf-detail"><span class="stat-label">Pelanggan</span><strong>' + intValue(data.pelanggan_unik, 0) + '</strong></article>' +
      '<article class="stat-card is-clickable" role="button" tabindex="0" data-action="employee-perf-detail"><span class="stat-label">Komisi</span><strong>' + fmtRp(data.komisi_total) + '</strong></article>' +
      '</div>';
    const periodSelect = $('#employeePerfPeriod');
    if (periodSelect) {
      periodSelect.addEventListener('change', () => loadEmployeePerformance());
    }
    const modeSuffix = employee.komisi_mode === 'PERSEN' ? '%' : ' / nota';
    const rates =
      'Barang ' +
      Number(employee.komisi_barang_nilai || 0) +
      modeSuffix +
      ' · Jasa ' +
      Number(employee.komisi_jasa_nilai || 0) +
      modeSuffix;
    const imbalanText =
      employee.jenis_imbalan === 'GAJI'
        ? 'Gaji ' + fmtRp(employee.gaji_bulanan || 0) + ' per bulan'
        : employee.jenis_imbalan === 'KOMISI_GAJI'
          ? 'Gaji ' + fmtRp(employee.gaji_bulanan || 0) + ' · ' + rates
          : rates;
    $('#employeePerfSubtitle').textContent =
      (employee.nama || 'Karyawan') + ' · ' + imbalanText;
  }

  function openEmployeePerfDetail() {
    const body = $('#employeePerfDetailBody');
    const empty = $('#employeePerfDetailEmpty');
    if (!body) return;
    const rows = state.employeePerfHistory || [];
    const employeeId = state.employeePerfId;
    $('#employeePerfDetailTitle').textContent =
      'Rincian ' + (state.employeePerfName || 'karyawan');
    if (!rows.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
    } else {
      if (empty) empty.classList.add('hidden');
      body.innerHTML = rows
        .map(
          (row) =>
            '<tr><td>' + esc(fmtDate(row.waktu_service)) + '</td>' +
            '<td>' + esc(row.no_nota) + '</td>' +
            '<td>' + esc(row.customer_nama) + '</td>' +
            '<td>' + esc(row.unit_deskripsi) + '</td>' +
            '<td class="text-right">' + fmtRp(row.total_servis) + '</td>' +
            '<td class="text-right">' + fmtRp(row.komisi) + '</td>' +
            '<td><div class="inline-action"><input type="number" class="input input-xs" id="empCommission-' +
            row.record_id + '" min="0" step="0.01" value="' +
            Number(row.komisi || 0) + '"><button type="button" class="btn btn-outline btn-xs" data-action="employee-commission-save" data-id="' +
            employeeId + '" data-record-id="' + row.record_id + '">Simpan</button></div></td></tr>'
        )
        .join('');
    }
    openModal('#employeePerfDetailModal');
  }

  async function saveEmployeeCommission(id, recordId) {
    const input = $('#empCommission-' + recordId);
    if (!input) return;
    try {
      await API.setEmployeeCommission(id, recordId, Number(input.value || 0));
      toast('Komisi manual disimpan.', 'success');
      await loadEmployeePerformance();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  /* ------------------------------ Supplier -------------------------------- */
  async function loadSuppliers() {
    try {
      state.suppliers = await API.suppliers('');
      if (!state.stock.length) await loadStock();
      renderSuppliers();
    } catch (err) {
      toast('Data supplier gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function renderSuppliers() {
    const body = $('#supplierBody');
    if (!body) return;
    const active = state.suppliers.filter((row) => row.aktif);
    const archivedCount = state.suppliers.length - active.length;
    const summary = $('#supplierSummary');
    if (summary) {
      summary.textContent =
        active.length +
        ' supplier aktif' +
        (archivedCount ? ' · ' + archivedCount + ' diarsip' : '');
    }
    if (!active.length) {
      body.innerHTML = '';
      $('#supplierEmpty').classList.remove('hidden');
      return;
    }
    $('#supplierEmpty').classList.add('hidden');
    body.innerHTML = active
      .map((supplier) => {
        const items = (supplier.items || [])
          .map((item) => item.nama)
          .join(', ') || '-';
        return (
          '<tr>' +
          '<td><span class="cell-primary">' +
          esc(supplier.nama) +
          '</span></td>' +
          '<td>' +
          esc(supplier.nomor_hp || '-') +
          '</td>' +
          '<td class="cell-sub">' +
          esc(items) +
          '</td>' +
          '<td class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="edit-supplier" data-id="' +
          supplier.id +
          '">Edit</button>' +
          '<button type="button" class="btn btn-ghost btn-xs" data-action="archive-supplier" data-id="' +
          supplier.id +
          '">Arsipkan</button>' +
          '<button type="button" class="btn btn-ghost btn-xs" data-action="delete-supplier" data-id="' +
          supplier.id +
          '">Hapus</button>' +
          '</td>' +
          '</tr>'
        );
      })
      .join('');
  }

  function populateSupplierItemPicker() {
    const select = $('#supplierItemPicker');
    if (!select) return;
    select.innerHTML =
      '<option value="">Pilih barang</option>' +
      state.stock
        .map(
          (item) =>
            '<option value="' +
            item.id +
            '">' +
            esc(item.nama) +
            ' (stok ' +
            item.jumlah +
            ')</option>'
        )
        .join('');
  }

  function renderSupplierSelectedItems() {
    const body = $('#supplierItemsBody');
    if (!body) return;
    const rows = state.supplierItemSelection
      .map((id) => state.stock.find((item) => item.id === id))
      .filter(Boolean);
    body.innerHTML = rows
      .map(
        (item) =>
          '<tr><td><span class="cell-primary">' +
          esc(item.nama) +
          '</span></td><td class="text-center">' +
          intValue(item.jumlah, 0) +
          '</td><td class="row-actions"><button type="button" class="btn btn-ghost btn-xs" data-action="supplier-item-remove" data-id="' +
          item.id +
          '">Hapus</button></td></tr>'
      )
      .join('');
    const empty = $('#supplierItemsEmpty');
    if (empty) empty.classList.toggle('hidden', rows.length > 0);
  }

  function addSupplierItem() {
    const select = $('#supplierItemPicker');
    if (!select) return;
    const id = intValue(select.value, 0);
    if (!id) return;
    if (!state.supplierItemSelection.includes(id)) {
      state.supplierItemSelection.push(id);
    }
    select.value = '';
    renderSupplierSelectedItems();
  }

  function removeSupplierItem(id) {
    state.supplierItemSelection = state.supplierItemSelection.filter(
      (value) => value !== id
    );
    renderSupplierSelectedItems();
  }

  function openSupplierModal(supplier) {
    const current = supplier || null;
    state.supplierItemSelection = current
      ? (current.items || []).map((item) => item.id)
      : [];
    if (!state.stock.length) {
      loadStock().then(() => {
        populateSupplierItemPicker();
        renderSupplierSelectedItems();
      });
    } else {
      populateSupplierItemPicker();
      renderSupplierSelectedItems();
    }
    $('#supplierModalTitle').textContent = current
      ? 'Edit supplier'
      : 'Tambah supplier';
    $('#supplierId').value = current ? current.id : '';
    $('#supplierNama').value = current ? current.nama : '';
    $('#supplierHp').value = current ? current.nomor_hp || '' : '';
    $('#supplierAlamat').value = current ? current.alamat || '' : '';
    $('#supplierCatatan').value = current ? current.catatan || '' : '';
    $('#supplierAktif').value = current && !current.aktif ? '0' : '1';
    openModal('#supplierModal');
    setTimeout(() => $('#supplierNama').focus(), 60);
  }

  async function handleSupplierSubmit(event) {
    event.preventDefault();
    const id = intValue($('#supplierId').value, 0);
    const selected = state.supplierItemSelection.slice();
    const payload = {
      nama: $('#supplierNama').value.trim(),
      nomor_hp: $('#supplierHp').value.trim(),
      alamat: $('#supplierAlamat').value.trim() || null,
      catatan: $('#supplierCatatan').value.trim() || null,
      aktif: $('#supplierAktif').value === '1',
      stock_item_ids: selected,
    };
    try {
      if (id) await API.updateSupplier(id, payload);
      else await API.createSupplier(payload);
      closeModal('#supplierModal');
      toast('Data supplier tersimpan.', 'success');
      await loadSuppliers();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function deleteSupplier(id) {
    const supplier = state.suppliers.find((row) => row.id === id);
    if (!supplier) return;
    if (
      !window.confirm(
        'Hapus supplier "' + supplier.nama + '"? Data barang tidak ikut terhapus.'
      )
    ) {
      return;
    }
    try {
      await API.deleteSupplier(id);
      toast('Supplier dihapus.', 'success');
      await loadSuppliers();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function archiveSupplier(id) {
    const supplier = state.suppliers.find((row) => row.id === id);
    if (!supplier) return;
    if (
      !window.confirm(
        'Arsipkan ' +
          supplier.nama +
          '? Data supplier tetap tersimpan dan bisa diaktifkan kembali.'
      )
    ) {
      return;
    }
    try {
      await API.updateSupplier(id, { aktif: false });
      toast('Supplier dipindahkan ke arsip.', 'success');
      await loadSuppliers();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function openSupplierArchive() {
    try {
      const all = await API.suppliers('');
      state.archivedSuppliers = all.filter((supplier) => !supplier.aktif);
      renderSupplierArchive();
      openModal('#supplierArchiveModal');
    } catch (err) {
      toast('Arsip supplier gagal dimuat. Coba lagi.', 'error', 6000);
    }
  }

  function renderSupplierArchive() {
    const body = $('#supplierArchiveBody');
    const empty = $('#supplierArchiveEmpty');
    if (!body) return;
    const suppliers = state.archivedSuppliers || [];
    $('#supplierArchiveSubtitle').textContent =
      suppliers.length + ' supplier di arsip. Data tetap tersimpan.';
    if (!suppliers.length) {
      body.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    body.innerHTML = suppliers
      .map((supplier) => {
        const items = (supplier.items || [])
          .map((item) => item.nama)
          .join(', ') || '-';
        return (
          '<tr><td><span class="cell-primary">' +
          esc(supplier.nama) +
          '</span></td><td>' +
          esc(supplier.nomor_hp || '-') +
          '</td><td class="cell-sub">' +
          esc(items) +
          '</td><td class="row-actions">' +
          '<button type="button" class="btn btn-primary btn-xs" data-action="reactivate-supplier" data-id="' +
          supplier.id +
          '">Aktifkan kembali</button></td></tr>'
        );
      })
      .join('');
  }

  async function reactivateSupplier(id) {
    const supplier =
      (state.archivedSuppliers || []).find((row) => row.id === id) ||
      state.suppliers.find((row) => row.id === id);
    if (!supplier) return;
    if (
      !window.confirm(
        'Aktifkan kembali ' +
          supplier.nama +
          '? Supplier akan muncul lagi di daftar aktif.'
      )
    ) {
      return;
    }
    try {
      await API.updateSupplier(id, { aktif: true });
      toast('Supplier diaktifkan kembali.', 'success');
      state.archivedSuppliers = (state.archivedSuppliers || []).filter(
        (row) => row.id !== id
      );
      renderSupplierArchive();
      await loadSuppliers();
    } catch (err) {
      toast(err.message, 'error', 6000);
    }
  }

  async function loadFollowupReseller() {
    const section = $('#followupResellerSection');
    if (!section) return;
    section.innerHTML = '<div class="empty-state sm">Memuat stok menipis...</div>';
    try {
      state.supplierGroups = await API.supplierFollowup();
      renderFollowupReseller();
    } catch (err) {
      section.innerHTML =
        '<div class="empty-state sm">Follow up reseller gagal dimuat. Coba lagi.</div>';
    }
  }

  function renderFollowupReseller() {
    const section = $('#followupResellerSection');
    if (!section) return;
    let lowCount = 0;
    let outCount = 0;
    const byItem = new Map();
    state.supplierGroups.forEach((group) => {
      group.items.forEach((item) => {
        if (item.status === 'HABIS') outCount += 1;
        else lowCount += 1;
        const entry = byItem.get(item.id) || { ...item, suppliers: [] };
        entry.suppliers.push({
          supplier_id: group.supplier_id,
          nama: group.nama,
          nomor_hp: group.nomor_hp,
        });
        byItem.set(item.id, entry);
      });
    });
    state.resellerItems = Array.from(byItem.values()).sort((a, b) =>
      a.status === b.status
        ? a.nama.localeCompare(b.nama, 'id')
        : a.status === 'HABIS'
          ? -1
          : 1
    );
    const set = (id, value) => {
      const el = $('#' + id);
      if (el) el.textContent = value;
    };
    set('resellerStatSuppliers', state.supplierGroups.length);
    set('resellerStatLow', lowCount);
    set('resellerStatOut', outCount);
    set('resellerStatItems', lowCount + outCount);

    if (!state.resellerItems.length) {
      section.innerHTML =
        '<div class="empty-state">Tidak ada barang menipis atau habis.</div>';
      return;
    }
    section.innerHTML =
      '<div class="receivable-list"><div class="receivable-group">' +
      state.resellerItems
        .map((item) => {
          const suppliers = item.suppliers.filter((row) =>
            waLink(row.nomor_hp)
          );
          const clickable = suppliers.length > 0;
          return (
            '<div class="pengerjaan-row' +
            (clickable ? ' is-clickable' : '') +
            '"' +
            (clickable
              ? ' role="button" tabindex="0" data-action="supplier-item-chat" data-id="' +
                item.id +
                '"'
              : '') +
            '><div class="pengerjaan-meta"><strong>' +
            esc(item.nama) +
            '</strong><span class="cell-sub">Sisa ' +
            intValue(item.jumlah, 0) +
            ' · minimum ' +
            intValue(item.minimum_efektif, 0) +
            '</span></div><div class="pengerjaan-actions">' +
            '<span class="badge ' +
            (item.status === 'HABIS' ? 'red' : 'amber') +
            '">' +
            (item.status === 'HABIS' ? 'Habis' : 'Menipis') +
            '</span>' +
            (clickable
              ? '<button type="button" class="btn btn-outline btn-xs" data-action="supplier-item-chat" data-id="' +
                item.id +
                '">WA</button>'
              : '<button type="button" class="btn btn-outline btn-xs" disabled title="Supplier belum diatur atau nomor WhatsApp tidak valid">WA</button>') +
            '</div></div>'
          );
        })
        .join('') +
      '</div></div>';
  }

  async function openSupplierItemChat(supplierId, itemId) {
    try {
      const preview = await API.supplierWhatsappPreview(supplierId, {
        stock_item_ids: [itemId],
      });
      openWaPreview({
        judul: 'Stok supplier · ' + preview.nama,
        subtitle: 'Periksa pesan untuk ' + preview.nama + '.',
        nomor: preview.nomor,
        text: preview.wa_text,
        note:
          'Membuka WhatsApp akan mencatat upaya penanyaan stok. ' +
          'Kasir tetap menekan kirim di WhatsApp.',
        onOpen: async (text) => {
          await API.supplierWhatsapp(supplierId, {
            stock_item_ids: [itemId],
            pesan: text,
          });
          toast('Pertanyaan stok tercatat.', 'success');
        },
      });
      closeModal('#supplierPickModal');
    } catch (err) {
      toast(err.message, 'error', 7000);
    }
  }

  function chatSupplierItem(itemId) {
    const item = state.resellerItems.find((row) => row.id === itemId);
    if (!item) return;
    const suppliers = item.suppliers.filter((row) => waLink(row.nomor_hp));
    if (!suppliers.length) {
      toast('Supplier untuk barang ini belum memiliki nomor WhatsApp valid.', 'warning');
      return;
    }
    if (suppliers.length === 1) {
      openSupplierItemChat(suppliers[0].supplier_id, item.id);
      return;
    }
    $('#supplierPickSubtitle').textContent =
      item.nama + ' · pilih supplier yang akan dihubungi.';
    $('#supplierPickBody').innerHTML = suppliers
      .map(
        (supplier) =>
          '<div class="pengerjaan-row"><div class="pengerjaan-meta"><strong>' +
          esc(supplier.nama) +
          '</strong><span class="cell-sub">' +
          esc(supplier.nomor_hp) +
          '</span></div><div class="pengerjaan-actions">' +
          '<button type="button" class="btn btn-primary btn-xs" data-action="supplier-item-chat-pick" data-id="' +
          supplier.supplier_id +
          '" data-item-id="' +
          item.id +
          '">Chat</button></div></div>'
      )
      .join('');
    openModal('#supplierPickModal');
  }

  function freezeFeatureSection(viewId, frozen) {
    const view = $('#' + viewId);
    if (!view) return;
    $$('#' + viewId + ' .card').forEach((card) => {
      card.classList.remove('feature-frozen');
      card.removeAttribute('inert');
      Array.from(card.children).forEach((child) => {
        if (child.classList.contains('card-head')) return;
        child.classList.toggle('feature-frozen', frozen);
        if (frozen) child.setAttribute('inert', '');
        else child.removeAttribute('inert');
      });
    });
  }

  function freezeViewContent(viewId, frozen) {
    const view = $('#' + viewId);
    if (!view) return;
    Array.from(view.children).forEach((child) => {
      if (child.classList.contains('page-head')) return;
      child.classList.toggle('feature-frozen', frozen);
      if (frozen) child.setAttribute('inert', '');
      else child.removeAttribute('inert');
    });
  }

  function syncFeatureToggles() {
    const ops = (state.config && state.config.ops) || {};
    const employeeAktif = ops.karyawan_aktif !== false;
    const supplierAktif = ops.supplier_aktif !== false;
    const followupAktif = ops.followup_aktif !== false;
    const employeeToggle = $('#employeeFeatureToggle');
    const supplierToggle = $('#supplierFeatureToggle');
    const followupToggle = $('#followupFeatureToggle');
    if (employeeToggle) employeeToggle.checked = employeeAktif;
    if (supplierToggle) supplierToggle.checked = supplierAktif;
    if (followupToggle) followupToggle.checked = followupAktif;
    $('#posEmployeeFields')?.classList.toggle('hidden', !employeeAktif);
    $('#dashboardEmployeeStats')?.classList.toggle('hidden', !employeeAktif);
    $('#dashboardPayrollCard')?.classList.toggle(
      'hidden',
      !employeeAktif || !state.payrollSummary
    );
    if (!employeeAktif) $('#payrollAlert')?.classList.add('hidden');
    $('#stockSupplierField')?.classList.toggle('hidden', !supplierAktif);
    const resellerTab = $('#followupTabSwitch [data-followup-tab="reseller"]');
    if (resellerTab) {
      resellerTab.classList.toggle(
        'hidden',
        !supplierAktif || isMenuHidden('reseller')
      );
    }
    if ($('#btnAddEmployee')) $('#btnAddEmployee').disabled = !employeeAktif;
    if ($('#btnEmployeeArchive')) $('#btnEmployeeArchive').disabled = !employeeAktif;
    if ($('#btnAddDebt')) $('#btnAddDebt').disabled = !employeeAktif;
    if ($('#btnAddSupplier')) $('#btnAddSupplier').disabled = !supplierAktif;
    freezeFeatureSection('view-employees', !employeeAktif);
    freezeFeatureSection('view-suppliers', !supplierAktif);
    freezeViewContent('view-followup', !followupAktif);
    if (!employeeAktif) {
      if ($('#posCashier')) $('#posCashier').value = '';
      $$('#posMechanics input').forEach((input) => {
        input.checked = false;
      });
      closeModal('#employeeModal');
      closeModal('#salaryModal');
      closeModal('#debtModal');
      closeModal('#employeePerfModal');
      closeModal('#employeePerfDetailModal');
      closeModal('#employeeDetailModal');
      closeModal('#employeeArchiveModal');
      closeModal('#debtDetailModal');
      closeModal('#payrollModal');
      closeModal('#payrollPayModal');
    }
    if (!supplierAktif) closeModal('#supplierModal');
    if (!followupAktif) {
      closeModal('#followupListModal');
      closeModal('#followupModal');
      closeModal('#followupStatusModal');
      closeModal('#followupRescheduleModal');
    }
  }

  async function updateFeatureToggle(key, enabled) {
    const labels = {
      karyawan_aktif: 'Fitur karyawan',
      supplier_aktif: 'Fitur supplier',
      followup_aktif: 'Fitur follow up',
    };
    try {
      const ops = await API.updateOpsSettings({ [key]: Boolean(enabled) });
      if (state.config) state.config.ops = ops;
      syncFeatureToggles();
      if (key === 'karyawan_aktif' && enabled) loadDashboard();
      toast(
        (labels[key] || 'Fitur') +
          (enabled ? ' diaktifkan.' : ' dinonaktifkan.'),
        'success'
      );
    } catch (err) {
      toast(err.message, 'error', 6000);
      syncFeatureToggles();
    }
  }

  /* ----------------------------- Settings --------------------------------- */
  function fillSettingsForm() {
    const bengkel = state.config && state.config.bengkel;
    if (!bengkel) return;

    const fields = {
      settingsNama: 'nama',
      settingsTagline: 'tagline',
      settingsAlamat: 'alamat',
      settingsTelepon: 'telepon',
      settingsWa: 'wa',
      settingsBankNama: 'bank_nama',
      settingsNoRekening: 'no_rekening',
      settingsAtasNama: 'atas_nama',
    };
    Object.keys(fields).forEach((id) => {
      const input = $('#' + id);
      if (input) input.value = bengkel[fields[id]] || '';
    });

    const note = $('#settingsAdminNote');
    if (note) {
      note.textContent =
        'Perubahan langsung tampil di aplikasi dan struk.';
    }
  }

  const RECEIPT_TOGGLE_FIELDS = [
    ['tagline', 'Tagline'],
    ['alamat', 'Alamat'],
    ['kontak', 'Telepon/WA'],
    ['no_nota', 'Nomor nota'],
    ['tanggal', 'Tanggal'],
    ['kasir', 'Nama kasir'],
    ['mekanik', 'Nama mekanik'],
    ['pelanggan', 'Pelanggan'],
    ['hp', 'Nomor HP pelanggan'],
    ['unit', 'Unit'],
    ['keluhan', 'Keluhan'],
    ['catatan', 'Catatan pengerjaan'],
    ['jasa', 'Tabel JASA'],
    ['part', 'Tabel PART'],
    ['total_jasa', 'Total Jasa'],
    ['total_part', 'Total Part'],
    ['diskon', 'Diskon'],
    ['grand_total', 'Grand Total'],
    ['metode', 'Metode bayar'],
    ['bayar', 'Nominal bayar'],
    ['kembalian', 'Kembalian'],
    ['status_bayar', 'Status bayar'],
    ['garansi', 'Garansi servis'],
    ['rekening', 'Rekening bengkel'],
    ['footer', 'Footer bukti garansi'],
  ];

  function fillReceiptForm() {
    const container = $('#receiptToggles');
    if (!container) return;
    const receipt = (state.config && state.config.receipt) || {};
    container.innerHTML = RECEIPT_TOGGLE_FIELDS.map(
      ([key, label]) =>
        '<label class="switch-row"><span>' +
        esc(label) +
        '</span><input type="checkbox" id="receiptShow-' +
        key +
        '"' +
        (receipt[key] === false ? '' : ' checked') +
        '><span class="switch-ui" aria-hidden="true"></span></label>'
    ).join('');
  }

  async function handleReceiptSettingsSubmit(event) {
    event.preventDefault();
    const payload = {};
    RECEIPT_TOGGLE_FIELDS.forEach(([key]) => {
      const input = $('#receiptShow-' + key);
      if (input) payload[key] = Boolean(input.checked);
    });
    const button = $('#receiptSettingsSave');
    setBusy(button, true, 'Menyimpan...');
    try {
      const receipt = await API.updateReceiptSettings(payload);
      if (state.config) state.config.receipt = receipt;
      fillReceiptForm();
      toast('Pengaturan struk disimpan.', 'success');
    } catch (err) {
      toast(err.message, 'error', 6000);
    } finally {
      setBusy(button, false);
    }
  }

  const OPS_INT_FIELDS = [
    { id: 'opsTempoHari', key: 'tempo_hari', low: 1, high: 365, label: 'Tempo piutang' },
    { id: 'opsStokMinimum', key: 'stok_minimum_default', low: 0, high: 1000000, label: 'Batas minimum stok' },
    { id: 'opsProspek1', key: 'prospek_hari_1', low: 7, high: 180, label: 'Prospek tahap 1' },
    { id: 'opsProspek2', key: 'prospek_hari_2', low: 30, high: 365, label: 'Prospek tahap 2' },
    { id: 'opsProspek3', key: 'prospek_hari_3', low: 60, high: 540, label: 'Prospek tahap 3' },
    { id: 'opsCooldownHari', key: 'cooldown_hari', low: 0, high: 90, label: 'Jeda follow-up' },
    { id: 'opsGaransiHari', key: 'garansi_akan_habis_hari', low: 1, high: 90, label: 'Pengingat garansi' },
    { id: 'opsGaransiArsip', key: 'garansi_arsip_hari', low: 1, high: 90, label: 'Arsip garansi' },
    { id: 'opsServisHari', key: 'servis_berkala_awal_hari', low: 1, high: 90, label: 'Pengingat servis berkala' },
    { id: 'opsPiutangJeda', key: 'piutang_jeda_hari', low: 1, high: 90, label: 'Jeda pengingat piutang' },
    { id: 'opsPiutangMaks', key: 'piutang_maks_pengingat', low: 1, high: 12, label: 'Maksimal pengingat piutang' },
    { id: 'opsBelumBisa', key: 'belum_bisa_hari', low: 1, high: 60, label: 'Belum bisa dihubungi lagi' },
    { id: 'opsBelumBisaPanjang', key: 'belum_bisa_panjang_hari', low: 7, high: 120, label: 'Belum bisa, pilihan panjang' },
    { id: 'opsMaksHari', key: 'maks_pesan_hari', low: 1, high: 5, label: 'Batas pesan per hari' },
    { id: 'opsMaksBulan', key: 'maks_pesan_bulan', low: 1, high: 20, label: 'Batas pesan per bulan' },
    { id: 'opsJedaProspek', key: 'jeda_prospek_servis_hari', low: 1, high: 90, label: 'Jeda prospek dan servis' },
    { id: 'opsMaksTidakRespon', key: 'maks_tidak_merespons', low: 1, high: 10, label: 'Batas tidak merespons' },
  ];

  function fillOpsForm() {
    const ops = state.config && state.config.ops;
    if (!ops || !$('#opsForm')) return;
    OPS_INT_FIELDS.forEach((field) => {
      const input = $('#' + field.id);
      if (input) input.value = String(intValue(ops[field.key], field.low));
    });
    const mulai = $('#opsFollowupMulai');
    const selesai = $('#opsFollowupSelesai');
    if (mulai) mulai.value = ops.followup_jam_mulai || '08:00';
    if (selesai) selesai.value = ops.followup_jam_selesai || '20:00';
  }

  async function handleOpsSubmit(event) {
    event.preventDefault();
    const payload = {};
    for (const field of OPS_INT_FIELDS) {
      const input = $('#' + field.id);
      if (!input) continue;
      const value = intValue(input.value, NaN);
      if (!Number.isFinite(value) || value < field.low || value > field.high) {
        toast(
          field.label + ' harus antara ' + field.low + ' dan ' + field.high + ' hari.',
          'warning'
        );
        input.focus();
        return;
      }
      payload[field.key] = value;
    }
    const timePattern = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
    const mulaiEl = $('#opsFollowupMulai');
    const selesaiEl = $('#opsFollowupSelesai');
    const mulai = mulaiEl ? mulaiEl.value : '';
    const selesai = selesaiEl ? selesaiEl.value : '';
    if (!timePattern.test(mulai) || !timePattern.test(selesai)) {
      toast('Isi jam mulai dan jam selesai follow up.', 'warning');
      if (mulaiEl) mulaiEl.focus();
      return;
    }
    if (mulai === selesai) {
      toast('Jam mulai dan jam selesai tidak boleh sama.', 'warning');
      return;
    }
    payload.followup_jam_mulai = mulai;
    payload.followup_jam_selesai = selesai;
    const button = $('#opsSave');
    setBusy(button, true, 'Menyimpan...');
    try {
      const ops = await API.updateOpsSettings(payload);
      if (state.config) state.config.ops = ops;
      fillOpsForm();
      syncFeatureToggles();
      toast('Pengaturan follow-up disimpan.', 'success');
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleSettingsSubmit(event) {
    event.preventDefault();
    const button = $('#settingsSave');
    const payload = {
      nama: $('#settingsNama').value.trim(),
      tagline: $('#settingsTagline').value.trim(),
      alamat: $('#settingsAlamat').value.trim(),
      telepon: $('#settingsTelepon').value.trim(),
      wa: $('#settingsWa').value.trim(),
      bank_nama: $('#settingsBankNama').value.trim(),
      no_rekening: $('#settingsNoRekening').value.trim(),
      atas_nama: $('#settingsAtasNama').value.trim(),
    };

    if (payload.nama.length < 2) {
      toast('Nama bengkel minimal 2 karakter.', 'warning');
      $('#settingsNama').focus();
      return;
    }

    setBusy(button, true, 'Menyimpan...');
    try {
      state.config.bengkel = await API.updateBengkel(payload);
      applyConfig();
      toast('Pengaturan bengkel tersimpan.', 'success');
    } catch (err) {
      toast('Pengaturan gagal disimpan. Coba lagi.', 'error', 6000);
    } finally {
      setBusy(button, false);
    }
  }

  /* ----------------------------- Telegram --------------------------------- */
  function renderTelegramStatus(telegram) {
    const status = $('#telegramStatus');
    if (!status) return;

    const banner = $('#telegramReconfigBanner');
    if (banner) {
      banner.classList.toggle('hidden', !telegram.needs_reconfig);
    }

    const parts = [];
    if (!telegram.configured) {
      parts.push('Bot token dan chat ID belum lengkap.');
    } else if (telegram.enabled) {
      parts.push(
        'Aktif, mengirim otomatis setiap hari pukul ' +
          (telegram.jam || '21:00') +
          '.'
      );
    } else {
      parts.push(
        'Pengiriman otomatis nonaktif (jadwal ' +
          (telegram.jam || '21:00') +
          ').'
      );
    }
    parts.push(
      telegram.last_sent_at
        ? 'Terakhir dikirim ' + fmtDateTime(telegram.last_sent_at) + '.'
        : 'Belum pernah dikirim.'
    );
    if (telegram.last_error) {
      parts.push('Pengiriman terakhir gagal. Periksa token, Chat ID, dan koneksi internet.');
    }
    status.textContent = parts.join(' ');
  }

  function fillTelegramForm() {
    const telegram = state.config && state.config.telegram;
    if (!telegram) return;
    $('#telegramAktif').checked = Boolean(telegram.enabled);
    $('#telegramJam').value = telegram.jam || '21:00';
    $('#telegramChatId').value = telegram.chat_id || '';
    renderTelegramStatus(telegram);
    renderBackupStatus();
    syncBackupPlatformUi();
    refreshBackupFolder();
    syncNativeBackupSchedule();
  }

  function syncBackupPlatformUi() {
    const native = hasNativeBridge();
    ['#backupFolderChoose', '#autoBackupFolderChoose'].forEach((selector) => {
      const button = $(selector);
      if (button) button.classList.toggle('hidden', !native);
    });
    const share = $('#shareBackupWrap');
    if (share) share.classList.toggle('hidden', !native);
  }

  function renderBackupFolder() {
    const folder = state.backupFolder || { configured: false, name: '' };
    const label =
      folder.configured && folder.name
        ? folder.name
        : 'Belum dipilih (memakai folder Unduhan)';
    ['#backupFolderName', '#autoBackupFolderName'].forEach((selector) => {
      const element = $(selector);
      if (element) element.textContent = label;
    });
    const hint = $('#settingsBackupHint');
    if (hint) {
      hint.textContent = folder.configured
        ? 'Menyimpan ke folder terpilih.'
        : 'Menyimpan ke folder Unduhan.';
    }
  }

  function refreshBackupFolder() {
    if (!hasNativeBridge()) {
      state.backupFolder = { configured: false, name: '' };
      renderBackupFolder();
      return;
    }
    window.BengkelBridge.call('backupFolderState', {}, 5000)
      .then(function (info) {
        state.backupFolder = {
          configured: Boolean(info && info.ok && info.configured),
          name: (info && info.name) || '',
        };
        renderBackupFolder();
      })
      .catch(function () {
        // Status folder opsional; backup tetap jatuh ke folder Unduhan.
      });
  }

  function chooseBackupFolder() {
    if (!hasNativeBridge()) {
      toast('Pemilihan folder hanya tersedia di aplikasi Android.', 'warning');
      return;
    }
    window.BengkelBridge.call('chooseBackupFolder', {}, 180000)
      .then(function (info) {
        if (!info || info.canceled) return;
        state.backupFolder = {
          configured: Boolean(info.configured),
          name: info.name || '',
        };
        renderBackupFolder();
        if (state.backupFolder.configured) {
          toast('Folder backup: ' + state.backupFolder.name + '.', 'success');
        }
      })
      .catch(function () {
        toast('Folder backup gagal dipilih. Coba lagi.', 'error', 7000);
      });
  }

  function renderBackupStatus() {
    const status = $('#backupStatus');
    if (!status) return;
    const backup = (state.config && state.config.backup) || {};

    const parts = [];
    parts.push(
      backup.last_local_at
        ? 'Backup terakhir: ' + fmtDateTime(backup.last_local_at) + '.'
        : 'Belum ada backup otomatis tersimpan.'
    );
    if (backup.last_status === 'failed' && backup.last_error) {
      parts.push('Backup otomatis terakhir gagal. Periksa ruang penyimpanan dan izin aplikasi.');
    }
    status.textContent = parts.join(' ');
    appendNativeBackupStatus(status, parts);

    const banner = $('#backupStaleBanner');
    if (!banner) return;
    // Peringatan basi hanya bermakna setelah ada backup pertama.
    banner.classList.toggle('hidden', !backup.last_local_at || !backup.stale);
    if (backup.stale) {
      banner.textContent =
        'Backup terakhir lebih dari ' +
        (backup.stale_days || 2) +
        ' hari. Periksa jadwal, koneksi, dan ruang penyimpanan.';
    }
  }

  function appendNativeBackupStatus(statusEl, parts) {
    // APK: tampilkan kegagalan jadwal native (mis. kredensial belum terbaca).
    if (!window.BengkelBridge || !window.BengkelBridge.available()) return;
    window.BengkelBridge.call('scheduledBackupStatus', {}, 5000)
      .then(function (info) {
        if (!info || !info.last_status || info.last_status === 'ok') return;
        if (!info.last_message) return;
        statusEl.textContent = parts
          .concat(['Jadwal backup: ' + info.last_message])
          .join(' ');
      })
      .catch(function () {
        // Status native opsional; jangan ganggu tampilan utama.
      });
  }

  function syncNativeBackupSchedule() {
    // APK: WorkManager memegang jadwal backup lokal, termasuk saat aplikasi
    // ditutup. Telegram hanya pengiriman tambahan yang diputuskan backend,
    // jadi jadwal ini tidak bergantung pada telegram.enabled.
    if (!window.BengkelBridge || !window.BengkelBridge.available()) return;
    const telegram = (state.config && state.config.telegram) || {};
    window.BengkelBridge.call(
      'syncScheduledBackup',
      {
        enabled: true,
        jam: telegram.jam || '21:00',
      },
      15000
    ).catch(function () {
      // Penjadwalan native opsional; halaman tetap berfungsi tanpa APK.
    });
  }

  async function handleTelegramSubmit(event) {
    event.preventDefault();
    const button = $('#telegramSave');
    const jam = $('#telegramJam').value || '21:00';
    const payload = {
      enabled: $('#telegramAktif').checked,
      jam: jam,
      chat_id: $('#telegramChatId').value.trim(),
      bot_token: $('#telegramToken').value.trim(),
    };

    setBusy(button, true, 'Menyimpan...');
    try {
      state.config.telegram = await API.updateTelegram(payload);
      $('#telegramToken').value = '';
      fillTelegramForm();
      toast('Pengaturan Telegram tersimpan.', 'success');
    } catch (err) {
      toast('Pengaturan Telegram gagal disimpan. Coba lagi.', 'error', 6000);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleTelegramSendNow() {
    const button = $('#telegramSendNow');
    const configured = Boolean(
      state.config && state.config.telegram && state.config.telegram.configured
    );

    setBusy(button, true, configured ? 'Mengirim...' : 'Menyiapkan...');
    try {
      const result = (await API.backupNow()) || {};
      const native = hasNativeBridge();
      const target = !native
        ? 'unduhan'
        : state.backupFolder.configured
          ? 'folder pilihan'
          : 'folder Unduhan';
      let local = null;
      let localError = '';
      if (result.filename) {
        try {
          local = await saveBackupCopy(result.filename);
        } catch (err) {
          localError = 'Backup tersimpan, tetapi gagal disalin ke folder.';
        }
      }
      const notes = result.jumlah_nota != null ? result.jumlah_nota + ' nota' : '';
      if (result.telegram_sent) {
        toast(
          'Backup terkirim ke Telegram' +
            (local ? ' dan ' + target : '') +
            (notes ? ' (' + notes + ')' : '') +
            '.',
          'success',
          7000
        );
      } else if (local) {
        toast(
          'Backup tersimpan di ' +
            target +
            '. Telegram belum dikirim: ' +
            (result.telegram_error || 'token dan chat ID belum lengkap.'),
          'warning',
          9000
        );
      } else {
        toast(localError || 'Backup gagal disimpan. Coba lagi.', 'error', 7000);
      }
      state.config = await API.getConfig();
      applyConfig();
    } catch (err) {
      toast(
        'Backup gagal dibuat. Periksa ruang penyimpanan lalu coba lagi.',
        'error',
        7000
      );
    } finally {
      setBusy(button, false);
    }
  }

  async function saveBackupCopy(filename) {
    if (hasNativeBridge()) {
      return window.BengkelBridge.call(
        'saveBackupFile',
        { filename: filename },
        180000
      );
    }
    return API.downloadBackupFile(filename);
  }

  /* ------------------------------ Restore --------------------------------- */
  function requestRestore() {
    const input = $('#settingsRestoreFile');
    if (input) input.click();
  }

  async function handleRestoreFile(event) {
    const input = event.target;
    const file = input.files && input.files[0];
    input.value = '';
    if (!file) return;

    const confirmed = window.confirm(
      'Pulihkan data dari "' +
        file.name +
        '"? Seluruh data saat ini akan diganti. Salinan pengaman tetap dibuat otomatis.'
    );
    if (!confirmed) return;

    const button = $('#settingsRestore');
    setBusy(button, true, 'Memulihkan...');
    try {
      await API.restoreDatabase(file);
      if (window.BengkelBridge && window.BengkelBridge.available()) {
        toast('Data berhasil dipulihkan. Menyiapkan ulang aplikasi...', 'success', 5000);
        try {
          await window.BengkelBridge.call('restartBackend', {}, 180000);
        } catch (err) {
          toast(
            'Data sudah dipulihkan, tetapi aplikasi gagal dimuat ulang. Tutup lalu buka aplikasi.',
            'error',
            9000
          );
          setBusy(button, false);
        }
        return;
      }
      toast('Data berhasil dipulihkan. Memuat ulang aplikasi...', 'success', 4000);
      setTimeout(() => window.location.reload(), 1200);
    } catch (err) {
      toast('Data gagal dipulihkan. Periksa file backup lalu coba lagi.', 'error', 7000);
      setBusy(button, false);
    }
  }

  async function handleBackup() {
    const button = $('#settingsBackup');
    setBusy(button, true, 'Membuat backup...');
    try {
      const result = (await API.downloadBackup()) || {};
      const locationText = result.location ? ' ke ' + result.location : '';
      toast(
        'Backup tersimpan' +
          locationText +
          ': ' +
          (result.filename || 'file backup'),
        'success',
        6000
      );
      refreshBackupFolder();
    } catch (err) {
      toast('Backup gagal dibuat. Periksa ruang penyimpanan lalu coba lagi.', 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleShareBackup() {
    if (!hasNativeBridge()) return;
    const button = $('#settingsShareBackup');
    setBusy(button, true, 'Menyiapkan...');
    try {
      await window.BengkelBridge.call('shareBackupNow', {}, 180000);
    } catch (err) {
      toast(
        (err && err.message) || 'Backup gagal dibagikan. Coba lagi.',
        'error',
        7000
      );
    } finally {
      setBusy(button, false);
    }
  }

  /* ------------------------------ Global events --------------------------- */
  function handleGlobalClick(event) {
    const target = event.target;

    const customerButton = target.closest('[data-customer-id]');
    if (customerButton) {
      const id = intValue(customerButton.dataset.customerId, 0);
      const customer = state.customerResults.find((item) => item.id === id);
      if (customer) chooseCustomer(customer);
      return;
    }

    const deleteUnitButton = target.closest('[data-delete-unit]');
    if (deleteUnitButton) {
      deleteUnit(intValue(deleteUnitButton.dataset.deleteUnit, 0));
      return;
    }

    const unitCard = target.closest('[data-unit-id]');
    if (unitCard) {
      selectUnit(intValue(unitCard.dataset.unitId, 0));
      return;
    }

    const removeButton = target.closest('[data-remove-kind]');
    if (removeButton) {
      removeItem(
        removeButton.dataset.removeKind,
        intValue(removeButton.dataset.index, -1)
      );
      return;
    }

    const actionButton = target.closest('[data-action]');
    if (actionButton) {
      handleAction(
        actionButton.dataset.action,
        intValue(actionButton.dataset.id, 0),
        actionButton.dataset
      );
      return;
    }

    if (!target.closest('.autocomplete')) {
      hideCustomerResults();
    }
  }

  function handleGlobalInput(event) {
    const target = event.target;
    if (
      target.id === 'keluhanInput' ||
      target.id === 'catatanPengerjaan' ||
      target.id === 'diskonInput' ||
      target.id === 'bayarInput' ||
      target.id === 'rencanaBayarInput' ||
      target.id === 'rencanaTanggalInput' ||
      target.id === 'kreditUangMukaInput'
    ) {
      invalidateNotaReview();
    }
    if (isMoneyField(target)) {
      formatMoneyField(target);
      if (target.matches('[data-kind][data-field]')) {
        handleItemInput(target);
        return;
      }
      if (
        target.id === 'diskonInput' ||
        target.id === 'bayarInput' ||
        target.id === 'rencanaBayarInput' ||
        target.id === 'kreditUangMukaInput'
      ) {
        updateSummary();
      }
      return;
    }
    if (target.matches('[data-kind][data-field]')) {
      handleItemInput(target);
      return;
    }
    if (target.id === 'diskonInput' || target.id === 'bayarInput') {
      updateSummary();
    }
  }

  function handleGlobalChange(event) {
    const target = event.target;
    if (target.matches('[data-kind][data-field="jumlah"]')) {
      renderItems();
    }
    if (target.id === 'paymentKreditAktif') {
      syncPaymentKreditUI();
    }
  }

  /* ------------------------------- Bindings ------------------------------- */
  function bindEvents() {
    applyNavOrder();
    applyMenuVisibility();
    fillMenuSettings();
    $('#menuToggleGrid').addEventListener('change', handleMenuToggleChange);
    $$('.nav-tab').forEach((tab) =>
      tab.addEventListener('click', () => {
        if (state.navEdit) setNavEdit(false);
        navigate(tab.dataset.view);
      })
    );
    $('#navOrderToggle').addEventListener('click', () =>
      setNavEdit(!state.navEdit)
    );
    $('#navTabs').addEventListener('click', (event) => {
      const moveButton = event.target.closest('[data-nav-move]');
      if (!moveButton) return;
      event.preventDefault();
      event.stopPropagation();
      const row = moveButton.closest('.nav-order-row');
      const tab = row && row.querySelector('.nav-tab');
      if (!tab) return;
      moveNavTab(tab.dataset.view, Number(moveButton.dataset.navMove));
    });

    $('#btnNewCustomerPos').addEventListener('click', () => openCustomerModal(true));

    $('#posReset').addEventListener('click', () => {
      if (window.confirm('Reset seluruh isian transaksi?')) resetPosState();
    });

    $$('#posModeSwitch button').forEach((button) => {
      button.addEventListener('click', () => setPosMode(button.dataset.posMode));
    });
    ['#garansiTukarAktif', '#garansiBarangAktif'].forEach((selector) => {
      $(selector)?.addEventListener('change', () => {
        updatePartWarrantyFields();
        invalidateNotaReview();
      });
    });
    ['#garansiTukarHari', '#garansiBarangNilai', '#garansiBarangSatuan'].forEach(
      (selector) => {
        $(selector)?.addEventListener('input', invalidateNotaReview);
        $(selector)?.addEventListener('change', invalidateNotaReview);
      }
    );

    $('#customerSearch').addEventListener('input', onCustomerSearchInput);
    $('#customerSearch').addEventListener('focus', () => {
      if ($('#customerResults').innerHTML.trim()) {
        $('#customerResults').classList.remove('hidden');
      }
    });

    $$('#unitTypeSwitch button').forEach((button) =>
      button.addEventListener('click', () => setUnitType(button.dataset.type))
    );
    $$('#stockFilterSwitch [data-stock-filter]').forEach((button) =>
      button.addEventListener('click', () => {
        state.stockFilter = button.dataset.stockFilter;
        renderStock();
      })
    );
    $('#btnAddUnit').addEventListener('click', handleAddUnit);
    $('#btnToggleNewUnit').addEventListener('click', () => {
      state.newUnitFormOpen = !state.newUnitFormOpen;
      syncNewUnitForm();
    });

    $('#jasaPicker').addEventListener('change', onJasaPickerChange);
    $('#partPicker').addEventListener('change', onPartPickerChange);
    $('#btnAddJob').addEventListener('click', addJob);
    $('#btnAddPart').addEventListener('click', addPart);
    $('#btnSaveComplaint').addEventListener('click', saveComplaint);

    $$('input[name="metode"]').forEach((radio) =>
      radio.addEventListener('change', handlePaymentModeChange)
    );
    $$('#jenisBayarSwitch button').forEach((button) =>
      button.addEventListener('click', () => {
        state.jenisBayar =
          button.dataset.jenis === 'KREDIT' ? 'KREDIT' : 'LUNAS';
        updateJenisBayar();
      })
    );
    $('#kreditUangMukaAktif').addEventListener('change', updateKreditUangMuka);
    $('#unitDitinggalAktif').addEventListener('change', invalidateNotaReview);
    $('#rencanaTanggalInput').addEventListener('change', invalidateNotaReview);
    $('#garansiAktif').addEventListener('change', updateGaransiFields);
    $('#garansiBulan').addEventListener('change', updateGaransiFields);
    $('#garansiBulanCustom').addEventListener('change', () => {
      $('#garansiBulanCustom').value = String(garansiBulanValue());
    });
    $('#btnReviewNota').addEventListener('click', reviewNota);
    $('#btnNotaEdit').addEventListener('click', editNotaReview);
    $('#notaReviewClose').addEventListener('click', editNotaReview);
    $('#btnNotaCorrect').addEventListener('click', confirmNotaReview);
    $('#btnSavePrint').addEventListener('click', () => saveTransaction(true));
    $('#btnSaveOnly').addEventListener('click', () => saveTransaction(false));
    $('#garansiAktif').addEventListener('change', invalidateNotaReview);
    $('#garansiBulan').addEventListener('change', invalidateNotaReview);
    $('#garansiBulanCustom').addEventListener('change', invalidateNotaReview);
    $('#garansiCatatan').addEventListener('input', invalidateNotaReview);

    $('#historySearch').addEventListener(
      'input',
      debounce(() => loadHistory($('#historySearch').value.trim()), 250)
    );
    $('#btnRefreshHistory').addEventListener('click', () =>
      loadHistory($('#historySearch').value.trim())
    );

    $('#customerDirectorySearch').addEventListener(
      'input',
      debounce(
        () =>
          loadCustomerDirectory(
            $('#customerDirectorySearch').value.trim()
          ),
        250
      )
    );
    $('#btnRefreshCustomers').addEventListener('click', () =>
      loadCustomerDirectory($('#customerDirectorySearch').value.trim())
    );
    $('#btnFollowupRefresh').addEventListener('click', loadFollowupPage);
    $('#btnAddCustomerDirectory').addEventListener('click', () =>
      openCustomerModal(false)
    );

    $('#btnAddEmployee').addEventListener('click', () => openEmployeeModal(null));
    $('#btnEmployeeArchive').addEventListener('click', openEmployeeArchive);
    $('#employeeDetailClose').addEventListener('click', () =>
      closeModal('#employeeDetailModal')
    );
    $('#employeeDetailDismiss').addEventListener('click', () =>
      closeModal('#employeeDetailModal')
    );
    $('#employeeArchiveClose').addEventListener('click', () =>
      closeModal('#employeeArchiveModal')
    );
    $('#employeeArchiveDismiss').addEventListener('click', () =>
      closeModal('#employeeArchiveModal')
    );
    $('#btnRefreshEmployees').addEventListener('click', loadEmployees);
    $$('#employeeTabSwitch [data-employee-tab]').forEach((button) =>
      button.addEventListener('click', () =>
        setEmployeeTab(button.dataset.employeeTab)
      )
    );
    $('#employeeForm').addEventListener('submit', handleEmployeeSubmit);
    $('#employeeJenisImbalan').addEventListener('change', syncEmployeeImbalanFields);
    $('#employeeKomisiMode').addEventListener('change', syncEmployeeImbalanFields);
    $('#employeePayrollPeriod').addEventListener('change', syncEmployeePayrollFields);
    $('#employeeFeatureToggle').addEventListener('change', (event) =>
      updateFeatureToggle('karyawan_aktif', event.target.checked)
    );
    $('#supplierFeatureToggle').addEventListener('change', (event) =>
      updateFeatureToggle('supplier_aktif', event.target.checked)
    );
    $('#followupFeatureToggle').addEventListener('change', (event) =>
      updateFeatureToggle('followup_aktif', event.target.checked)
    );
    $('#employeeModalClose').addEventListener('click', () =>
      closeModal('#employeeModal')
    );
    $('#employeeCancel').addEventListener('click', () =>
      closeModal('#employeeModal')
    );
    $('#btnAddDebt').addEventListener('click', () => openDebtModal(null));
    $('#debtForm').addEventListener('submit', handleDebtSubmit);
    $('#debtModalClose').addEventListener('click', () =>
      closeModal('#debtModal')
    );
    $('#debtCancel').addEventListener('click', () => closeModal('#debtModal'));
    $('#debtDetailClose').addEventListener('click', () =>
      closeModal('#debtDetailModal')
    );
    $('#debtDetailDismiss').addEventListener('click', () =>
      closeModal('#debtDetailModal')
    );
    $('#btnDebtHistoryAll').addEventListener('click', openDebtHistoryModal);
    $('#debtHistoryClose').addEventListener('click', () =>
      closeModal('#debtHistoryModal')
    );
    $('#debtHistoryDismiss').addEventListener('click', () =>
      closeModal('#debtHistoryModal')
    );
    $('#btnSalaryHistoryAll').addEventListener('click', openSalaryHistoryModal);
    $('#salaryHistoryClose').addEventListener('click', () =>
      closeModal('#salaryHistoryModal')
    );
    $('#salaryHistoryDismiss').addEventListener('click', () =>
      closeModal('#salaryHistoryModal')
    );
    $('#salaryForm').addEventListener('submit', handleSalarySubmit);
    $('#salaryMetode').addEventListener('change', syncSalaryBankRow);
    $('#salaryModalClose').addEventListener('click', () =>
      closeModal('#salaryModal')
    );
    $('#payrollModalClose').addEventListener('click', () =>
      closeModal('#payrollModal')
    );
    $('#payrollModalDismiss').addEventListener('click', () =>
      closeModal('#payrollModal')
    );
    $('#payrollPayClose').addEventListener('click', () =>
      closeModal('#payrollPayModal')
    );
    $('#payrollPayCancel').addEventListener('click', () =>
      closeModal('#payrollPayModal')
    );
    $('#payrollCicilAktif').addEventListener('change', (event) => {
      if (event.target.checked && $('#payrollFullDebtAktif')) {
        $('#payrollFullDebtAktif').checked = false;
      }
      $('#payrollCicilRow')?.classList.toggle(
        'hidden',
        !event.target.checked
      );
      if (event.target.checked) $('#payrollCicilNominal')?.focus();
      renderPayrollPaySummary();
    });
    $('#payrollFullDebtAktif').addEventListener('change', (event) => {
      if (event.target.checked) {
        if ($('#payrollCicilAktif')) $('#payrollCicilAktif').checked = false;
        $('#payrollCicilRow')?.classList.add('hidden');
      }
      renderPayrollPaySummary();
    });
    $('#payrollBonusAktif').addEventListener('change', (event) => {
      $('#payrollBonusRow')?.classList.toggle(
        'hidden',
        !event.target.checked
      );
      if (event.target.checked) $('#payrollBonusNominal')?.focus();
      renderPayrollPaySummary();
    });
    $('#payrollCicilNominal').addEventListener(
      'input',
      renderPayrollPaySummary
    );
    $('#payrollBonusNominal').addEventListener(
      'input',
      renderPayrollPaySummary
    );
    $('#salaryCancel').addEventListener('click', () =>
      closeModal('#salaryModal')
    );
    $('#employeePerfClose').addEventListener('click', () =>
      closeModal('#employeePerfModal')
    );
    $('#employeePerfDismiss').addEventListener('click', () =>
      closeModal('#employeePerfModal')
    );
    $('#employeePerfDetailClose').addEventListener('click', () =>
      closeModal('#employeePerfDetailModal')
    );
    $('#employeePerfDetailDismiss').addEventListener('click', () =>
      closeModal('#employeePerfDetailModal')
    );
    $('#btnAddSupplier').addEventListener('click', () => openSupplierModal(null));
    $('#btnRefreshSuppliers').addEventListener('click', loadSuppliers);
    $('#btnSupplierArchive').addEventListener('click', openSupplierArchive);
    $('#supplierArchiveClose').addEventListener('click', () =>
      closeModal('#supplierArchiveModal')
    );
    $('#supplierArchiveDismiss').addEventListener('click', () =>
      closeModal('#supplierArchiveModal')
    );
    $('#supplierForm').addEventListener('submit', handleSupplierSubmit);
    $('#btnAddSupplierItem').addEventListener('click', addSupplierItem);
    $('#supplierPickClose').addEventListener('click', () =>
      closeModal('#supplierPickModal')
    );
    $('#supplierPickDismiss').addEventListener('click', () =>
      closeModal('#supplierPickModal')
    );
    $('#supplierModalClose').addEventListener('click', () =>
      closeModal('#supplierModal')
    );
    $('#supplierCancel').addEventListener('click', () =>
      closeModal('#supplierModal')
    );
    $$('#followupTabSwitch [data-followup-tab]').forEach((button) =>
      button.addEventListener('click', () => {
        state.followupTab = button.dataset.followupTab;
        loadFollowupPage();
      })
    );
    $('#btnAddStock').addEventListener('click', () => openStockModal(null));
    $('#btnAddJasa').addEventListener('click', () => openJasaModal(null));

    $('#btnLoadReport').addEventListener('click', loadReport);
    $('#reportPeriod').addEventListener('change', loadReport);
    $$('#reportTabSwitch [data-report-tab]').forEach((button) =>
      button.addEventListener('click', () => setReportTab(button.dataset.reportTab))
    );

    $('#receiptWidthSwitch').addEventListener('click', onReceiptWidthClick);
    $('#btnBrowserPrint').addEventListener('click', () => {
      if (!state.receipt) return;
      browserPrint(currentReceiptLines(), state.receiptWidth);
      setReceiptPrintStatus(
        'info',
        'Dialog cetak browser dibuka. Pilih printer lalu konfirmasi.',
        {}
      );
      sendReceiptToWhatsapp(state.receipt);
    });
    $('#btnReceiptCopyText').addEventListener('click', () => {
      if (!state.receipt) return;
      copyText(currentReceiptLines().join('\n'), 'Teks struk disalin.');
    });
    const waFallback = $('#btnReceiptWhatsappFallback');
    if (waFallback) {
      waFallback.addEventListener('click', () => {
        if (state.receipt) sendReceiptToWhatsapp(state.receipt);
      });
    }

    $('#waModalOpen').addEventListener('click', handleWaOpen);
    $('#waModalClose').addEventListener('click', () => closeModal('#waModal'));
    $('#waModalCancel').addEventListener('click', () => closeModal('#waModal'));

    $('#followupListClose').addEventListener('click', closeFollowupList);
    $('#followupListDismiss').addEventListener('click', closeFollowupList);
    $('#followupModalClose').addEventListener('click', () =>
      closeModal('#followupModal')
    );
    $('#followupModalDismiss').addEventListener('click', () =>
      closeModal('#followupModal')
    );
    $('#followupStatusClose').addEventListener('click', () =>
      closeModal('#followupStatusModal')
    );
    $('#followupStatusDismiss').addEventListener('click', () =>
      closeModal('#followupStatusModal')
    );
    $('#followupRescheduleClose').addEventListener('click', () =>
      closeModal('#followupRescheduleModal')
    );
    $('#followupRescheduleDismiss').addEventListener('click', () =>
      closeModal('#followupRescheduleModal')
    );
    $('#receivablesClose').addEventListener('click', () =>
      closeModal('#receivablesModal')
    );
    $('#receivablesDismiss').addEventListener('click', () =>
      closeModal('#receivablesModal')
    );
    $('#rescheduleClose').addEventListener('click', () =>
      closeModal('#rescheduleModal')
    );
    $('#rescheduleCancel').addEventListener('click', () =>
      closeModal('#rescheduleModal')
    );
    $('#rescheduleForm').addEventListener('submit', submitReschedule);
    $('#pengerjaanClose').addEventListener('click', () =>
      closeModal('#pengerjaanModal')
    );
    $('#pengerjaanDismiss').addEventListener('click', () =>
      closeModal('#pengerjaanModal')
    );
    $('#pengerjaanStatusClose').addEventListener('click', () =>
      closeModal('#pengerjaanStatusModal')
    );
    $('#pengerjaanStatusDismiss').addEventListener('click', () =>
      closeModal('#pengerjaanStatusModal')
    );

    $('#receiptClose').addEventListener('click', () => closeModal('#receiptModal'));
    $('#notaListClose').addEventListener('click', () =>
      closeModal('#notaListModal')
    );
    $('#notaListDismiss').addEventListener('click', () =>
      closeModal('#notaListModal')
    );
    $('#recordClose').addEventListener('click', () => closeModal('#recordModal'));
    $('#recordDismiss').addEventListener('click', () =>
      closeModal('#recordModal')
    );
    $('#btnExchangePart').addEventListener('click', openExchangeModal);
    $('#exchangeClose').addEventListener('click', () =>
      closeModal('#exchangeModal')
    );
    $('#exchangeCancel').addEventListener('click', () =>
      closeModal('#exchangeModal')
    );
    $('#exchangeSubmit').addEventListener('click', submitExchange);
    $('#exchangePart').addEventListener('change', syncExchangeQtyMax);
    $('#exchangeQty').addEventListener('input', syncExchangeSummary);
    $('#exchangePrice').addEventListener('input', syncExchangeSummary);
    $('#exchangeStock').addEventListener('change', () => {
      const select = $('#exchangeStock');
      const option = select?.options?.[select.selectedIndex];
      $('#exchangePrice').value = String(
        Math.round(Number(option?.dataset.price || 0))
      );
      syncExchangeSummary();
    });
    $('#customerDetailClose').addEventListener('click', () =>
      closeModal('#customerDetailModal')
    );
    $('#customerStatClose').addEventListener('click', () =>
      closeModal('#customerStatModal')
    );
    $('#customerStatDismiss').addEventListener('click', () =>
      closeModal('#customerStatModal')
    );
    $('#customerDetailDismiss').addEventListener('click', () =>
      closeModal('#customerDetailModal')
    );
    $('#btnCustomerDetailService').addEventListener('click', async () => {
      if (!state.detailCustomer) return;
      const customer = state.detailCustomer;
      closeAllModals();
      navigate('pos');
      await chooseCustomer(customer);
    });
    $('#customerModalClose').addEventListener('click', () =>
      closeModal('#customerModal')
    );
    $('#customerCancel').addEventListener('click', () =>
      closeModal('#customerModal')
    );
    $('#stockModalClose').addEventListener('click', () => closeModal('#stockModal'));
    $('#stockCancel').addEventListener('click', () => closeModal('#stockModal'));
    $('#jasaModalClose').addEventListener('click', () => closeModal('#jasaModal'));
    $('#jasaCancel').addEventListener('click', () => closeModal('#jasaModal'));

    $('#customerForm').addEventListener('submit', handleCustomerSubmit);
    $('#stockForm').addEventListener('submit', handleStockSubmit);
    $('#jasaForm').addEventListener('submit', handleJasaSubmit);
    $('#settingsForm').addEventListener('submit', handleSettingsSubmit);
    $('#settingsReset').addEventListener('click', fillSettingsForm);
    $('#opsForm').addEventListener('submit', handleOpsSubmit);
    $('#receiptSettingsForm').addEventListener('submit', handleReceiptSettingsSubmit);

    $('#settingsBackup').addEventListener('click', handleBackup);
    $('#backupFolderChoose').addEventListener('click', chooseBackupFolder);
    $('#autoBackupFolderChoose').addEventListener('click', chooseBackupFolder);
    $('#settingsShareBackup').addEventListener('click', handleShareBackup);
    $('#settingsRestore').addEventListener('click', requestRestore);
    $('#settingsRestoreFile').addEventListener('change', handleRestoreFile);

    $('#telegramForm').addEventListener('submit', handleTelegramSubmit);
    $('#telegramSendNow').addEventListener('click', handleTelegramSendNow);

    $('#authSetupForm').addEventListener('submit', handleAuthSetupSubmit);
    $('#authLoginForm').addEventListener('submit', handleAuthLoginSubmit);
    $$('#authSetupPin, #authSetupPinConfirm, #authLoginPin').forEach((input) => {
      input.addEventListener('input', () => {
        const digits = normalizePin(input.value);
        if (input.value !== digits) input.value = digits;
      });
    });

    document.addEventListener('click', handleGlobalClick);
    document.addEventListener('input', handleGlobalInput);
    document.addEventListener('change', handleGlobalChange);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeAllModals();
      if (
        (event.key === 'Enter' || event.key === ' ') &&
        event.target.matches('[role="button"][data-action]')
      ) {
        event.preventDefault();
        handleAction(
          event.target.dataset.action,
          intValue(event.target.dataset.id, 0),
          event.target.dataset
        );
      }
    });

    $$('.modal-backdrop').forEach((backdrop) => {
      backdrop.addEventListener('mousedown', (event) => {
        if (event.target === backdrop) closeModal('#' + backdrop.id);
      });
    });
  }

  /* ------------------------------ Tampilan -------------------------------- */
  const THEME_KEY = 'bengkel.theme';
  const THEME_COLOR = { light: '#f7f7f7', dark: '#0d0d0e' };

  function normalizeTheme(value) {
    return String(value) === 'dark' ? 'dark' : 'light';
  }

  function storedTheme() {
    try {
      return normalizeTheme(window.localStorage.getItem(THEME_KEY));
    } catch (error) {
      return 'light';
    }
  }

  function syncThemeUI(theme) {
    $$('#themeSwitch button').forEach((button) => {
      const active = button.dataset.themeValue === theme;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function applyTheme(theme, persist) {
    const next = normalizeTheme(theme);
    document.documentElement.setAttribute('data-theme', next);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', THEME_COLOR[next]);
    if (persist) {
      try {
        window.localStorage.setItem(THEME_KEY, next);
      } catch (error) {
        // Mode tetap berlaku untuk sesi ini meski penyimpanan diblokir.
      }
    }
    const shell = window.BengkelPin;
    if (shell && typeof shell.applyChromeTheme === 'function') {
      try {
        shell.applyChromeTheme(next);
      } catch (error) {
        // Status bar native memakai warna bawaan bila jembatan tidak tersedia.
      }
    }
    syncThemeUI(next);
  }

  function initTheme() {
    applyTheme(storedTheme(), false);
    $$('#themeSwitch button').forEach((button) => {
      button.addEventListener('click', () =>
        applyTheme(button.dataset.themeValue, true)
      );
    });
  }

  function initSettingsAccordion() {
    $$('#view-settings .settings-collapsible').forEach((card) => {
      const head = card.querySelector(':scope > .card-head');
      if (!head) return;
      card.classList.add('is-collapsed');
      head.setAttribute('role', 'button');
      head.setAttribute('tabindex', '0');
      head.setAttribute('aria-expanded', 'false');
      const toggle = () => {
        const collapsed = card.classList.toggle('is-collapsed');
        head.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      };
      head.addEventListener('click', (event) => {
        if (event.target.closest('button, a, input, select, textarea, label')) {
          return;
        }
        toggle();
      });
      head.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          toggle();
        }
      });
    });
  }

  /* ---------------------------- PIN keamanan APK --------------------------- */
  function initPinSecurityCard() {
    const bridge = window.BengkelPin;
    const card = $('#pinSecurityCard');
    if (!card || !bridge) return;
    card.classList.remove('hidden');

    const select = $('#pinIdleMinutes');
    const current = String(bridge.getIdleMinutes());
    if (Array.from(select.options).some((option) => option.value === current)) {
      select.value = current;
    }
    select.addEventListener('change', () => {
      bridge.setIdleMinutes(Number(select.value));
    });
    $('#pinLockNow').addEventListener('click', () => bridge.lockNow());
  }

  /* --------------------------------- Init --------------------------------- */
  async function startApp() {
    hideAuthGate();
    try {
      const results = await Promise.all([
        API.getConfig(),
        API.stock(),
        API.jasa(),
        API.employees(false),
        API.suppliers(''),
      ]);
      state.config = results[0];
      state.stock = results[1];
      state.jasa = results[2];
      state.employees = results[3] || [];
      state.suppliers = results[4] || [];
      applyConfig();
      populatePickers();
      populateEmployeeOptions();
      renderStock();
      renderJasa();
      await loadPrinterSettings(false);
    } catch (err) {
      if (err.status !== 401) {
        toast('Aplikasi gagal memuat data awal. Tutup lalu buka lagi.', 'error', 8000);
      }
      return;
    }

    authState.started = true;
    resetPosState();
    refreshReceiptPrinterUI();
    await loadDashboard();
  }

  async function init() {
    initTheme();
    bindEvents();
    initSettingsAccordion();
    $$('.money-input').forEach(formatMoneyField);
    startClock();
    initPrinter();
    initPinSecurityCard();
    window.addEventListener('bengkel:unauthorized', handleUnauthorized);

    const ready = await ensureAuthenticated();
    if (!ready) return;
    await startApp();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
