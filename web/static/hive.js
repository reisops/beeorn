const canvas = document.getElementById("hive-canvas");
const ctx = canvas.getContext("2d");
const API_URL = "http://localhost:5000/api/hive/hive-01/status";

// --- Layout das camadas (de cima pra baixo no desenho) ---
const LAYERS = {
  melgueira: { top: 40, height: 140, color: "#f4e2b8" },
  ninho:     { top: 190, height: 220, color: "#e8c98a" },
  assoalho:  { top: 420, height: 60,  color: "#d9b76f" },
};

let nestBees = [];
let superBees = [];
let entranceBees = [];
let currentStatus = "normal";
let activity = 0.5;

function initBees() {
  nestBees = Array.from({ length: 20 }, () => randomBeeIn(LAYERS.ninho));
  superBees = Array.from({ length: 8 }, () => randomBeeIn(LAYERS.melgueira));
  entranceBees = [];
}

function randomBeeIn(layer) {
  return {
    x: 40 + Math.random() * 420,
    y: layer.top + 10 + Math.random() * (layer.height - 20),
    dx: (Math.random() - 0.5) * 2,
    dy: (Math.random() - 0.5) * 2,
  };
}

function drawBox(layer, label) {
  ctx.fillStyle = layer.color;
  ctx.fillRect(30, layer.top, 440, layer.height);
  ctx.strokeStyle = "#6b4423";
  ctx.lineWidth = 3;
  ctx.strokeRect(30, layer.top, 440, layer.height);
  ctx.fillStyle = "#4a3016";
  ctx.font = "13px sans-serif";
  ctx.fillText(label, 40, layer.top + 16);
}

function drawBee(bee, agitated) {
  ctx.beginPath();
  ctx.arc(bee.x, bee.y, 4.5, 0, Math.PI * 2);
  ctx.fillStyle = agitated ? "#5a3a1a" : "#3a2a1a";
  ctx.fill();
  ctx.strokeStyle = "#f2c14e";
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function moveBee(bee, layer, speed) {
  bee.x += bee.dx * speed;
  bee.y += bee.dy * speed;
  if (bee.x < 40 || bee.x > 460) bee.dx *= -1;
  if (bee.y < layer.top + 8 || bee.y > layer.top + layer.height - 8) bee.dy *= -1;
}

function drawEntranceFlow() {
  // seta indicando fluxo de abelhas na entrada, proporcional à atividade
  const arrows = Math.round(activity * 6);
  ctx.fillStyle = "#4a3016";
  ctx.font = "16px sans-serif";
  for (let i = 0; i < arrows; i++) {
    const x = 60 + i * 60;
    ctx.fillText(i % 2 === 0 ? "🐝→" : "←🐝", x, LAYERS.assoalho.top + 38);
  }
  if (arrows === 0) {
    ctx.fillText("(sem voos — período de repouso)", 130, LAYERS.assoalho.top + 38);
  }
}

function animate() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  drawBox(LAYERS.melgueira, "MELGUEIRA");
  drawBox(LAYERS.ninho, "NINHO");
  drawBox(LAYERS.assoalho, "ENTRADA");

  const agitated = currentStatus === "alerta";
  const speed = agitated ? 3.5 : 1 + activity * 1.5;

  for (const bee of nestBees) {
    moveBee(bee, LAYERS.ninho, speed);
    drawBee(bee, agitated);
  }
  for (const bee of superBees) {
    moveBee(bee, LAYERS.melgueira, speed * 0.4); // melgueira sempre mais calma
    drawBee(bee, false);
  }

  drawEntranceFlow();

  requestAnimationFrame(animate);
}

function renderComposition(data) {
  const parts = [
    { label: "Abelhas", value: (data.population || 0) * 0.0001, color: "#3a2a1a" },
    { label: "Mel", value: data.honey_kg || 0, color: "#f2b134" },
    { label: "Pólen", value: data.pollen_kg || 0, color: "#c9a227" },
    { label: "Néctar", value: data.nectar_kg || 0, color: "#8fbf5f" },
  ];
  const max = Math.max(...parts.map(p => p.value), 1);
  const container = document.getElementById("comp-bars");
  container.innerHTML = "";
  for (const p of parts) {
    const row = document.createElement("div");
    row.className = "comp-row";
    row.innerHTML = `
      <span class="comp-label">${p.label}</span>
      <span class="comp-bar-bg"><span class="comp-bar-fill" style="width:${(p.value / max * 100).toFixed(0)}%; background:${p.color}"></span></span>
      <span>${p.value.toFixed(2)} kg</span>
    `;
    container.appendChild(row);
  }
}

async function fetchStatus() {
  try {
    const res = await fetch(API_URL);
    const data = await res.json();

    currentStatus = data.status || "normal";
    activity = data.activity ?? 0.5;

    document.getElementById("status-badge").textContent =
      currentStatus === "normal" ? "Colônia saudável" :
      currentStatus === "atencao" ? "Atenção" : "Alerta!";
    document.getElementById("status-badge").className = "status-" + currentStatus;

    document.getElementById("weight").textContent = `${data.weight_kg?.toFixed(2)} kg`;
    document.getElementById("temp").textContent = `${data.temp_c?.toFixed(1)} °C`;
    document.getElementById("humidity").textContent = `${data.humidity_pct?.toFixed(1)} %`;
    document.getElementById("population").textContent = `${data.population?.toLocaleString("pt-BR")} abelhas`;

    renderComposition(data);

    // menos abelhas visíveis no ninho se a população cair muito (enxameação)
    const nestCount = data.population < 25000 ? 8 : 20;
    if (nestBees.length !== nestCount) {
      nestBees = Array.from({ length: nestCount }, () => randomBeeIn(LAYERS.ninho));
    }

  } catch (err) {
    document.getElementById("status-badge").textContent = "Sem conexão com a API";
  }
}

initBees();
animate();
fetchStatus();
setInterval(fetchStatus, 5000);
