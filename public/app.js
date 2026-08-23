const STORAGE_KEY = "signal-desk-history-v2";
const ACCESS_KEY = "signal-desk-access-v2";
const ADMIN_ACCESS_KEY = "signal-desk-admin-access-v1";
const TOUR_KEY = "signal-desk-tour-v1";
const MAX_HISTORY = 12;
const adminRouteEnabled = new URLSearchParams(window.location.search).get("admin") === "1";

const messagesNode = document.querySelector("#messages");
const welcomeNode = document.querySelector("#welcome");
const form = document.querySelector("#composer");
const question = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat");
const accessPanel = document.querySelector("#access-panel");
const accessInput = document.querySelector("#access-code");
const saveAccessButton = document.querySelector("#save-access");
const openTourButton = document.querySelector("#open-tour");
const tourDialog = document.querySelector("#tour-dialog");
const closeTourButton = document.querySelector("#close-tour");
const tourNextButton = document.querySelector("#tour-next");
const tourKicker = document.querySelector("#tour-kicker");
const tourTitle = document.querySelector("#tour-title");
const tourCopy = document.querySelector("#tour-copy");
const tourExample = document.querySelector("#tour-example");
const tourProgress = [...document.querySelectorAll(".tour-progress span")];
const chatTab = document.querySelector("#chat-tab");
const adminTab = document.querySelector("#admin-tab");
const adminRole = document.querySelector("#admin-role");
const adminConsole = document.querySelector("#admin-console");
const adminAuthCard = document.querySelector("#admin-auth-card");
const adminTraceContent = document.querySelector("#admin-trace-content");
const adminAccessInput = document.querySelector("#admin-access-code");
const verifyAdminButton = document.querySelector("#verify-admin");
const adminAuthStatus = document.querySelector("#admin-auth-status");
const traceCount = document.querySelector("#trace-count");
const traceRequest = document.querySelector("#trace-request");
const traceDuration = document.querySelector("#trace-duration");
const traceStepsCount = document.querySelector("#trace-steps-count");
const traceToolsCount = document.querySelector("#trace-tools-count");
const safeguardStrip = document.querySelector("#safeguard-strip");
const traceNotice = document.querySelector("#trace-notice");
const traceStepsNode = document.querySelector("#trace-steps");

let history = readHistory();
let pendingMessage = "";
let tourStep = 0;
let adminAuthorized = false;
let activeView = "chat";

const tourSteps = [
  {
    title: "Start with a specific question",
    copy: "Use an example card or type your own question. Name the coins and comparison points you care about.",
    example: "“Compare BTC and ETH using current price and 24-hour change.”",
  },
  {
    title: "Run the analysis",
    copy: "Signal Desk checks current prices, recent news, or both. The question determines which source it opens.",
    example: "Market question → tool choice → live provider data → answer",
  },
  {
    title: "Check the evidence",
    copy: "Read the source and retrieval time under the answer. Price questions also show a chart tied to the same provider response.",
    example: "Look for: Source · Tool · Retrieved time",
  },
];

function readHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.slice(-MAX_HISTORY) : [];
  } catch {
    return [];
  }
}

function saveHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-MAX_HISTORY)));
}

function appendInlineFormatting(node, text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.forEach((part) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      node.append(strong);
    } else {
      node.append(document.createTextNode(part));
    }
  });
}

function tableCells(line) {
  return line.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((cell) => cell.trim());
}

function isTableDivider(line) {
  const cells = tableCells(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderAnswer(node, text) {
  node.replaceChildren();
  const lines = text.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const line = rawLine.trim();
    const nextLine = lines[index + 1]?.trim() || "";
    if (line.startsWith("|") && isTableDivider(nextLine)) {
      const wrapper = document.createElement("div");
      wrapper.className = "answer-table-wrap";
      const table = document.createElement("table");
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      tableCells(line).forEach((value) => {
        const cell = document.createElement("th");
        appendInlineFormatting(cell, value);
        headRow.append(cell);
      });
      head.append(headRow);
      table.append(head);

      const body = document.createElement("tbody");
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        const row = document.createElement("tr");
        tableCells(lines[index]).forEach((value) => {
          const cell = document.createElement("td");
          appendInlineFormatting(cell, value);
          row.append(cell);
        });
        body.append(row);
        index += 1;
      }
      index -= 1;
      table.append(body);
      wrapper.append(table);
      node.append(wrapper);
      continue;
    }
    if (!line) {
      const space = document.createElement("div");
      space.className = "answer-space";
      node.append(space);
      continue;
    }
    const block = document.createElement("div");
    if (line.startsWith("### ")) {
      block.className = "answer-heading";
      appendInlineFormatting(block, line.slice(4));
    } else if (line.startsWith("## ")) {
      block.className = "answer-heading";
      appendInlineFormatting(block, line.slice(3));
    } else if (line.startsWith("- ")) {
      block.className = "answer-list-item";
      appendInlineFormatting(block, line.slice(2));
    } else {
      block.className = "answer-line";
      appendInlineFormatting(block, line);
    }
    node.append(block);
  }
}

function formatUsd(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "Unavailable";
  const digits = number > 0 && number < 1 ? 6 : 2;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: digits,
  }).format(number);
}

function renderPriceChart(chart) {
  if (!chart || chart.kind !== "price_comparison" || !Array.isArray(chart.points)) return null;
  const points = chart.points
    .map((point) => ({ ...point, price_usd: Number(point.price_usd) }))
    .filter((point) => point.symbol && Number.isFinite(point.price_usd) && point.price_usd >= 0)
    .slice(0, 5);
  if (!points.length) return null;

  const section = document.createElement("section");
  section.className = "market-chart";
  const accessibleSummary = points
    .map((point) => `${point.symbol} ${formatUsd(point.price_usd)}`)
    .join(", ");
  section.setAttribute("role", "img");
  section.setAttribute("aria-label", `Current price comparison in US dollars: ${accessibleSummary}`);

  const header = document.createElement("div");
  header.className = "market-chart-header";
  const title = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.textContent = "> PRICE CHART";
  const heading = document.createElement("strong");
  heading.textContent = "CURRENT PRICE // USD";
  title.append(kicker, heading);
  const note = document.createElement("span");
  note.textContent = "CURRENT SNAPSHOT · ONE RETRIEVAL TIME";
  header.append(title, note);

  const plot = document.createElement("div");
  plot.className = "market-chart-plot";
  const maximum = Math.max(...points.map((point) => point.price_usd), 1);
  points.forEach((point, index) => {
    const row = document.createElement("div");
    row.className = "market-chart-row";

    const symbol = document.createElement("strong");
    symbol.className = "market-chart-symbol";
    symbol.textContent = point.symbol;

    const track = document.createElement("div");
    track.className = "market-chart-track";
    const bar = document.createElement("span");
    bar.className = "market-chart-bar";
    bar.style.width = `${(point.price_usd / maximum) * 100}%`;
    bar.style.animationDelay = `${index * 90}ms`;
    track.append(bar);

    const values = document.createElement("div");
    values.className = "market-chart-values";
    const price = document.createElement("strong");
    price.textContent = formatUsd(point.price_usd);
    values.append(price);
    if (Number.isFinite(Number(point.change_24h_pct))) {
      const change = Number(point.change_24h_pct);
      const changeNode = document.createElement("span");
      changeNode.className = change >= 0 ? "positive" : "negative";
      changeNode.textContent = `${change >= 0 ? "+" : ""}${change.toFixed(2)}% 24H`;
      values.append(changeNode);
    }
    row.append(symbol, track, values);
    plot.append(row);
  });

  const footer = document.createElement("div");
  footer.className = "market-chart-footer";
  footer.textContent = `SOURCE: ${chart.source} · RETRIEVED: ${chart.retrieved_at}`;
  section.append(header, plot, footer);
  return section;
}

function addMessage(role, content, metadata = {}) {
  welcomeNode?.remove();
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "YOU" : "AI";

  const contentNode = document.createElement("div");
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "Your question" : "Signal Desk analysis";

  const body = document.createElement("div");
  body.className = "message-body";
  if (role === "agent") renderAnswer(body, content);
  else body.textContent = content;
  contentNode.append(label);
  if (role === "agent") {
    const chart = renderPriceChart(metadata.chart);
    if (chart) contentNode.append(chart);
  }
  contentNode.append(body);

  const evidence = document.createElement("div");
  evidence.className = "evidence-strip";
  const tags = [
    ...(metadata.tools_used || []).map((value) => `Tool: ${value}`),
    ...(metadata.sources || []).map((value) => `Source: ${value}`),
    ...(metadata.retrieved_at || []).map((value) => `Retrieved: ${value}`),
  ];
  tags.forEach((value) => {
    const tag = document.createElement("span");
    tag.className = "evidence-tag";
    tag.textContent = value;
    evidence.append(tag);
  });
  (metadata.citations || []).forEach((citation, index) => {
    const link = document.createElement("a");
    link.className = "citation-link";
    link.href = citation.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = `Article ${index + 1}`;
    link.title = citation.label;
    evidence.append(link);
  });
  if (evidence.children.length) contentNode.append(evidence);

  article.append(avatar, contentNode);
  messagesNode.append(article);
  messagesNode.scrollTop = messagesNode.scrollHeight;
  return article;
}

function addThinking() {
  const article = addMessage("agent", "");
  article.id = "thinking-message";
  const body = article.querySelector(".message-body");
  body.className = "thinking";
  body.innerHTML = "<i></i><span>Choosing sources and checking current evidence...</span>";
}

function removeThinking() {
  document.querySelector("#thinking-message")?.remove();
}

function showError(message) {
  addMessage("agent", message);
}

function showView(view) {
  activeView = view === "admin" ? "admin" : "chat";
  const showAdmin = activeView === "admin";
  messagesNode.hidden = showAdmin;
  form.hidden = showAdmin;
  accessPanel.hidden = showAdmin || adminAuthorized;
  adminConsole.hidden = !showAdmin;
  chatTab.classList.toggle("active", !showAdmin);
  chatTab.setAttribute("aria-pressed", String(!showAdmin));
  adminTab.classList.toggle("active", showAdmin);
  adminTab.setAttribute("aria-pressed", String(showAdmin));
}

function appendJsonBlock(parent, label, value) {
  const wrapper = document.createElement("div");
  wrapper.className = "trace-json";
  const title = document.createElement("span");
  title.textContent = label;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(value, null, 2);
  wrapper.append(title, pre);
  parent.append(wrapper);
}

function renderAdminTrace(payload) {
  if (!Array.isArray(payload.trace)) return;
  traceStepsNode.replaceChildren();
  payload.trace.forEach((step) => {
    const article = document.createElement("article");
    article.className = `trace-step trace-${step.stage}`;
    const header = document.createElement("header");
    const sequence = document.createElement("span");
    sequence.textContent = String(step.sequence).padStart(2, "0");
    const title = document.createElement("strong");
    title.textContent = step.label;
    const stage = document.createElement("small");
    stage.textContent = step.stage;
    header.append(sequence, title, stage);
    article.append(header);
    appendJsonBlock(article, "INPUT", step.input);
    appendJsonBlock(article, "OUTPUT", step.output);
    traceStepsNode.append(article);
  });

  safeguardStrip.replaceChildren();
  (payload.safeguards || []).forEach((value) => {
    const tag = document.createElement("span");
    tag.textContent = value;
    safeguardStrip.append(tag);
  });
  traceRequest.textContent = payload.request_id || "Unknown";
  traceDuration.textContent = `${payload.duration_ms ?? 0} ms`;
  traceStepsCount.textContent = String(payload.trace.length);
  traceToolsCount.textContent = String((payload.tools_used || []).length);
  traceCount.textContent = String(payload.trace.length);
  traceNotice.textContent = payload.trace_notice || "Redacted observable execution metadata.";
}

function setAdminAuthorized(authorized) {
  adminAuthorized = authorized;
  adminAuthCard.hidden = authorized;
  adminTraceContent.hidden = !authorized;
  adminRole.hidden = !authorized;
}

async function verifyAdminRole() {
  const code = adminAccessInput.value.trim() || sessionStorage.getItem(ADMIN_ACCESS_KEY) || "";
  if (!code) {
    adminAuthStatus.textContent = "Enter the separate admin code.";
    return;
  }
  verifyAdminButton.disabled = true;
  adminAuthStatus.textContent = "Verifying role...";
  try {
    const response = await fetch("/api/admin/session", {
      method: "POST",
      headers: { "X-Admin-Access-Code": code },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.role !== "admin") {
      throw new Error(payload.detail || "Admin role verification failed.");
    }
    sessionStorage.setItem(ADMIN_ACCESS_KEY, code);
    adminAccessInput.value = "";
    adminAuthStatus.textContent = "";
    setAdminAuthorized(true);
    showView("chat");
    fillComposer("Compare BTC and ETH using current price and 24-hour change.");
  } catch (error) {
    sessionStorage.removeItem(ADMIN_ACCESS_KEY);
    setAdminAuthorized(false);
    adminAuthStatus.textContent = error instanceof Error ? error.message : "Access denied.";
  } finally {
    verifyAdminButton.disabled = false;
  }
}

function setBusy(busy) {
  sendButton.disabled = busy;
  question.disabled = busy;
  sendButton.querySelector("span").textContent = busy ? "Checking sources" : "Run analysis";
}

async function submitMessage(rawMessage, displayUser = true) {
  const message = rawMessage.trim();
  if (!message || sendButton.disabled) return;

  const context = history.slice(-MAX_HISTORY).map((item) => ({
    role: item.role,
    content: item.content,
  }));
  pendingMessage = message;
  if (displayUser) addMessage("user", message);
  question.value = "";
  resizeComposer();
  addThinking();
  setBusy(true);

  try {
    const headers = { "Content-Type": "application/json" };
    const useAdminTrace = adminRouteEnabled && adminAuthorized;
    if (useAdminTrace) {
      headers["X-Admin-Access-Code"] = sessionStorage.getItem(ADMIN_ACCESS_KEY) || "";
    } else {
      const accessCode = sessionStorage.getItem(ACCESS_KEY) || "";
      if (accessCode) headers["X-Demo-Access-Code"] = accessCode;
    }

    const response = await fetch(useAdminTrace ? "/api/admin/chat" : "/api/chat", {
      method: "POST",
      headers,
      body: JSON.stringify({ message, history: context }),
    });
    const payload = await response.json().catch(() => ({}));

    if (response.status === 401) {
      removeThinking();
      if (useAdminTrace) {
        sessionStorage.removeItem(ADMIN_ACCESS_KEY);
        setAdminAuthorized(false);
        adminAuthStatus.textContent = payload.detail || "Admin access required.";
        showView("admin");
        adminAccessInput.focus();
      } else {
        accessPanel.classList.remove("hidden");
        accessInput.focus();
      }
      return;
    }
    if (!response.ok) {
      throw new Error(payload.detail || "The analysis request failed. Try again.");
    }

    removeThinking();
    addMessage("agent", payload.answer, payload);
    if (useAdminTrace) renderAdminTrace(payload);
    history.push(
      { role: "user", content: message },
      {
        role: "assistant",
        content: payload.answer,
        metadata: {
          tools_used: payload.tools_used,
          sources: payload.sources,
          retrieved_at: payload.retrieved_at,
          citations: payload.citations,
          chart: payload.chart,
        },
      },
    );
    history = history.slice(-MAX_HISTORY);
    saveHistory();
    pendingMessage = "";
  } catch (error) {
    removeThinking();
    showError(error instanceof Error ? error.message : "The request failed. Try again.");
  } finally {
    setBusy(false);
    if (accessPanel.classList.contains("hidden")) question.focus();
  }
}

function resizeComposer() {
  question.style.height = "auto";
  question.style.height = `${Math.min(question.scrollHeight, 150)}px`;
}

function fillComposer(message) {
  question.value = message;
  resizeComposer();
  form.scrollIntoView({ behavior: "smooth", block: "end" });
  form.classList.remove("flash");
  window.requestAnimationFrame(() => form.classList.add("flash"));
  window.setTimeout(() => form.classList.remove("flash"), 900);
  question.focus();
}

function renderTourStep() {
  const step = tourSteps[tourStep];
  tourKicker.textContent = `30-second tour · Step ${tourStep + 1} of ${tourSteps.length}`;
  tourTitle.textContent = step.title;
  tourCopy.textContent = step.copy;
  tourExample.textContent = step.example;
  tourProgress.forEach((item, index) => item.classList.toggle("active", index <= tourStep));
  tourNextButton.textContent = tourStep === tourSteps.length - 1 ? "Try an example" : "Next step";
}

function openTour() {
  tourStep = 0;
  renderTourStep();
  if (!tourDialog.open) tourDialog.showModal();
}

function closeTour() {
  localStorage.setItem(TOUR_KEY, "seen");
  tourDialog.close();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitMessage(question.value);
});

question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

question.addEventListener("input", resizeComposer);

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => fillComposer(button.dataset.prompt || ""));
});

openTourButton.addEventListener("click", openTour);
chatTab.addEventListener("click", () => showView("chat"));
adminTab.addEventListener("click", () => showView("admin"));
verifyAdminButton.addEventListener("click", verifyAdminRole);
adminAccessInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") verifyAdminRole();
});
closeTourButton.addEventListener("click", closeTour);
tourNextButton.addEventListener("click", () => {
  if (tourStep < tourSteps.length - 1) {
    tourStep += 1;
    renderTourStep();
    return;
  }
  closeTour();
  fillComposer("Compare BTC and ETH using current price and 24-hour change.");
});

tourDialog.addEventListener("cancel", () => localStorage.setItem(TOUR_KEY, "seen"));

newChatButton.addEventListener("click", () => {
  history = [];
  localStorage.removeItem(STORAGE_KEY);
  window.location.reload();
});

saveAccessButton.addEventListener("click", () => {
  const code = accessInput.value.trim();
  if (!code) return;
  sessionStorage.setItem(ACCESS_KEY, code);
  accessInput.value = "";
  accessPanel.classList.add("hidden");
  if (pendingMessage) submitMessage(pendingMessage, false);
  else question.focus();
});

accessInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") saveAccessButton.click();
});

history.forEach((item) =>
  addMessage(item.role === "user" ? "user" : "agent", item.content, item.metadata || {}),
);
if (adminRouteEnabled) {
  adminTab.hidden = false;
  const storedAdminCode = sessionStorage.getItem(ADMIN_ACCESS_KEY);
  if (storedAdminCode) {
    verifyAdminRole();
  }
}
if (!sessionStorage.getItem(ACCESS_KEY)) accessPanel.classList.remove("hidden");
if (!localStorage.getItem(TOUR_KEY) && history.length === 0) {
  window.setTimeout(openTour, 350);
} else {
  question.focus();
}
