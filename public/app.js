const STORAGE_KEY = "signal-desk-history-v1";
const ACCESS_KEY = "signal-desk-access-v1";
const MAX_HISTORY = 12;

const messagesNode = document.querySelector("#messages");
const welcomeNode = document.querySelector("#welcome");
const form = document.querySelector("#composer");
const question = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat");
const accessPanel = document.querySelector("#access-panel");
const accessInput = document.querySelector("#access-code");
const saveAccessButton = document.querySelector("#save-access");

let history = readHistory();
let pendingMessage = "";

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
  contentNode.append(label, body);

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

function setBusy(busy) {
  sendButton.disabled = busy;
  question.disabled = busy;
  sendButton.querySelector("span").textContent = busy ? "Checking sources" : "Run analysis";
}

async function submitMessage(rawMessage, displayUser = true) {
  const message = rawMessage.trim();
  if (!message || sendButton.disabled) return;

  const context = history.slice(-MAX_HISTORY);
  pendingMessage = message;
  if (displayUser) addMessage("user", message);
  question.value = "";
  resizeComposer();
  addThinking();
  setBusy(true);

  try {
    const headers = { "Content-Type": "application/json" };
    const accessCode = sessionStorage.getItem(ACCESS_KEY) || "";
    if (accessCode) headers["X-Demo-Access-Code"] = accessCode;

    const response = await fetch("/api/chat", {
      method: "POST",
      headers,
      body: JSON.stringify({ message, history: context }),
    });
    const payload = await response.json().catch(() => ({}));

    if (response.status === 401) {
      removeThinking();
      accessPanel.classList.remove("hidden");
      accessInput.focus();
      return;
    }
    if (!response.ok) {
      throw new Error(payload.detail || "The analysis request failed. Try again.");
    }

    removeThinking();
    addMessage("agent", payload.answer, payload);
    history.push(
      { role: "user", content: message },
      { role: "assistant", content: payload.answer },
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
  button.addEventListener("click", () => submitMessage(button.dataset.prompt || ""));
});

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
});

accessInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") saveAccessButton.click();
});

history.forEach((item) => addMessage(item.role === "user" ? "user" : "agent", item.content));
question.focus();
