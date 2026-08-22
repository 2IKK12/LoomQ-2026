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
const circuitCard = document.querySelector('#circuit-card');
const circuitViewport = document.querySelector('#circuit-viewport');
const circuitLegend = document.querySelector('#circuit-legend');
const circuitLive = document.querySelector('#circuit-live');
const playCircuitButton = document.querySelector('#play-circuit');
const dictionaryTerms = document.querySelector('#dictionary-terms');
const dictionaryDialog = document.querySelector('#dictionary');
const dictionaryTitle = document.querySelector('#dictionary-title');
const dictionaryCopy = document.querySelector('#dictionary-copy');
const dictionaryAi = document.querySelector('#dictionary-ai');
const hardwareStatusText = document.querySelector('#hardware-status');
const hardwareBackendWrap = document.querySelector('#hardware-backend-wrap');
const hardwareConfirm = document.querySelector('#hardware-confirm');
const resultTableBody = document.querySelector('#result-table tbody');
const resultTotal = document.querySelector('#result-total');

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
let hardwareConfirmed = false;
let circuitTimers = [];
const SESSION_KEY = 'loomq-exploration-v1';

const GATE_LABELS = {
  h: 'H', x: 'X', s: 'S', sdg: 'S†', t: 'T', tdg: 'T†', rz: 'RZ', ry: 'RY',
  cx: 'CX', cu1: 'CU1', swap: 'SWAP', ccx: 'CCX', measure: 'M',
};

const QUANTUM_DICTIONARY = {
  superposition: {
    title: '叠加态（Quantum Superposition）',
    tags: ['量子力学', '量子信息', '固定知识'],
    definition: '叠加态是由多个基态线性组合而成的量子态。一个量子比特可写成 |ψ⟩ = α|0⟩ + β|1⟩。概率幅的模平方给出各测量结果的概率。',
    plain: '测量前，量子比特的状态可以同时包含得到 0 和得到 1 的可能性，也包含会影响后续干涉的相位信息。一次测量只产生一个结果，重复准备和测量才能看到概率分布。',
    origin: 'Superposition 的基本含义是“组合在一起”。在量子力学中，它专指多个量子基态的线性组合。',
    misconception: '叠加态不一定对应 50% 和 50%。测量概率取决于概率幅。',
    sources: [['IBM Quantum Learning · Quantum mechanics basics', 'https://quantum.cloud.ibm.com/learning/en/courses/use-a-qc-today/quantum-mechanics-basics'], ['Wikipedia · Quantum superposition（延伸阅读）', 'https://en.wikipedia.org/wiki/Quantum_superposition']],
  },
  h: {
    title: 'Hadamard 门（H Gate）', tags: ['量子计算', '单量子比特门', '固定知识'],
    definition: 'Hadamard 门是单量子比特的幺正变换。它满足 H|0⟩=(|0⟩+|1⟩)/√2，H|1⟩=(|0⟩−|1⟩)/√2。',
    plain: 'H 门重新组合 0 和 1 的概率幅。输入为 |0⟩ 时，它产生等权叠加态。对该状态再应用一次 H 门，可恢复为 |0⟩，因此这是可逆计算操作。',
    origin: '该量子门以法国数学家 Jacques Hadamard 命名，它的矩阵形式与 Hadamard 矩阵有关。',
    misconception: 'H 门不是随机数开关，也不会对所有输入产生同样的 50% 对 50% 结果。',
    sources: [['IBM Quantum Learning · Bits, gates, and circuits', 'https://quantum.cloud.ibm.com/learning/en/courses/utility-scale-quantum-computing/bits-gates-and-circuits']],
  },
  cx: {
    title: '受控非门（CX / CNOT Gate）', tags: ['量子计算', '双量子比特门', '固定知识'],
    definition: '受控非门是双量子比特的幺正变换。控制位为 0 时目标位保持原状态；控制位为 1 时，目标位执行 X 变换。',
    plain: 'CX 门先读取控制位的量子状态，再决定是否翻转目标位。控制位处于叠加态时，CX 可以让两个量子比特的状态无法分开描述，从而生成纠缠。',
    origin: 'Controlled-NOT 直接描述它的操作：由一个量子比特控制，对另一个量子比特执行 NOT。CX 中的 X 指 Pauli-X 门。',
    misconception: '只有 CX 门不一定产生纠缠，还要看它的输入状态。',
    sources: [['IBM Quantum Learning · Quantum circuits', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/quantum-circuits/circuits']],
  },
  measure: {
    title: '量子测量（Measurement）', tags: ['量子力学', '读取操作', '固定知识'],
    definition: '量子测量将量子态映射为选定测量基中的经典结果。计算基测量一个量子比特时，结果为 0 或 1。',
    plain: '每次测量只记录一个确定结果。为了了解原量子状态的概率分布，实验需要重新准备相同状态并测量多次。',
    origin: 'Measurement 在此指对量子系统进行观测并产生经典读数的操作。',
    misconception: '一次测量不能显示完整概率分布，柱状图来自多次独立重复实验。',
    sources: [['IBM Quantum Learning · Quantum circuits', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/quantum-circuits/circuits']],
  },
  qubit: {
    title: '量子比特（Qubit）', tags: ['量子信息', '基本单位', '固定知识'],
    definition: '量子比特是量子信息的基本单位。它的状态可由 |0⟩ 和 |1⟩ 两个基态的线性组合表示。',
    plain: '量子比特是量子线路处理信息的最小单位。它可以保存 0 和 1 的概率幅与相位信息；测量时则记录为 0 或 1。',
    origin: 'Qubit 是 quantum bit 的缩写，对应经典计算中的 bit（比特）。',
    misconception: '量子比特并不是同时输出 0 和 1；一次计算基测量只记录一个结果。',
    sources: [['IBM Quantum Learning · Quantum information', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/single-systems/quantum-information']],
  },
  entanglement: {
    title: '量子纠缠（Quantum Entanglement）', tags: ['量子力学', '多比特关联', '固定知识'],
    definition: '量子纠缠是一种复合量子状态，整体状态无法写成各个子系统状态的简单乘积。',
    plain: '纠缠后，多个量子比特需要用一个整体状态描述。在 Bell 实验中，这会表现为测量结果 00 和 11 更容易出现，而非两个结果各自独立变化。',
    origin: 'Entanglement 的日常词义是“缠绕、交织”，在量子力学中表示子系统之间无法分开描述的关联。',
    misconception: '纠缠关联不能用来超光速传送可控信息。',
    sources: [['IBM Quantum Learning · Multiple systems', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/multiple-systems/quantum-information']],
  },
  circuit: {
    title: '量子线路（Quantum Circuit）', tags: ['量子计算', '计算模型', '固定知识'],
    definition: '量子线路是按顺序组织量子比特、量子门和测量操作的计算表示。',
    plain: '图中每一条横线代表一个量子比特，操作按从左到右的顺序执行。方块或连线表示量子门，M 表示测量。',
    origin: 'Circuit 原指电路中的连接路径；量子计算沿用这个词来表示操作流程。',
    misconception: '线路图表示操作顺序，不表示量子比特在设备中的真实空间位置。',
    sources: [['IBM Quantum Learning · Quantum circuits', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/quantum-circuits/circuits']],
  },
  bell: {
    title: 'Bell 态（Bell State）', tags: ['量子信息', '两比特纠缠', '固定知识'],
    definition: 'Bell 态是四种特定的两量子比特最大纠缠态。LoomQ 常用的一种可写成 (|00⟩+|11⟩)/√2。',
    plain: '在计算基中重复测量这个状态，主要得到 00 和 11。两个量子比特的结果需要作为一个整体理解。',
    origin: '这个名称来自物理学家 John Bell。Bell 态常用于讨论纠缠、量子传送和 Bell 不等式。',
    misconception: '只看到 00 和 11 的相关分布，不足以单独完成 Bell 不等式检验。',
    sources: [['IBM Quantum Learning · Entanglement in action', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/entanglement-in-action/introduction']],
  },
  ghz: {
    title: 'GHZ 态（Greenberger–Horne–Zeilinger State）', tags: ['量子信息', '多比特纠缠', '固定知识'],
    definition: 'n 量子比特 GHZ 态可写成 (|00…00⟩+|11…11⟩)/√2，是一类多量子比特纠缠态。',
    plain: '以三比特 GHZ 态为例，在计算基中重复测量时，主要得到 000 和 111。它把两比特 Bell 关联扩展到更多量子比特。',
    origin: 'GHZ 取自物理学家 Daniel Greenberger、Michael Horne 和 Anton Zeilinger 的姓氏首字母。',
    misconception: 'GHZ 态很容易受噪声影响；真机结果可能出现 000 和 111 以外的次要结果。',
    sources: [['IBM Quantum Learning · GHZ utility experiment', 'https://quantum.cloud.ibm.com/learning/en/courses/utility-scale-quantum-computing/utility-i']],
  },
  amplitude: {
    title: '概率幅（Probability Amplitude）', tags: ['量子力学', '复数', '固定知识'],
    definition: '概率幅是量子态中与各个基态对应的复数系数。它的模平方给出相应测量结果的概率。',
    plain: '概率幅同时包含大小和相位。量子门改变概率幅，不同路径的概率幅可以相加或抵消。',
    origin: 'Amplitude 在物理中通常指振幅；在量子力学中，它表示与某个结果相关的复数幅度。',
    misconception: '概率幅本身不是概率，它可以是负数或复数。',
    sources: [['IBM Quantum Learning · Quantum information', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/single-systems/quantum-information']],
  },
  phase: {
    title: '量子相位（Quantum Phase）', tags: ['量子力学', '概率幅', '固定知识'],
    definition: '相位是概率幅的复数角度信息。相对相位可以改变后续干涉和测量结果。',
    plain: '两个量子态可能有相同的直接测量概率，却具有不同的相对相位。通过后续量子门产生干涉，差别才会显示在测量结果中。',
    origin: 'Phase 来自波动与振动的描述，用于表示一个复数幅度在周期中的角度位置。',
    misconception: '所有概率幅同时乘上同一相位的“全局相位”不会改变测量统计；关键是相对相位。',
    sources: [['IBM Quantum Learning · Quantum information', 'https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/single-systems/quantum-information']],
  },
  interference: {
    title: '量子干涉（Quantum Interference）', tags: ['量子力学', '概率幅', '固定知识'],
    definition: '量子干涉是不同计算路径的概率幅相加或抵消，从而提高或降低某些测量结果的概率。',
    plain: '量子线路利用门操作调整概率幅的相位，让目标结果的概率幅加强，其他结果的概率幅减弱。',
    origin: 'Interference 是波的叠加效应。量子力学中相加的是概率幅。',
    misconception: '干涉不是同一次测量同时显示多个结果；它改变的是重复实验的统计分布。',
    sources: [['IBM Quantum Learning · Quantum mechanics basics', 'https://quantum.cloud.ibm.com/learning/en/courses/use-a-qc-today/quantum-mechanics-basics']],
  },
};

const DICTIONARY_ALIASES = {
  entanglement: ['量子纠缠', '纠缠'], superposition: ['量子叠加态', '叠加态', '量子叠加'],
  measure: ['量子测量', '测量'], h: ['Hadamard 门', 'Hadamard Gate', 'H 门'],
  cx: ['受控非门', 'CNOT 门', 'CX 门'], qubit: ['量子比特'], circuit: ['量子线路', '量子电路'],
  bell: ['Bell 态', '贝尔态'], ghz: ['GHZ 态', 'GHZ态'], amplitude: ['概率幅'],
  phase: ['相对相位', '量子相位', '相位'], interference: ['量子干涉', '干涉'],
};

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

function renderExplanation(text) {
  const content = plainReply(text);
  explanation.replaceChildren();
  if (!content) {
    explanation.textContent = '实验已经设计好了。你可以直接开始，不需要读懂专业代码。';
    return;
  }
  const aliases = Object.entries(DICTIONARY_ALIASES)
    .flatMap(([key, labels]) => labels.map((label) => ({ key, label })))
    .sort((a, b) => b.label.length - a.label.length);
  const pattern = new RegExp(`(${aliases.map(({ label }) => label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g');
  const keyForLabel = new Map(aliases.map(({ key, label }) => [label, key]));
  content.split(pattern).forEach((part) => {
    const key = keyForLabel.get(part);
    if (!key) {
      explanation.append(document.createTextNode(part));
      return;
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'dictionary-link';
    button.textContent = part;
    button.title = '打开量子词典';
    button.setAttribute('aria-label', `查看“${part}”的量子词典解释`);
    button.addEventListener('click', () => openDictionary(key));
    explanation.append(button);
  });
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

function gateDescription(operation) {
  const qubits = (operation.qubits || []).map((value) => `q[${value}]`).join('、');
  const parameter = Number.isFinite(operation.parameter) ? `，参数 ${operation.parameter.toFixed(3)}` : '';
  const descriptions = {
    h: '应用 Hadamard 门，重新组合 0 和 1 的概率幅',
    x: '应用 Pauli-X 门，翻转 0 和 1',
    s: '应用 S 相位门', sdg: '应用 S 门的逆操作',
    t: '应用 T 相位门', tdg: '应用 T 门的逆操作',
    rz: '绕 Z 轴旋转量子态', ry: '绕 Y 轴旋转量子态',
    cx: '根据控制位的状态决定是否翻转目标位',
    cu1: '根据控制位应用受控相位', swap: '交换两个量子比特的状态',
    ccx: '两个控制位都满足条件时翻转目标位',
  };
  return `${descriptions[operation.name] || '执行量子门'}：${qubits}${parameter}。`;
}

function renderCircuit() {
  circuitTimers.forEach(clearTimeout);
  circuitTimers = [];
  const operations = currentCircuit && Array.isArray(currentCircuit.operations) ? currentCircuit.operations : [];
  const qubits = currentCircuit ? Number(currentCircuit.qubits) : 0;
  circuitCard.classList.toggle('hidden', !qubits);
  circuitViewport.replaceChildren();
  circuitLegend.replaceChildren();
  dictionaryTerms.replaceChildren();
  if (!qubits) return;

  const diagram = document.createElement('div');
  diagram.className = 'circuit-diagram';
  diagram.style.setProperty('--qubits', String(qubits));
  const labels = document.createElement('div');
  labels.className = 'circuit-labels';
  for (let index = 0; index < qubits; index += 1) {
    const label = document.createElement('span');
    label.innerHTML = `<b>q[${index}]</b><small>|0⟩</small>`;
    labels.append(label);
  }
  const columns = document.createElement('div');
  columns.className = 'circuit-columns';
  const allSteps = [...operations, { name: 'measure', qubits: Array.from({ length: qubits }, (_, index) => index) }];
  allSteps.forEach((operation, columnIndex) => {
    const column = document.createElement('button');
    column.type = 'button';
    column.className = 'circuit-column';
    column.dataset.step = String(columnIndex);
    column.setAttribute('aria-label', operation.name === 'measure' ? '测量全部量子比特' : gateDescription(operation));
    const affected = operation.qubits || [];
    const first = Math.min(...affected);
    const last = Math.max(...affected);
    if (affected.length > 1) {
      const connector = document.createElement('i');
      connector.className = 'gate-connector';
      connector.style.setProperty('--from', String(first));
      connector.style.setProperty('--span', String(last - first + 1));
      column.append(connector);
    }
    for (let row = 0; row < qubits; row += 1) {
      const cell = document.createElement('span');
      cell.className = 'circuit-cell';
      if (affected.includes(row)) {
        const marker = document.createElement('b');
        marker.className = `gate-marker gate-marker--${operation.name}`;
        if (operation.name === 'cx') marker.textContent = row === affected[0] ? '•' : '⊕';
        else if (operation.name === 'ccx') marker.textContent = row === affected[affected.length - 1] ? '⊕' : '•';
        else if (operation.name === 'swap') marker.textContent = '×';
        else marker.textContent = GATE_LABELS[operation.name] || operation.name.toUpperCase();
        cell.append(marker);
      }
      column.append(cell);
    }
    column.addEventListener('click', () => {
      columns.querySelectorAll('.circuit-column').forEach((item) => item.classList.toggle('is-active', item === column));
      circuitLive.textContent = operation.name === 'measure'
        ? `第 ${columnIndex + 1} 步：测量全部 ${qubits} 个量子比特，将结果记录为经典比特串。`
        : `第 ${columnIndex + 1} 步：${gateDescription(operation)}`;
    });
    columns.append(column);

    const legendItem = document.createElement('button');
    legendItem.type = 'button';
    legendItem.innerHTML = `<b>${columnIndex + 1}. ${GATE_LABELS[operation.name] || operation.name.toUpperCase()}</b><span>${operation.name === 'measure' ? '记录测量结果' : gateDescription(operation)}</span>`;
    legendItem.addEventListener('click', () => column.click());
    circuitLegend.append(legendItem);
  });
  diagram.append(labels, columns);
  circuitViewport.append(diagram);
  circuitLive.textContent = `初始状态：${qubits} 个量子比特都从 |0⟩ 开始。点击量子门可以查看该步的作用。`;

  const termKeys = new Set(['measure']);
  operations.forEach((operation) => {
    if (QUANTUM_DICTIONARY[operation.name]) termKeys.add(operation.name);
    if (operation.name === 'h') termKeys.add('superposition');
  });
  termKeys.forEach((key) => {
    const item = QUANTUM_DICTIONARY[key];
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'term-chip';
    button.textContent = item.title.split('（')[0];
    button.addEventListener('click', () => openDictionary(key));
    dictionaryTerms.append(button);
  });
}

function openDictionary(key) {
  const item = QUANTUM_DICTIONARY[key];
  if (!item) return;
  dictionaryTitle.textContent = item.title;
  dictionaryCopy.replaceChildren();
  const meta = document.createElement('div');
  meta.className = 'dictionary-meta';
  item.tags.forEach((tag) => { const span = document.createElement('span'); span.textContent = tag; meta.append(span); });
  dictionaryCopy.append(meta);
  [['学科定义', item.definition], ['简单解释', item.plain], ['名称来源', item.origin]].forEach(([heading, copy]) => {
    const title = document.createElement('h3'); title.textContent = heading;
    const paragraph = document.createElement('p'); paragraph.textContent = copy;
    dictionaryCopy.append(title, paragraph);
  });
  const note = document.createElement('p'); note.className = 'dictionary-note'; note.innerHTML = `<strong>常见误解：</strong>${item.misconception}`;
  const sources = document.createElement('div'); sources.className = 'dictionary-sources'; sources.innerHTML = '<strong>参考来源</strong>';
  item.sources.forEach(([label, href]) => { const link = document.createElement('a'); link.href = href; link.target = '_blank'; link.rel = 'noreferrer'; link.textContent = label; sources.append(link); });
  dictionaryCopy.append(note, sources);
  dictionaryAi.classList.remove('hidden');
  dictionaryAi.innerHTML = '<b>AI 正在结合你的问题解释这个词在当前实验中的作用…</b>';
  dictionaryDialog.showModal();
  if (!currentQasm || demoMode) {
    dictionaryAi.innerHTML = '<b>当前实验案例</b><p>完成真实 AI 实验设计后，这里会根据当前问题和经 L1 验证的线路生成解释。</p>';
    return;
  }
  request('/api/dictionary', { term_key: key, prompt: lastExperimentContext || lastPrompt, qasm: currentQasm })
    .then((data) => { dictionaryAi.innerHTML = '<b>AI 结合当前实验的解释</b>'; const p = document.createElement('p'); p.textContent = data.contextual_explanation; dictionaryAi.append(p); })
    .catch((error) => { dictionaryAi.innerHTML = '<b>AI 当前无法生成案例</b>'; const p = document.createElement('p'); p.textContent = error.message; dictionaryAi.append(p); });
}

playCircuitButton.addEventListener('click', () => {
  circuitTimers.forEach(clearTimeout); circuitTimers = [];
  const columns = [...circuitViewport.querySelectorAll('.circuit-column')];
  playCircuitButton.disabled = true; playCircuitButton.textContent = '正在播放…';
  columns.forEach((column, index) => circuitTimers.push(setTimeout(() => column.click(), index * 900)));
  circuitTimers.push(setTimeout(() => { playCircuitButton.disabled = false; playCircuitButton.textContent = '重新播放线路'; }, columns.length * 900));
});

document.querySelector('#close-dictionary').addEventListener('click', () => dictionaryDialog.close());
dictionaryDialog.addEventListener('click', (event) => { if (event.target === dictionaryDialog) dictionaryDialog.close(); });

async function loadHardwareStatus() {
  try {
    const response = await fetch('/api/backends', { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const backend = data.backends && data.backends[0];
    if (backend && backend.configured) {
      hardwareStatusText.textContent = '已配置；提交前会再次确认费用和排队';
      hardwareStatusText.dataset.ready = 'true';
    } else {
      hardwareStatusText.textContent = `未连接：${(backend && backend.missing || []).join('、') || '缺少真机配置'}`;
      hardwareStatusText.dataset.ready = 'false';
    }
  } catch (_) {
    hardwareStatusText.textContent = '无法读取真机连接状态';
    hardwareStatusText.dataset.ready = 'false';
  }
}

document.querySelectorAll('input[name="execution-mode"]').forEach((input) => input.addEventListener('change', () => {
  const hardware = document.querySelector('input[name="execution-mode"]:checked').value === 'hardware';
  hardwareBackendWrap.classList.toggle('hidden', !hardware);
  document.querySelector('#target').closest('label').classList.toggle('hidden', hardware);
  const actionTitle = document.querySelector('.primary-action b');
  const actionCopy = document.querySelector('.primary-action div span');
  actionTitle.textContent = hardware ? '量子真机需要凭证并可能产生费用' : '不需要账号，不产生费用';
  actionCopy.textContent = hardware ? '只有在你二次确认后才会创建真实云任务' : '首次体验默认在你的电脑本地模拟运行';
}));

loadHardwareStatus();

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
renderCircuit();
if (conversationHistory.length) {
  designStage.classList.remove('hidden');
  const restoredAnswer = [...conversationHistory].reverse().find((item) => item.role === 'assistant');
  renderExplanation(restoredAnswer ? restoredAnswer.content : '已恢复本次探索记录。');
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
  renderCircuit();
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
    renderExplanation(data.reply);
    currentQasm = data.qasm || '';
    currentTranslations = data.translations || null;
    currentCircuit = data.circuit || null;
    renderTranslations();
    renderCircuit();
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
  renderExplanation(SAMPLE_EXPLANATION);
  lastAgentReply = SAMPLE_EXPLANATION;
  currentQasm = SAMPLE_QASM;
  currentTranslations = null;
  currentCircuit = {
    qubits: 2,
    classical_bits: 2,
    gates: ['h', 'cx'],
    measurements: 2,
    operations: [
      { name: 'h', qubits: [0], parameter: null },
      { name: 'cx', qubits: [0, 1], parameter: null },
    ],
    measurement_map: [[0, 0], [1, 1]],
  };
  renderTranslations();
  renderCircuit();
  runButton.disabled = false;
  copyButton.disabled = false;
  statusBadge.textContent = '固定示例 · 未调用 AI';
  statusBadge.className = 'badge warning';
  setOrb(agentOrb, 'idle');
  demoFallback.classList.add('hidden');
});

runButton.addEventListener('click', async () => {
  const executionMode = document.querySelector('input[name="execution-mode"]:checked').value;
  if (executionMode === 'hardware' && !hardwareConfirmed) {
    if (hardwareStatusText.dataset.ready !== 'true') {
      statusBadge.textContent = '真机未连接';
      statusBadge.className = 'badge warning';
      explanation.textContent += '\n\n真机任务没有提交。请先按文档安装 Amazon Braket SDK，并在启动 LoomQ 的终端中配置 AWS 凭证、Device ARN 和 S3 存储桶。';
      return;
    }
    hardwareConfirm.showModal();
    return;
  }
  hardwareConfirmed = false;
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
        execution_mode: executionMode,
        hardware_backend: document.querySelector('#hardware-backend').value,
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
    const realHardware = result.meta && result.meta.execution_type === 'real_hardware';
    runMeta.textContent = isDemo
      ? '示例结果 · 非真实运行'
      : realHardware
        ? `量子真机 · ${Number(result.shots).toLocaleString()} 次 · job ${result.job_id}`
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
  resultTableBody.replaceChildren();
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
    const tableRow = document.createElement('tr');
    const stateCell = document.createElement('th'); stateCell.scope = 'row'; const code = document.createElement('code'); code.textContent = state; stateCell.append(code);
    const countCell = document.createElement('td'); countCell.textContent = Number(count).toLocaleString();
    const rateCell = document.createElement('td'); rateCell.textContent = `${(probability * 100).toFixed(2)}%`;
    tableRow.append(stateCell, countCell, rateCell); resultTableBody.append(tableRow);
  });
  resultTotal.textContent = Number(result.shots).toLocaleString();

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
  renderCircuit();
  demoMode = false;
  setOrb(agentOrb, 'idle');
  setJourney(1);
  scrollToStage(curiosityStage);
});

document.querySelector('#cancel-hardware').addEventListener('click', () => hardwareConfirm.close());
document.querySelector('#confirm-hardware').addEventListener('click', () => {
  hardwareConfirm.close();
  hardwareConfirmed = true;
  runButton.click();
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
