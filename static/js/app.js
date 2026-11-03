const state = {
  assets: [],
  selectedId: null,
  histories: {},
  sparklines: {},
  minutes: 1440,
  feed: [],
  editId: null,
  connected: false,
  es: null,
  chart: null,
  notifyAll: localStorage.getItem("notifyAll") === "1",
  notifyAlerts: localStorage.getItem("notifyAlerts") !== "0",
};

const els = {};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])
  );

const fmtNumber = (value, digits = 2) =>
  value == null
    ? "—"
    : Number(value).toLocaleString("pt-BR", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

const fmtMoney = (value, currency = "R$") =>
  value == null ? "—" : `${currency} ${fmtNumber(value)}`;

const fmtTime = (iso) => {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

function hexToRgba(hex, alpha) {
  const value = parseInt(hex.replace("#", ""), 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function getSelected() {
  return state.assets.find((asset) => asset.id === state.selectedId) || null;
}

function cacheElements() {
  const ids = [
    "assets-grid", "assets-count", "empty-state", "empty-add-btn", "status-pill",
    "status-text", "notify-btn", "refresh-btn", "add-btn", "chart-title",
    "chart-subtitle", "range-group", "price-chart", "chart-empty", "feed",
    "clear-feed", "notify-all", "notify-alerts", "status-detail", "toast-container",
    "modal", "modal-title", "asset-form", "form-errors", "close-modal", "cancel-modal",
  ];
  ids.forEach((id) => {
    const key = id.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    els[key] = document.getElementById(id);
  });
}

/* ------------------------------------------------------------------ cards */

function renderAssets() {
  els.assetsGrid.innerHTML = "";
  els.assetsCount.textContent = state.assets.length
    ? `${state.assets.length} ativo${state.assets.length > 1 ? "s" : ""}`
    : "";
  els.emptyState.classList.toggle("hidden", state.assets.length > 0);

  state.assets.forEach((asset) => {
    const card = document.createElement("article");
    card.className = "asset-card" + (asset.id === state.selectedId ? " selected" : "");
    card.dataset.id = asset.id;

    let changeClass = "flat";
    let changeText = "aguardando leitura";
    if (asset.change != null) {
      changeClass = asset.change > 0 ? "up" : asset.change < 0 ? "down" : "flat";
      const arrow = asset.change > 0 ? "▲" : asset.change < 0 ? "▼" : "•";
      const sign = asset.change_pct > 0 ? "+" : "";
      changeText = `${arrow} ${sign}${fmtNumber(asset.change_pct)}% · ${fmtNumber(
        Math.abs(asset.change)
      )}`;
    }

    const chips = [];
    if (asset.alert_above != null) {
      chips.push(
        `<span class="chip above">↑ ${fmtMoney(asset.alert_above, asset.currency)}</span>`
      );
    }
    if (asset.alert_below != null) {
      chips.push(
        `<span class="chip below">↓ ${fmtMoney(asset.alert_below, asset.currency)}</span>`
      );
    }

    card.innerHTML = `
      <div class="asset-top">
        <div>
          <div class="asset-symbol">${esc(asset.symbol)}</div>
          <div class="asset-name" title="${esc(asset.name)}">${esc(asset.name)}</div>
        </div>
        <div class="asset-actions">
          <button class="icon-btn" data-action="edit" data-id="${asset.id}" title="Editar ativo">✎</button>
          <button class="icon-btn" data-action="delete" data-id="${asset.id}" title="Remover ativo">🗑</button>
        </div>
      </div>
      <div class="asset-price">${fmtMoney(asset.price, asset.currency)}</div>
      <div class="asset-change ${changeClass}">${changeText}</div>
      <canvas class="asset-spark"></canvas>
      <div class="asset-meta">
        <span class="asset-time">${
          asset.captured_at ? `Atualizado ${fmtTime(asset.captured_at)}` : "Sem leitura"
        }</span>
        <div class="alert-chips">${chips.join("")}</div>
      </div>`;

    els.assetsGrid.appendChild(card);
    drawSparkline(card.querySelector("canvas"), state.sparklines[asset.id] || [], asset.change);
  });
}

function drawSparkline(canvas, points, change) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = rect.width || 200;
  const height = rect.height || 38;
  canvas.width = width * dpr;
  canvas.height = height * dpr;

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  if (!points || points.length < 2) return;

  const prices = points.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const pad = 2;
  const xAt = (i) => pad + (i / (points.length - 1)) * (width - pad * 2);
  const yAt = (v) => height - pad - ((v - min) / range) * (height - pad * 2);
  const color = change == null ? "#4d9fff" : change >= 0 ? "#2ecc71" : "#ff5c6c";

  ctx.beginPath();
  points.forEach((point, index) => {
    const px = xAt(index);
    const py = yAt(point.price);
    if (index === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.lineJoin = "round";
  ctx.stroke();

  ctx.lineTo(xAt(points.length - 1), height);
  ctx.lineTo(xAt(0), height);
  ctx.closePath();
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, hexToRgba(color, 0.26));
  gradient.addColorStop(1, hexToRgba(color, 0));
  ctx.fillStyle = gradient;
  ctx.fill();
}

/* ------------------------------------------------------------------ chart */

function updateChartHeader() {
  const asset = getSelected();
  if (!asset) {
    els.chartTitle.textContent = "Histórico de preço";
    els.chartSubtitle.textContent = "Selecione um ativo";
    return;
  }
  els.chartTitle.textContent = `${asset.symbol} · ${asset.name}`;
  els.chartSubtitle.textContent = asset.captured_at
    ? `Última leitura ${fmtTime(asset.captured_at)} · ${fmtMoney(asset.price, asset.currency)}`
    : "Aguardando primeira leitura";
}

function formatAxisTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  if (state.minutes && state.minutes <= 1440) {
    return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderChart() {
  const asset = getSelected();
  if (!asset) return;

  if (state.chart) {
    state.chart.destroy();
    state.chart = null;
  }

  const points = (state.histories[asset.id] || []).map((point) => ({
    x: new Date(point.captured_at).getTime(),
    y: point.price,
  }));

  if (typeof Chart === "undefined") {
    els.chartEmpty.textContent = "Chart.js não carregou. Verifique sua conexão.";
    els.chartEmpty.classList.remove("hidden");
    return;
  }

  els.chartEmpty.classList.toggle("hidden", points.length > 0);
  if (points.length === 0) return;

  const color =
    points.length > 1 && points[points.length - 1].y < points[0].y ? "#ff5c6c" : "#2ecc71";

  state.chart = new Chart(els.priceChart.getContext("2d"), {
    type: "line",
    data: {
      datasets: [
        {
          label: asset.symbol,
          data: points,
          borderColor: color,
          backgroundColor: hexToRgba(color, 0.1),
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: points.length === 1 ? 4 : 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: color,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0d131a",
          borderColor: "#24303d",
          borderWidth: 1,
          titleColor: "#e8eef5",
          bodyColor: "#8a99ab",
          padding: 10,
          displayColors: false,
          callbacks: {
            title: (items) => new Date(items[0].parsed.x).toLocaleString("pt-BR"),
            label: (item) => fmtMoney(item.parsed.y, asset.currency),
          },
        },
      },
      scales: {
        x: {
          type: "linear",
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "#8a99ab", maxTicksLimit: 8, callback: (value) => formatAxisTime(value) },
        },
        y: {
          position: "right",
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#8a99ab", callback: (value) => fmtNumber(value) },
        },
      },
    },
  });
}

function updateChartLast(price, capturedAt) {
  if (!state.chart) {
    renderChart();
    return;
  }
  state.chart.data.datasets[0].data.push({
    x: new Date(capturedAt).getTime(),
    y: price,
  });
  state.chart.update("none");
  els.chartEmpty.classList.add("hidden");
}

/* ------------------------------------------------------------------ data */

async function loadAssets() {
  state.assets = await fetchJson("/api/assets");

  if (!state.assets.length) {
    state.selectedId = null;
    renderAssets();
    updateChartHeader();
    renderChart();
    return;
  }

  if (!state.assets.some((asset) => asset.id === state.selectedId)) {
    state.selectedId = state.assets[0].id;
  }

  renderAssets();
  updateChartHeader();
  state.assets.forEach((asset) => loadSparkline(asset.id));
  await loadChartHistory();
}

async function fetchHistory(assetId, { minutes = null, limit = 2000 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (minutes) params.set("minutes", String(minutes));
  return fetchJson(`/api/assets/${assetId}/history?${params.toString()}`);
}

async function loadSparkline(assetId, force = false) {
  if (state.sparklines[assetId] && !force) return;
  try {
    const data = await fetchHistory(assetId, { limit: 80 });
    state.sparklines[assetId] = data;
    const canvas = els.assetsGrid.querySelector(
      `.asset-card[data-id="${assetId}"] canvas`
    );
    const asset = state.assets.find((item) => item.id === assetId);
    drawSparkline(canvas, data, asset ? asset.change : null);
  } catch (error) {
    /* silencioso: sparkline é opcional */
  }
}

async function loadChartHistory() {
  const asset = getSelected();
  if (!asset) return;
  try {
    state.histories[asset.id] = await fetchHistory(asset.id, {
      minutes: state.minutes || null,
      limit: 5000,
    });
    renderChart();
  } catch (error) {
    els.chartEmpty.textContent = "Não foi possível carregar o histórico.";
    els.chartEmpty.classList.remove("hidden");
  }
}

function selectAsset(assetId, force = false) {
  if (!force && state.selectedId === assetId) return;
  state.selectedId = assetId;
  renderAssets();
  updateChartHeader();
  loadChartHistory();
}

async function loadAlerts() {
  try {
    const alerts = await fetchJson("/api/alerts?limit=60");
    state.feed = alerts.map((alert) => ({
      title: alert.message,
      at: alert.created_at,
      tone: alert.kind === "above" ? "alert-above" : "alert-below",
    }));
    renderFeed();
  } catch (error) {
    /* ignora */
  }
}

async function loadStatus() {
  try {
    const status = await fetchJson("/api/status");
    const errorLine = status.last_error
      ? `<br><span style="color:var(--red)">${esc(status.last_error)}</span>`
      : "";
    els.statusDetail.innerHTML = `
      Intervalo: <strong>${status.poll_interval}s</strong><br>
      Ciclos: <strong>${status.cycles}</strong><br>
      Última leitura: <strong>${status.last_success ? fmtTime(status.last_success) : "—"}</strong>
      ${errorLine}`;
  } catch (error) {
    /* ignora */
  }
}

/* ------------------------------------------------------------------ stream */

function setConnection(online) {
  state.connected = online;
  els.statusPill.classList.toggle("online", online);
  els.statusPill.classList.toggle("offline", !online);
  els.statusText.textContent = online ? "Ao vivo" : "Reconectando…";
}

function connectStream() {
  if (state.es) state.es.close();
  const source = new EventSource("/api/stream");
  state.es = source;

  source.onopen = () => setConnection(true);
  source.onerror = () => setConnection(false);
  source.onmessage = (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    handleEvent(payload);
  };
}

function handleEvent(event) {
  switch (event.type) {
    case "hello":
      setConnection(true);
      break;
    case "price":
      applyPrice(event);
      break;
    case "alert":
      applyAlert(event);
      break;
    case "error":
      addFeed({
        title: "Falha na captura",
        detail: event.message,
        at: event.at,
        tone: "error",
      });
      toast("Falha na captura", event.message, "error");
      break;
    default:
      break;
  }
}

function applyPrice(event) {
  const asset = state.assets.find((item) => item.id === event.asset_id);
  if (!asset) {
    loadAssets();
    return;
  }

  asset.price = event.price;
  asset.previous_price = event.previous_price;
  asset.change = event.change;
  asset.change_pct = event.change_pct;
  asset.captured_at = event.captured_at;

  const sparkline = state.sparklines[asset.id] || (state.sparklines[asset.id] = []);
  sparkline.push({ price: event.price, captured_at: event.captured_at });
  if (sparkline.length > 120) sparkline.shift();

  if (state.histories[asset.id] && state.selectedId === asset.id) {
    state.histories[asset.id].push({
      price: event.price,
      captured_at: event.captured_at,
    });
  }

  renderAssets();
  if (state.selectedId === asset.id) {
    updateChartHeader();
    updateChartLast(event.price, event.captured_at);
  }

  if (state.notifyAll && asset.previous_price != null && event.price !== event.previous_price) {
    const direction = event.change > 0 ? "▲" : "▼";
    const sign = event.change_pct > 0 ? "+" : "";
    notify(
      `${asset.symbol} ${direction}`,
      `${fmtMoney(event.price, asset.currency)} (${sign}${fmtNumber(event.change_pct)}%)`,
      `price-${asset.id}`
    );
  }
}

function applyAlert(event) {
  addFeed({
    title: event.message,
    at: event.created_at,
    tone: event.kind === "above" ? "alert-above" : "alert-below",
  });
  toast("Alerta de preço", event.message, "alert");
  if (state.notifyAlerts) {
    notify(`🚨 ${event.symbol}`, event.message, `alert-${event.asset_id}`);
  }
}

/* ------------------------------------------------------------------ feed */

function addFeed(item) {
  state.feed.unshift(item);
  if (state.feed.length > 100) state.feed.pop();
  renderFeed();
}

function renderFeed() {
  if (!state.feed.length) {
    els.feed.innerHTML = '<li class="feed-empty">Aguardando eventos…</li>';
    return;
  }
  els.feed.innerHTML = state.feed
    .map(
      (item) => `
      <li class="${item.tone || ""}">
        <div class="feed-title">${esc(item.title)}</div>
        ${item.detail ? `<div class="muted">${esc(item.detail)}</div>` : ""}
        <div class="feed-time">${esc(fmtTime(item.at))}</div>
      </li>`
    )
    .join("");
}

/* ------------------------------------------------------------------ notify */

function notify(title, body, tag) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    new Notification(title, { body, tag });
  } catch (error) {
    /* alguns navegadores exigem service worker */
  }
}

function updateNotifyButton() {
  if (!("Notification" in window)) {
    els.notifyBtn.textContent = "Notificações indisponíveis";
    els.notifyBtn.disabled = true;
    return;
  }
  if (Notification.permission === "granted") {
    els.notifyBtn.textContent = "🔔 Notificações ativas";
  } else if (Notification.permission === "denied") {
    els.notifyBtn.textContent = "🔕 Notificações bloqueadas";
  } else {
    els.notifyBtn.textContent = "🔔 Ativar notificações";
  }
}

async function requestNotifications() {
  if (!("Notification" in window)) {
    toast("Notificações não suportadas", "Use um navegador moderno.", "error");
    return;
  }
  const permission = await Notification.requestPermission();
  updateNotifyButton();
  if (permission === "granted") {
    toast("Notificações ativadas", "Você será avisado sobre as mudanças.", "success");
    notify("Market Watch", "Notificações ativadas com sucesso!");
  }
}

function toast(title, body, tone = "") {
  const element = document.createElement("div");
  element.className = `toast ${tone}`;
  element.innerHTML = `
    <div class="toast-title">${esc(title)}</div>
    <div class="toast-body">${esc(body)}</div>`;
  els.toastContainer.appendChild(element);
  setTimeout(() => {
    element.style.transition = "opacity .2s ease, transform .2s ease";
    element.style.opacity = "0";
    element.style.transform = "translateX(16px)";
    setTimeout(() => element.remove(), 220);
  }, 4500);
}

/* ------------------------------------------------------------------ modal */

function openModal(asset = null) {
  state.editId = asset ? asset.id : null;
  els.formErrors.textContent = "";
  els.assetForm.reset();

  if (asset) {
    els.modalTitle.textContent = `Editar ${asset.symbol}`;
    els.assetForm.elements.namedItem("symbol").value = asset.symbol;
    els.assetForm.elements.namedItem("symbol").disabled = true;
    els.assetForm.elements.namedItem("name").value = asset.name;
    els.assetForm.elements.namedItem("alert_above").value =
      asset.alert_above != null ? asset.alert_above : "";
    els.assetForm.elements.namedItem("alert_below").value =
      asset.alert_below != null ? asset.alert_below : "";
  } else {
    els.modalTitle.textContent = "Adicionar ativo";
    els.assetForm.elements.namedItem("symbol").disabled = false;
  }

  els.modal.classList.remove("hidden");
}

function closeModal() {
  els.modal.classList.add("hidden");
  state.editId = null;
}

function showFormErrors(errors) {
  els.formErrors.innerHTML = errors.map((error) => `<div>${esc(error)}</div>`).join("");
}

async function submitAsset(event) {
  event.preventDefault();
  const form = els.assetForm;
  const field = (name) => form.elements.namedItem(name);
  const payload = {
    symbol: field("symbol").value.trim(),
    name: field("name").value.trim(),
    provider: "yahoo",
    alert_above: field("alert_above").value || null,
    alert_below: field("alert_below").value || null,
  };

  const isEdit = state.editId != null;
  const editId = state.editId;
  const url = isEdit ? `/api/assets/${editId}` : "/api/assets";
  const method = isEdit ? "PATCH" : "POST";
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;

  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      showFormErrors(data.errors || ["Não foi possível salvar o ativo."]);
      return;
    }

    closeModal();
    await loadAssets();
    if (!isEdit && data.id) selectAsset(data.id, true);
    await loadSparkline(isEdit ? editId : data.id, true).catch(() => {});
    toast(
      isEdit ? "Ativo atualizado" : "Ativo adicionado",
      `${payload.symbol} está no monitoramento.`,
      "success"
    );
  } catch (error) {
    showFormErrors(["Falha de conexão com o servidor."]);
  } finally {
    submitButton.disabled = false;
  }
}

async function removeAsset(assetId) {
  const asset = state.assets.find((item) => item.id === assetId);
  if (!asset) return;
  if (!confirm(`Remover ${asset.symbol} do monitoramento?`)) return;

  try {
    await fetchJson(`/api/assets/${assetId}`, { method: "DELETE" });
    delete state.histories[assetId];
    delete state.sparklines[assetId];
    if (state.selectedId === assetId) state.selectedId = null;
    await loadAssets();
    toast("Ativo removido", `${asset.symbol} saiu do monitoramento.`, "success");
  } catch (error) {
    toast("Erro", "Não foi possível remover o ativo.", "error");
  }
}

/* ------------------------------------------------------------------ boot */

function bindEvents() {
  els.addBtn.addEventListener("click", () => openModal());
  els.emptyAddBtn.addEventListener("click", () => openModal());
  els.closeModal.addEventListener("click", closeModal);
  els.cancelModal.addEventListener("click", closeModal);
  els.modal.addEventListener("click", (event) => {
    if (event.target === els.modal) closeModal();
  });
  els.assetForm.addEventListener("submit", submitAsset);

  els.assetsGrid.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (button) {
      event.stopPropagation();
      const assetId = Number(button.dataset.id);
      if (button.dataset.action === "edit") {
        openModal(state.assets.find((item) => item.id === assetId));
      } else if (button.dataset.action === "delete") {
        removeAsset(assetId);
      }
      return;
    }
    const card = event.target.closest(".asset-card");
    if (card) selectAsset(Number(card.dataset.id));
  });

  els.rangeGroup.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-minutes]");
    if (!button) return;
    state.minutes = Number(button.dataset.minutes);
    els.rangeGroup.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    loadChartHistory();
  });

  els.notifyBtn.addEventListener("click", requestNotifications);
  els.refreshBtn.addEventListener("click", async () => {
    try {
      await fetchJson("/api/refresh", { method: "POST" });
      toast("Atualização solicitada", "Aguardando uma nova leitura dos ativos.", "success");
    } catch (error) {
      toast("Erro", "Não foi possível solicitar a atualização.", "error");
    }
  });

  els.clearFeed.addEventListener("click", () => {
    state.feed = [];
    renderFeed();
  });

  els.notifyAll.addEventListener("change", (event) => {
    state.notifyAll = event.target.checked;
    localStorage.setItem("notifyAll", state.notifyAll ? "1" : "0");
  });
  els.notifyAlerts.addEventListener("change", (event) => {
    state.notifyAlerts = event.target.checked;
    localStorage.setItem("notifyAlerts", state.notifyAlerts ? "0" : "1");
  });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(renderAssets, 180);
  });
}

async function boot() {
  cacheElements();
  bindEvents();
  updateNotifyButton();
  els.notifyAll.checked = state.notifyAll;
  els.notifyAlerts.checked = state.notifyAlerts;

  try {
    await loadAssets();
  } catch (error) {
    toast("Erro", "Não foi possível carregar os ativos.", "error");
  }

  await Promise.all([loadAlerts(), loadStatus()]);
  connectStream();
  setInterval(loadStatus, 15000);
}

document.addEventListener("DOMContentLoaded", boot);
