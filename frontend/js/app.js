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

  function parseMoney(value) {
    const digits = String(value == null ? '' : value).replace(/[^\d]/g, '');
    return digits ? Number(digits) : 0;
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
    if (unit.unit_type === 'MOBIL') {
      let text = unit.nopol || '-';
      if (unit.jenis_mobil) text += ' (' + unit.jenis_mobil + ')';
      return text;
    }
    let text = '[BAWA RADIATOR SAJA] ' + (unit.label_radiator || '-');
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
    unitType: 'MOBIL',
    jobs: [],
    parts: [],
    stock: [],
    jasa: [],
    history: [],
    customerDirectory: [],
    dashboardRecords: [],
    dashboardToday: [],
    reportRows: [],
    reportLabel: 'Hari ini',
    notaList: [],
    detailRecord: null,
    detailRecordCustomerId: null,
    detailCustomer: null,
    receipt: null,
    receiptWidth: 58,
    customerReturnToPos: false,
    editingStock: null,
    editingJasa: null,
    searchTimer: null,
    saving: false,
    pendingRequest: null,
    lastBackup: null,
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

  function openModal(selector) {
    const modal = $(selector);
    if (!modal) return;
    modalLayer += 1;
    modal.style.zIndex = String(modalLayer);
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeModal(selector) {
    const modal = $(selector);
    if (!modal) return;
    modal.classList.add('hidden');
    if (!$$('.modal-backdrop:not(.hidden)').length) {
      document.body.style.overflow = '';
      modalLayer = 100;
    }
  }

  function closeAllModals() {
    $$('.modal-backdrop').forEach((modal) => modal.classList.add('hidden'));
    document.body.style.overflow = '';
    modalLayer = 100;
  }

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
    if (!record.bergaransi) {
      return '<span class="badge gray">Tanpa garansi</span>';
    }
    if (record.status_klaim === 'Sudah claim') {
      return '<span class="badge blue">Sudah claim</span>';
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
  function navigate(view) {
    $$('.nav-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.view === view);
    });
    $$('.view').forEach((section) => section.classList.add('hidden'));
    const target = $('#view-' + view);
    if (target) target.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (view === 'dashboard') loadDashboard();
    if (view === 'history') loadHistory($('#historySearch').value.trim());
    if (view === 'stock') renderStock();
    if (view === 'jasa') renderJasa();
    if (view === 'customers') {
      loadCustomerDirectory($('#customerDirectorySearch').value.trim());
    }
    if (view === 'report') loadReport();
    if (view === 'settings') {
      fillSettingsForm();
      fillTelegramForm();
    }
    if (view === 'pos' && !state.selectedCustomer) {
      const search = $('#customerSearch');
      if (search) search.focus();
    }
  }

  /* ------------------------------ Config ---------------------------------- */
  function applyConfig() {
    const config = state.config;
    if (!config) return;

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
    updateReceiptNotice();
    fillSettingsForm();
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
    if (!state.selectedCustomer) {
      label.textContent = 'Belum ada pelanggan dipilih';
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
    $('#unitCard').classList.add('hidden');
    $('#complaintCard').classList.add('hidden');
    $('#itemsCard').classList.add('hidden');
    $('#unitList').innerHTML = '';
    renderSelectedCustomer();
    renderItems();
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
      toast('Pencarian pelanggan gagal: ' + err.message, 'error');
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
        '<div class="autocomplete-empty">Pelanggan tidak ditemukan. Gunakan tombol Pelanggan Baru.</div>';
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
    state.selectedCustomer = customer;
    state.selectedUnit = null;
    state.jobs = [];
    state.parts = [];
    state.units = [];

    $('#customerSearch').value = customer.nama;
    hideCustomerResults();
    renderSelectedCustomer();
    renderItems();
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
      toast('Gagal memuat unit pelanggan: ' + err.message, 'error');
    }
  }

  function renderUnits() {
    const container = $('#unitList');
    if (!container) return;

    if (!state.units.length) {
      container.innerHTML =
        '<div class="empty-state sm">Belum ada unit terdaftar. Daftarkan mobil atau radiator baru di bawah.</div>';
      return;
    }

    container.innerHTML = state.units
      .map((unit) => {
        const selected =
          state.selectedUnit && state.selectedUnit.id === unit.id;
        const isCar = unit.unit_type === 'MOBIL';
        const title = isCar ? unit.nopol || '-' : unit.label_radiator || '-';
        const subtitle = isCar
          ? [unit.jenis_mobil, unit.tahun_mobil].filter(Boolean).join(' - ') ||
            'Mobil lengkap'
          : unit.tipe_radiator || 'Radiator copotan';
        const tag = isCar
          ? ''
          : '<span class="unit-label">TANPA NOPOL</span>';
        return (
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
          tag +
          '</span>' +
          '</button>'
        );
      })
      .join('');
  }

  function selectUnit(unitId) {
    const unit = state.units.find((item) => item.id === unitId);
    if (!unit) return;
    state.selectedUnit = unit;
    renderUnits();
    $('#complaintCard').classList.remove('hidden');
    $('#itemsCard').classList.remove('hidden');
    updateSummaryCustomer();
    updateSummary();
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
      renderUnits();
      selectUnit(unit.id);
      resetUnitForm();
      toast(
        unit.unit_type === 'RADIATOR_ONLY'
          ? 'Unit radiator ' + unit.label_radiator + ' tersimpan.'
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
    $('#customerModalTitle').textContent = 'Tambah Pelanggan';
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
    const title = isCar ? unit.nopol || '-' : unit.label_radiator || '-';
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
      (isCar ? 'MOBIL' : 'RADIATOR') +
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
      '">Buat Servis</button>' +
      '</div>' +
      '</article>'
    );
  }

  async function loadCustomerDirectory(query) {
    try {
      state.customerDirectory = await API.customerOverview(query || '');
      renderCustomerDirectory();
    } catch (err) {
      toast('Gagal memuat database pelanggan: ' + err.message, 'error', 6000);
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
    $('#customerDirectoryCount').textContent = customers.length + ' pelanggan';

    if (!customers.length) {
      grid.innerHTML = '';
      const query = $('#customerDirectorySearch').value.trim();
      $('#customerDirectoryEmpty').textContent = query
        ? 'Tidak ada pelanggan yang cocok dengan pencarian "' + query + '".'
        : 'Belum ada pelanggan terdaftar. Tambahkan pelanggan baru untuk mulai mencatat kepemilikan unit.';
      $('#customerDirectoryEmpty').classList.remove('hidden');
      return;
    }

    $('#customerDirectoryEmpty').classList.add('hidden');
    grid.innerHTML = customers.map(customerCardHtml).join('');
  }

  /* ------------------------------- Items ---------------------------------- */
  function populatePickers() {
    const jasaPicker = $('#jasaPicker');
    if (jasaPicker) {
      jasaPicker.innerHTML =
        '<option value="">- Pilih tarif jasa (opsional) -</option>' +
        state.jasa
          .map(
            (jasa) =>
              '<option value="' +
              jasa.id +
              '">' +
              esc(jasa.nama) +
              ' - ' +
              fmtRp(jasa.harga_standar) +
              '</option>'
          )
          .join('');
    }

    const partPicker = $('#partPicker');
    if (partPicker) {
      partPicker.innerHTML =
        '<option value="">- Pilih sparepart (opsional) -</option>' +
        state.stock
          .map(
            (item) =>
              '<option value="' +
              item.id +
              '">' +
              esc(item.nama) +
              ' (stok ' +
              item.jumlah +
              ') - ' +
              fmtRp(item.harga_jual) +
              '</option>'
          )
          .join('');
    }
  }

  function onJasaPickerChange() {
    const id = intValue($('#jasaPicker').value, 0);
    const master = state.jasa.find((jasa) => jasa.id === id);
    if (!master) return;
    $('#jasaNama').value = master.nama;
    $('#jasaHarga').value = String(Math.round(Number(master.harga_standar) || 0));
    $('#jasaQty').value = '1';
  }

  function onPartPickerChange() {
    const id = intValue($('#partPicker').value, 0);
    const stock = state.stock.find((item) => item.id === id);
    const hint = $('#partStockHint');
    if (!stock) {
      if (hint) hint.textContent = 'Stok gudang otomatis dipotong.';
      return;
    }
    $('#partNama').value = stock.nama;
    $('#partHarga').value = String(Math.round(Number(stock.harga_jual) || 0));
    $('#partQty').value = '1';
    if (hint) {
      hint.textContent =
        'Stok tersedia: ' +
        stock.jumlah +
        ' - harga patokan ' +
        fmtRp(stock.harga_jual);
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
    const price = parseMoney($('#jasaHarga').value);

    state.jobs.push({
      harga_jasa_id: master ? master.id : null,
      deskripsi: description,
      jumlah: quantity,
      harga: String(price),
    });

    $('#jasaPicker').value = '';
    $('#jasaNama').value = '';
    $('#jasaQty').value = '1';
    $('#jasaHarga').value = '';
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
    const price = parseMoney($('#partHarga').value);

    state.parts.push({
      stock_item_id: stock ? stock.id : null,
      nama_part: name,
      jumlah: quantity,
      harga_satuan: String(price),
    });

    $('#partPicker').value = '';
    $('#partNama').value = '';
    $('#partQty').value = '1';
    $('#partHarga').value = '';
    $('#partStockHint').textContent = 'Stok gudang otomatis dipotong.';
    renderItems();
  }

  function renderItems() {
    const jobsBody = $('#jobsBody');
    const partsBody = $('#partsBody');
    if (!jobsBody || !partsBody) return;

    jobsBody.innerHTML = state.jobs
      .map((job, index) => {
        const subtotal = parseMoney(job.harga) * intValue(job.jumlah, 0);
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
          esc(job.harga) +
          '"></td>' +
          '<td class="text-right item-subtotal">' +
          fmtRp(subtotal) +
          '</td>' +
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
        const subtotal =
          parseMoney(part.harga_satuan) * intValue(part.jumlah, 0);
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
          esc(part.harga_satuan) +
          '"></td>' +
          '<td class="text-right item-subtotal">' +
          fmtRp(subtotal) +
          '</td>' +
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

    item[field] = target.value;

    if (field === 'jumlah' || field === 'harga' || field === 'harga_satuan') {
      const row = target.closest('tr');
      if (row) {
        const unitPrice =
          kind === 'job' ? parseMoney(item.harga) : parseMoney(item.harga_satuan);
        const subtotal = unitPrice * intValue(item.jumlah, 0);
        const cell = row.querySelector('.item-subtotal');
        if (cell) cell.textContent = fmtRp(subtotal);
      }
    }
    updateSummary();
  }

  /* ------------------------------ Summary --------------------------------- */
  function calcTotals() {
    const jobTotal = state.jobs.reduce(
      (sum, job) => sum + parseMoney(job.harga) * intValue(job.jumlah, 0),
      0
    );
    const partTotal = state.parts.reduce(
      (sum, part) =>
        sum + parseMoney(part.harga_satuan) * intValue(part.jumlah, 0),
      0
    );
    const subtotal = jobTotal + partTotal;
    const discount = Math.min(parseMoney($('#diskonInput').value), subtotal);
    const grand = Math.max(0, subtotal - discount);
    return { jobTotal, partTotal, discount, grand };
  }

  function getMetode() {
    const checked = $('input[name="metode"]:checked');
    return checked ? checked.value : 'CASH';
  }

  function updateSummary() {
    const jobEl = $('#jobSubtotal');
    if (!jobEl) return;

    const totals = calcTotals();
    $('#jobSubtotal').textContent = fmtRp(totals.jobTotal);
    $('#partSubtotal').textContent = fmtRp(totals.partTotal);
    $('#grandTotalValue').textContent = fmtRp(totals.grand);

    const transfer = getMetode() === 'TRANSFER';
    const paidInput = $('#bayarInput');
    paidInput.disabled = transfer;
    $('#bankInfo').classList.toggle('hidden', !transfer);

    if (transfer) paidInput.value = String(totals.grand);

    const paid = transfer ? totals.grand : parseMoney(paidInput.value);
    const changeEl = $('#kembalianValue');
    const changeRow = changeEl ? changeEl.parentElement : null;

    if (changeEl) {
      if (paid >= totals.grand) {
        changeEl.textContent = fmtRp(paid - totals.grand);
        if (changeRow) changeRow.classList.remove('short');
      } else {
        changeEl.textContent = 'Kurang ' + fmtRp(totals.grand - paid);
        if (changeRow) changeRow.classList.add('short');
      }
    }
  }

  function handlePaymentModeChange() {
    updateSummary();
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

  function resetPosState() {
    state.pendingRequest = null;
    state.selectedCustomer = null;
    state.customerResults = [];
    state.units = [];
    state.selectedUnit = null;
    state.jobs = [];
    state.parts = [];
    state.unitType = 'MOBIL';

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
    $('#metodeCash').checked = true;
    $('#metodeTransfer').checked = false;
    $('#garansiAktif').checked = true;

    if (state.config) {
      setGaransiBulan(state.config.default_garansi_bulan || 1);
      $('#garansiCatatan').value = state.config.garansi_syarat || '';
    }

    setUnitType('MOBIL');
    resetUnitForm();
    updateGaransiFields();
    renderSelectedCustomer();
    renderItems();
    updateSummary();
  }

  /* ---------------------------- Transaction ------------------------------- */
  function buildTransactionPayload() {
    const totals = calcTotals();
    const metode = getMetode();
    const paid =
      metode === 'CASH' ? parseMoney($('#bayarInput').value) : totals.grand;

    return {
      unit_id: state.selectedUnit.id,
      keluhan_awal: $('#keluhanInput').value.trim(),
      catatan_pengerjaan: $('#catatanPengerjaan').value.trim() || null,
      diskon: String(totals.discount),
      metode_bayar: metode,
      bayar: String(paid),
      bergaransi: $('#garansiAktif').checked,
      garansi_bulan: garansiBulanValue(),
      catatan_garansi: $('#garansiCatatan').value.trim() || null,
      jobs: state.jobs.map((job) => ({
        harga_jasa_id: job.harga_jasa_id || null,
        deskripsi: job.deskripsi,
        jumlah: Math.max(1, intValue(job.jumlah, 1)),
        harga: String(parseMoney(job.harga)),
      })),
      parts: state.parts.map((part) => ({
        stock_item_id: part.stock_item_id || null,
        nama_part: part.nama_part,
        jumlah: Math.max(1, intValue(part.jumlah, 1)),
        harga_satuan: String(parseMoney(part.harga_satuan)),
      })),
    };
  }

  async function saveTransaction(printAfter) {
    if (state.saving) return;
    if (!state.selectedCustomer) {
      toast('Pilih pelanggan terlebih dahulu.', 'warning');
      return;
    }
    if (!state.selectedUnit) {
      toast('Pilih unit servis terlebih dahulu.', 'warning');
      return;
    }
    if (!$('#keluhanInput').value.trim()) {
      toast('Keluhan awal wajib diisi.', 'warning');
      $('#keluhanInput').focus();
      return;
    }
    if (!state.jobs.length && !state.parts.length) {
      toast('Tambahkan minimal satu jasa atau sparepart.', 'warning');
      return;
    }

    const totals = calcTotals();
    if (getMetode() === 'CASH') {
      const paid = parseMoney($('#bayarInput').value);
      if (paid < totals.grand) {
        toast('Uang diterima kurang dari grand total.', 'warning');
        $('#bayarInput').focus();
        return;
      }
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

      showReceipt(result.receipt);
      resetPosState();

      await Promise.all([loadDashboard(), loadStock()]);

      if (printAfter) await printReceipt(result.receipt, true);
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      state.saving = false;
      setBusy(button, false);
    }
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
    return normalizeReceiptWidth(
      state.config && state.config.printer.paper_width
    );
  }

  function showReceipt(receipt) {
    state.receipt = receipt;
    state.receiptWidth = preferredReceiptWidth();
    syncReceiptWidthUI();
    $('#receiptTitle').textContent = 'Struk ' + receipt.no_nota;
    $('#receiptSubtitle').textContent =
      receipt.customer_nama + ' - ' + receipt.unit_deskripsi;
    renderReceiptPreview();
    updateReceiptNotice();
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

  function updateReceiptNotice() {
    const note = $('#receiptNotice');
    if (!note) return;
    if (!window.BluetoothPrinter.isSupported()) {
      note.textContent =
        'Cetak printer sistem bisa dipakai untuk printer thermal maupun printer biasa (A4).';
      return;
    }
    if (window.BluetoothPrinter.connected) {
      note.textContent =
        'Printer siap: ' + (window.BluetoothPrinter.name || 'Printer Thermal');
      return;
    }
    note.textContent =
      'Klik Cetak Bluetooth untuk pairing thermal, atau Cetak printer sistem untuk printer lain.';
  }

  async function printReceipt(receipt, silent) {
    if (!receipt) {
      toast('Tidak ada struk untuk dicetak.', 'warning');
      return false;
    }

    const width = state.receiptWidth;
    const lines = width === 58 ? receipt.struk_58 : receipt.struk_80;
    const printer = window.BluetoothPrinter;

    if (width === 'A4') {
      browserPrint(lines, 'A4');
      return false;
    }

    const base64 =
      width === 80 ? receipt.escpos_80_base64 : receipt.escpos_58_base64;

    if (printer.isSupported() && printer.connected) {
      try {
        await printer.printBase64(base64);
        toast('Struk dikirim ke printer Bluetooth.', 'success');
        return true;
      } catch (err) {
        toast('Print Bluetooth gagal: ' + err.message, 'error', 6000);
      }
    }

    if (!silent && printer.isSupported()) {
      const ask = window.confirm(
        'Printer Bluetooth belum terhubung. Hubungkan sekarang?'
      );
      if (ask) {
        try {
          await printer.connect();
          await printer.printBase64(base64);
          toast('Struk dicetak.', 'success');
          return true;
        } catch (err) {
          if (err && err.name === 'NotFoundError') {
            toast('Pemilihan printer dibatalkan.', 'info');
          } else {
            toast(
              'Gagal menghubungkan printer: ' + err.message,
              'error',
              6000
            );
          }
        }
      }
    }

    browserPrint(lines, width);
    return false;
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

  /* ------------------------------- Printer -------------------------------- */
  function initPrinter() {
    const printer = window.BluetoothPrinter;
    const button = $('#printerBtn');

    printer.onChange((status) => {
      if (!button) return;
      button.classList.toggle('connected', status.connected);
      button.classList.toggle('connecting', status.connecting);
      let label = 'Printer: Belum Terhubung';
      if (status.connecting) label = 'Printer: Menghubungkan...';
      else if (status.connected) {
        label = 'Printer: ' + (status.name || 'Terhubung');
      }
      $('#printerLabel').textContent = label;
      updateReceiptNotice();
    });

    button.addEventListener('click', async () => {
      if (!printer.isSupported()) {
        toast(
          'Web Bluetooth tidak didukung browser ini. Gunakan tombol "Cetak printer sistem" pada struk untuk printer thermal maupun printer biasa.',
          'warning',
          7000
        );
        return;
      }
      if (printer.connected) {
        if (window.confirm('Putuskan koneksi printer Bluetooth?')) {
          printer.disconnect();
          toast('Printer diputuskan.', 'info');
        }
        return;
      }
      try {
        await printer.connect();
        toast('Printer berhasil terhubung.', 'success');
      } catch (err) {
        if (err && err.name === 'NotFoundError') {
          toast('Pemilihan printer dibatalkan.', 'info');
        } else {
          toast('Gagal menghubungkan printer: ' + err.message, 'error', 6000);
        }
      }
    });
  }

  /* ------------------------------ Dashboard ------------------------------- */
  async function loadDashboard() {
    try {
      const results = await Promise.all([
        API.records(''),
        API.daily(todayISO()),
      ]);
      const records = results[0];
      const daily = results[1];

      state.dashboardRecords = records;
      state.dashboardToday = daily.transaksi || [];

      $('#statUnit').textContent = daily.jumlah_unit_servis;
      $('#statCash').textContent = fmtRp(daily.total_cash);
      $('#statTransfer').textContent = fmtRp(daily.total_transfer);
      $('#statWarranty').textContent = daily.garansi_aktif;

      renderRecent(records.slice(0, 6));
    } catch (err) {
      toast('Gagal memuat dasbor: ' + err.message, 'error', 6000);
    }
  }

  function renderRecent(records) {
    const body = $('#recentBody');
    if (!body) return;

    if (!records.length) {
      body.innerHTML = '';
      $('#recentEmpty').classList.remove('hidden');
      return;
    }

    $('#recentEmpty').classList.add('hidden');
    body.innerHTML = records
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
          '</button><span class="cell-sub">' +
          esc(record.customer_hp) +
          '</span></td>' +
          '<td>' +
          esc(record.unit_deskripsi) +
          '</td>' +
          '<td class="text-right money">' +
          fmtRp(record.total_servis) +
          '</td>' +
          '<td>' +
          metodeBadge(record.metode_bayar) +
          '</td>' +
          '<td class="row-actions"><button type="button" class="btn btn-outline btn-xs" data-action="reprint" data-id="' +
          record.id +
          '">Cetak Ulang</button></td>' +
          '</tr>'
      )
      .join('');
  }

  /* ------------------------------- History -------------------------------- */
  async function loadHistory(query) {
    try {
      state.history = await API.records(query || '');
      renderHistory();
    } catch (err) {
      toast('Gagal memuat riwayat: ' + err.message, 'error', 6000);
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
          record.bergaransi && record.status_klaim !== 'Sudah claim';
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
          '</button></td>' +
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
          fmtRp(record.total_servis) +
          '</td>' +
          '<td>' +
          metodeBadge(record.metode_bayar) +
          '</td>' +
          '<td>' +
          warrantyBadge(record) +
          '</td>' +
          '<td class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-xs" data-action="reprint" data-id="' +
          record.id +
          '">Cetak Ulang</button>' +
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
  function findRecordById(id) {
    const lists = [
      state.history,
      state.reportRows,
      state.dashboardRecords,
      state.dashboardToday,
      state.notaList,
    ];
    for (let i = 0; i < lists.length; i += 1) {
      const found = (lists[i] || []).find((record) => record.id === id);
      if (found) return found;
    }
    return null;
  }

  function findRecordByCustomerId(customerId) {
    const lists = [
      state.history,
      state.reportRows,
      state.dashboardRecords,
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
        acc.omset += Number(record.total_servis) || 0;
        acc.profit += Number(record.laba_kotor) || 0;
        return acc;
      },
      { omset: 0, profit: 0 }
    );

    $('#notaListTitle').textContent = title;
    const meta = [list.length + ' nota', 'total ' + fmtRp(totals.omset)];
    if (opts.note) meta.push(opts.note);
    if (opts.showProfit) meta.push('laba kotor ' + fmtRp(totals.profit));
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
            '</button></td>' +
            '<td><button type="button" class="cell-link" data-action="customer-detail" data-id="' +
            record.customer_id +
            '">' +
            esc(record.customer_nama) +
            '</button><span class="cell-sub">' +
            esc(record.customer_hp) +
            '</span></td>' +
            '<td class="text-right money">' +
            fmtRp(record.total_servis) +
            (opts.showProfit
              ? '<span class="cell-sub">Laba ' +
                fmtRp(record.laba_kotor) +
                '</span>'
              : '') +
            '</td>' +
            '<td>' +
            metodeBadge(record.metode_bayar) +
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

  function renderRecordDetail(receipt) {
    const jobs = receipt.jobs || [];
    const parts = receipt.parts || [];
    const jobsHtml = jobs.length
      ? jobs
          .map(
            (job) =>
              '<tr><td>' +
              esc(job.deskripsi) +
              '</td><td class="text-center">' +
              intValue(job.jumlah, 0) +
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
              intValue(part.jumlah, 0) +
              '</td><td class="text-right money">' +
              fmtRp(part.harga_satuan) +
              '</td><td class="text-right money">' +
              fmtRp(part.subtotal) +
              '</td></tr>'
          )
          .join('')
      : '<tr><td colspan="4" class="muted">Tidak ada sparepart.</td></tr>';

    $('#recordTitle').textContent = 'Nota ' + receipt.no_nota;
    $('#recordSubtitle').textContent =
      receipt.customer_nama + ' · ' + receipt.unit_deskripsi;

    $('#recordDetail').innerHTML =
      '<div class="detail-grid">' +
      detailItem('Waktu servis', esc(fmtDateTime(receipt.waktu_service))) +
      detailItem('Metode bayar', metodeBadge(receipt.metode_bayar)) +
      detailItem('Status garansi', warrantyBadge(receipt)) +
      detailItem(
        'Garansi sampai',
        esc(receipt.garansi_sampai ? fmtDate(receipt.garansi_sampai) : '-')
      ) +
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
      '<div class="detail-total-row is-grand"><span>Total servis</span><strong>' +
      fmtRp(receipt.total_servis) +
      '</strong></div>' +
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
        : '');

    $('#btnRecordCustomer').classList.toggle(
      'hidden',
      !state.detailRecordCustomerId
    );
  }

  async function openRecordDetail(id) {
    if (!id) return;
    try {
      const receipt = await API.receipt(id);
      const source = findRecordById(id);
      state.detailRecord = receipt;
      state.detailRecordCustomerId = source ? source.customer_id : null;
      renderRecordDetail(receipt);
      openModal('#recordModal');
    } catch (err) {
      toast('Gagal memuat detail nota: ' + err.message, 'error', 6000);
    }
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
      '</div></div>';
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
        toast('Gagal memuat detail pelanggan: ' + err.message, 'error', 6000);
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
    } else if (filter === 'warranty') {
      list = (state.dashboardRecords || []).filter(
        (record) => record.garansi_aktif
      );
      title = 'Nota bergaransi aktif';
      note = 'garansi masih aktif';
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
      title = 'Laba kotor part · ' + period;
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

    if (!id) return;

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
      renderStock();
      renderJasa();
    } catch (err) {
      toast('Gagal memuat stok: ' + err.message, 'error', 6000);
    }
  }

  function renderStock() {
    const stockBody = $('#stockBody');
    if (!stockBody) return;

    const lowStock = state.stock.filter((item) => item.jumlah <= 3).length;
    $('#stockSummary').textContent =
      state.stock.length +
      ' item - ' +
      lowStock +
      ' stok kritis (<= 3)';

    stockBody.innerHTML = state.stock
      .map((item) => {
        const critical = item.jumlah <= 3;
        const badgeClass = item.jumlah === 0 ? 'red' : critical ? 'amber' : 'gray';
        return (
          '<tr>' +
          '<td><span class="cell-sub">' +
          esc(item.kode || '-') +
          '</span></td>' +
          '<td><span class="cell-primary">' +
          esc(item.nama) +
          '</span></td>' +
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

    $('#stockEmpty').classList.toggle('hidden', state.stock.length > 0);
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
    $('#stockModalTitle').textContent = item ? 'Edit Sparepart' : 'Tambah Sparepart';
    $('#stockId').value = item ? item.id : '';
    $('#stockKode').value = item ? item.kode || '' : '';
    $('#stockNama').value = item ? item.nama : '';
    $('#stockModalHarga').value = item
      ? String(Math.round(Number(item.harga_modal) || 0))
      : '0';
    $('#stockJualHarga').value = item
      ? String(Math.round(Number(item.harga_jual) || 0))
      : '0';
    $('#stockJumlah').value = item ? item.jumlah : '0';
    openModal('#stockModal');
    setTimeout(() => $('#stockNama').focus(), 60);
  }

  async function handleStockSubmit(event) {
    event.preventDefault();
    const id = intValue($('#stockId').value, 0);
    const payload = {
      kode: $('#stockKode').value.trim() || null,
      nama: $('#stockNama').value.trim(),
      harga_modal: String(parseMoney($('#stockModalHarga').value)),
      harga_jual: String(parseMoney($('#stockJualHarga').value)),
      jumlah: Math.max(0, intValue($('#stockJumlah').value, 0)),
    };

    try {
      if (id) await API.updateStock(id, payload);
      else await API.createStock(payload);
      closeModal('#stockModal');
      toast('Data sparepart tersimpan.', 'success');
      await loadStock();
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
    $('#jasaModalTitle').textContent = jasa ? 'Edit Tarif Jasa' : 'Tambah Tarif Jasa';
    $('#jasaId').value = jasa ? jasa.id : '';
    $('#jasaNamaInput').value = jasa ? jasa.nama : '';
    $('#jasaHargaInput').value = jasa
      ? String(Math.round(Number(jasa.harga_standar) || 0))
      : '0';
    openModal('#jasaModal');
    setTimeout(() => $('#jasaNamaInput').focus(), 60);
  }

  async function handleJasaSubmit(event) {
    event.preventDefault();
    const id = intValue($('#jasaId').value, 0);
    const payload = {
      nama: $('#jasaNamaInput').value.trim(),
      harga_standar: String(parseMoney($('#jasaHargaInput').value)),
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

  function emptyPeriodSummary() {
    return {
      jumlah_transaksi: 0,
      jumlah_unit_servis: 0,
      total_omset: 0,
      total_cash: 0,
      total_transfer: 0,
      total_jasa: 0,
      total_part: 0,
      total_diskon: 0,
      laba_kotor: 0,
      garansi_aktif: 0,
      harian: [],
      transaksi: [],
    };
  }

  function mergePeriodChunks(chunks) {
    const merged = emptyPeriodSummary();
    for (let i = chunks.length - 1; i >= 0; i -= 1) {
      const chunk = chunks[i];
      merged.jumlah_transaksi += chunk.jumlah_transaksi;
      merged.jumlah_unit_servis += chunk.jumlah_unit_servis;
      merged.total_omset += Number(chunk.total_omset) || 0;
      merged.total_cash += Number(chunk.total_cash) || 0;
      merged.total_transfer += Number(chunk.total_transfer) || 0;
      merged.total_jasa += Number(chunk.total_jasa) || 0;
      merged.total_part += Number(chunk.total_part) || 0;
      merged.total_diskon += Number(chunk.total_diskon) || 0;
      merged.laba_kotor += Number(chunk.laba_kotor) || 0;
      merged.garansi_aktif = Math.max(
        merged.garansi_aktif,
        intValue(chunk.garansi_aktif, 0)
      );
      merged.harian = merged.harian.concat(chunk.harian || []);
      merged.transaksi = merged.transaksi.concat(chunk.transaksi || []);
    }
    merged.transaksi.sort(
      (a, b) =>
        String(b.waktu_service || '').localeCompare(
          String(a.waktu_service || '')
        ) || b.id - a.id
    );
    return merged;
  }

  async function loadAllTimePeriod() {
    const chunks = [];
    let windowEnd = new Date();
    for (let i = 0; i < 20; i += 1) {
      const windowStart = new Date(windowEnd);
      windowStart.setDate(windowStart.getDate() - 366);
      const chunk = await API.period(
        toISODate(windowStart),
        toISODate(windowEnd)
      );
      if (!chunk.jumlah_transaksi) break;
      chunks.push(chunk);
      windowEnd = new Date(windowStart);
      windowEnd.setDate(windowEnd.getDate() - 1);
    }
    if (!chunks.length) {
      return { data: emptyPeriodSummary(), startISO: todayISO() };
    }
    const oldest = chunks[chunks.length - 1];
    const firstActive = (oldest.harian || []).find(
      (day) => day.jumlah_transaksi > 0
    );
    return {
      data: mergePeriodChunks(chunks),
      startISO: firstActive
        ? String(firstActive.tanggal).slice(0, 10)
        : todayISO(),
    };
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
          fmtRp(day.laba_kotor) +
          '</td>' +
          '</tr>'
      )
      .join('');
    wrap.classList.remove('hidden');
  }

  function renderSoldParts(sold, periodLabel) {
    const wrap = $('#soldPartsWrap');
    const items = sold && Array.isArray(sold.items) ? sold.items : [];
    if (!items.length) {
      $('#soldPartsBody').innerHTML = '';
      wrap.classList.add('hidden');
      return;
    }
    $('#soldPartsNote').textContent =
      periodLabel +
      ' · ' +
      items.length +
      ' penjualan · ' +
      intValue(sold.total_qty, 0) +
      ' unit terjual · harga akhir (deal), barang sama urut sesuai waktu.';
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
    wrap.classList.remove('hidden');
  }

  let reportRequestId = 0;

  async function loadReport() {
    const requestId = (reportRequestId += 1);
    const select = $('#reportPeriod');
    const period = select.value || 'today';
    const periodLabel = select.selectedOptions.length
      ? select.selectedOptions[0].textContent.trim()
      : 'Hari ini';
    const endISO = todayISO();
    const soldRequest = period === 'all' ? API.soldParts() : null;
    try {
      let data;
      let startISO;
      if (period === 'all') {
        const allTime = await loadAllTimePeriod();
        data = allTime.data;
        startISO = allTime.startISO;
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
      $('#reportDateLabel').textContent =
        periodLabel +
        ' · ' +
        (startISO === endISO
          ? fmtDate(startISO)
          : fmtDate(startISO) + ' – ' + fmtDate(endISO));

      $('#reportMeta').innerHTML =
        '<span class="meta-chip"><strong>' +
        data.jumlah_transaksi +
        '</strong> transaksi</span>' +
        '<span class="meta-chip"><strong>' +
        data.jumlah_unit_servis +
        '</strong> unit</span>' +
        '<span class="meta-chip">Diskon <strong>' +
        fmtRp(data.total_diskon) +
        '</strong></span>' +
        '<span class="meta-chip">Garansi aktif <strong>' +
        data.garansi_aktif +
        '</strong></span>';

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
              fmtRp(record.total_servis) +
              '<span class="cell-sub">Laba kotor ' +
              fmtRp(record.laba_kotor) +
              '</span></td>' +
              '<td>' +
              metodeBadge(record.metode_bayar) +
              '</td>' +
              '</tr>'
          )
          .join('');
      }

      renderPeriodRecap(data.harian, period, periodLabel);
      renderSoldParts(soldData, periodLabel);
    } catch (err) {
      if (requestId === reportRequestId) {
        toast('Gagal memuat laporan: ' + err.message, 'error', 6000);
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
          ? 'Server lokal belum siap. Tutup lalu buka lagi aplikasi.'
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
      setAuthError($('#authSetupError'), 'Ulangi PIN belum sama.');
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
        'Perubahan disimpan di database lokal pada PC kasir ini.';
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
      toast('Gagal menyimpan pengaturan: ' + err.message, 'error', 6000);
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
      parts.push('Kesalahan terakhir: ' + telegram.last_error);
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
      toast('Gagal menyimpan Telegram: ' + err.message, 'error', 6000);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleTelegramSendNow() {
    const button = $('#telegramSendNow');
    if (!state.config || !state.config.telegram.configured) {
      toast('Simpan bot token dan chat ID terlebih dahulu.', 'warning');
      return;
    }

    setBusy(button, true, 'Mengirim...');
    try {
      const result = await API.sendTelegramBackup();
      toast(
        'Backup terkirim: ' + result.filename + ' (' + result.jumlah_nota + ' nota).',
        'success',
        7000
      );
      state.config = await API.getConfig();
      applyConfig();
    } catch (err) {
      toast('Gagal mengirim backup: ' + err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
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
      'Pulihkan database dari "' +
        file.name +
        '"? Seluruh data saat ini akan diganti. Backup keamanan tetap dibuat otomatis.'
    );
    if (!confirmed) return;

    const button = $('#settingsRestore');
    setBusy(button, true, 'Memulihkan...');
    try {
      await API.restoreDatabase(file);
      if (window.BengkelBridge && window.BengkelBridge.available()) {
        toast('Database berhasil dipulihkan. Menyiapkan ulang aplikasi...', 'success', 5000);
        try {
          await window.BengkelBridge.call('restartBackend', {}, 180000);
        } catch (err) {
          toast(
            'Data sudah dipulihkan, tetapi server gagal dimuat ulang: ' +
              err.message +
              ' Tutup lalu buka aplikasi.',
            'error',
            9000
          );
          setBusy(button, false);
        }
        return;
      }
      toast('Database berhasil dipulihkan. Memuat ulang aplikasi...', 'success', 4000);
      setTimeout(() => window.location.reload(), 1200);
    } catch (err) {
      toast('Gagal memulihkan database: ' + err.message, 'error', 7000);
      setBusy(button, false);
    }
  }

  async function handleBackup() {
    const button = $('#settingsBackup');
    setBusy(button, true, 'Membuat backup...');
    try {
      const result = await API.downloadBackup();
      state.lastBackup = result || null;
      const shareButton = $('#settingsShareBackup');
      if (shareButton) {
        const canShare =
          state.lastBackup &&
          window.BengkelBridge &&
          window.BengkelBridge.available();
        shareButton.classList.toggle('hidden', !canShare);
      }
      const locationText = state.lastBackup.location
        ? ' ke ' + state.lastBackup.location
        : '';
      toast(
        'File backup database berhasil disimpan' +
          locationText +
          ': ' +
          state.lastBackup.filename,
        'success',
        6000
      );
    } catch (err) {
      toast(err.message, 'error', 7000);
    } finally {
      setBusy(button, false);
    }
  }

  async function handleShareBackup() {
    if (!state.lastBackup || !window.BengkelBridge) return;
    try {
      await window.BengkelBridge.call('shareBackup', {
        filename: state.lastBackup.filename,
      });
    } catch (err) {
      toast('Gagal membagikan backup: ' + err.message, 'error', 7000);
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
  }

  /* ------------------------------- Bindings ------------------------------- */
  function bindEvents() {
    $$('.nav-tab').forEach((tab) =>
      tab.addEventListener('click', () => navigate(tab.dataset.view))
    );

    $('#heroNewService').addEventListener('click', () => navigate('pos'));
    $('#heroNewCustomer').addEventListener('click', () => openCustomerModal(false));
    $('#btnNewCustomerPos').addEventListener('click', () => openCustomerModal(true));
    $('#refreshDashboard').addEventListener('click', loadDashboard);

    $('#posReset').addEventListener('click', () => {
      if (window.confirm('Reset seluruh isian transaksi?')) resetPosState();
    });

    $('#customerSearch').addEventListener('input', onCustomerSearchInput);
    $('#customerSearch').addEventListener('focus', () => {
      if ($('#customerResults').innerHTML.trim()) {
        $('#customerResults').classList.remove('hidden');
      }
    });

    $$('#unitTypeSwitch button').forEach((button) =>
      button.addEventListener('click', () => setUnitType(button.dataset.type))
    );
    $('#btnAddUnit').addEventListener('click', handleAddUnit);

    $('#jasaPicker').addEventListener('change', onJasaPickerChange);
    $('#partPicker').addEventListener('change', onPartPickerChange);
    $('#btnAddJob').addEventListener('click', addJob);
    $('#btnAddPart').addEventListener('click', addPart);

    $$('input[name="metode"]').forEach((radio) =>
      radio.addEventListener('change', handlePaymentModeChange)
    );
    $('#garansiAktif').addEventListener('change', updateGaransiFields);
    $('#garansiBulan').addEventListener('change', updateGaransiFields);
    $('#garansiBulanCustom').addEventListener('change', () => {
      $('#garansiBulanCustom').value = String(garansiBulanValue());
    });
    $('#btnSavePrint').addEventListener('click', () => saveTransaction(true));
    $('#btnSaveOnly').addEventListener('click', () => saveTransaction(false));

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
    $('#btnAddCustomerDirectory').addEventListener('click', () =>
      openCustomerModal(false)
    );

    $('#btnAddStock').addEventListener('click', () => openStockModal(null));
    $('#btnAddJasa').addEventListener('click', () => openJasaModal(null));

    $('#btnLoadReport').addEventListener('click', loadReport);
    $('#reportPeriod').addEventListener('change', loadReport);
    $('#btnBackup').addEventListener('click', handleBackup);

    $('#receiptWidthSwitch').addEventListener('click', onReceiptWidthClick);
    $('#btnBluetoothPrint').addEventListener('click', () =>
      printReceipt(state.receipt, false)
    );
    $('#btnBrowserPrint').addEventListener('click', () => {
      if (state.receipt) browserPrint(currentReceiptLines(), state.receiptWidth);
    });

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
    $('#btnRecordReprint').addEventListener('click', () => {
      if (state.detailRecord) {
        handleAction('reprint', state.detailRecord.id);
      }
    });
    $('#btnRecordCustomer').addEventListener('click', () => {
      if (state.detailRecordCustomerId) {
        openCustomerDetail(state.detailRecordCustomerId);
      }
    });
    $('#customerDetailClose').addEventListener('click', () =>
      closeModal('#customerDetailModal')
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

    $('#settingsBackup').addEventListener('click', handleBackup);
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
      ]);
      state.config = results[0];
      state.stock = results[1];
      state.jasa = results[2];
      applyConfig();
      populatePickers();
      renderStock();
      renderJasa();
    } catch (err) {
      if (err.status !== 401) {
        toast('Gagal memuat konfigurasi awal: ' + err.message, 'error', 8000);
      }
      return;
    }

    authState.started = true;
    resetPosState();
    updateReceiptNotice();
    await loadDashboard();
  }

  async function init() {
    bindEvents();
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
