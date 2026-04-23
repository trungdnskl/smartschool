/**
 * Classroom Engagement Analysis System
 * Frontend Application - Vietnamese Dashboard
 * WebSocket + REST API + Canvas Gauge + Timeline Charts
 */

// ===== Configuration =====
const API_BASE = window.location.origin;
const WS_URL = `ws://${window.location.host}/ws`;

// ===== State =====
let ws = null;
let sessionActive = false;
let sessionId = null;
let sessionStartTime = null;
let timerInterval = null;
let engagementTimeline = [];
let currentView = 'dashboard';

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  loadInitialData();
  drawGauge(0);
  drawTimeline();
});

// ===== WebSocket =====
function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('[WS] Connected');
    updateConnectionStatus(true);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleWSMessage(msg);
    } catch (e) {
      console.error('[WS] Parse error:', e);
    }
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected');
    updateConnectionStatus(false);
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    updateConnectionStatus(false);
  };

  // Ping every 25 seconds
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 25000);
}

function handleWSMessage(msg) {
  switch (msg.type) {
    case 'engagement_update':
      updateDashboard(msg.data);
      break;
    case 'alert':
      addAlert(msg.data);
      showToast(msg.data.message, msg.data.severity || 'warning');
      break;
    case 'session_status':
      handleSessionStatus(msg.data);
      break;
    case 'attendance':
      updateAttendanceView();
      break;
    case 'init':
    case 'heartbeat':
      if (msg.data.session_active) {
        sessionActive = true;
        updateSessionUI(true);
      }
      break;
  }
}

// ===== Connection Status =====
function updateConnectionStatus(online) {
  const el = document.getElementById('connectionStatus');
  if (online) {
    el.innerHTML = '<span class="status-dot online"></span><span>Trực tuyến</span>';
  } else {
    el.innerHTML = '<span class="status-dot offline"></span><span>Mất kết nối</span>';
  }
}

// ===== Session Control =====
async function toggleSession() {
  if (sessionActive) {
    await stopSession();
  } else {
    await startSession();
  }
}

async function startSession() {
  const subject = document.getElementById('inputSubject').value || 'Toán học';
  const teacher = document.getElementById('inputTeacher').value || '';

  try {
    const resp = await fetch(`${API_BASE}/api/sessions/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_name: `Buổi học ${new Date().toLocaleDateString('vi-VN')}`,
        subject: subject,
        teacher_name: teacher,
        class_name: '',
      }),
    });

    const data = await resp.json();
    if (resp.ok) {
      sessionActive = true;
      sessionId = data.session_id;
      sessionStartTime = new Date();
      engagementTimeline = [];
      updateSessionUI(true);
      startTimer();
      showToast('🎓 Buổi học đã bắt đầu!', 'success');
    } else {
      showToast(data.detail || 'Lỗi khi bắt đầu buổi học', 'error');
    }
  } catch (e) {
    showToast('Không thể kết nối server', 'error');
  }
}

async function stopSession() {
  try {
    const resp = await fetch(`${API_BASE}/api/sessions/stop`, { method: 'POST' });
    const data = await resp.json();

    if (resp.ok) {
      sessionActive = false;
      sessionId = null;
      stopTimer();
      updateSessionUI(false);
      showToast('✅ Buổi học đã kết thúc!', 'success');

      // Load summary
      if (data.summary) {
        showSessionSummary(data.summary);
      }
    }
  } catch (e) {
    showToast('Lỗi khi kết thúc buổi học', 'error');
  }
}

function updateSessionUI(active) {
  const btn = document.getElementById('btnSessionToggle');
  const timer = document.getElementById('sessionTimer');
  const status = document.getElementById('sessionStatus');
  const liveBadge = document.getElementById('liveBadge');

  if (active) {
    btn.innerHTML = '<span class="btn-icon">⬛</span> Kết thúc buổi học';
    btn.classList.add('active');
    timer.style.display = 'flex';
    status.textContent = 'Đang giám sát...';
    liveBadge.style.display = 'inline';
  } else {
    btn.innerHTML = '<span class="btn-icon">▶</span> Bắt đầu buổi học';
    btn.classList.remove('active');
    timer.style.display = 'none';
    status.textContent = 'Chưa bắt đầu buổi học';
    liveBadge.style.display = 'none';
  }
}

function handleSessionStatus(data) {
  if (data.status === 'started') {
    sessionActive = true;
    sessionId = data.session_id;
    sessionStartTime = new Date();
    updateSessionUI(true);
    startTimer();
  } else if (data.status === 'stopped') {
    sessionActive = false;
    stopTimer();
    updateSessionUI(false);
  }
}

// ===== Timer =====
function startTimer() {
  sessionStartTime = sessionStartTime || new Date();
  timerInterval = setInterval(updateTimer, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  document.getElementById('timerValue').textContent = '00:00:00';
}

function updateTimer() {
  if (!sessionStartTime) return;
  const elapsed = Math.floor((new Date() - sessionStartTime) / 1000);
  const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
  const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
  const s = String(elapsed % 60).padStart(2, '0');
  document.getElementById('timerValue').textContent = `${h}:${m}:${s}`;
}

// ===== Dashboard Update =====
function updateDashboard(data) {
  // Update stats
  const engagement = Math.round(data.avg_engagement || 0);
  document.getElementById('statEngagement').textContent = engagement;
  document.getElementById('statFaces').textContent = data.total_faces || 0;

  // Update gauge
  drawGauge(engagement);
  document.getElementById('gaugeValue').textContent = `${engagement}%`;
  document.getElementById('gaugeLabel').textContent = getEngagementLabel(engagement);

  // Update emotion distribution
  const emotions = data.emotion_distribution || {};
  const total = Object.values(emotions).reduce((a, b) => a + b, 0) || 1;

  ['happy', 'neutral', 'surprise', 'sad', 'angry', 'fear'].forEach(em => {
    const count = emotions[em] || 0;
    const pct = (count / total * 100).toFixed(0);
    const bar = document.getElementById(`bar-${em}`);
    const countEl = document.getElementById(`count-${em}`);
    if (bar) bar.style.width = `${pct}%`;
    if (countEl) countEl.textContent = count;
  });

  // Update learning states
  const states = data.learning_state_distribution || {};
  ['engaged', 'neutral', 'confused', 'bored', 'frustrated'].forEach(s => {
    const el = document.getElementById(`ls-${s}`);
    if (el) el.textContent = states[s] || 0;
  });

  // Update attention
  const attention = data.attention_distribution || {};
  document.getElementById('att-teacher').textContent = attention.looking_at_teacher || 0;
  document.getElementById('att-away').textContent = attention.looking_away || 0;
  document.getElementById('att-down').textContent = attention.looking_down || 0;
  document.getElementById('att-sleep').textContent = attention.head_down || 0;

  // Update timeline
  engagementTimeline.push({
    time: data.timestamp || new Date().toISOString(),
    value: engagement,
    faces: data.total_faces || 0,
  });
  if (engagementTimeline.length > 150) engagementTimeline.shift();
  drawTimeline();

  // Update student emotion list
  updateStudentEmotions(data.students || []);

  // Update present count
  const presentCount = (data.students || []).length;
  document.getElementById('statPresent').textContent = presentCount;
}

function getEngagementLabel(score) {
  if (score >= 80) return 'Xuất sắc 🎉';
  if (score >= 60) return 'Tốt 👍';
  if (score >= 40) return 'Trung bình ⚠️';
  if (score >= 20) return 'Thấp 😟';
  if (score > 0) return 'Rất thấp 🚨';
  return 'Chưa hoạt động';
}

// ===== Gauge Drawing =====
function drawGauge(value) {
  const canvas = document.getElementById('gaugeCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h - 10;
  const radius = Math.min(w, h) - 30;

  ctx.clearRect(0, 0, w, h);

  // Background arc
  ctx.beginPath();
  ctx.arc(cx, cy, radius, Math.PI, 2 * Math.PI);
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 20;
  ctx.lineCap = 'round';
  ctx.stroke();

  // Value arc
  const angle = Math.PI + (value / 100) * Math.PI;
  const gradient = ctx.createLinearGradient(0, h, w, 0);

  if (value >= 70) {
    gradient.addColorStop(0, '#10b981');
    gradient.addColorStop(1, '#34d399');
  } else if (value >= 40) {
    gradient.addColorStop(0, '#f59e0b');
    gradient.addColorStop(1, '#fbbf24');
  } else {
    gradient.addColorStop(0, '#ef4444');
    gradient.addColorStop(1, '#f87171');
  }

  ctx.beginPath();
  ctx.arc(cx, cy, radius, Math.PI, angle);
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 20;
  ctx.lineCap = 'round';
  ctx.stroke();

  // Glow effect
  ctx.beginPath();
  ctx.arc(cx, cy, radius, Math.PI, angle);
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 20;
  ctx.lineCap = 'round';
  ctx.shadowColor = value >= 70 ? '#10b981' : value >= 40 ? '#f59e0b' : '#ef4444';
  ctx.shadowBlur = 15;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Scale labels
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.font = '11px Inter';
  ctx.textAlign = 'center';
  ctx.fillText('0', cx - radius - 5, cy + 20);
  ctx.fillText('50', cx, cy - radius - 8);
  ctx.fillText('100', cx + radius + 5, cy + 20);
}

// ===== Timeline Drawing =====
function drawTimeline() {
  const canvas = document.getElementById('timelineCanvas');
  if (!canvas) return;

  // Resize canvas to container
  const container = canvas.parentElement;
  canvas.width = container.clientWidth - 24;
  canvas.height = 200;

  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const padding = { top: 20, right: 20, bottom: 30, left: 40 };

  ctx.clearRect(0, 0, w, h);

  if (engagementTimeline.length < 2) {
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    ctx.font = '13px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Đang chờ dữ liệu...', w / 2, h / 2);
    return;
  }

  const chartW = w - padding.left - padding.right;
  const chartH = h - padding.top - padding.bottom;
  const data = engagementTimeline;
  const step = chartW / (data.length - 1);

  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + chartH * (1 - i / 4);
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(w - padding.right, y);
    ctx.stroke();

    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'right';
    ctx.fillText(`${i * 25}%`, padding.left - 6, y + 4);
  }

  // Gradient fill
  const grad = ctx.createLinearGradient(0, padding.top, 0, h - padding.bottom);
  grad.addColorStop(0, 'rgba(0, 212, 255, 0.25)');
  grad.addColorStop(1, 'rgba(0, 212, 255, 0)');

  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top + chartH);

  data.forEach((d, i) => {
    const x = padding.left + i * step;
    const y = padding.top + chartH * (1 - d.value / 100);
    if (i === 0) ctx.lineTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.lineTo(padding.left + (data.length - 1) * step, padding.top + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  data.forEach((d, i) => {
    const x = padding.left + i * step;
    const y = padding.top + chartH * (1 - d.value / 100);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = '#00d4ff';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Alert threshold line
  const thresholdY = padding.top + chartH * (1 - 40 / 100);
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(padding.left, thresholdY);
  ctx.lineTo(w - padding.right, thresholdY);
  ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = 'rgba(239, 68, 68, 0.5)';
  ctx.font = '9px Inter';
  ctx.textAlign = 'left';
  ctx.fillText('Ngưỡng cảnh báo', w - padding.right - 80, thresholdY - 4);

  // Latest point dot
  if (data.length > 0) {
    const last = data[data.length - 1];
    const lx = padding.left + (data.length - 1) * step;
    const ly = padding.top + chartH * (1 - last.value / 100);

    ctx.beginPath();
    ctx.arc(lx, ly, 5, 0, 2 * Math.PI);
    ctx.fillStyle = '#00d4ff';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(lx, ly, 8, 0, 2 * Math.PI);
    ctx.strokeStyle = 'rgba(0, 212, 255, 0.4)';
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

// ===== Alerts =====
let alerts = [];

function addAlert(alert) {
  alerts.unshift(alert);
  if (alerts.length > 20) alerts.pop();

  const count = alerts.length;
  document.getElementById('statAlerts').textContent = count;

  renderAlerts();
}

function renderAlerts() {
  const container = document.getElementById('alertsList');
  if (alerts.length === 0) {
    container.innerHTML = '<div class="alert-empty">Chưa có cảnh báo</div>';
    return;
  }

  container.innerHTML = alerts.slice(0, 10).map(a => {
    const time = a.timestamp ? a.timestamp.split(' ')[1] || a.timestamp.split('T')[1]?.substring(0, 8) || '' : '';
    const cls = a.severity === 'critical' ? 'critical' : a.severity === 'info' ? 'info' : '';
    return `
      <div class="alert-item ${cls}">
        <span class="alert-time">${time}</span>
        <span class="alert-message">${a.message}</span>
      </div>
    `;
  }).join('');
}

// ===== Student Emotions =====
function updateStudentEmotions(students) {
  const container = document.getElementById('studentEmotionList');
  if (!students || students.length === 0) {
    container.innerHTML = '<div class="table-empty">Đang chờ dữ liệu...</div>';
    return;
  }

  const emojis = {
    happy: '😊', sad: '😢', angry: '😠', surprise: '😲',
    fear: '😨', disgust: '😖', neutral: '😐',
  };

  container.innerHTML = students.map((s, i) => `
    <div class="student-emotion-item">
      <span class="student-emotion-emoji">${emojis[s.emotion] || '😐'}</span>
      <div class="student-emotion-info">
        <div class="student-emotion-name">${s.student_name || `Học sinh #${s.face_id}`}</div>
        <div class="student-emotion-state">${s.learning_state_vi || s.learning_state} · ${s.attention_direction_vi || ''}</div>
      </div>
      <span class="student-emotion-score">${Math.round(s.engagement_score || 0)}%</span>
    </div>
  `).join('');
}

// ===== Emotion Pie Chart =====
function drawEmotionPie(distribution) {
  const canvas = document.getElementById('emotionPieCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const radius = Math.min(w, h) / 2 - 40;

  ctx.clearRect(0, 0, w, h);

  const colors = {
    happy: '#10b981', neutral: '#6b7280', surprise: '#7c3aed',
    sad: '#3b82f6', angry: '#ef4444', fear: '#f59e0b', disgust: '#8b5cf6',
  };

  const entries = Object.entries(distribution);
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
  let startAngle = -Math.PI / 2;

  entries.forEach(([emotion, count]) => {
    const sliceAngle = (count / total) * 2 * Math.PI;

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, startAngle, startAngle + sliceAngle);
    ctx.closePath();
    ctx.fillStyle = colors[emotion] || '#666';
    ctx.fill();

    // Label
    if (count > 0) {
      const midAngle = startAngle + sliceAngle / 2;
      const lx = cx + (radius * 0.65) * Math.cos(midAngle);
      const ly = cy + (radius * 0.65) * Math.sin(midAngle);

      ctx.fillStyle = '#fff';
      ctx.font = '12px Inter';
      ctx.textAlign = 'center';
      ctx.fillText(`${Math.round(count / total * 100)}%`, lx, ly);
    }

    startAngle += sliceAngle;
  });

  // Center hole (donut)
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.5, 0, 2 * Math.PI);
  ctx.fillStyle = '#141b2d';
  ctx.fill();
}

// ===== View Switching =====
function switchView(viewName) {
  currentView = viewName;

  // Update sidebar
  document.querySelectorAll('.sidebar-icon').forEach(btn => btn.classList.remove('active'));
  const navBtn = document.getElementById(`nav-${viewName}`);
  if (navBtn) navBtn.classList.add('active');

  // Show view
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const view = document.getElementById(`view-${viewName}`);
  if (view) view.classList.add('active');

  // Load data for specific views
  if (viewName === 'attendance') loadAttendance();
  if (viewName === 'cameras') loadCameras();
  if (viewName === 'students') loadStudents();
  if (viewName === 'analytics') loadAnalyticsSessions();
  if (viewName === 'settings') loadPerformanceStats();
}

// ===== Attendance =====
async function loadAttendance() {
  if (!sessionId && !sessionActive) return;

  try {
    const resp = await fetch(`${API_BASE}/api/attendance/current`);
    const data = await resp.json();

    document.getElementById('attPresent').textContent = data.present || 0;
    document.getElementById('attLate').textContent = data.late || 0;
    document.getElementById('attAbsent').textContent = data.absent || 0;

    const tbody = document.getElementById('attendanceBody');
    const records = data.records || [];

    if (records.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="table-empty">Chưa có dữ liệu điểm danh</td></tr>';
      return;
    }

    tbody.innerHTML = records.map((r, i) => {
      const statusMap = { present: 'Có mặt', late: 'Muộn', absent: 'Vắng' };
      return `
        <tr>
          <td>${i + 1}</td>
          <td>${r.student_id || '-'}</td>
          <td>${r.student_name || `Học sinh #${i + 1}`}</td>
          <td><span class="status-badge ${r.status}">${statusMap[r.status] || r.status}</span></td>
          <td>${r.arrival_time || '-'}</td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.error('Load attendance error:', e);
  }
}

function updateAttendanceView() {
  if (currentView === 'attendance') loadAttendance();
}

// ===== Camera Management =====
let cameraRefreshInterval = null;

async function loadCameras() {
  try {
    const resp = await fetch(`${API_BASE}/api/cameras`);
    const data = await resp.json();
    const cameras = data.cameras || [];

    // Update stats
    const total = cameras.length;
    const online = cameras.filter(c => c.status === 'running').length;
    const errors = cameras.filter(c => c.status === 'error' || c.status === 'disconnected').length;
    const offline = total - online - errors;

    document.getElementById('camStatTotal').textContent = total;
    document.getElementById('camStatOnline').textContent = online;
    document.getElementById('camStatOffline').textContent = offline;
    document.getElementById('camStatError').textContent = errors;

    const grid = document.getElementById('camerasGrid');
    if (cameras.length === 0) {
      grid.innerHTML = `
        <div class="table-empty" style="grid-column:1/-1;">
          <p style="font-size:2rem;margin-bottom:10px;">📷</p>
          <p>Chưa có camera nào được cấu hình</p>
          <p style="font-size:0.78rem;margin-top:8px;color:var(--text-muted);">Nhấn "+ Thêm Camera" để thêm camera mới</p>
        </div>`;
      return;
    }

    grid.innerHTML = cameras.map(cam => renderCameraCard(cam)).join('');

    // Auto-refresh khi có camera đang chạy
    if (online > 0 && currentView === 'cameras') {
      if (!cameraRefreshInterval) {
        cameraRefreshInterval = setInterval(() => {
          if (currentView === 'cameras') loadCameras();
          else { clearInterval(cameraRefreshInterval); cameraRefreshInterval = null; }
        }, 5000);
      }
    }
  } catch (e) {
    console.error('Load cameras error:', e);
  }
}

function detectCameraType(url) {
  if (!url) return { type: 'unknown', label: 'Không rõ', icon: '❓' };
  if (/^\d+$/.test(url)) return { type: 'webcam', label: 'Webcam USB', icon: '🖥️' };
  if (url.startsWith('rtsp://')) return { type: 'rtsp', label: 'Camera IP', icon: '📡' };
  if (url.startsWith('http://') || url.startsWith('https://')) return { type: 'http', label: 'HTTP Stream', icon: '🌐' };
  if (/\.(mp4|avi|mkv|mov|wmv|flv)$/i.test(url)) return { type: 'file', label: 'Video file', icon: '🎞️' };
  return { type: 'file', label: 'File/Khác', icon: '📁' };
}

function getStatusInfo(status) {
  switch (status) {
    case 'running': return { label: 'Đang chạy', cls: 'online', icon: '●' };
    case 'stopped': return { label: 'Đã dừng', cls: 'offline', icon: '●' };
    case 'error': return { label: 'Lỗi kết nối', cls: 'error', icon: '⚠' };
    case 'disconnected': return { label: 'Mất kết nối', cls: 'error', icon: '✕' };
    default: return { label: status, cls: 'offline', icon: '●' };
  }
}

function maskUrl(url) {
  return url.replace(/:([^@:]+)@/, ':***@');
}

function renderCameraCard(cam) {
  const camType = detectCameraType(cam.url);
  const statusInfo = getStatusInfo(cam.status);
  const isRunning = cam.status === 'running';
  const cardClass = isRunning ? 'cam-online' : (cam.status === 'error' || cam.status === 'disconnected') ? 'cam-error' : 'cam-offline';
  const safeName = cam.name.replace(/'/g, "\\'");
  const safeUrl = cam.url.replace(/'/g, "\\'");

  const previewContent = isRunning
    ? `<div style="position:relative;width:100%;height:100%;">
         <img src="${API_BASE}/api/cameras/${cam.id}/snapshot?overlay=true&t=${Date.now()}"
              alt="snapshot" style="width:100%;height:100%;object-fit:cover;"
              onerror="this.style.display='none'">
         <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
                     background:rgba(0,0,0,.4);opacity:0;transition:opacity 0.2s;
                     border-radius:8px 8px 0 0;font-size:13px;color:#fff;font-weight:600;
                     cursor:pointer;"
              onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0"
              onclick="openLiveViewForCamera('${cam.id}', '${safeName}')">
           📺 Click xem Live
         </div>
         <span style="position:absolute;top:6px;right:6px;" class="cam-preview-fps">${cam.fps || 0} FPS</span>
       </div>`
    : `<span class="cam-preview-icon">${camType.icon}</span>
       <span class="cam-preview-type">${camType.label}</span>`;

  return `
    <div class="camera-card ${cardClass}">
      <div class="cam-preview" style="position:relative;">
        ${previewContent}
        <span class="cam-preview-status ${statusInfo.cls}" style="position:absolute;top:6px;left:6px;">
          <span class="status-dot ${statusInfo.cls}"></span>
          ${statusInfo.label}
        </span>
      </div>
      <div class="cam-card-body">
        <div class="cam-card-header">
          <span class="cam-card-name">${cam.name}</span>
          <span class="cam-card-id">${cam.id}</span>
        </div>
        <div class="cam-url-display">
          <code title="${cam.url}">${maskUrl(cam.url)}</code>
          <button class="cam-url-copy" onclick="copyToClipboard('${safeUrl}')" title="Sao chép URL">📋</button>
        </div>
        <div class="cam-card-stats">
          <div class="cam-card-stat">
            <span class="cam-card-stat-value">${cam.fps || 0}</span>
            <span class="cam-card-stat-label">FPS</span>
          </div>
          <div class="cam-card-stat">
            <span class="cam-card-stat-value">${formatFrameCount(cam.frame_count || 0)}</span>
            <span class="cam-card-stat-label">Frames</span>
          </div>
          <div class="cam-card-stat">
            <span class="cam-card-stat-value">${cam.last_frame_time || '--:--'}</span>
            <span class="cam-card-stat-label">Last Frame</span>
          </div>
        </div>
        ${cam.error_message ? `<div class="cam-error-msg">⚠ ${cam.error_message}</div>` : ''}
        <div class="cam-card-actions">
          ${isRunning
            ? `<button class="cam-btn cam-btn-stop" onclick="toggleCamera('${cam.id}', 'running')">⏹ Dừng</button>`
            : `<button class="cam-btn cam-btn-start" onclick="toggleCamera('${cam.id}', 'stopped')">▶ Chạy</button>`
          }
          ${isRunning ? `<button class="cam-btn" style="color:#00d4ff;" onclick="openLiveViewForCamera('${cam.id}', '${safeName}')">📺 Live</button>` : ''}
          <button class="cam-btn" onclick="testCameraById('${cam.id}', '${safeUrl}')" title="Kiểm tra">🔍 Test</button>
          <button class="cam-btn cam-btn-delete" onclick="deleteCamera('${cam.id}', '${cam.name}')">🗑</button>
        </div>
      </div>
    </div>`;
}

function formatFrameCount(count) {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count;
}

async function toggleCamera(camId, currentStatus) {
  const action = currentStatus === 'running' ? 'stop' : 'start';
  try {
    await fetch(`${API_BASE}/api/cameras/${camId}/${action}`, { method: 'POST' });
    showToast(action === 'start' ? `▶ Camera ${camId} đang kết nối...` : `⏹ Camera ${camId} đã dừng`, 'info');
    setTimeout(loadCameras, 1000);
  } catch (e) {
    showToast('Lỗi điều khiển camera', 'error');
  }
}

async function deleteCamera(camId, camName) {
  if (!confirm(`Bạn có chắc muốn xóa camera "${camName}" (${camId})?`)) return;
  try {
    const resp = await fetch(`${API_BASE}/api/cameras/${camId}`, { method: 'DELETE' });
    if (resp.ok) {
      showToast(`🗑 Đã xóa camera ${camName}`, 'success');
      loadCameras();
    } else {
      showToast('Lỗi xóa camera', 'error');
    }
  } catch (e) {
    showToast('Không thể kết nối server', 'error');
  }
}

async function testCameraById(camId, url) {
  showToast(`🔍 Đang kiểm tra ${camId}...`, 'info');
  try {
    const formData = new FormData();
    formData.append('url', url);
    const resp = await fetch(`${API_BASE}/api/cameras/test`, { method: 'POST', body: formData });
    const result = await resp.json();
    if (result.success) {
      showToast(`✅ ${camId}: ${result.message}`, 'success');
    } else {
      showToast(`❌ ${camId}: ${result.message}`, 'error');
    }
  } catch (e) {
    showToast('Lỗi kiểm tra kết nối', 'error');
  }
}

// ===== Add Camera Form =====
function showAddCameraForm() {
  const form = document.getElementById('camAddForm');
  form.style.display = 'block';
  document.getElementById('camNewId').focus();
}

function hideAddCameraForm() {
  document.getElementById('camAddForm').style.display = 'none';
  document.getElementById('camTestResult').textContent = '';
  document.getElementById('camTestResult').className = 'cam-test-result';
}

function onCamTypeChange() {
  const type = document.getElementById('camNewType').value;
  const urlInput = document.getElementById('camNewUrl');
  const templates = document.getElementById('camUrlTemplates');

  templates.style.display = type === 'rtsp' ? 'flex' : 'none';

  switch (type) {
    case 'webcam':
      urlInput.placeholder = 'Nhập số (0 = webcam đầu tiên, 1 = thứ 2...)';
      urlInput.value = '0';
      break;
    case 'file':
      urlInput.placeholder = 'Nhập đường dẫn file video (VD: E:/videos/demo.mp4)';
      urlInput.value = '';
      break;
    case 'http':
      urlInput.placeholder = 'Nhập URL HTTP (VD: http://192.168.1.100:8080/video)';
      urlInput.value = 'http://';
      break;
    default:
      urlInput.placeholder = 'VD: rtsp://admin:pass@192.168.1.100:554/stream1';
      urlInput.value = '';
  }
}

const CAM_TEMPLATES = {
  hikvision: 'rtsp://admin:Admin123@192.168.1.100:554/Streaming/Channels/102',
  dahua: 'rtsp://admin:Admin123@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1',
  kbvision: 'rtsp://admin:Admin123@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1',
  tapo: 'rtsp://admin:Admin123@192.168.1.100:554/stream1',
  ezviz: 'rtsp://admin:Admin123@192.168.1.100:554/h264/ch1/main/av_stream',
  phone: 'http://192.168.1.100:8080/video',
};

function fillCamTemplate(brand) {
  const url = CAM_TEMPLATES[brand] || '';
  document.getElementById('camNewUrl').value = url;

  if (brand === 'phone') {
    document.getElementById('camNewType').value = 'http';
  } else {
    document.getElementById('camNewType').value = 'rtsp';
  }

  showToast(`📋 Đã điền mẫu ${brand.toUpperCase()} — thay IP và mật khẩu`, 'info');
}

async function testCameraConnection() {
  const url = document.getElementById('camNewUrl').value;
  if (!url) { showToast('Vui lòng nhập URL camera', 'error'); return; }

  const resultEl = document.getElementById('camTestResult');
  const btn = document.getElementById('btnTestCam');

  resultEl.textContent = '⏳ Đang kiểm tra...';
  resultEl.className = 'cam-test-result loading';
  btn.disabled = true;

  try {
    const formData = new FormData();
    formData.append('url', url);
    const resp = await fetch(`${API_BASE}/api/cameras/test`, { method: 'POST', body: formData });
    const result = await resp.json();

    if (result.success) {
      resultEl.textContent = `✅ ${result.message}`;
      resultEl.className = 'cam-test-result success';
    } else {
      resultEl.textContent = `❌ ${result.message}`;
      resultEl.className = 'cam-test-result error';
    }
  } catch (e) {
    resultEl.textContent = '❌ Không thể kết nối server';
    resultEl.className = 'cam-test-result error';
  }

  btn.disabled = false;
}

async function submitAddCamera() {
  const id = document.getElementById('camNewId').value.trim();
  const name = document.getElementById('camNewName').value.trim();
  const url = document.getElementById('camNewUrl').value.trim();

  if (!id || !name || !url) {
    showToast('Vui lòng điền đầy đủ thông tin', 'error');
    return;
  }

  try {
    const formData = new FormData();
    formData.append('cam_id', id);
    formData.append('name', name);
    formData.append('url', url);

    const resp = await fetch(`${API_BASE}/api/cameras`, { method: 'POST', body: formData });
    const data = await resp.json();

    if (resp.ok) {
      showToast(`✅ Đã thêm camera "${name}"`, 'success');
      hideAddCameraForm();
      document.getElementById('camNewId').value = '';
      document.getElementById('camNewName').value = '';
      document.getElementById('camNewUrl').value = '';
      loadCameras();
    } else {
      showToast(data.detail || 'Lỗi thêm camera', 'error');
    }
  } catch (e) {
    showToast('Không thể kết nối server', 'error');
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('📋 Đã sao chép URL', 'info');
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('📋 Đã sao chép URL', 'info');
  });
}

function toggleCamHelp() {
  const content = document.getElementById('camHelpContent');
  content.style.display = content.style.display === 'none' ? 'block' : 'none';
}

// ===== LiveView Panel =====
let _liveViewActive = false;
let _liveHudTimer = null;

function toggleLiveView() {
  const panel = document.getElementById('liveViewPanel');
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    _liveViewActive = true;
    document.getElementById('btnLiveView').style.background = 'var(--accent-primary)';
    document.getElementById('btnLiveView').style.color = '#000';
    // Populate camera select
    _populateLiveViewSelect();
  } else {
    closeLiveView();
  }
}

function closeLiveView() {
  const panel = document.getElementById('liveViewPanel');
  panel.style.display = 'none';
  // Stop stream
  const img = document.getElementById('liveViewImg');
  img.src = '';
  document.getElementById('liveHud').style.display = 'none';
  document.getElementById('liveViewPlaceholder').style.display = 'flex';
  _liveViewActive = false;
  const btn = document.getElementById('btnLiveView');
  btn.style.background = '';
  btn.style.color = '';
  if (_liveHudTimer) { clearInterval(_liveHudTimer); _liveHudTimer = null; }
}

function openLiveViewForCamera(camId, camName) {
  const panel = document.getElementById('liveViewPanel');
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    _liveViewActive = true;
    document.getElementById('btnLiveView').style.background = 'var(--accent-primary)';
    document.getElementById('btnLiveView').style.color = '#000';
    _populateLiveViewSelect();
  }
  // Switch to this cam
  document.getElementById('liveViewCamSelect').value = camId;
  switchLiveViewCam();
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function _populateLiveViewSelect() {
  fetch(`${API_BASE}/api/cameras`)
    .then(r => r.json())
    .then(data => {
      const sel = document.getElementById('liveViewCamSelect');
      const running = (data.cameras || []).filter(c => c.status === 'running');
      sel.innerHTML = running.length === 0
        ? '<option value="">-- Không có camera nào đang chạy --</option>'
        : running.map(c => `<option value="${c.id}">${c.name} (${c.id})</option>`).join('');
      if (running.length > 0) switchLiveViewCam();
    })
    .catch(() => {});
}

function switchLiveViewCam() {
  const camId = document.getElementById('liveViewCamSelect').value;
  const overlay = document.getElementById('liveOverlayToggle').checked;
  const img = document.getElementById('liveViewImg');
  const placeholder = document.getElementById('liveViewPlaceholder');
  const hud = document.getElementById('liveHud');

  if (!camId) {
    img.src = '';
    img.style.display = 'none';
    placeholder.style.display = 'flex';
    hud.style.display = 'none';
    return;
  }

  const streamUrl = `${API_BASE}/api/cameras/${camId}/stream?overlay=${overlay}`;
  img.src = streamUrl;
  img.style.display = 'block';
  placeholder.style.display = 'none';
  hud.style.display = 'block';

  // HUD updates
  if (_liveHudTimer) clearInterval(_liveHudTimer);
  _liveHudTimer = setInterval(() => {
    const now = new Date();
    const t = now.toLocaleTimeString('vi-VN');
    document.getElementById('liveHudText').textContent = `● LIVE — ${t}`;
  }, 1000);
}

function onStreamError(imgEl) {
  imgEl.style.display = 'none';
  document.getElementById('liveViewPlaceholder').style.display = 'flex';
  document.getElementById('liveHud').style.display = 'none';
  document.getElementById('liveViewPlaceholder').innerHTML = `
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
    <span style="color:#ef4444;font-size:13px;">Stream lỗi — Camera chưa chạy hoặc chưa có frame</span>
    <button class="btn-sm" onclick="switchLiveViewCam()" style="margin-top:8px;">🔄 Thử lại</button>
  `;
}

function openFullscreen() {
  const img = document.getElementById('liveViewImg');
  if (!img.src) return;
  // Open stream in new tab (most reliable cross-browser fullscreen for MJPEG)
  window.open(img.src, '_blank');
}

// ===== Students =====
async function loadStudents() {
  try {
    const resp = await fetch(`${API_BASE}/api/students`);
    const data = await resp.json();
    const students = data.students || [];

    const tbody = document.getElementById('studentsBody');
    if (students.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="table-empty">Chưa có học sinh nào được đăng ký</td></tr>';
      return;
    }

    tbody.innerHTML = students.map(s => `
      <tr>
        <td>${s.student_id}</td>
        <td>${s.name}</td>
        <td>${s.class_name || '-'}</td>
        <td>${s.has_consent ? '✅' : '❌'}</td>
        <td>${s.enrolled_at || '-'}</td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Load students error:', e);
  }
}

// ===== Enroll =====
function showEnrollModal() {
  document.getElementById('enrollModal').classList.add('active');
}

function closeEnrollModal() {
  document.getElementById('enrollModal').classList.remove('active');
}

async function submitEnroll(e) {
  e.preventDefault();

  const formData = new FormData();
  formData.append('student_id', document.getElementById('enrollId').value);
  formData.append('name', document.getElementById('enrollName').value);
  formData.append('class_name', document.getElementById('enrollClass').value);

  const photo = document.getElementById('enrollPhoto').files[0];
  if (photo) formData.append('photo', photo);

  try {
    const resp = await fetch(`${API_BASE}/api/students/enroll`, {
      method: 'POST',
      body: formData,
    });

    const data = await resp.json();
    if (resp.ok) {
      showToast(`✅ ${data.message}`, 'success');
      closeEnrollModal();
      document.getElementById('enrollForm').reset();
      loadStudents();
    } else {
      showToast(data.detail || 'Lỗi đăng ký', 'error');
    }
  } catch (e) {
    showToast('Không thể kết nối server', 'error');
  }
}

// ===== Analytics =====
async function loadAnalyticsSessions() {
  try {
    const resp = await fetch(`${API_BASE}/api/sessions?limit=20`);
    const data = await resp.json();
    const sessions = data.sessions || [];

    const select = document.getElementById('analyticsSessionSelect');
    select.innerHTML = '<option value="">Chọn buổi học...</option>';
    sessions.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `#${s.id} - ${s.session_name || s.subject || 'Buổi học'} (${s.start_time || ''})`;
      select.appendChild(opt);
    });
  } catch (e) {
    console.error('Load sessions error:', e);
  }
}

async function loadSessionAnalytics() {
  const sid = document.getElementById('analyticsSessionSelect').value;
  if (!sid) return;

  try {
    const [summaryResp, timelineResp] = await Promise.all([
      fetch(`${API_BASE}/api/sessions/${sid}/summary`),
      fetch(`${API_BASE}/api/sessions/${sid}/engagement`),
    ]);

    if (summaryResp.ok) {
      const summary = await summaryResp.json();
      renderAnalyticsSummary(summary);
    }

    if (timelineResp.ok) {
      const tData = await timelineResp.json();
      drawAnalyticsTimeline(tData.timeline || []);
    }
  } catch (e) {
    console.error('Load analytics error:', e);
  }
}

function renderAnalyticsSummary(s) {
  document.getElementById('analyticsSummary').innerHTML = `
    <div class="analytics-stat">
      <div class="analytics-stat-label">Engagement TB</div>
      <div class="analytics-stat-value">${(s.avg_engagement || 0).toFixed(1)}%</div>
    </div>
    <div class="analytics-stat">
      <div class="analytics-stat-label">Đỉnh cao</div>
      <div class="analytics-stat-value" style="color:#10b981;">${(s.peak_engagement || 0).toFixed(1)}%</div>
    </div>
    <div class="analytics-stat">
      <div class="analytics-stat-label">Thấp nhất</div>
      <div class="analytics-stat-value" style="color:#ef4444;">${(s.lowest_engagement || 0).toFixed(1)}%</div>
    </div>
    <div class="analytics-stat">
      <div class="analytics-stat-label">Thời lượng</div>
      <div class="analytics-stat-value">${(s.duration_minutes || 0).toFixed(0)} phút</div>
    </div>
    <div class="analytics-stat">
      <div class="analytics-stat-label">Có mặt</div>
      <div class="analytics-stat-value">${s.present_count || 0}/${s.total_students || 0}</div>
    </div>
    <div class="analytics-stat">
      <div class="analytics-stat-label">Cảnh báo</div>
      <div class="analytics-stat-value">${s.alerts_count || 0}</div>
    </div>
  `;

  // Recommendations
  const recList = document.getElementById('recommendationsList');
  const recs = s.recommendations || [];
  if (recs.length > 0) {
    recList.innerHTML = recs.map(r => `
      <div class="recommendation-item">${r}</div>
    `).join('');
  } else {
    recList.innerHTML = '<div class="table-empty">Chưa có gợi ý</div>';
  }

  // Draw pie chart
  if (s.emotion_distribution) {
    drawEmotionPie(s.emotion_distribution);
  }
}

function drawAnalyticsTimeline(timeline) {
  const canvas = document.getElementById('analyticsTimelineCanvas');
  if (!canvas || !timeline.length) return;

  const container = canvas.parentElement;
  canvas.width = container.clientWidth - 40;
  canvas.height = 250;

  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const pad = { top: 20, right: 20, bottom: 30, left: 45 };
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + chartH * (1 - i / 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();

    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'right';
    ctx.fillText(`${i * 25}%`, pad.left - 6, y + 4);
  }

  const step = chartW / (timeline.length - 1);

  // Fill
  const grad = ctx.createLinearGradient(0, pad.top, 0, h - pad.bottom);
  grad.addColorStop(0, 'rgba(124, 58, 237, 0.3)');
  grad.addColorStop(1, 'rgba(124, 58, 237, 0)');

  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top + chartH);
  timeline.forEach((d, i) => {
    const x = pad.left + i * step;
    const y = pad.top + chartH * (1 - (d.avg_engagement || 0) / 100);
    ctx.lineTo(x, y);
  });
  ctx.lineTo(pad.left + (timeline.length - 1) * step, pad.top + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  timeline.forEach((d, i) => {
    const x = pad.left + i * step;
    const y = pad.top + chartH * (1 - (d.avg_engagement || 0) / 100);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = '#7c3aed';
  ctx.lineWidth = 2;
  ctx.stroke();
}

// ===== Performance Stats =====
async function loadPerformanceStats() {
  try {
    const resp = await fetch(`${API_BASE}/api/stats`);
    const data = await resp.json();

    document.getElementById('perfFrames').textContent = data.total_frames || 0;
    document.getElementById('perfTime').textContent = `${data.avg_process_time_ms || 0}ms`;
    document.getElementById('perfFaces').textContent = data.tracked_faces || 0;
  } catch (e) {
    console.error('Load perf stats error:', e);
  }
}

// ===== Session Summary Modal =====
function showSessionSummary(summary) {
  // Switch to analytics view with the summary
  switchView('analytics');
  renderAnalyticsSummary(summary);

  if (summary.engagement_timeline) {
    drawAnalyticsTimeline(summary.engagement_timeline);
  }
}

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(50px)';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

// ===== Load Initial Data =====
async function loadInitialData() {
  try {
    // Check if there's an active session
    const resp = await fetch(`${API_BASE}/api/sessions/active`);
    const data = await resp.json();

    if (data.active && data.session) {
      sessionActive = true;
      sessionId = data.session.id;
      sessionStartTime = new Date(data.session.start_time);
      updateSessionUI(true);
      startTimer();
    }
  } catch (e) {
    console.log('Server not ready yet');
  }
}
