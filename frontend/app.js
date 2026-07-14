// app.js — LINE Auditor Medico Digital v2.1
// ── CONFIGURACIÓN DE API (CAMBIAR EN PRODUCCIÓN) ───────────────────────
// URL del servidor backend FastAPI
// - Desarrollo: http://127.0.0.1:8000/api
// - Producción: Cambiar a la URL del servidor real (ej: https://api.tudominio.com/api)
const API = "http://127.0.0.1:8000/api";

let pacienteActual = null;
let atencionesActuales = [];
let ultimoResultadoPF = null;
let ultimoFormData = null;

// ── Neural Network Animation ────────────────────────────────────────
let neuralAnim = null;

class NeuralNetworkAnimation {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.connections = [];
    this.pulses = [];
    this.pulseInterval = null;
    this.animId = null;
    this.running = false;
    this.time = 0;

    this.resize();
    this.initNodes();
    this.initConnections();
    this.initPulses();

    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  initNodes() {
    const count = Math.min(80, Math.floor((window.innerWidth * window.innerHeight) / 15000));
    for (let i = 0; i < count; i++) {
      this.nodes.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        r: 1.5 + Math.random() * 3,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        phase: Math.random() * Math.PI * 2,
        hue: 200 + Math.random() * 40
      });
    }
  }

  initConnections() {
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const dx = this.nodes[i].x - this.nodes[j].x;
        const dy = this.nodes[i].y - this.nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 200 && Math.random() < 0.12) {
          this.connections.push({ a: i, b: j, dist: dist });
        }
      }
    }
  }

  initPulses() {
    if (this.pulseInterval) clearInterval(this.pulseInterval);
    this.pulseInterval = setInterval(() => {
      if (!this.running) return;
      if (this.connections.length === 0) return;
      const conn = this.connections[Math.floor(Math.random() * this.connections.length)];
      this.pulses.push({
        a: conn.a,
        b: conn.b,
        progress: 0,
        speed: 0.015 + Math.random() * 0.01
      });
    }, 400);
  }

  start() {
    if (!this.canvas) return;
    this.running = true;
    this.animate();
  }

  stop() {
    this.running = false;
    if (this.pulseInterval) {
      clearInterval(this.pulseInterval);
      this.pulseInterval = null;
    }
    if (this.animId) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
    if (this.ctx) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
    this.pulses = [];
  }

  animate() {
    if (!this.running) return;
    this.time += 0.016;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    for (const node of this.nodes) {
      node.x += node.vx;
      node.y += node.vy;
      if (node.x < -20 || node.x > this.canvas.width + 20) node.vx *= -1;
      if (node.y < -20 || node.y > this.canvas.height + 20) node.vy *= -1;
    }

    const brightnesses = this.nodes.map((node, i) => {
      return 0.25 + 0.35 * Math.sin(this.time * 0.4 + node.phase);
    });

    for (const conn of this.connections) {
      const a = this.nodes[conn.a];
      const b = this.nodes[conn.b];
      const alpha = brightnesses[conn.a] * brightnesses[conn.b] * 0.35;
      ctx.strokeStyle = `rgba(0, 160, 255, ${alpha})`;
      ctx.lineWidth = 0.6;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }

    for (let i = this.pulses.length - 1; i >= 0; i--) {
      const p = this.pulses[i];
      p.progress += p.speed;
      if (p.progress >= 1) {
        this.pulses.splice(i, 1);
        continue;
      }
      const a = this.nodes[p.a];
      const b = this.nodes[p.b];
      const x = a.x + (b.x - a.x) * p.progress;
      const y = a.y + (b.y - a.y) * p.progress;
      const fade = Math.sin(p.progress * Math.PI);

      const grad = ctx.createRadialGradient(x, y, 0, x, y, 12);
      grad.addColorStop(0, `rgba(100, 220, 255, ${fade * 0.9})`);
      grad.addColorStop(0.5, `rgba(0, 180, 255, ${fade * 0.4})`);
      grad.addColorStop(1, `rgba(0, 120, 255, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(x, y, 12, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = `rgba(255, 255, 255, ${fade * 0.8})`;
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    for (let i = 0; i < this.nodes.length; i++) {
      const node = this.nodes[i];
      const b = brightnesses[i];

      const grad = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.r * 3);
      grad.addColorStop(0, `rgba(80, 200, 255, ${b * 0.5})`);
      grad.addColorStop(1, `rgba(40, 150, 255, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r * 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = `rgba(180, 230, 255, ${0.4 + b * 0.6})`;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
      ctx.fill();
    }

    this.animId = requestAnimationFrame(() => this.animate());
  }
}

// ── Toast / Notification System ──────────────────────────────────────
function showToast(message, type = 'info', duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="material-symbols-outlined text-sm">${type === 'success' ? 'check_circle' : type === 'error' ? 'error' : 'info'}</span>
    <span class="font-body-sm">${message}</span>
  `;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ── Model Toggle Logic ──────────────────────────────────────────────
let modeloSeleccionado = "cnn_local";

function syncModelSelectors() {
  const loteModelo = document.getElementById("loteModelo");
  if (loteModelo) {
    loteModelo.value = modeloSeleccionado;
  }
}

function initModelToggle() {
  const toggleCnn = document.getElementById("toggleCnn");
  const toggleXgb = document.getElementById("toggleXgb");
  const toggleNemotron = document.getElementById("toggleNemotron");
  const desc = document.getElementById("modelDescription");

  if (!toggleCnn || !toggleXgb || !toggleNemotron) return;

  const descriptions = {
    cnn_local: "MobileNetV2 entrenado localmente — Clasificación binaria sobre imágenes 32×32",
    xgboost_local: "XGBoost con features tabulares + SHAP — Rápido, interpretable, con explicabilidad",
    nemotron_externo: "NVIDIA Nemotron-3 — Razonamiento LLM con contexto clínico completo"
  };

  function setModel(value) {
    modeloSeleccionado = value;
    toggleCnn.classList.toggle("active", value === "cnn_local");
    toggleXgb.classList.toggle("active", value === "xgboost_local");
    toggleNemotron.classList.toggle("active", value === "nemotron_externo");
    if (desc) desc.textContent = descriptions[value] || "";
    updateModoLabel(value);
    updateFileInput(value);
    syncModelSelectors();
  }

  toggleCnn.addEventListener("click", () => setModel("cnn_local"));
  toggleXgb.addEventListener("click", () => setModel("xgboost_local"));
  toggleNemotron.addEventListener("click", () => setModel("nemotron_externo"));

  // Event listener for loteModelo selector to sync with sidebar
  const loteModelo = document.getElementById("loteModelo");
  if (loteModelo) {
    loteModelo.addEventListener("change", (e) => {
      const value = e.target.value;
      if (value === "cnn_local" || value === "xgboost_local" || value === "nemotron_externo") {
        setModel(value);
      }
    });
  }
}

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initModelToggle();
  checkFormValidity();
  fileInputHandler();
  await cargarModelos();
  updateModoLabel();
  updateFileInput();
  cargarConsultasRecientes();
  try {
    const h = await fetch(`${API}/health`).then(r => r.json());
    const badge = document.getElementById("statusBadge");
    badge.textContent = h.modelo_cargado ? "⚡ IA Activa" : "⚠️ Modo Reglas";
    badge.className = h.modelo_cargado
      ? "badge badge-success"
      : "badge badge-warning";
  } catch(e) {
    console.warn("Backend no detectado:", e);
    document.getElementById("statusBadge").textContent = "⚠️ Backend offline";
    document.getElementById("statusBadge").className = "badge badge-error";
  }
});

// ── Cargar modelos disponibles ─────────────────────────────────────
async function cargarModelos() {
  try {
    const resp = await fetch(`${API}/modelos`).then(r => r.json());
    const modelos = resp.modelos || [];
    const btnMap = { cnn_local: "toggleCnn", xgboost_local: "toggleXgb", nemotron_externo: "toggleNemotron" };
    for (const m of modelos) {
      const btnId = btnMap[m.id];
      if (btnId && !m.disponible) {
        const btn = document.getElementById(btnId);
        if (btn) {
          btn.classList.add("opacity-40", "pointer-events-none");
          if (modeloSeleccionado === m.id) {
            const available = modelos.find(mm => mm.disponible && mm.id !== m.id);
            if (available) document.getElementById(btnMap[available.id])?.click();
          }
        }
      }
    }
  } catch(e) {
    console.warn("No se pudieron cargar modelos:", e);
  }
}

// ── Validacion del formulario ──────────────────────────────────────
function checkFormValidity() {
  const form = document.getElementById("registrationForm");
  if (!form) return;
  const submitBtn = document.getElementById("submitBtn");
  const inputs = form.querySelectorAll("input[required], select[required]");
  let isValid = true;
  inputs.forEach(input => {
    if (!input.value || !input.value.trim()) isValid = false;
  });
  const fileInput = document.getElementById("fileUpload");
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) isValid = false;
  if (isValid) {
    submitBtn.disabled = false;
    submitBtn.classList.remove("disabled-btn");
  } else {
    submitBtn.disabled = true;
    submitBtn.classList.add("disabled-btn");
  }
}

document.addEventListener("input", e => {
  if (e.target.closest("#registrationForm")) checkFormValidity();
});
document.addEventListener("change", e => {
  if (e.target.closest("#registrationForm")) checkFormValidity();
});

// ── Dynamic File Input ────────────────────────────────────────────
function updateFileInput(modelo) {
  if (!modelo) {
    modelo = document.getElementById("toggleCnn")?.classList.contains("active") ? "cnn_local" : "nemotron_externo";
  }
  const fileInput = document.getElementById("fileUpload");
  const fileLabel = document.getElementById("fileLabel");
  const fileHint = document.getElementById("fileHint");
  if (!fileInput) return;

  if (modelo === "nemotron_externo") {
    fileInput.accept = ".pdf,.csv";
    if (fileLabel) fileLabel.textContent = "Subir archivo PDF o CSV de prefactura";
    if (fileHint) fileHint.textContent = "O arrastre y suelte aquí";
  } else {
    fileInput.accept = ".csv";
    if (fileLabel) fileLabel.textContent = "Subir archivo CSV de prefactura";
    if (fileHint) fileHint.textContent = "O arrastre y suelte aquí";
  }
  // Reset file if format changed
  if (fileInput.files.length > 0) {
    const f = fileInput.files[0];
    const ext = f.name.split('.').pop().toLowerCase();
    if ((modelo === "cnn_local" && ext !== "csv") || (modelo === "nemotron_externo" && ext !== "pdf" && ext !== "csv")) {
      fileInput.value = "";
      if (fileLabel) {
        fileLabel.textContent = (modelo === "nemotron_externo") ? "Subir archivo PDF o CSV de prefactura" : "Subir archivo CSV de prefactura";
        fileLabel.style.color = "";
      }
      if (fileHint) fileHint.textContent = "O arrastre y suelte aquí";
      checkFormValidity();
    }
  }
}

function fileInputHandler() {
  const fileInput = document.getElementById("fileUpload");
  const fileLabel = document.getElementById("fileLabel");
  const fileHint = document.getElementById("fileHint");
  const dropzone = document.getElementById("fileUploadContainer");
  if (!fileInput) return;
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      const f = e.target.files[0];
      fileLabel.textContent = f.name;
      if (fileHint) fileHint.textContent = `${(f.size / 1024).toFixed(1)} KB`;
      fileLabel.style.color = "var(--color-secondary)";
      dropzone?.classList.add('drag-active');
    } else {
      fileLabel.textContent = modeloSeleccionado === "nemotron_externo" ? "Subir archivo PDF o CSV de prefactura" : "Subir archivo CSV de prefactura";
      fileLabel.style.color = "";
      if (fileHint) fileHint.textContent = "O arrastre y suelte aquí";
      dropzone?.classList.remove('drag-active');
    }
    checkFormValidity();
  });
}

// ── Normalizacion de EPS ──────────────────────────────────────────
function normalizarEPS(eps) {
  if (!eps) return "";
  let normalized = eps.toUpperCase().trim();
  const suffixes = [' EPS-S', ' EPS', ' - EPS', '-EPS'];
  for (const suffix of suffixes) {
    if (normalized.endsWith(suffix.toUpperCase())) {
      normalized = normalized.slice(0, -suffix.length).trim();
      break;
    }
  }
  return normalized;
}

// ── Pantalla 1: Verificar y Analizar Prefactura ────────────────────
async function verificarPaciente(event) {
  event.preventDefault();

  const tipoDoc = document.getElementById("tipoDoc").value;
  const numDoc = document.getElementById("numDoc").value.trim();
  const nombres = document.getElementById("nombres").value.trim();
  const apellidos = document.getElementById("apellidos").value.trim();
  const nombre = nombres + " " + apellidos;
  const tipo_afiliacion = document.getElementById("tipo_afiliacion").value;
  const eps = document.getElementById("eps").value;
  const fileInput = document.getElementById("fileUpload");

  if (!numDoc) return showToast("Ingrese el número de documento.", "error");
  if (!fileInput || !fileInput.files || fileInput.files.length === 0)
    return showToast("Debe cargar un archivo de prefactura.", "error");

  ultimoFormData = { nombres, apellidos, nombre, tipoDoc, numDoc, tipo_afiliacion, eps, file: fileInput.files[0]?.name };

  // Read model from toggle
  const cnnActive = document.getElementById("toggleCnn").classList.contains("active");
  const xgbActive = document.getElementById("toggleXgb")?.classList.contains("active");
  const modeloSeleccionado = cnnActive ? "cnn_local" : xgbActive ? "xgboost_local" : "nemotron_externo";

  showLoading(true);
  try {
    // 1. Verificar ADRES
    let adresResp = null;
    try {
      adresResp = await fetch(`${API}/paciente/verificar-adres`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo_documento: tipoDoc.toUpperCase(), numero_documento: numDoc })
      }).then(r => r.json());
    } catch(e) { console.warn("ADRES falló:", e); }

    const adresDiv = document.getElementById("adresResult");
    if (adresResp && adresResp.fuente === "adres_bdua") {
      const d = adresResp.data || {};
      const af = d.estado_afiliacion || {};
      const esScraping = adresResp.origen === "web_scraping";
      const fuenteLabel = esScraping ? "ADRES (Web Scraping)" : "BDUA ADRES";
      const fuenteIcon = esScraping ? "travel_explore" : "verified_user";

      adresDiv.innerHTML = `
        <div style="background: linear-gradient(135deg, var(--color-success-container) 0%, var(--color-success-container) 100%); border: 1px solid var(--color-success); border-radius: 12px; padding: 20px;">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-full" style="background: var(--color-success-container);">
              <span class="material-symbols-outlined" style="color: var(--color-success);">${fuenteIcon}</span>
            </div>
            <div>
              <h4 class="font-semibold" style="color: var(--color-success);">${fuenteLabel} — Afiliado Activo</h4>
              <p style="font-size: 11px; color: var(--color-success); opacity: 0.7;">Consulta verificada exitosamente</p>
            </div>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 12px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block; margin-bottom: 4px;">Nombre Completo (ADRES)</span>
              <strong style="color: var(--color-on-surface);">${d.nombres || ""} ${d.apellidos || ""}</strong>
              ${d.nombres && d.apellidos ? `<span style="font-size: 10px; color: var(--color-success); display: block; margin-top: 4px;">✓ Nombre verificado vía ADRES</span>` : `<span style="font-size: 10px; color: var(--color-warning); display: block; margin-top: 4px;">⚠ Nombre no verificado (ADRES no disponible)</span>`}
            </div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 12px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block; margin-bottom: 4px;">Identificación</span>
              <strong style="color: var(--color-on-surface);">${d.tipo_de_identificacion || tipoDoc} ${d.numero_de_identificacion || numDoc}</strong>
            </div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 12px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block; margin-bottom: 4px;">Estado</span>
              <strong style="color: var(--color-success); display: flex; align-items: center; gap: 4px;"><span class="material-symbols-outlined" style="font-size: 14px;">check_circle</span> ${af.estado || "ACTIVO"}</strong>
            </div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 12px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block; margin-bottom: 4px;">EPS BDUA</span>
              <strong style="color: var(--color-on-surface);">${af.entidad || ""}</strong>
            </div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 12px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block; margin-bottom: 4px;">Régimen</span>
              <strong style="color: var(--color-on-surface);">${af.regimen || ""}</strong>
            </div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 12px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block; margin-bottom: 4px;">Nacimiento</span>
              <strong style="color: var(--color-on-surface);">${d.fecha_de_nacimiento || ""}</strong>
            </div>
          </div>
          ${af.entidad && eps && (af.entidad_normalizada || normalizarEPS(af.entidad)) !== normalizarEPS(eps) ? `
          <div style="margin-top: 16px; background: rgba(186, 26, 26, 0.05); border: 1px solid rgba(186, 26, 26, 0.2); border-radius: 8px; padding: 12px; color: var(--color-error); display: flex; align-items: center; gap: 8px; font-size: 14px;">
            <span class="material-symbols-outlined">warning</span> EPS en BDUA (${af.entidad}) ≠ EPS ingresada (${eps}). Posible irregularidad.
          </div>` : ""}
        </div>`;
      adresDiv.classList.remove("hidden");
    } else if (adresResp && (adresResp.fuente === "adres_no_disponible" || adresResp.fuente === "adres_sin_datos")) {
      adresDiv.innerHTML = `<div style="background: linear-gradient(135deg, var(--color-warning-container) 0%, var(--color-warning-container) 100%); border: 1px solid var(--color-warning); border-radius: 12px; padding: 16px; display: flex; gap: 12px; align-items: flex-start;">
        <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0" style="background: rgba(239, 108, 0, 0.1);">
          <span class="material-symbols-outlined" style="color: var(--color-warning);">cloud_off</span>
        </div>
        <div>
          <strong style="color: var(--color-warning); font-size: 14px;">BDUA no disponible</strong>
          <p style="font-size: 12px; color: var(--color-on-surface-variant); margin-top: 4px;">${adresResp.mensaje || "No se pudo consultar ADRES. La auditoría procede con datos locales."}</p>
          <p style="font-size: 11px; color: var(--color-outline); margin-top: 8px;">Puede continuar con el análisis usando los datos del formulario.</p>
        </div>
      </div>`;
      adresDiv.classList.remove("hidden");
    } else {
      adresDiv.classList.add("hidden");
    }

    // 2. Busqueda local
    let localResp = null;
    try {
      localResp = await fetch(`${API}/pacientes?q=${encodeURIComponent(numDoc)}`).then(r => r.json());
    } catch(e) { console.warn("Busqueda local falló:", e); }

    const localDiv = document.getElementById("localResult");
    if (localResp && localResp.results && localResp.results.length > 0) {
      pacienteActual = localResp.results[0];
      pacienteActual.eps_normalizada = normalizarEPS(pacienteActual.eps || "");
      localDiv.innerHTML = `
        <div style="background: linear-gradient(135deg, rgba(0, 52, 97, 0.03) 0%, rgba(0, 52, 97, 0.08) 100%); border: 1px solid rgba(0, 52, 97, 0.2); border-radius: 12px; padding: 16px;">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background: rgba(0, 52, 97, 0.1);">
              <span class="material-symbols-outlined" style="color: var(--color-primary);">folder_open</span>
            </div>
            <div>
              <h4 class="font-semibold text-sm" style="color: var(--color-primary);">Registros Locales — Health & Life IPS</h4>
              <p style="font-size: 11px; color: var(--color-primary); opacity: 0.7;">Paciente encontrado en base de datos</p>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-2 text-sm">
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">ID</span><br><strong>${pacienteActual.id_paciente || "—"}</strong></div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">EPS</span><br><strong>${pacienteActual.eps || "?"}</strong></div>
            <div style="background: rgba(255,255,255,0.5); border-radius: 8px; padding: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Afiliación</span><br><strong>${pacienteActual.tipo_afiliacion || "?"}</strong></div>
          </div>
        </div>`;
      localDiv.classList.remove("hidden");
    } else {
      pacienteActual = {
        id_paciente: `FORM-${numDoc}`,
        tipo_documento: tipoDoc,
        eps: eps,
        tipo_afiliacion: tipo_afiliacion,
        _fromForm: true
      };
      localDiv.innerHTML = `
        <div style="background: linear-gradient(135deg, rgba(239, 108, 0, 0.05) 0%, rgba(239, 108, 0, 0.12) 100%); border: 1px solid rgba(239, 108, 0, 0.2); border-radius: 12px; padding: 16px;">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background: rgba(239, 108, 0, 0.1);">
              <span class="material-symbols-outlined" style="color: var(--color-warning);">person_search</span>
            </div>
            <div>
              <strong style="color: var(--color-warning); font-size: 14px;">Paciente no encontrado en registros locales</strong>
              <p style="font-size: 12px; color: var(--color-on-surface-variant); margin-top: 4px;">Se usarán los datos del formulario para el análisis.</p>
            </div>
          </div>
        </div>`;
      localDiv.classList.remove("hidden");
    }

    document.getElementById("loadingMsg").textContent = "Analizando prefactura con IA...";

    // 3. SUBIR PREFACTURA Y ANALIZAR
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("tipo_doc", tipoDoc);
    formData.append("num_doc", numDoc);
    formData.append("eps", eps);
    formData.append("id_atencion", "");
    formData.append("modelo_selector", modeloSeleccionado);
    
    // Pasar resultado de ADRES si está disponible
    if (adresResp && adresResp.fuente === "adres_bdua") {
      formData.append("adres_result", JSON.stringify(adresResp));
    }

    let pfResult = null;
    try {
      const pfResp = await fetch(`${API}/prefactura/analizar`, {
        method: "POST",
        body: formData,
      });
      if (!pfResp.ok) {
        const errText = await pfResp.text();
        throw new Error(`Servidor respondió ${pfResp.status}: ${errText}`);
      }
      pfResult = await pfResp.json();
    } catch(fetchErr) {
      console.error("Error en análisis de prefactura:", fetchErr);
      showToast("Error al analizar la prefactura: " + fetchErr.message + "\nVerifique que el servidor esté iniciado.", "error");
      showLoading(false);
      return;
    }

    if (pfResult && pfResult.error) {
      showToast("Error analizando prefactura: " + pfResult.error, "error");
      showLoading(false);
      return;
    }

    ultimoResultadoPF = pfResult;
    mostrarResultadoPF(pfResult);

  } catch(e) {
    showToast("Error: " + e.message, "error");
  } finally {
    showLoading(false);
  }
  return false;
}

// ── Pantalla Prefactura: Vista comparativa ────────────────
function mostrarResultadoPF(data) {
  document.getElementById("screen1").classList.add("hidden");
  document.getElementById("screen2").classList.add("hidden");
  document.getElementById("screen3").classList.add("hidden");

  const sPf = document.getElementById("screenPf");
  sPf.classList.remove("hidden");
  sPf.classList.add("fade-in");

  const res = data.resumen || {};
  const pac = data.paciente || {};
  const ate = data.atencion || {};
  const cruces = data.cruces || [];
  const fugas = data.fugas || [];
  const fd = ultimoFormData || {};
  const isPdf = data.tipo_archivo === "pdf";

  const totalItems = res.total_items || 0;
  const consistentes = res.consistentes || 0;
  const inconsistentes = res.inconsistentes || 0;
  const nFugas = res.fugas_encontradas || fugas.length || 0;
  const recom = res.recomendacion || "REVISAR";
  const valorTotal = res.valor_total_prefactura || 0;
  const valorInconsistente = res.valor_en_inconsistencias || 0;
  const porcentajeInconsistente = res.porcentaje_inconsistente || 0;

  // ── MODO PDF ──
  if (isPdf) {
    const nemotronResult = data.modelos?.nemotron_externo?.resultado || {};
    const itemsDetectados = nemotronResult.items_detectados || [];
    const fugasDetectadas = nemotronResult.fugas_detectadas || [];

    document.getElementById("pfSummaryCards").innerHTML = `
      <div style="background: linear-gradient(135deg, rgba(0,52,97,0.03) 0%, rgba(0,52,97,0.08) 100%); border: 1px solid rgba(0,52,97,0.2); border-radius: 12px; padding: 20px; display: flex; gap: 16px; align-items: flex-start; margin-bottom: 16px;">
        <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" style="background: rgba(0,52,97,0.1);">
          <span class="material-symbols-outlined text-xl" style="color: var(--color-primary);">picture_as_pdf</span>
        </div>
        <div>
          <p class="text-sm font-semibold" style="color: var(--color-primary);">Análisis desde PDF</p>
          <p style="font-size: 12px; color: var(--color-on-surface-variant); margin-top: 4px;">Archivo: ${data.pdf_filename || "PDF"} · Procesado con NVIDIA Nemotron</p>
        </div>
      </div>
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; padding: 20px; margin-bottom: 16px;">
        <h4 class="font-semibold text-sm flex items-center gap-2 mb-3" style="color: var(--color-primary);">
          <span class="material-symbols-outlined text-sm">analytics</span> Análisis General
        </h4>
        <p style="font-size: 14px; color: var(--color-on-surface-variant);">${nemotronResult.analisis_general || "No disponible"}</p>
        ${nemotronResult.observaciones ? `<p style="font-size: 14px; color: var(--color-on-surface-variant); margin-top: 12px; background: var(--color-surface); padding: 12px; border-radius: 8px;"><strong>Observaciones:</strong> ${nemotronResult.observaciones}</p>` : ""}
      </div>
      ${itemsDetectados.length > 0 ? `
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; padding: 20px; margin-bottom: 16px;">
        <h4 class="font-semibold text-sm flex items-center gap-2 mb-3" style="color: var(--color-primary);">
          <span class="material-symbols-outlined text-sm">receipt_long</span> Items Detectados (${itemsDetectados.length})
        </h4>
        <div class="space-y-2 max-h-80 overflow-y-auto custom-scrollbar pr-1">
          ${itemsDetectados.map((item, i) => `
            <div class="p-3 hover:shadow-sm transition-shadow" style="background: var(--color-background); border-radius: 8px; border-left: 2px solid var(--color-primary);">
              <div class="flex justify-between items-start">
                <div>
                  <p class="text-xs font-semibold">${item.codigo || "—"} — ${item.descripcion || ""}</p>
                  <p style="font-size: 10px; color: var(--color-on-surface-variant); margin-top: 4px;">Cant: ${item.cantidad || 0} · Vr Unit: $${(item.valor_unitario || 0).toLocaleString()} · Total: $${(item.valor_total || 0).toLocaleString()}</p>
                </div>
              </div>
              ${item.analisis ? `<p style="font-size: 10px; color: var(--color-on-surface-variant); margin-top: 4px; font-style: italic; background: var(--color-surface); padding: 8px; border-radius: 4px;">${item.analisis}</p>` : ""}
            </div>
          `).join("")}
        </div>
      </div>` : ""}
      ${fugasDetectadas.length > 0 ? `
      <div style="background: linear-gradient(135deg, rgba(239,108,0,0.05) 0%, rgba(239,108,0,0.12) 100%); border: 1px solid rgba(239,108,0,0.2); border-radius: 12px; padding: 20px; margin-bottom: 16px;">
        <h4 class="font-semibold text-sm flex items-center gap-2 mb-3" style="color: var(--color-warning);">
          <span class="material-symbols-outlined text-sm">monetization_on</span> Posibles Fugas de Ingreso
        </h4>
        <ul class="space-y-2">
          ${fugasDetectadas.map(f => `<li style="font-size: 12px; color: var(--color-on-surface-variant); display: flex; gap: 8px; background: rgba(255,255,255,0.5); padding: 8px; border-radius: 8px;"><span class="material-symbols-outlined text-sm" style="color: var(--color-warning); margin-top: 2px;">arrow_right</span> ${f}</li>`).join("")}
        </ul>
      </div>` : ""}
    `;

    document.getElementById("pfCruces").innerHTML = "";
    document.getElementById("pfFugas").classList.add("hidden");

    const nemotronRaw = data.modelos?.nemotron_externo;
    if (nemotronRaw) {
      document.getElementById("pfModelos").innerHTML = `
        <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; padding: 16px;">
          <h4 class="font-semibold text-sm flex items-center gap-2" style="color: var(--color-primary);">
            <span class="material-symbols-outlined">artist</span> NVIDIA Nemotron
          </h4>
          ${nemotronRaw.error ? `<p style="font-size: 12px; color: var(--color-error); margin-top: 8px; background: rgba(186,26,26,0.05); padding: 8px; border-radius: 4px;">Error: ${nemotronRaw.error}</p>` : `
          <div class="mt-3 text-sm">
            <p style="font-size: 12px; color: var(--color-on-surface-variant);">${nemotronResult.analisis_general || ""}</p>
            <div class="flex justify-between items-center mt-2" style="padding: 8px; background: var(--color-background); border-radius: 4px;">
              <span style="font-size: 11px; color: var(--color-on-surface-variant);">Recomendación:</span>
              <strong style="color: ${nemotronResult.recomendacion === 'APROBAR' ? 'var(--color-success)' : nemotronResult.recomendacion === 'RECHAZAR' ? 'var(--color-error)' : 'var(--color-warning)'};">${nemotronResult.recomendacion || "N/A"}</strong>
            </div>
          </div>`}
        </div>
      `;
    }

    guardarConsultaReciente({
      paciente: fd.nombre || pac.id || "Desconocido",
      documento: `${fd.tipoDoc || ""} ${fd.numDoc || ""} [PDF]`,
      fecha: new Date().toISOString(),
      totalItems, consistentes, inconsistentes, fugas: nFugas, recomendacion: recom,
      data, formData: fd,
    });
    return;
  }

  // ── Badge de recomendación ──
  const badge = document.getElementById("pfBadge");
  const badgeConfig = {
    APROBAR: { icon: "check_circle", label: "APROBAR", cls: "badge-success" },
    RECHAZAR: { icon: "cancel", label: "RECHAZAR", cls: "badge-error" },
    REVISAR: { icon: "error_outline", label: "REVISAR", cls: "badge-warning" }
  };
  const bc = badgeConfig[recom] || badgeConfig.REVISAR;
  badge.innerHTML = `<span class="material-symbols-outlined text-sm">${bc.icon}</span> ${bc.label}`;
  badge.className = `badge ${bc.cls}`;

  // ── Resumen ──
  let resumenTexto = "";
  if (inconsistentes > 0) {
    resumenTexto = `${inconsistentes} de ${totalItems} items con inconsistencia detectada`;
  } else {
    resumenTexto = `Todos los ${totalItems} items son consistentes`;
  }
  if (nFugas > 0) resumenTexto += ` · ${nFugas} fuga(s) de ingreso`;
  if (valorInconsistente > 0) resumenTexto += ` · $${valorInconsistente.toLocaleString()} en inconsistencias`;
  document.getElementById("pfResumen").textContent = resumenTexto;

  // ── Vista comparativa lado a lado ──
  function badgeCompare(valPf, valBd, label, normalizeEps = false) {
    let pf = (valPf || "").toString().trim().toUpperCase();
    let bd = (valBd || "").toString().trim().toUpperCase();
    if (normalizeEps) {
      pf = normalizarEPS(pf);
      bd = normalizarEPS(bd);
    }
    const igual = pf && bd && pf === bd;
    return `
      <div class="flex items-center justify-between p-3 rounded-lg" style="${igual ? 'background: rgba(46,125,50,0.05); border: 1px solid rgba(46,125,50,0.1);' : 'background: rgba(186,26,26,0.05); border: 1px solid rgba(186,26,26,0.1);'}">
        <span style="font-size: 11px; color: var(--color-on-surface-variant);">${label}</span>
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold" style="color: ${igual ? 'var(--color-success)' : 'var(--color-error)'};">${valPf || "—"}</span>
          <span class="material-symbols-outlined text-xs" style="color: var(--color-outline);">arrow_forward</span>
          <span class="text-xs font-semibold" style="color: ${igual ? 'var(--color-success)' : 'var(--color-error)'};">${valBd || "—"}</span>
          <span class="material-symbols-outlined text-sm" style="color: ${igual ? 'var(--color-success)' : 'var(--color-error)'};">${igual ? 'check_circle' : 'warning'}</span>
        </div>
      </div>`;
  }

  document.getElementById("pfSummaryCards").innerHTML = `
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <!-- COLUMNA IZQUIERDA: Datos de la Prefactura -->
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; overflow: hidden;">
        <div style="background: rgba(0,52,97,0.05); padding: 16px; border-bottom: 1px solid var(--color-outline-variant);">
          <h4 class="font-semibold text-sm flex items-center gap-2" style="color: var(--color-primary);">
            <span class="material-symbols-outlined text-sm">description</span> Datos de la Prefactura
          </h4>
        </div>
        <div class="p-5">
          <div class="space-y-2 mb-5">
            <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Paciente</span><span class="text-xs font-semibold">${fd.nombre || "—"}</span></div>
            <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Documento</span><span class="text-xs font-semibold">${fd.tipoDoc || ""} ${fd.numDoc || ""}</span></div>
            <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Régimen</span><span class="text-xs font-semibold">${fd.tipo_afiliacion || "—"}</span></div>
            <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">EPS</span><span class="text-xs font-semibold">${fd.eps || "—"}</span></div>
            <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Archivo</span><span class="text-xs font-semibold truncate" style="max-width: 200px;">${fd.file || "—"}</span></div>
          </div>
          
          <div class="flex items-center justify-between mb-3">
            <h5 class="font-semibold text-sm" style="color: var(--color-on-surface);">Items Facturados</h5>
            <span class="text-xs px-2 py-0.5 rounded-full" style="background: rgba(0,52,97,0.1); color: var(--color-primary);">${cruces.length} items</span>
          </div>
          <div class="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-1">
            ${cruces.map(c => {
              const esInconsistente = c.resultado === 'INCONSISTENTE';
              return `
                <div class="flex justify-between items-center p-3 hover:shadow-sm transition-shadow" style="background: var(--color-background); border-radius: 8px; border-left: 3px solid ${esInconsistente ? 'var(--color-error)' : 'var(--color-success)'};">
                  <div class="min-w-0 flex-1">
                    <p class="text-xs font-semibold truncate">${c.codigo_cups_pf || ""}</p>
                    <p style="font-size: 10px; color: var(--color-on-surface-variant); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${c.descripcion_pf || ""}</p>
                  </div>
                  <div class="text-right ml-3 shrink-0">
                    <span class="text-xs font-bold block">x${c.cantidad_pf || 0}</span>
                    <span style="font-size: 10px; color: var(--color-on-surface-variant);">$${(c.valor_total_pf || 0).toLocaleString()}</span>
                  </div>
                </div>`;
            }).join("")}
          </div>
        </div>
      </div>

      <!-- COLUMNA DERECHA: Datos Verificados -->
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; overflow: hidden;">
        <div style="background: rgba(0,110,37,0.05); padding: 16px; border-bottom: 1px solid var(--color-outline-variant);">
          <h4 class="font-semibold text-sm flex items-center gap-2" style="color: var(--color-secondary);">
            <span class="material-symbols-outlined text-sm">verified</span> Datos Verificados
          </h4>
        </div>
        <div class="p-5">
          <!-- Verificaciones ADRES y BD Local -->
          <div class="space-y-2 mb-5">
            ${data.verificaciones ? `
              <div class="flex justify-between items-center p-3 rounded-lg" style="background: rgba(0,52,97,0.05); border: 1px solid rgba(0,52,97,0.1);">
                <span style="font-size: 11px; color: var(--color-on-surface-variant);">ADRES</span>
                <div class="flex items-center gap-2">
                  ${data.verificaciones.adres.indicador === "✅" ? 
                    '<span class="material-symbols-outlined text-xs" style="color: var(--color-success);">check_circle</span>' : 
                    data.verificaciones.adres.indicador === "⚠️" ?
                    '<span class="material-symbols-outlined text-xs" style="color: var(--color-warning);">warning</span>' :
                    '<span class="material-symbols-outlined text-xs" style="color: var(--color-error);">cancel</span>'}
                </div>
              </div>
              <div class="flex justify-between items-center p-3 rounded-lg" style="background: rgba(0,52,97,0.05); border: 1px solid rgba(0,52,97,0.1);">
                <span style="font-size: 11px; color: var(--color-on-surface-variant);">BD Local</span>
                <div class="flex items-center gap-2">
                  ${data.verificaciones.bd_local.indicador === "✅" ? 
                    '<span class="material-symbols-outlined text-xs" style="color: var(--color-success);">check_circle</span>' : 
                    '<span class="material-symbols-outlined text-xs" style="color: var(--color-error);">cancel</span>'}
                </div>
              </div>
            ` : ''}
            
            ${pac.encontrado_db_local ? `
              <div class="flex justify-between items-center p-3 rounded-lg" style="background: rgba(0,52,97,0.05); border: 1px solid rgba(0,52,97,0.1);">
                <span style="font-size: 11px; color: var(--color-on-surface-variant);">Documento</span>
                <div class="flex items-center gap-2">
                  <span class="text-xs font-semibold" style="color: var(--color-primary);">${fd.tipoDoc || ""} ${fd.numDoc || ""}</span>
                  <span class="material-symbols-outlined text-xs" style="color: var(--color-success);">check_circle</span>
                </div>
              </div>
              ${badgeCompare(pac.eps_adres || fd.eps, pac.eps || "", "EPS", true)}
              ${badgeCompare(fd.tipo_afiliacion, pac.tipo_afiliacion, "Régimen")}
            ` : `
              <div class="flex items-center gap-3 p-3 rounded-lg" style="background: rgba(239,108,0,0.05); border: 1px solid rgba(239,108,0,0.1);">
                <span class="material-symbols-outlined text-sm" style="color: var(--color-warning);">info</span>
                <div>
                  <span class="text-xs font-medium" style="color: var(--color-warning);">Paciente no encontrado en DB local</span>
                  <span style="font-size: 11px; color: var(--color-on-surface-variant); display: block;">Verificación con datos del formulario</span>
                </div>
              </div>
              <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Tipo Doc</span><span class="text-xs font-semibold">${fd.tipoDoc || "—"}</span></div>
              <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Número Doc</span><span class="text-xs font-semibold">${fd.numDoc || "—"}</span></div>
              <div class="flex justify-between items-center p-2.5" style="background: var(--color-background); border-radius: 8px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">EPS</span><span class="text-xs font-semibold">${fd.eps || "—"}</span></div>
            `}
          </div>
          
          <div class="flex items-center justify-between mb-3">
            <h5 class="font-semibold text-sm" style="color: var(--color-on-surface);">Registros en Historia Clínica</h5>
            <span class="text-xs px-2 py-0.5 rounded-full" style="background: rgba(0,110,37,0.1); color: var(--color-secondary);">${cruces.filter(c => c.codigo_cups_hc).length} registros</span>
          </div>
          <div class="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-1">
            ${cruces.map(c => {
              const esInconsistente = c.resultado === "INCONSISTENTE";
              const tieneHC = c.codigo_cups_hc && c.codigo_cups_hc !== "";
              return `
                <div class="p-3 hover:shadow-sm transition-shadow" style="background: var(--color-background); border-radius: 8px; border-left: 3px solid ${esInconsistente ? 'var(--color-error)' : 'var(--color-success)'};">
                  <div class="flex justify-between items-start">
                    <div class="min-w-0 flex-1">
                      <p class="text-xs font-semibold" style="color: ${tieneHC ? (esInconsistente ? 'var(--color-error)' : 'var(--color-success)') : 'var(--color-outline)'};">${c.codigo_cups_hc || "Sin registro"}</p>
                      <p style="font-size: 10px; color: var(--color-on-surface-variant); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${c.descripcion_hc || "No encontrado en HC"}</p>
                    </div>
                    <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold" style="${esInconsistente ? 'background: rgba(186,26,26,0.1); color: var(--color-error);' : 'background: rgba(46,125,50,0.1); color: var(--color-success);'}">${c.tipo_alerta}</span>
                  </div>
                  <div class="flex items-center gap-3 mt-2" style="font-size: 10px; color: var(--color-on-surface-variant);">
                    <span class="flex items-center gap-1"><span class="material-symbols-outlined text-xs">medical_services</span> HC: x${c.cantidad_hc || 0}</span>
                    <span class="flex items-center gap-1"><span class="material-symbols-outlined text-xs">receipt</span> PF: x${c.cantidad_pf || 0}</span>
                    <span class="flex items-center gap-1"><span class="material-symbols-outlined text-xs">description</span> ${c.soporte_clinico || "N/A"}</span>
                  </div>
                  ${c.alertas && c.alertas.length ? c.alertas.map(a => `
                    <div class="mt-2 flex items-center gap-1 p-1.5 rounded" style="font-size: 10px; color: var(--color-error); background: rgba(186,26,26,0.05);">
                      <span class="material-symbols-outlined text-xs">error</span> ${a.descripcion}
                    </div>`).join("") : ""}
                </div>`;
            }).join("")}
          </div>
        </div>
      </div>
    </div>
  `;

  // ── Fugas ──
  if (fugas.length > 0) {
    document.getElementById("pfFugas").classList.remove("hidden");
    document.getElementById("pfFugasList").innerHTML = `
      <div class="space-y-2">
        ${fugas.map(f => `
          <div class="flex items-start gap-3 hover:shadow-sm transition-shadow" style="background: linear-gradient(135deg, rgba(239,108,0,0.05) 0%, rgba(239,108,0,0.12) 100%); border: 1px solid rgba(239,108,0,0.2); border-radius: 12px; padding: 16px;">
            <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style="background: rgba(239,108,0,0.1);">
              <span class="material-symbols-outlined text-sm" style="color: var(--color-warning);">monetization_on</span>
            </div>
            <div class="flex-1">
              <div class="flex items-center justify-between">
                <strong class="text-sm" style="color: var(--color-on-surface);">${f.codigo_cups}</strong>
                <span class="text-[10px] px-2 py-0.5 rounded-full" style="background: rgba(239,108,0,0.1); color: var(--color-warning);">Fuga de Ingreso</span>
              </div>
              <p style="font-size: 12px; color: var(--color-on-surface-variant); margin-top: 4px;">${f.descripcion}</p>
              <p style="font-size: 11px; color: var(--color-outline); margin-top: 4px;">Cantidad realizada: ${f.cantidad_realizada} · ${f.descripcion_alerta}</p>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  } else {
    document.getElementById("pfFugas").classList.add("hidden");
  }

  // ── Modelos ──
  const modelosHTML = [];
  const cnn = data.modelos?.cnn_local;
  const xgb = data.modelos?.xgboost_local;
  const nemotron = data.modelos?.nemotron_externo;

  if (cnn) {
    modelosHTML.push(`
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; padding: 16px; transition: box-shadow 0.2s;" onmouseover="this.style.boxShadow='var(--card-hover)'" onmouseout="this.style.boxShadow=''">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: rgba(0,52,97,0.1);">
            <span class="material-symbols-outlined text-sm" style="color: var(--color-primary);">neurology</span>
          </div>
          <h4 class="font-semibold text-sm" style="color: var(--color-primary);">CNN MobileNetV2</h4>
        </div>
        ${cnn.error ? `<p style="font-size: 12px; color: var(--color-error); background: rgba(186,26,26,0.05); padding: 8px; border-radius: 4px;">Error: ${cnn.error}</p>` : `
        <div class="space-y-2 text-sm">
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Consistentes:</span><strong style="color: var(--color-success);">${cnn.consistentes}</strong></div>
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Inconsistentes:</span><strong style="color: var(--color-error);">${cnn.inconsistentes}</strong></div>
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Threshold:</span><span class="text-xs">${(cnn.threshold * 100).toFixed(1)}%</span></div>
        </div>`}
      </div>
    `);
  }

  if (xgb) {
    modelosHTML.push(`
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; padding: 16px; transition: box-shadow 0.2s;" onmouseover="this.style.boxShadow='var(--card-hover)'" onmouseout="this.style.boxShadow=''">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: rgba(0,110,37,0.1);">
            <span class="material-symbols-outlined text-sm" style="color: var(--color-secondary);">bar_chart</span>
          </div>
          <h4 class="font-semibold text-sm" style="color: var(--color-secondary);">XGBoost</h4>
        </div>
        ${xgb.error ? `<p style="font-size: 12px; color: var(--color-error); background: rgba(186,26,26,0.05); padding: 8px; border-radius: 4px;">Error: ${xgb.error}</p>` : `
        <div class="space-y-2 text-sm">
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Consistentes:</span><strong style="color: var(--color-success);">${xgb.consistentes}</strong></div>
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Inconsistentes:</span><strong style="color: var(--color-error);">${xgb.inconsistentes}</strong></div>
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Threshold:</span><span class="text-xs">${(xgb.threshold * 100).toFixed(1)}%</span></div>
        </div>`}
      </div>
    `);
  }

  if (nemotron) {
    const nr = nemotron.resultado;
    modelosHTML.push(`
      <div style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-radius: 12px; padding: 16px; transition: box-shadow 0.2s;" onmouseover="this.style.boxShadow='var(--card-hover)'" onmouseout="this.style.boxShadow=''">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: rgba(0,52,97,0.1);">
            <span class="material-symbols-outlined text-sm" style="color: var(--color-primary);">psychology</span>
          </div>
          <h4 class="font-semibold text-sm" style="color: var(--color-primary);">NVIDIA Nemotron</h4>
        </div>
        ${nemotron.error ? `<p style="font-size: 12px; color: var(--color-error); background: rgba(186,26,26,0.05); padding: 8px; border-radius: 4px;">Error: ${nemotron.error}</p>` : nr ? `
        <div class="space-y-2 text-sm">
          <p style="font-size: 12px; color: var(--color-on-surface-variant); background: var(--color-surface); padding: 8px; border-radius: 4px;">${nr.analisis_general || ""}</p>
          <div class="flex justify-between items-center p-2" style="background: var(--color-background); border-radius: 4px;"><span style="font-size: 11px; color: var(--color-on-surface-variant);">Recomendación:</span><strong style="color: ${nr.recomendacion === 'APROBAR' ? 'var(--color-success)' : nr.recomendacion === 'RECHAZAR' ? 'var(--color-error)' : 'var(--color-warning)'};">${nr.recomendacion || "N/A"}</strong></div>
          ${nr.observaciones ? `<p style="font-size: 11px; color: var(--color-outline); margin-top: 4px; font-style: italic;">${nr.observaciones}</p>` : ""}
        </div>` : nemotron.respuesta_raw ? `
        <p style="font-size: 12px; color: var(--color-on-surface-variant); margin-top: 8px; background: var(--color-surface); padding: 8px; border-radius: 4px;">${nemotron.respuesta_raw}</p>` : `
        <p style="font-size: 12px; color: var(--color-outline); margin-top: 8px;">Sin respuesta</p>`}
      </div>
    `);
  }

  document.getElementById("pfModelos").innerHTML = modelosHTML.join("");

  // ── Guardar en consultas recientes ──
  guardarConsultaReciente({
    paciente: fd.nombre || pac.id || "Desconocido",
    documento: `${fd.tipoDoc || ""} ${fd.numDoc || ""}`,
    fecha: new Date().toISOString(),
    totalItems, consistentes, inconsistentes, fugas: nFugas, recomendacion: recom,
    data, formData: fd,
  });
}

function exportarResultadoPF() {
  if (!ultimoResultadoPF) return showToast("No hay resultados para exportar.", "error");
  const data = JSON.stringify(ultimoResultadoPF, null, 2);
  const blob = new Blob([data], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `prefactura_analisis_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Resultado exportado correctamente", "success");
}

// ── Pantalla 2: Seleccion atencion ────────────────────────────────
async function mostrarScreen2() {
  document.getElementById("screen1").classList.add("hidden");
  document.getElementById("screen3").classList.add("hidden");
  document.getElementById("screenPf").classList.add("hidden");
  const s2 = document.getElementById("screen2");
  s2.classList.remove("hidden");
  s2.classList.add("fade-in");

  if (pacienteActual) {
    document.getElementById("pacInfo").textContent =
      `Paciente: ${pacienteActual.id_paciente} | EPS: ${pacienteActual.eps || "?"}`;

    if (!pacienteActual._fromForm) {
      try {
        const resp = await fetch(`${API}/atenciones?pac_id=${encodeURIComponent(pacienteActual.id_paciente)}`).then(r => r.json());
        atencionesActuales = resp.results || [];
      } catch(e) { atencionesActuales = []; }
    } else {
      atencionesActuales = [];
    }

    const sel = document.getElementById("selAtencion");
    if (atencionesActuales.length > 0) {
      sel.innerHTML = atencionesActuales.map(a =>
        `<option value="${a.id_atencion}">${a.id_atencion} — ${a.fecha_atencion?.slice(0,10) || ""} | ${a.tipo_atencion || ""} | ${a.diagnostico_principal_cie10 || ""}</option>`
      ).join("");
    } else {
      sel.innerHTML = "<option disabled selected>Sin atenciones registradas — use el campo abajo</option>";
      if (!document.getElementById("manualAtencionContainer")) {
        const div = document.createElement("div");
        div.id = "manualAtencionContainer";
        div.className = "mt-4";
        div.innerHTML = `
          <label class="block text-sm mb-2" style="color: var(--color-on-surface-variant);">O ingrese ID de atención manualmente (Ej: ATN-000001)</label>
          <div class="relative">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2" style="color: var(--color-outline);">medical_information</span>
            <input class="w-full pl-10 pr-4 py-3 rounded-xl outline-none font-body" id="manualAtencion" placeholder="ATN-XXXXXX" type="text" style="background: var(--color-surface-container-lowest); border: 1px solid var(--color-outline-variant); color: var(--color-on-surface);"/>
          </div>`;
        sel.parentElement.appendChild(div);
      }
    }
  }
}

// ── Pantalla 3: Auditoría ─────────────────────────────────────────
async function auditar() {
  let idAtencion = document.getElementById("selAtencion").value;
  if (!idAtencion || idAtencion === "Sin atenciones registradas — use el campo abajo") {
    const manual = document.getElementById("manualAtencion");
    if (manual) idAtencion = manual.value.trim();
  }
  if (!idAtencion) return showToast("Seleccione o ingrese un ID de atención.", "error");

  showLoading(true);
  try {
    const cruces = await fetch(`${API}/cruces-atencion/${idAtencion}`).then(r => r.json());
    const resultados = [];
    for (const c of (cruces.results || []).slice(0, 10)) {
      const r = await fetch(`${API}/auditar/${c.id_cruce}`).then(r => r.json());
      resultados.push(r);
    }

    if (resultados.length === 0) {
      showToast("No se encontraron cruces para la atención " + idAtencion, "error");
      showLoading(false);
      document.getElementById("screen2").classList.remove("hidden");
      return;
    }

    mostrarResultado(resultados, idAtencion);
  } catch(e) {
    showToast("Error en auditoría: " + e.message, "error");
  } finally {
    showLoading(false);
  }
}

function mostrarResultado(resultados, idAtencion) {
  document.getElementById("screen2").classList.add("hidden");
  document.getElementById("screenPf").classList.add("hidden");
  const s3 = document.getElementById("screen3");
  s3.classList.remove("hidden");
  s3.classList.add("fade-in");

  document.getElementById("cruceLabel").textContent =
    `Atención: ${idAtencion} | ${resultados.length} items auditados`;

  const algunaInconsistente = resultados.some(r => r.tipo_alerta_final !== "CONSISTENTE");
  const badge = document.getElementById("resultBadge");
  if (algunaInconsistente) {
    badge.innerHTML = `<span class="material-symbols-outlined text-sm">warning</span> INCONSISTENTE`;
    badge.className = "badge badge-error flex items-center gap-1";
  } else {
    badge.innerHTML = `<span class="material-symbols-outlined text-sm">check_circle</span> CONSISTENTE`;
    badge.className = "badge badge-success flex items-center gap-1";
  }

  let detailHTML = "";
  resultados.forEach((r, i) => {
    const hc = r.hc_vs_pf;
    const iaProb = r.resultado_ia?.probabilidad_inconsistencia;
    const iaPred = r.resultado_ia?.prediccion;
    const esInconsistente = r.tipo_alerta_final !== "CONSISTENTE";
    detailHTML += `
      <div class="p-4 rounded-xl hover:shadow-sm transition-shadow" style="background: var(--color-surface-container-low); border: 1px solid var(--color-outline-variant); border-left: 4px solid ${esInconsistente ? 'var(--color-error)' : 'var(--color-success)'};">
        <div class="flex justify-between items-start">
          <div><strong class="text-sm" style="color: var(--color-primary);">${r.id_cruce}</strong> · ${r.diagnostico || ""}</div>
          <span class="text-xs px-2 py-1 rounded-full font-semibold" style="${esInconsistente ? 'background: rgba(186,26,26,0.1); color: var(--color-error);' : 'background: rgba(46,125,50,0.1); color: var(--color-success);'}">${r.tipo_alerta_final}</span>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-3 text-sm">
          <div class="p-3 rounded-lg" style="background: var(--color-background);">
            <span style="font-size: 10px; color: var(--color-outline); text-transform: uppercase;">HC Registró</span><br>
            <strong>${hc.codigo_cups_hc || "—"}</strong> ${hc.descripcion_hc || ""}<br>
            <span style="font-size: 11px; color: var(--color-outline);">Cantidad: ${hc.cantidad_hc}</span>
          </div>
          <div class="p-3 rounded-lg" style="background: var(--color-background);">
            <span style="font-size: 10px; color: var(--color-outline); text-transform: uppercase;">PF Cobró</span><br>
            <strong>${hc.codigo_cups_pf || "—"}</strong> ${hc.descripcion_pf || ""}<br>
            <span style="font-size: 11px; color: var(--color-outline);">Cantidad: ${hc.cantidad_pf} · ${hc.valor_total_pf ? '$' + hc.valor_total_pf.toLocaleString() : "—"}</span>
          </div>
        </div>
        ${r.resultado_reglas?.alertas?.length ? r.resultado_reglas.alertas.map(a => `
          <div class="mt-2 flex items-center gap-1 p-1.5 rounded" style="font-size: 10px; color: var(--color-error); background: rgba(186,26,26,0.05);">
            <span class="material-symbols-outlined text-xs">error</span> ${a.descripcion}
          </div>`).join("") : ""}
        <div class="mt-2" style="font-size: 11px; color: var(--color-outline);">IA: ${iaPred || "N/D"} (${iaProb ? (iaProb * 100).toFixed(1) + "%" : "N/A"}) · Modo: ${r.modo || ""}</div>
      </div>`;
  });
  document.getElementById("resultDetail").innerHTML = detailHTML;
  const nCon = resultados.filter(r => r.tipo_alerta_final === "CONSISTENTE").length;
  const nInc = resultados.filter(r => r.tipo_alerta_final !== "CONSISTENTE").length;
  document.getElementById("comparativa").innerHTML =
    `<div style="font-size: 11px; color: var(--color-on-surface-variant);">Total items: ${resultados.length} · Consistentes: ${nCon} · Inconsistentes: ${nInc}</div>`;
}

function exportarCSV() {
  showToast("Use el endpoint /api/auditar/{id_cruce} para descargar resultados.", "info");
}

// ── Modo de Operación ─────────────────────────────────────────────
function updateModoLabel(modelo) {
  if (!modelo) {
    const cnnActive = document.getElementById("toggleCnn")?.classList.contains("active");
    const xgbActive = document.getElementById("toggleXgb")?.classList.contains("active");
    modelo = cnnActive ? "cnn_local" : xgbActive ? "xgboost_local" : "nemotron_externo";
  }
  const label = document.getElementById("modoLabel");
  const confianza = document.getElementById("confianzaLabel");
  const confianzaBar = document.getElementById("confianzaBar");
  if (!label) return;

  if (modelo === "cnn_local") {
    label.innerHTML = `<span class="flex items-center gap-2"><span class="material-symbols-outlined text-sm" style="color: var(--color-primary);">neurology</span> <strong>CNN MobileNetV2</strong> — Modelo local entrenado con datos de la IPS. Auditoría basada en patrones históricos y reglas clínicas.</span>`;
    if (confianza) confianza.textContent = "94%";
    if (confianzaBar) confianzaBar.style.width = "94%";
  } else if (modelo === "xgboost_local") {
    label.innerHTML = `<span class="flex items-center gap-2"><span class="material-symbols-outlined text-sm" style="color: var(--color-primary);">bar_chart</span> <strong>XGBoost</strong> — Modelo local de gradient boosting con features tabulares. Rápido, interpretable con SHAP, optimizado para datos tabulares.</span>`;
    if (confianza) confianza.textContent = "95%";
    if (confianzaBar) confianzaBar.style.width = "95%";
  } else {
    label.innerHTML = `<span class="flex items-center gap-2"><span class="material-symbols-outlined text-sm" style="color: var(--color-primary);">psychology</span> <strong>NVIDIA Nemotron-3</strong> — Modelo externo con razonamiento LLM. Auditoría basada en análisis semántico y contexto clínico.</span>`;
    if (confianza) confianza.textContent = "96%";
    if (confianzaBar) confianzaBar.style.width = "96%";
  }
}

// ── Consultas Recientes (localStorage) ────────────────────────────
const RECENT_KEY = "hl_recent_checkups";

function guardarConsultaReciente(consulta) {
  try {
    let list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    list.unshift(consulta);
    if (list.length > 10) list = list.slice(0, 10);
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
    renderConsultasRecientes();
  } catch(e) {
    console.warn("No se pudo guardar consulta reciente:", e);
  }
}

function renderConsultasRecientes() {
  const list = document.getElementById("recentCheckupsList");
  if (!list) return;
  try {
    const items = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    if (items.length === 0) {
      list.innerHTML = `<div class="flex items-center justify-center py-4" style="color: var(--color-outline); font-size: 14px;">Sin consultas recientes</div>`;
      return;
    }
    list.innerHTML = items.slice(0, 5).map((c, i) => {
      const fecha = new Date(c.fecha);
      const fechaStr = fecha.toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
      const color = c.recomendacion === "APROBAR" ? "var(--color-success)" : c.recomendacion === "RECHAZAR" ? "var(--color-error)" : "var(--color-warning)";
      const icon = c.recomendacion === "APROBAR" ? "check_circle" : c.recomendacion === "RECHAZAR" ? "cancel" : "error_outline";
      const inicial = (c.paciente || "?")[0].toUpperCase();
      return `
        <button onclick="verConsultaReciente(${i})" class="w-full flex items-center gap-3 p-3 rounded-xl transition-all cursor-pointer hover:translate-x-1" style="background: var(--color-surface-container-lowest); border: 1px solid var(--color-outline-variant); text-align: left;">
          <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0" style="background: var(--color-secondary-container); color: var(--color-on-secondary-container);">${inicial}</div>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-semibold truncate" style="color: var(--color-on-surface);">${c.paciente}</p>
            <p style="font-size: 10px; color: var(--color-outline);">${c.documento} · ${fechaStr}</p>
          </div>
          <span class="material-symbols-outlined text-sm shrink-0" style="color: ${color};">${icon}</span>
        </button>`;
    }).join("");
  } catch(e) {
    list.innerHTML = `<div class="flex items-center justify-center py-4" style="color: var(--color-outline); font-size: 14px;">Error cargando</div>`;
  }
}

function cargarConsultasRecientes() {
  renderConsultasRecientes();
}

function verConsultaReciente(index) {
  try {
    const items = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    const item = items[index];
    if (item && item.data) {
      ultimoFormData = item.formData;
      ultimoResultadoPF = item.data;
      mostrarResultadoPF(item.data);
    }
  } catch(e) {
    console.warn("Error al recuperar consulta:", e);
  }
}

// ── Soporte ────────────────────────────────────────────────────────
function mostrarSoporte(section) {
  const overlay = document.getElementById("soporteOverlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");

  const content = document.getElementById("soporteContent");
  if (section === "privacidad") {
    content.innerHTML = `
      <div class="flex items-center gap-3 mb-8">
        <span class="material-symbols-outlined text-3xl" style="color: var(--color-primary);">lock</span>
        <h3 class="font-headline" style="color: var(--color-primary);">Políticas de Privacidad</h3>
      </div>
      <div class="space-y-4 text-sm" style="color: var(--color-on-surface-variant);">
        <p>En <strong>Health & Life IPS</strong> protegemos los datos personales de nuestros pacientes conforme a la Ley 1581 de 2012 y el Decreto 1377 de 2013.</p>
        <p><strong>Datos recopilados:</strong> Identificación, datos de salud con fines de auditoría médica, historias clínicas y facturación.</p>
        <p><strong>Finalidad:</strong> Verificación de prefacturas, control de calidad, auditoría médica y cumplimiento normativo.</p>
        <p><strong>Derechos:</strong> Acceder, actualizar, rectificar y solicitar la eliminación de sus datos personales contactando a nuestro departamento de datos.</p>
        <p style="font-size: 11px; margin-top: 16px;">Para más información, contáctenos en protecciondatos@hlsite.com.co</p>
      </div>
      <button onclick="cerrarSoporte()" class="mt-8 w-full py-3 rounded-xl font-label" style="background: var(--color-primary); color: var(--color-on-primary);">Cerrar</button>`;
  } else if (section === "terminos") {
    content.innerHTML = `
      <div class="flex items-center gap-3 mb-8">
        <span class="material-symbols-outlined text-3xl" style="color: var(--color-primary);">gavel</span>
        <h3 class="font-headline" style="color: var(--color-primary);">Términos de Uso</h3>
      </div>
      <div class="space-y-4 text-sm" style="color: var(--color-on-surface-variant);">
        <p>El uso del sistema <strong>LINE — Auditor Médico Digital</strong> está sujeto a los siguientes términos:</p>
        <p>1. El sistema es una herramienta de apoyo a la auditoría médica. Las decisiones finales son responsabilidad del profesional de la salud.</p>
        <p>2. Los datos ingresados deben ser veraces y corresponder a atenciones reales de la IPS.</p>
        <p>3. El uso indebido del sistema puede resultar en la suspensión del acceso.</p>
        <p>4. Health & Life IPS no se hace responsable por decisiones tomadas basadas exclusivamente en la salida del modelo de IA sin supervisión clínica.</p>
      </div>
      <button onclick="cerrarSoporte()" class="mt-8 w-full py-3 rounded-xl font-label" style="background: var(--color-primary); color: var(--color-on-primary);">Cerrar</button>`;
  } else {
    content.innerHTML = `
      <div class="flex items-center gap-3 mb-8">
        <span class="material-symbols-outlined text-3xl" style="color: var(--color-primary);">support_agent</span>
        <h3 class="font-headline" style="color: var(--color-primary);">Centro de Soporte</h3>
      </div>
      <div class="space-y-4 text-sm">
        <div style="background: var(--color-surface-container); border-radius: 12px; padding: 16px;">
          <p class="font-semibold flex items-center gap-2" style="color: var(--color-on-surface);"><span class="material-symbols-outlined" style="color: var(--color-primary);">mail</span> Correo</p>
          <p class="mt-1" style="color: var(--color-on-surface-variant);">soporte@hlsite.com.co</p>
        </div>
        <div style="background: var(--color-surface-container); border-radius: 12px; padding: 16px;">
          <p class="font-semibold flex items-center gap-2" style="color: var(--color-on-surface);"><span class="material-symbols-outlined" style="color: var(--color-primary);">call</span> Teléfono</p>
          <p class="mt-1" style="color: var(--color-on-surface-variant);">+57 (1) 234 5678</p>
        </div>
        <div style="background: var(--color-surface-container); border-radius: 12px; padding: 16px;">
          <p class="font-semibold flex items-center gap-2" style="color: var(--color-on-surface);"><span class="material-symbols-outlined" style="color: var(--color-primary);">schedule</span> Horarios</p>
          <p class="mt-1" style="color: var(--color-on-surface-variant);">Lun–Vie 7:00 AM – 6:00 PM · Sáb 8:00 AM – 1:00 PM</p>
        </div>
        <div style="background: var(--color-surface-container); border-radius: 12px; padding: 16px;">
          <p class="font-semibold flex items-center gap-2" style="color: var(--color-on-surface);"><span class="material-symbols-outlined" style="color: var(--color-primary);">location_on</span> Dirección</p>
          <p class="mt-1" style="color: var(--color-on-surface-variant);">Bogotá D.C., Colombia</p>
        </div>
      </div>
      <button onclick="cerrarSoporte()" class="mt-8 w-full py-3 rounded-xl font-label" style="background: var(--color-primary); color: var(--color-on-primary);">Cerrar</button>`;
  }
}

function cerrarSoporte() {
  const overlay = document.getElementById("soporteOverlay");
  if (overlay) overlay.classList.add("hidden");
}

// ── Loading Overlay ───────────────────────────────────────────────
function showLoading(v) {
  const loading = document.getElementById("loading");
  loading.classList.toggle("hidden", !v);

  if (v) {
    ["screen1", "screen2", "screen3", "screenPf"].forEach(s => {
      const el = document.getElementById(s);
      if (el) el.classList.add("hidden");
    });

    if (!neuralAnim) {
      neuralAnim = new NeuralNetworkAnimation("neuralCanvas");
    } else {
      neuralAnim.resize();
    }
    neuralAnim.start();
  } else {
    if (neuralAnim) neuralAnim.stop();
  }
}

// ── Navigation ─────────────────────────────────────────────────────
function setNavActive(navId) {
  const navButtons = ['navValidacion', 'navImportacionMasiva', 'navSoporte'];
  navButtons.forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      if (id === navId) {
        btn.style.background = 'var(--color-primary-container)';
        btn.style.color = 'var(--color-primary)';
        btn.style.borderLeft = '3px solid var(--color-primary)';
        btn.querySelector('.material-symbols-outlined').style.color = 'var(--color-primary)';
      } else {
        btn.style.background = 'transparent';
        btn.style.color = 'var(--color-on-surface-variant)';
        btn.style.borderLeft = 'none';
        btn.querySelector('.material-symbols-outlined').style.color = '';
      }
    }
  });
}

function mostrarScreen1() {
  setNavActive('navValidacion');
  ["screen3", "screen2", "screenPf"].forEach(s => document.getElementById(s).classList.add("hidden"));
  const s1 = document.getElementById("screen1");
  s1.classList.remove("hidden");
  s1.classList.remove("fade-in");
  s1.classList.add("slide-in");
  setTimeout(() => s1.classList.remove("slide-in"), 600);
  document.getElementById("adresResult").classList.add("hidden");
  document.getElementById("localResult").classList.add("hidden");
  document.getElementById("continuarBtn").classList.add("hidden");

  const form = document.getElementById("registrationForm");
  if (form) form.reset();
  const fileInput = document.getElementById("fileUpload");
  if (fileInput) fileInput.value = "";
  const fileLabel = document.getElementById("fileLabel");
  const fileHint = document.getElementById("fileHint");
  const dropzone = document.getElementById("fileUploadContainer");
  if (fileLabel) {
    fileLabel.textContent = modeloSeleccionado === "nemotron_externo" ? "Subir archivo PDF o CSV de prefactura" : "Subir archivo CSV de prefactura";
    fileLabel.style.color = "";
  }
  if (fileHint) fileHint.textContent = "O arrastre y suelte aquí";
  dropzone?.classList.remove('drag-active');
  pacienteActual = null;
  atencionesActuales = [];
  ultimoResultadoPF = null;
  checkFormValidity();
}

function pantallaCarga(show) {
  showLoading(show);
}

// ── Importación Masiva ───────────────────────────────────────────────
let loteArchivoSeleccionado = null;
let loteResultadosGuardados = null;

function mostrarImportacionMasiva() {
  setNavActive('navImportacionMasiva');
  syncModelSelectors();
  ["screen1", "screen2", "screen3", "screenPf"].forEach(s => document.getElementById(s).classList.add("hidden"));
  const sLote = document.getElementById("screenImportacionMasiva");
  sLote.classList.remove("hidden");
  sLote.classList.remove("fade-in");
  sLote.classList.add("slide-in");
  setTimeout(() => sLote.classList.remove("slide-in"), 600);

  // Reset form
  document.getElementById("loteFileUpload").value = "";
  document.getElementById("loteFileLabel").textContent = "Arrastre su archivo CSV aquí";
  document.getElementById("loteFileHint").textContent = "o haga clic para seleccionar";
  document.getElementById("loteSubmitBtn").disabled = true;
  document.getElementById("loteProgress").classList.add("hidden");
  document.getElementById("loteResults").classList.add("hidden");
  loteArchivoSeleccionado = null;
  loteResultadosGuardados = null;

  // Setup file input handler
  const loteFileInput = document.getElementById("loteFileUpload");
  loteFileInput.addEventListener("change", handleLoteFileSelect);
}

function handleLoteFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;

  if (!file.name.toLowerCase().endsWith(".csv")) {
    showToast("Por favor seleccione un archivo CSV", "error");
    e.target.value = "";
    return;
  }

  loteArchivoSeleccionado = file;
  document.getElementById("loteFileLabel").textContent = file.name;
  document.getElementById("loteFileHint").textContent = `${(file.size / 1024).toFixed(1)} KB`;
  document.getElementById("loteSubmitBtn").disabled = false;
}

async function procesarLote() {
  if (!loteArchivoSeleccionado) {
    showToast("Seleccione un archivo CSV primero", "error");
    return;
  }

  const modelo = document.getElementById("loteModelo").value;
  const chunkSize = parseInt(document.getElementById("loteChunkSize").value);

  // Show progress
  document.getElementById("loteProgress").classList.remove("hidden");
  document.getElementById("loteResults").classList.add("hidden");
  document.getElementById("loteSubmitBtn").disabled = true;

  const progressBar = document.getElementById("loteProgressBar");
  const progressText = document.getElementById("loteProgressText");
  const statusText = document.getElementById("loteStatusText");

  statusText.textContent = "Subiendo archivo...";

  try {
    const formData = new FormData();
    formData.append("file", loteArchivoSeleccionado);
    formData.append("modelo_selector", modelo);
    formData.append("chunk_size", chunkSize);

    const response = await fetch(`${API}/prefactura/analizar-lote`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Error ${response.status}: ${errText}`);
    }

    const data = await response.json();

    // Update progress to 100%
    progressBar.style.width = "100%";
    progressText.textContent = "100%";
    statusText.textContent = "Procesamiento completado";

    // Store results
    loteResultadosGuardados = data;

    // Show results after a short delay
    setTimeout(() => {
      mostrarResultadosLote(data);
    }, 500);

  } catch (error) {
    console.error("Error procesando lote:", error);
    showToast("Error al procesar el lote: " + error.message, "error");
    statusText.textContent = "Error en el procesamiento";
    progressBar.style.width = "0%";
    document.getElementById("loteSubmitBtn").disabled = false;
  }
}

function mostrarResultadosLote(data) {
  document.getElementById("loteProgress").classList.add("hidden");
  document.getElementById("loteResults").classList.remove("hidden");
  document.getElementById("loteSubmitBtn").disabled = false;

  const resumen = data.resumen_global || {};
  const resultados = data.resultados_por_prefactura || [];

  // Update summary cards
  document.getElementById("loteTotalRegistros").textContent = resumen.total_registros || 0;
  document.getElementById("loteAprobados").textContent = resumen.aprobados || 0;
  document.getElementById("loteRechazados").textContent = resumen.rechazados || 0;
  document.getElementById("loteRevision").textContent = resumen.revision || 0;
  document.getElementById("loteValorTotal").textContent = `$${(resumen.valor_total || 0).toLocaleString()}`;
  document.getElementById("loteValorRechazado").textContent = `$${(resumen.valor_rechazado || 0).toLocaleString()}`;

  // Update results table
  const tbody = document.getElementById("loteResultsBody");
  tbody.innerHTML = resultados.map(r => {
    const badgeClass = r.recomendacion === "APROBAR" ? "badge-success" : r.recomendacion === "RECHAZAR" ? "badge-error" : "badge-warning";
    const badgeIcon = r.recomendacion === "APROBAR" ? "check_circle" : r.recomendacion === "RECHAZAR" ? "cancel" : "error_outline";
    return `
      <tr style="border-bottom: 1px solid var(--color-outline-variant);">
        <td class="py-2 px-3 font-semibold" style="color: var(--color-on-surface);">${r.id_prefactura || "—"}</td>
        <td class="py-2 px-3" style="color: var(--color-on-surface-variant);">${r.id_paciente || "—"}</td>
        <td class="py-2 px-3 text-center" style="color: var(--color-on-surface);">${r.total_items || 0}</td>
        <td class="py-2 px-3 text-center" style="color: var(--color-error);">${r.inconsistentes || 0}</td>
        <td class="py-2 px-3 text-center">
          <span class="badge ${badgeClass} text-[10px]">
            <span class="material-symbols-outlined text-[10px]">${badgeIcon}</span>
            ${r.recomendacion || "REVISAR"}
          </span>
        </td>
        <td class="py-2 px-3 text-right font-semibold" style="color: var(--color-on-surface);">$${(r.valor_total || 0).toLocaleString()}</td>
      </tr>
    `;
  }).join("");

  showToast("Lote procesado exitosamente", "success");
}

function descargarResultadosLote() {
  if (!loteResultadosGuardados) {
    showToast("No hay resultados para descargar", "error");
    return;
  }

  const resultados = loteResultadosGuardados.resultados_por_prefactura || [];
  const filename = loteResultadosGuardados.archivo_exportacion || "resultados_lote.csv";

  // Create CSV content
  const headers = ["ID Prefactura", "Paciente", "Recomendación", "Total Items", "Inconsistentes", "Valor Total"];
  const rows = resultados.map(r => [
    r.id_prefactura || "",
    r.id_paciente || "",
    r.recomendacion || "",
    r.total_items || 0,
    r.inconsistentes || 0,
    r.valor_total || 0,
  ]);

  const csvContent = [headers, ...rows].map(row => row.join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  showToast("Archivo descargado", "success");
}