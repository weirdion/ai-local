'use strict';

const API_BASE = 'http://127.0.0.1:11434';
const conversation = [];
let context = null;

const modelSelect = document.getElementById('modelSelect');
const refreshBtn = document.getElementById('refreshModels');
const resetBtn = document.getElementById('resetChat');
const themeToggle = document.getElementById('themeToggle');
const conversationEl = document.getElementById('conversation');
const promptEl = document.getElementById('prompt');
const formEl = document.getElementById('chatForm');
const statusEl = document.getElementById('status');
const submitBtn = formEl.querySelector('button[type="submit"]');
const bodyEl = document.body;

function setTheme(theme) {
  const nextTheme = theme === 'light' ? 'light' : 'dark';
  bodyEl.dataset.theme = nextTheme;
  themeToggle.textContent = nextTheme === 'dark' ? 'Switch to Light' : 'Switch to Dark';
}

function toggleTheme() {
  const current = bodyEl.dataset.theme === 'light' ? 'light' : 'dark';
  setTheme(current === 'dark' ? 'light' : 'dark');
}

themeToggle.addEventListener('click', toggleTheme);

globalThis.addEventListener('DOMContentLoaded', () => {
  setTheme('dark');
  loadModels();
});

function setStatus(text, isError = false) {
  statusEl.textContent = text || '';
  statusEl.style.color = isError ? '#f87171' : 'var(--muted-text)';
}

function renderConversation() {
  conversationEl.innerHTML = '';
  conversation.forEach(({ role, content }) => {
    const wrapper = document.createElement('div');
    wrapper.className = `message ${role}`;

    const label = document.createElement('span');
    label.textContent = role === 'user' ? 'You' : role === 'assistant' ? 'Model' : role;
    wrapper.appendChild(label);

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = content;
    wrapper.appendChild(bubble);

    conversationEl.appendChild(wrapper);
  });
  conversationEl.scrollTop = conversationEl.scrollHeight;
}

async function loadModels() {
  try {
    setStatus('Loading models…');
    const res = await fetch(`${API_BASE}/api/tags`, { credentials: 'omit' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const models = data.models || [];

    modelSelect.innerHTML = '';
    models.forEach((model) => {
      const option = document.createElement('option');
      option.value = model.name;
      option.textContent = model.name;
      modelSelect.appendChild(option);
    });
    if (!modelSelect.value && models[0]) {
      modelSelect.value = models[0].name;
    }
    setStatus(models.length ? 'Models synced.' : 'No models available. Pull one first.');
  } catch (err) {
    setStatus(`Failed to load models: ${err.message}`, true);
  }
}

async function sendMessage(prompt) {
  const model = modelSelect.value;
  if (!model) {
    setStatus('Select a model first.', true);
    return;
  }

  conversation.push({ role: 'user', content: prompt });
  renderConversation();

  submitBtn.disabled = true;
  setStatus('Waiting for model…');

  try {
    const payload = { model, messages: conversation, stream: false };
    if (context) payload.context = context;

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'omit',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const assistantMessage = data.message && data.message.content ? data.message.content : data.response;
    if (assistantMessage) {
      conversation.push({ role: 'assistant', content: assistantMessage });
    }
    context = data.context || context;
    renderConversation();
    setStatus('');
  } catch (err) {
    setStatus(`Request failed: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

refreshBtn.addEventListener('click', () => {
  loadModels();
});

resetBtn.addEventListener('click', () => {
  conversation.length = 0;
  context = null;
  renderConversation();
  setStatus('Session cleared.');
});

formEl.addEventListener('submit', (event) => {
  event.preventDefault();
  const prompt = promptEl.value.trim();
  if (!prompt) {
    setStatus('Enter a prompt first.', true);
    return;
  }
  promptEl.value = '';
  void sendMessage(prompt);
});
