const form = document.querySelector('#chat-form');
const promptInput = document.querySelector('#prompt');
const sendButton = document.querySelector('#send');
const messages = document.querySelector('#messages');
const qasmView = document.querySelector('#qasm code');
const statusBadge = document.querySelector('#circuit-status');
const runButton = document.querySelector('#run');
const copyButton = document.querySelector('#copy');
const resultPanel = document.querySelector('#result');
const bars = document.querySelector('#bars');
let currentQasm = '';

function addMessage(kind, speaker, text, extraClass = '') {
  const item = document.createElement('div');
  item.className = `message ${kind} ${extraClass}`.trim();
  const label = document.createElement('span');
  label.className = 'speaker';
  label.textContent = speaker;
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  item.append(label, paragraph);
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

async function request(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({ error: '服务器返回了无法读取的结果' }));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function setCircuit(qasm) {
  currentQasm = qasm || '';
  qasmView.textContent = currentQasm || '// 这次回答没有生成电路\n// 你仍可以继续追问';
  runButton.disabled = !currentQasm;
  copyButton.disabled = !currentQasm;
  statusBadge.textContent = currentQasm ? '已通过 L1 检查' : '无电路输出';
  statusBadge.classList.toggle('ready', Boolean(currentQasm));
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  addMessage('user', '你', prompt);
  promptInput.value = '';
  sendButton.disabled = true;
  const pending = addMessage('guide', 'LoomQ', '正在理解意图、编织电路并做运行前检查…', 'thinking');
  try {
    const data = await request('/api/chat', { prompt });
    pending.remove();
    addMessage('guide', 'LoomQ', data.reply);
    setCircuit(data.qasm);
  } catch (error) {
    pending.remove();
    addMessage('error', '需要处理', `${error.message}\n检查模型环境变量和网络后再试一次。`);
  } finally {
    sendButton.disabled = false;
    promptInput.focus();
  }
});

document.querySelectorAll('[data-prompt]').forEach((button) => {
  button.addEventListener('click', () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
  });
});

runButton.addEventListener('click', async () => {
  runButton.disabled = true;
  runButton.textContent = '正在运行…';
  try {
    const data = await request('/api/run', {
      qasm: currentQasm,
      target: document.querySelector('#target').value,
      shots: Number(document.querySelector('#shots').value),
    });
    renderResult(data.result);
  } catch (error) {
    bars.innerHTML = '';
    const message = document.createElement('p');
    message.textContent = `${error.message}，请返回对话让 LoomQ 修复电路。`;
    bars.append(message);
  } finally {
    runButton.disabled = false;
    runButton.textContent = '运行实验';
  }
});

function renderResult(result) {
  resultPanel.classList.remove('empty');
  bars.innerHTML = '';
  Object.entries(result.counts)
    .sort((a, b) => b[1] - a[1])
    .forEach(([state, count]) => {
      const probability = count / result.shots;
      const row = document.createElement('div');
      row.className = 'bar';
      const stateLabel = document.createElement('span');
      stateLabel.textContent = `|${state}⟩`;
      const track = document.createElement('div');
      track.className = 'bar-track';
      const fill = document.createElement('div');
      fill.className = 'bar-fill';
      fill.style.width = `${Math.max(probability * 100, 1)}%`;
      track.append(fill);
      const value = document.createElement('span');
      value.textContent = `${(probability * 100).toFixed(1)}%`;
      row.append(stateLabel, track, value);
      bars.append(row);
    });
}

copyButton.addEventListener('click', async () => {
  await navigator.clipboard.writeText(currentQasm);
  copyButton.textContent = '已复制';
  setTimeout(() => { copyButton.textContent = '复制'; }, 1400);
});
