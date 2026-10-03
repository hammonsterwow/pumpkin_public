const statusPanel = document.getElementById("statusPanel");
const statusTitle = document.getElementById("statusTitle");
const statusDetail = document.getElementById("statusDetail");
const userSubtitle = document.getElementById("userSubtitle");
const robotSubtitle = document.getElementById("robotSubtitle");
const orderGrid = document.getElementById("orderGrid");
const orderHint = document.getElementById("orderHint");

let socket = null;
let reconnectTimer = null;
let state = {};

const ATTENTION_DECISIONS = new Set([
  "ASK_MENU",
  "ASK_TEMPERATURE",
  "ASK_QUANTITY",
  "REPROMPT",
  "REORDER_REQUEST",
  "MODIFY_ORDER",
  "OUT_OF_POLICY",
  "STT_RETRY",
  "STT_FAILED",
]);

const CONFIRM_DECISIONS = new Set([
  "CONFIRM_ITEM",
  "CONFIRM_ORDER",
  "ORDER_CONFIRMED",
]);

function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}

function connect() {
  if (socket && socket.readyState <= WebSocket.OPEN) {
    return;
  }

  socket = new WebSocket(websocketUrl());
  socket.addEventListener("open", () => renderConnection(true));
  socket.addEventListener("message", (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    if (payload.type === "snapshot" && payload.state) {
      state = payload.state;
      render();
    }
  });
  socket.addEventListener("close", () => {
    renderConnection(false);
    scheduleReconnect();
  });
  socket.addEventListener("error", () => socket.close());
}

function scheduleReconnect() {
  if (reconnectTimer) {
    return;
  }
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 1000);
}

function renderConnection(connected) {
  if (connected) {
    return;
  }
  statusPanel.dataset.mode = "idle";
  statusTitle.textContent = "대기 중";
  statusDetail.textContent = "로봇과 연결을 확인하고 있어요.";
}

function render() {
  renderStatus();
  renderSubtitles();
  renderOrder();
}

function resolveStatus() {
  const connected = Boolean(state.connected);
  const present = Boolean(state.presence);
  const stt = String(state.stt_status || "").trim().toLowerCase();
  const tts = String(state.tts_status || "").trim().toLowerCase();
  const decision = String(state.decision || "").trim().toUpperCase();
  const waiting = state.waiting_for && typeof state.waiting_for === "object" ? state.waiting_for : null;

  if (!connected) {
    return ["idle", "대기 중", "로봇과 연결을 확인하고 있어요."];
  }

  // Robot speech always wins over stale STT state. The customer must never be
  // told to speak while TTS is still playing.
  if (tts === "speaking") {
    return ["processing", "로봇이 안내하고 있어요", "안내가 끝나면 말씀해 주세요."];
  }

  if (stt === "transcribing") {
    return ["processing", "음성을 확인하는 중", "방금 말씀하신 내용을 확인하고 있어요."];
  }

  if (stt === "speech_detected" || stt === "recording") {
    return ["listening", "듣는 중", "계속 말씀해 주세요."];
  }

  if (stt === "listening") {
    return ["ready", "지금 말씀해 주세요", promptForDecision(decision, waiting)];
  }

  if (decision === "NEXT_CUSTOMER_READY") {
    return ["complete", "주문 완료", "주문이 접수되었습니다. 감사합니다."];
  }

  if (CONFIRM_DECISIONS.has(decision)) {
    const detail = decision === "ORDER_CONFIRMED"
      ? "추가 주문 여부를 확인하고 있어요."
      : "화면의 주문 내용이 맞는지 확인해 주세요.";
    return ["confirm", "주문 확인 중", detail];
  }

  if (ATTENTION_DECISIONS.has(decision)) {
    return ["attention", "재질문/입력 필요", promptForDecision(decision, waiting)];
  }

  if (!present) {
    return ["idle", "대기 중", "고객을 기다리고 있어요."];
  }

  return ["idle", "대기 중", "잠시만 기다려 주세요."];
}

function promptForDecision(decision, waiting) {
  const slot = String(waiting?.slot || "").toLowerCase();
  if (decision === "ASK_MENU" || slot === "menu") {
    return "원하시는 메뉴를 말씀해 주세요.";
  }
  if (decision === "ASK_TEMPERATURE" || slot === "temperature") {
    return "아이스 또는 따뜻하게 중에서 말씀해 주세요.";
  }
  if (decision === "ASK_QUANTITY" || slot === "quantity") {
    return "몇 잔인지 말씀해 주세요.";
  }
  if (decision === "MODIFY_ORDER") {
    return "바꾸고 싶은 주문 내용을 말씀해 주세요.";
  }
  if (decision === "OUT_OF_POLICY") {
    return "가능한 메뉴나 옵션으로 다시 말씀해 주세요.";
  }
  if (decision === "STT_FAILED" || decision === "STT_RETRY") {
    return "한 번 더 또렷하게 말씀해 주세요.";
  }
  if (decision === "REORDER_REQUEST") {
    return "주문을 처음부터 다시 말씀해 주세요.";
  }
  return "한 번 더 말씀해 주세요.";
}

function renderStatus() {
  const [mode, title, detail] = resolveStatus();
  statusPanel.dataset.mode = mode;
  statusTitle.textContent = title;
  statusDetail.textContent = detail;
}

function renderSubtitles() {
  const userText = String(state.user_text || "").trim();
  const robotText = String(state.robot_text || "").trim();

  userSubtitle.textContent = userText || "말씀하신 내용이 여기에 보여요.";
  userSubtitle.classList.toggle("muted", !userText);

  robotSubtitle.textContent = robotText || "로봇의 안내가 여기에 보여요.";
  robotSubtitle.classList.toggle("muted", !robotText);
}

function renderOrder() {
  const items = Array.isArray(state.items) ? state.items : [];
  orderGrid.replaceChildren();
  orderGrid.className = "order-grid";

  if (!items.length) {
    orderGrid.classList.add("empty");
    orderHint.textContent = "아직 주문 정보가 없어요.";
    const empty = document.createElement("div");
    empty.className = "empty-order";
    empty.textContent = "메뉴를 말씀하시면 인식된 주문이 표시됩니다.";
    orderGrid.append(empty);
    return;
  }

  if (items.length === 1) {
    orderGrid.classList.add("count-1");
  } else if (items.length === 2) {
    orderGrid.classList.add("count-2");
  } else {
    orderGrid.classList.add("count-many");
  }

  const missingCount = items.reduce((sum, item) => {
    return sum + [item.menu, item.temperature, item.quantity].filter((value) => value === null || value === undefined || value === "").length;
  }, 0);
  orderHint.textContent = missingCount > 0 ? "노란 항목을 말씀해 주세요." : "인식된 주문 내용입니다.";

  items.forEach((item, index) => {
    orderGrid.append(buildOrderCard(item, index));
  });
}

function buildOrderCard(item, index) {
  const missing = new Set(Array.isArray(item.missing_slots) ? item.missing_slots : []);
  const values = {
    menu: item.menu || null,
    temperature: formatTemperature(item.temperature),
    quantity: formatQuantity(item.quantity),
  };
  Object.entries(values).forEach(([key, value]) => {
    if (!value) {
      missing.add(key);
    }
  });

  const card = document.createElement("article");
  card.className = "order-card";
  if (missing.size) {
    card.classList.add("needs-input");
  }

  const header = document.createElement("div");
  header.className = "order-card-header";

  const title = document.createElement("h3");
  title.className = "order-card-title";
  title.textContent = `주문 ${index + 1}`;
  header.append(title);

  if (missing.size) {
    const badge = document.createElement("span");
    badge.className = "need-badge";
    badge.textContent = "확인 필요";
    header.append(badge);
  }

  const slots = document.createElement("div");
  slots.className = "slot-list";
  slots.append(
    buildSlot("메뉴", values.menu, missing.has("menu")),
    buildSlot("온도", values.temperature, missing.has("temperature")),
    buildSlot("수량", values.quantity, missing.has("quantity")),
  );

  card.append(header, slots);
  return card;
}

function buildSlot(label, value, isMissing) {
  const slot = document.createElement("div");
  slot.className = "slot";
  if (isMissing || !value) {
    slot.classList.add("missing");
  }

  const labelEl = document.createElement("span");
  labelEl.className = "slot-label";
  labelEl.textContent = label;

  const valueEl = document.createElement("span");
  valueEl.className = "slot-value";
  valueEl.textContent = value || "선택 필요";

  slot.append(labelEl, valueEl);
  return slot;
}

function formatTemperature(value) {
  const normalized = String(value || "").trim().toUpperCase();
  if (normalized === "ICE") {
    return "아이스";
  }
  if (normalized === "HOT") {
    return "따뜻하게";
  }
  return null;
}

function formatQuantity(value) {
  const quantity = Number(value);
  if (!Number.isFinite(quantity) || quantity <= 0) {
    return null;
  }
  return `${quantity}잔`;
}

connect();
