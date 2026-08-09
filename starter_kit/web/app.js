const form = document.querySelector('#chat-form');
const promptInput = document.querySelector('#prompt');
const sendButton = document.querySelector('#send');
const heroStartBtn = document.querySelector('#hero-start');
const heroAboutBtn = document.querySelector('#hero-about');
const aboutPanel = document.querySelector('#about-panel');
const curiosityStage = document.querySelector('#curiosity-stage');
const designStage = document.querySelector('#design-stage');
const resultStage = document.querySelector('#result-stage');
const explanation = document.querySelector('#explanation');
const statusBadge = document.querySelector('#circuit-status');
const runButton = document.querySelector('#run');
const copyButton = document.querySelector('#copy');
const bars = document.querySelector('#bars');
const meaning = document.querySelector('#meaning');
const runMeta = document.querySelector('#run-meta');
const agentOrb = document.querySelector('#agent-orb-status');
const demoFallback = document.querySelector('#demo-fallback');
const demoButton = document.querySelector('#show-demo');
const themeToggle = document.querySelector('#theme-toggle');
const previewNotice = document.querySelector('#preview-notice');
const conversationPanel = document.querySelector('#conversation-panel');
const conversationLog = document.querySelector('#conversation-log');
const translationProof = document.querySelector('#translation-proof');
const translationQuestion = document.querySelector('#translation-question');
const translationQasm = document.querySelector('#translation-qasm');
const translationTargets = document.querySelector('#translation-targets');
const translatorIr = document.querySelector('#translator-ir');

let currentQasm = '';
let lastPrompt = '';
let lastAgentReply = '';
let lastResult = null;
let lastResultExplanation = '';
let lastExperimentContext = '';
let conversationHistory = [];
let currentTranslations = null;
let currentCircuit = null;
let demoMode = false;
const SESSION_KEY = 'loomq-exploration-v1';

const SAMPLE_QASM = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];`;
const SAMPLE_EXPLANATION = '【固定界面示例，不调用 AI】这段文字只用来展示 LoomQ 的界面和实验流程，不会根据你刚才的问题发生变化。要获得 DeepSeek 针对不同问题生成的回答，请通过 http://127.0.0.1:8765 打开 LoomQ。这个固定示例会让两个量子比特建立关联，重复测量后，结果集中在“00”或“11”。';
const SAMPLE_RESULT = { counts: { '00': 512, '11': 512 }, shots: 1024 };

function setOrb(el, state) {
  if (el) el.dataset.state = state;
}

function request(path, payload) {
  if (window.location.protocol === 'file:') {
    return Promise.reject(new Error('当前通过文件方式打开，只能查看静态界面，无法连接 LoomQ AI'));
  }
  return fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(async (response) => {
    const data = await response.json().catch(() => ({ error: '服务器返回了无法读取的内容' }));
    if (!response.ok) {
      if (response.status === 404 && path.startsWith('/api/')) {
        throw new Error('本地 LoomQ 服务仍是旧版本。请在启动服务的终端按 Control+C 停止，再运行 python3 web_app.py 后刷新页面');
      }
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  });
}

function applyTheme(theme) {
  const isLight = theme === 'light';
  document.body.dataset.theme = isLight ? 'light' : 'dark';
  document.documentElement.style.colorScheme = isLight ? 'light' : 'dark';
  themeToggle.setAttribute('aria-pressed', String(isLight));
  themeToggle.setAttribute('aria-label', isLight ? '切换为夜晚模式' : '切换为白天模式');
  themeToggle.querySelector('.theme-icon').textContent = isLight ? '☾' : '☼';
  themeToggle.querySelector('.theme-label').textContent = isLight ? '夜晚' : '白天';
}

let savedTheme = null;
try { savedTheme = window.localStorage.getItem('loomq-theme'); } catch (_) { /* storage may be unavailable */ }
applyTheme(savedTheme === 'light' ? 'light' : 'dark');

themeToggle.addEventListener('click', () => {
  const nextTheme = document.body.dataset.theme === 'light' ? 'dark' : 'light';
  applyTheme(nextTheme);
  try { window.localStorage.setItem('loomq-theme', nextTheme); } catch (_) { /* keep the in-page choice */ }
});

if (window.location.protocol === 'file:') previewNotice.classList.remove('hidden');

function setJourney(step) {
  document.querySelectorAll('.journey-step').forEach((item) => {
    const value = Number(item.dataset.step);
    item.classList.toggle('active', value === step);
    item.classList.toggle('done', value < step);
  });
  document.querySelector('#journey-fill').style.width = `${((step - 1) / 3) * 100}%`;
}

function scrollToStage(stage) {
  stage.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
}

function plainReply(text) {
  return String(text || '')
    .replace(/```(?:qasm|openqasm)?\s*([\s\S]*?)```/gi, (_, code) => `\n\n${code.trim()}\n\n`)
    .replace(/^#{1,6}\s*/gm, '')
    .trim();
}

function conversationReply(text) {
  return String(text || '')
    .replace(/```(?:qasm|openqasm)?\s*[\s\S]*?```/gi, '\n\n[代码见当前回答与“看看 LoomQ 是怎么翻译的”]\n\n')
    .replace(/^#{1,6}\s*/gm, '')
    .trim();
}

function saveExploration() {
  const state = {
    history: conversationHistory,
    qasm: currentQasm,
    prompt: lastPrompt,
    agentReply: lastAgentReply,
    experimentContext: lastExperimentContext,
    translations: currentTranslations,
    circuit: currentCircuit,
  };
  try { window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(state)); } catch (_) { /* page still works without storage */ }
}

function clearSavedExploration() {
  try { window.sessionStorage.removeItem(SESSION_KEY); } catch (_) { /* storage may be unavailable */ }
}

function restoreExploration() {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(SESSION_KEY) || 'null');
    if (!saved || !Array.isArray(saved.history)) return;
    conversationHistory = saved.history
      .filter((item) => item && ['user', 'assistant'].includes(item.role) && typeof item.content === 'string')
      .slice(-8);
    currentQasm = typeof saved.qasm === 'string' ? saved.qasm : '';
    lastPrompt = typeof saved.prompt === 'string' ? saved.prompt : '';
    lastAgentReply = typeof saved.agentReply === 'string' ? saved.agentReply : '';
    lastExperimentContext = typeof saved.experimentContext === 'string' ? saved.experimentContext : '';
    currentTranslations = saved.translations && Array.isArray(saved.translations.targets) ? saved.translations : null;
    currentCircuit = saved.circuit && Number.isInteger(saved.circuit.qubits) ? saved.circuit : null;
  } catch (_) {
    clearSavedExploration();
  }
}

function renderTranslations() {
  const targets = currentTranslations && Array.isArray(currentTranslations.targets)
    ? currentTranslations.targets
    : [];
  const validTargets = targets.filter((item) => item && typeof item.output === 'string' && item.output.trim());
  translationProof.classList.toggle('hidden', !currentQasm || validTargets.length === 0);
  translationQuestion.textContent = lastPrompt;
  translationQasm.textContent = currentQasm;
  translatorIr.textContent = currentCircuit
    ? `共享 IR：${currentCircuit.qubits} qubits · ${(currentCircuit.gates || []).map((gate) => gate.toUpperCase()).join(' → ') || '无量子门'} · ${currentCircuit.measurements} measurements`
    : '等待 L1 解析';
  translationTargets.replaceChildren();
  validTargets.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'translation-target';
    const head = document.createElement('div');
    const name = document.createElement('b');
    name.textContent = item.label || item.target;
    const status = document.createElement('span');
    status.textContent = item.status === 'generated_from_shared_ir' ? '同源 IR 已生成 ✓' : '状态未知';
    head.append(name, status);
    const code = document.createElement('pre');
    code.textContent = item.output;
    card.append(head, code);
    translationTargets.append(card);
  });
}

function renderConversation(pendingPrompt = '') {
  const items = conversationHistory.slice();
  if (pendingPrompt) items.push({ role: 'user', content: pendingPrompt, pending: true });
  conversationPanel.classList.toggle('hidden', items.length === 0);
  conversationLog.replaceChildren();
  items.forEach((item) => {
    const message = document.createElement('article');
    message.className = `conversation-message conversation-message--${item.role}${item.pending ? ' is-pending' : ''}`;
    const label = document.createElement('b');
    label.textContent = item.role === 'user' ? (item.pending ? '你 · 正在发送' : '你') : 'LoomQ';
    const content = document.createElement('p');
    content.textContent = item.role === 'assistant' ? conversationReply(item.content) : item.content;
    message.append(label, content);
    conversationLog.append(message);
  });
  conversationLog.scrollTop = conversationLog.scrollHeight;
}

restoreExploration();
renderConversation();
renderTranslations();
if (conversationHistory.length) {
  designStage.classList.remove('hidden');
  const restoredAnswer = [...conversationHistory].reverse().find((item) => item.role === 'assistant');
  explanation.textContent = restoredAnswer ? plainReply(restoredAnswer.content) : '已恢复本次探索记录。';
  runButton.disabled = !currentQasm;
  copyButton.disabled = !currentQasm;
  statusBadge.textContent = currentQasm ? '已恢复，可以运行' : '已恢复对话记录';
  statusBadge.className = `badge${currentQasm ? ' ready' : ''}`;
  setOrb(agentOrb, currentQasm ? 'verified' : 'idle');
  setJourney(2);
}

async function createExperiment(prompt) {
  lastPrompt = prompt.trim();
  if (!lastPrompt) return;
  demoMode = false;
  currentTranslations = null;
  currentCircuit = null;
  renderTranslations();
  sendButton.disabled = true;
  sendButton.querySelector('span').textContent = '正在把好奇翻译成实验…';
  designStage.classList.remove('hidden');
  resultStage.classList.add('hidden');
  demoFallback.classList.add('hidden');
  explanation.innerHTML = '<p class="thinking">正在理解你想知道的事，然后设计一个可以亲手运行的小实验…</p>';
  statusBadge.textContent = '正在设计';
  statusBadge.className = 'badge';
  setOrb(agentOrb, 'thinking');
  setJourney(2);
  renderConversation(lastPrompt);
  scrollToStage(designStage);
  try {
    const userContext = conversationHistory
      .filter((item) => item.role === 'user')
      .map((item) => item.content);
    userContext.push(lastPrompt);
    const data = await request('/api/chat', {
      prompt: lastPrompt,
      history: conversationHistory,
    });
    lastAgentReply = data.reply || '';
    lastExperimentContext = userContext.join('\n');
    conversationHistory.push(
      { role: 'user', content: lastPrompt },
      { role: 'assistant', content: lastAgentReply },
    );
    conversationHistory = conversationHistory.slice(-8);
    renderConversation();
    const friendly = plainReply(data.reply);
    explanation.textContent = friendly || '实验已经设计好了。你可以直接开始，不需要读懂专业代码。';
    currentQasm = data.qasm || '';
    currentTranslations = data.translations || null;
    currentCircuit = data.circuit || null;
    renderTranslations();
    saveExploration();
    runButton.disabled = !currentQasm;
    copyButton.disabled = !currentQasm;
    statusBadge.textContent = currentQasm ? '已检查，可以运行' : '这次是概念回答';
    statusBadge.className = `badge${currentQasm ? ' ready' : ''}`;
    setOrb(agentOrb, currentQasm ? 'verified' : 'idle');
    promptInput.value = '';
  } catch (error) {
    renderConversation();
    explanation.innerHTML = '';
    const title = document.createElement('h3');
    title.textContent = '这次还没有准备好实验';
    const detail = document.createElement('p');
    const validationFailure = /valid QASM|validation|validator|requested .* qubits|supported gate/i.test(error.message);
    detail.textContent = validationFailure
      ? `${error.message}。模型生成的实验没有通过 LoomQ 校验，因此没有被运行。你输入的问题不会丢失，可以修改要求后重试。`
      : `${error.message}。检查模型环境变量和网络后再试一次，你输入的问题不会丢失。`;
    explanation.append(title, detail);
    demoFallback.classList.remove('hidden');
    promptInput.value = lastPrompt;
    runButton.disabled = true;
    statusBadge.textContent = '需要重试';
    statusBadge.className = 'badge warning';
    setOrb(agentOrb, 'warning');
  } finally {
    sendButton.disabled = false;
    sendButton.querySelector('span').textContent = '把好奇变成实验';
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  createExperiment(promptInput.value);
});

document.querySelectorAll('[data-prompt]').forEach((button) => {
  button.addEventListener('click', () => createExperiment(button.dataset.prompt));
});

heroStartBtn.addEventListener('click', () => {
  scrollToStage(curiosityStage);
  promptInput.focus();
});

heroAboutBtn.addEventListener('click', () => {
  const expanded = heroAboutBtn.getAttribute('aria-expanded') === 'true';
  heroAboutBtn.setAttribute('aria-expanded', String(!expanded));
  aboutPanel.classList.toggle('hidden', expanded);
  if (!expanded) scrollToStage(aboutPanel);
});

demoButton.addEventListener('click', () => {
  demoMode = true;
  explanation.textContent = SAMPLE_EXPLANATION;
  lastAgentReply = SAMPLE_EXPLANATION;
  currentQasm = SAMPLE_QASM;
  currentTranslations = null;
  currentCircuit = null;
  renderTranslations();
  runButton.disabled = false;
  copyButton.disabled = false;
  statusBadge.textContent = '固定示例 · 未调用 AI';
  statusBadge.className = 'badge warning';
  setOrb(agentOrb, 'idle');
  demoFallback.classList.add('hidden');
});

runButton.addEventListener('click', async () => {
  runButton.disabled = true;
  runButton.innerHTML = '正在重复实验并整理结果…';
  setOrb(agentOrb, 'thinking');
  setJourney(3);
  const isDemo = demoMode;
  try {
    let result;
    if (isDemo) {
      await new Promise((resolve) => setTimeout(resolve, 600));
      result = SAMPLE_RESULT;
    } else {
      const shots = Number(document.querySelector('#shots').value);
      const data = await request('/api/run', {
        qasm: currentQasm,
        target: document.querySelector('#target').value,
        shots,
        explain: true,
        prompt: lastExperimentContext || lastPrompt,
        agent_reply: lastAgentReply,
      });
      result = data.result;
      result.aiExplanation = data.explanation || '';
    }
    lastResult = result;
    renderResult(result, isDemo, result.aiExplanation || '');
    lastResultExplanation = meaning.textContent;
    resultStage.classList.remove('hidden');
    const elapsed = result.meta && Number.isFinite(Number(result.meta.execution_ms))
      ? ` · ${Number(result.meta.execution_ms).toLocaleString()} ms`
      : '';
    runMeta.textContent = isDemo
      ? '示例结果 · 非真实运行'
      : `本地模拟器 · ${Number(result.shots).toLocaleString()} 次${elapsed}`;
    runMeta.className = isDemo ? 'badge warning' : 'badge badge--gold';
    setOrb(agentOrb, 'success');
    setJourney(4);
    scrollToStage(resultStage);
  } catch (error) {
    statusBadge.textContent = '运行时遇到问题';
    statusBadge.className = 'badge warning';
    explanation.textContent += `\n\n运行没有完成：${error.message}。你可以返回上方修改问题，或重新设计实验。`;
    setOrb(agentOrb, 'warning');
    setJourney(2);
  } finally {
    runButton.disabled = false;
    runButton.innerHTML = '运行我的第一次量子实验 <span aria-hidden="true">→</span>';
  }
});

function renderResult(result, isDemo, aiExplanation = '') {
  bars.innerHTML = '';
  if (!result || !result.counts || !Number.isFinite(Number(result.shots)) || Number(result.shots) <= 0) {
    throw new Error('运行结果缺少有效的测量次数或计数数据');
  }
  const entries = Object.entries(result.counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) throw new Error('运行完成了，但没有返回可展示的测量结果');
  entries.forEach(([state, count]) => {
    const probability = count / result.shots;
    const row = document.createElement('div');
    row.className = 'bar';
    const stateLabel = document.createElement('span');
    stateLabel.textContent = state;
    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    fill.style.width = `${Math.max(probability * 100, 1)}%`;
    track.append(fill);
    const value = document.createElement('span');
    value.textContent = `${count} 次 · ${(probability * 100).toFixed(1)}%`;
    row.append(stateLabel, track, value);
    bars.append(row);
  });

  const top = entries[0];
  const allZero = entries.find(([state]) => /^0+$/.test(state));
  const allOne = entries.find(([state]) => /^1+$/.test(state));
  let text;
  if (entries.length === 2 && allZero && allOne) {
    const zeroRate = (allZero[1] / result.shots * 100).toFixed(1);
    const oneRate = (allOne[1] / result.shots * 100).toFixed(1);
    if (allZero[0].length === 1) {
      text = `实验重复了 ${result.shots.toLocaleString()} 次：“${allZero[0]}”出现 ${zeroRate}%，“${allOne[0]}”出现 ${oneRate}%。两种测量结果都在统计图中出现，这就是这个量子随机实验希望观察的现象。`;
    } else {
      text = `实验重复了 ${result.shots.toLocaleString()} 次，结果集中在“${allZero[0]}”（${zeroRate}%）和“${allOne[0]}”（${oneRate}%）。这说明这些量子比特不是各自独立变化，而是表现出一起变化的关联——量子计算中把这类关联称为“纠缠”。\n\n这能说明的是：测量结果彼此相关。这不能说明的是：量子比特之间发生了超过光速的信息传递。`;
    }
  } else {
    text = `实验重复了 ${result.shots.toLocaleString()} 次，最常出现的是“${top[0]}”，共 ${top[1]} 次。量子结果不是每次都一样，我们通过重复实验来看出哪些可能性更容易发生，而不是通过单次测量下结论。`;
  }
  if (isDemo) {
    text = `【示例内容，非真实运行结果】\n\n${text}`;
  }
  meaning.textContent = aiExplanation.trim() || text;
}

copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(currentQasm);
    copyButton.textContent = '已复制';
  } catch (_) {
    copyButton.textContent = '复制失败，请手动选择';
  }
  setTimeout(() => { copyButton.textContent = '复制源程序'; }, 1800);
});

document.querySelector('#new-experiment').addEventListener('click', () => {
  resultStage.classList.add('hidden');
  designStage.classList.add('hidden');
  demoFallback.classList.add('hidden');
  promptInput.value = '';
  currentQasm = '';
  lastAgentReply = '';
  lastResult = null;
  lastResultExplanation = '';
  lastExperimentContext = '';
  conversationHistory = [];
  currentTranslations = null;
  currentCircuit = null;
  clearSavedExploration();
  renderConversation();
  renderTranslations();
  demoMode = false;
  setOrb(agentOrb, 'idle');
  setJourney(1);
  scrollToStage(curiosityStage);
});

document.querySelector('#ask-why').addEventListener('click', async (event) => {
  const button = event.currentTarget;
  if (demoMode) {
    meaning.textContent += '\n\n这是固定界面示例，没有调用 AI。启动 LoomQ 服务并完成真实实验后，追问会沿用同一次实验的代码和结果。';
    return;
  }
  if (!lastResult || !currentQasm) return;
  button.disabled = true;
  button.textContent = '正在结合这次实验继续解释…';
  try {
    const data = await request('/api/explain', {
      prompt: lastExperimentContext || lastPrompt,
      qasm: currentQasm,
      result: lastResult,
      agent_reply: lastAgentReply,
      previous_explanation: lastResultExplanation,
      question: '为什么这段代码会产生刚才的测量结果？请继续围绕同一个实验，用零基础能懂的方式解释，并说明类比的边界。',
    });
    meaning.textContent = data.explanation;
    lastResultExplanation = data.explanation;
  } catch (error) {
    meaning.textContent += `\n\n继续解释时遇到问题：${error.message}`;
  } finally {
    button.disabled = false;
    button.textContent = '我还想知道“为什么”';
  }
});
