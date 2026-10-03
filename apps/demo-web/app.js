const cameraStream = document.getElementById("cameraStream");
const cameraFallback = document.getElementById("cameraFallback");
const liveBadge = document.getElementById("liveBadge");
const presenceStatus = document.getElementById("presenceStatus");
const gestureStatus = document.getElementById("gestureStatus");
const interactionStatus = document.getElementById("interactionStatus");
const interactionStatusLabel = document.getElementById("interactionStatusLabel");
const interactionStatusText = document.getElementById("interactionStatusText");
const brainHistory = document.getElementById("brainHistory");
const userSubtitle = document.getElementById("userSubtitle");
const robotSubtitle = document.getElementById("robotSubtitle");
const logButton = document.getElementById("logButton");
const closeLogButton = document.getElementById("closeLogButton");
const logPanel = document.getElementById("logPanel");
const logList = document.getElementById("logList");

const GESTURE_VISIBLE_MS = 1800;
const MAX_BROWSER_LOGS = 200;
const MAX_BRAIN_HISTORY = 5;
const BRAIN_EVENT_LIFETIME_MS = 12000;

let socket = null;
let reconnectTimer = null;
let state = {};
let logEntries = [];
let brainEntries = [];
let brainTimers = new Map();
let gestureTimer = null;
let cameraReady = false;

function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}

function setConnected(connected) {
  liveBadge.classList.toggle("connected", connected);
  if (!connected) {
    presenceStatus.textContent = "CONNECTION LOST";
  } else {
    renderVisionState();
  }
}

function connect() {
  if (socket && socket.readyState <= WebSocket.OPEN) {
    return;
  }

  socket = new WebSocket(websocketUrl());
  socket.addEventListener("open", () => {
    setConnected(true);
  });

  socket.addEventListener("message", (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    handleMessage(payload);
  });

  socket.addEventListener("close", () => {
    setConnected(false);
    scheduleReconnect();
  });

  socket.addEventListener("error", () => {
    socket.close();
  });
}

function scheduleReconnect() {
  if (reconnectTimer) {
    return;
  }
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 1200);
}

function handleMessage(payload) {
  if (payload.type === "snapshot") {
    state = payload.state || {};
    renderState();
    const recent = Array.isArray(payload.recent_logs) ? payload.recent_logs : [];
    logEntries = recent.slice(-MAX_BROWSER_LOGS);
    hydrateBrainHistory(recent);
    renderLogs();
    return;
  }

  if (payload.type === "update") {
    if (payload.state) {
      state = { ...state, ...payload.state };
      renderState();
    }
    const events = Array.isArray(payload.events) ? payload.events : [];
    events.forEach(handleEvent);
  }
}

function handleEvent(event) {
  addLog(event);
  if (event.show_in_brain) {
    addBrainEvent(event);
  }
}

function renderState() {
  renderVisionState();
  renderInteractionStatus();
  renderSubtitles();
}

function renderVisionState() {
  const connected = Boolean(state.connected);
  const present = Boolean(state.presence);
  if (!connected) {
    presenceStatus.textContent = "CONNECTION LOST";
  } else if (present) {
    presenceStatus.textContent = "PERSON DETECTED";
  } else {
    presenceStatus.textContent = "WAITING FOR CUSTOMER";
  }

  const gestureAt = Number(state.gesture_at || 0) * 1000;
  const freshGesture = Date.now() - gestureAt <= GESTURE_VISIBLE_MS;
  if (freshGesture && state.gesture) {
    showGesture(String(state.gesture));
  }
}

function showGesture(gesture) {
  const normalized = gesture.toUpperCase();
  if (!["NOD", "SHAKE"].includes(normalized)) {
    return;
  }
  const meaning = normalized === "NOD" ? "YES" : "NO";
  gestureStatus.textContent = `${normalized} → ${meaning}`;
  gestureStatus.classList.add("visible");
  if (gestureTimer) {
    window.clearTimeout(gestureTimer);
  }
  gestureTimer = window.setTimeout(() => {
    gestureStatus.classList.remove("visible");
  }, GESTURE_VISIBLE_MS);
}

function renderInteractionStatus() {
  const stt = String(state.stt_status || "").trim().toLowerCase();
  const tts = String(state.tts_status || "").trim().toLowerCase();

  let label = "";
  let text = "";
  let mode = "";

  if (tts === "speaking") {
    label = "ROBOT SPEAKING";
    text = "로봇이 말하고 있습니다.";
    mode = "speaking";
  } else if (stt === "listening") {
    label = "LISTENING";
    text = "지금 말씀해주세요.";
    mode = "listening";
  } else if (stt === "speech_detected" || stt === "recording") {
    label = "LISTENING";
    text = "말씀을 듣고 있습니다.";
    mode = "listening";
  } else if (stt === "transcribing") {
    label = "SPEECH RECOGNITION";
    text = "음성을 인식하고 있습니다.";
    mode = "processing";
  }

  if (!label) {
    interactionStatus.hidden = true;
    interactionStatus.removeAttribute("data-mode");
    return;
  }

  interactionStatusLabel.textContent = label;
  interactionStatusText.textContent = text;
  interactionStatus.dataset.mode = mode;
  interactionStatus.hidden = false;
}

function renderSubtitles() {
  const userText = String(state.user_text || "").trim();
  const robotText = String(state.robot_text || "").trim();

  userSubtitle.textContent = userText || "고객의 음성 인식을 기다리고 있습니다.";
  userSubtitle.classList.toggle("muted", !userText);

  robotSubtitle.textContent = robotText || "로봇의 응답을 기다리고 있습니다.";
  robotSubtitle.classList.toggle("muted", !robotText);
}

function hydrateBrainHistory(recent) {
  clearBrainTimers();
  const now = Date.now();
  brainEntries = recent
    .filter((entry) => entry && entry.show_in_brain)
    .filter((entry) => now - Number(entry.timestamp || 0) * 1000 < BRAIN_EVENT_LIFETIME_MS)
    .slice(-MAX_BRAIN_HISTORY);

  brainEntries.forEach((entry) => scheduleBrainExpiry(entry));
  renderBrainHistory();
}

function addBrainEvent(event) {
  if (!event) {
    return;
  }

  const seq = Number(event.seq || 0);
  if (seq && brainEntries.some((entry) => Number(entry.seq || 0) === seq)) {
    return;
  }

  brainEntries.push(event);
  if (brainEntries.length > MAX_BRAIN_HISTORY) {
    const removed = brainEntries.splice(0, brainEntries.length - MAX_BRAIN_HISTORY);
    removed.forEach((entry) => clearBrainTimer(entry));
  }

  scheduleBrainExpiry(event);
  renderBrainHistory();
}

function scheduleBrainExpiry(event) {
  const key = brainKey(event);
  clearBrainTimer(event);

  const ageMs = Math.max(0, Date.now() - Number(event.timestamp || 0) * 1000);
  const remainingMs = Math.max(600, BRAIN_EVENT_LIFETIME_MS - ageMs);
  const timer = window.setTimeout(() => {
    brainTimers.delete(key);
    brainEntries = brainEntries.filter((entry) => brainKey(entry) !== key);
    renderBrainHistory();
  }, remainingMs);
  brainTimers.set(key, timer);
}

function brainKey(event) {
  if (event && event.seq !== undefined && event.seq !== null) {
    return `seq:${event.seq}`;
  }
  return `${event?.timestamp || 0}:${event?.title || ""}:${event?.headline || ""}`;
}

function clearBrainTimer(event) {
  const key = brainKey(event);
  const timer = brainTimers.get(key);
  if (timer) {
    window.clearTimeout(timer);
    brainTimers.delete(key);
  }
}

function clearBrainTimers() {
  brainTimers.forEach((timer) => window.clearTimeout(timer));
  brainTimers.clear();
}

function renderBrainHistory() {
  brainHistory.replaceChildren();
  if (!brainEntries.length) {
    return;
  }

  const fragment = document.createDocumentFragment();
  const total = brainEntries.length;

  brainEntries.forEach((entry, index) => {
    const ageFromLatest = total - 1 - index;
    const article = document.createElement("article");
    article.className = "brain-history-entry";
    article.dataset.depth = String(Math.min(ageFromLatest, 3));

    const title = document.createElement("p");
    title.className = "brain-history-title";
    title.textContent = entry.title || "";

    const headline = document.createElement(ageFromLatest === 0 ? "h1" : "h2");
    headline.className = "brain-history-headline";
    headline.textContent = entry.headline || "";

    article.append(title, headline);

    const lines = Array.isArray(entry.lines) ? entry.lines : [];
    if (lines.length) {
      const linesWrap = document.createElement("div");
      linesWrap.className = "brain-history-lines";
      lines.forEach((line) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = line;
        linesWrap.appendChild(paragraph);
      });
      article.appendChild(linesWrap);
    }

    if (entry.detail) {
      const detail = document.createElement("p");
      detail.className = "brain-history-detail";
      detail.textContent = entry.detail;
      article.appendChild(detail);
    }

    fragment.appendChild(article);
  });

  brainHistory.appendChild(fragment);
}

function addLog(event) {
  if (!event || !event.log_label) {
    return;
  }
  logEntries.push(event);
  if (logEntries.length > MAX_BROWSER_LOGS) {
    logEntries = logEntries.slice(-MAX_BROWSER_LOGS);
  }
  if (!logPanel.hidden) {
    renderLogs();
  }
}

function formatTime(timestamp) {
  const date = new Date(Number(timestamp || Date.now() / 1000) * 1000);
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function renderLogs() {
  logList.replaceChildren();
  if (!logEntries.length) {
    const empty = document.createElement("p");
    empty.className = "log-empty";
    empty.textContent = "아직 기록된 이벤트가 없습니다.";
    logList.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  logEntries.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "log-entry";

    const time = document.createElement("span");
    time.className = "log-time";
    time.textContent = formatTime(entry.timestamp);

    const label = document.createElement("span");
    label.className = "log-label";
    label.textContent = entry.log_label || "EVENT";

    const text = document.createElement("span");
    text.className = "log-text";
    text.textContent = entry.log_text || entry.headline || "";

    row.append(time, label, text);
    fragment.appendChild(row);
  });
  logList.appendChild(fragment);
  logList.scrollTop = logList.scrollHeight;
}

function openLogs() {
  logPanel.hidden = false;
  logButton.setAttribute("aria-expanded", "true");
  renderLogs();
}

function closeLogs() {
  logPanel.hidden = true;
  logButton.setAttribute("aria-expanded", "false");
}

cameraStream.addEventListener("load", () => {
  cameraReady = true;
  cameraFallback.classList.add("hidden");
});

cameraStream.addEventListener("error", () => {
  cameraReady = false;
  cameraFallback.classList.remove("hidden");
});

window.setInterval(() => {
  if (!cameraReady) {
    cameraFallback.classList.remove("hidden");
  }
  const gestureAt = Number(state.gesture_at || 0) * 1000;
  if (Date.now() - gestureAt > GESTURE_VISIBLE_MS) {
    gestureStatus.classList.remove("visible");
  }
}, 500);

logButton.addEventListener("click", openLogs);
closeLogButton.addEventListener("click", closeLogs);
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !logPanel.hidden) {
    closeLogs();
  }
});
window.addEventListener("beforeunload", clearBrainTimers);

connect();
