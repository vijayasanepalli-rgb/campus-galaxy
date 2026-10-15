/* Campus Galaxy front-end helpers */
const PALETTE = {violet: "#6c5ce7", violet2: "#8c7bff", cyan: "#35c6f4", pink: "#ff6fb5", grid: "#eceefb", text: "#6a6f94"};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}
/* tiny markdown: **bold**, [text](https://...), "- " bullets, newlines. Input is escaped first. */
function md(text) {
  let h = esc(text);
  h = h.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  h = h.replace(/^- (.*)$/gm, "&bull; $1");
  return h.replace(/\n/g, "<br>");
}

/* ---------- charts: dependency-free SVG, kept deliberately simple ---------- */
function _svgBox(id){const el=document.getElementById(id);if(!el)return null;const box=el.parentNode;box.innerHTML="";return box;}
function _axes(W,H,L,B,T,R){let g="";for(const v of [0,25,50,75,100]){const y=T+(H-T-B)*(1-v/100);
  g+=`<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke="${PALETTE.grid}"/><text x="${L-8}" y="${y+4}" text-anchor="end" font-size="11" fill="${PALETTE.text}">${v}</text>`;}return g;}
function _short(t){t=String(t);return t.length>12?t.slice(0,11)+"…":t;}
function lineChart(id,labels,data,label){
  const box=_svgBox(id);if(!box)return;const W=520,H=260,L=40,B=34,T=14,R=40,n=data.length;
  const X=i=>n===1?(L+W-R)/2:L+(W-L-R)*i/(n-1),Y=v=>T+(H-T-B)*(1-v/100);
  const pts=data.map((v,i)=>[X(i),Y(v)]);
  let h=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="100%" role="img" aria-label="${esc(label)}">${_axes(W,H,L,B,T,R)}`;
  h+=`<path d="M${pts[0][0]},${Y(0)} L${pts.map(p=>p.join(",")).join(" L")} L${pts[n-1][0]},${Y(0)}Z" fill="rgba(108,92,231,.12)"/>`;
  h+=`<polyline points="${pts.map(p=>p.join(",")).join(" ")}" fill="none" stroke="${PALETTE.violet}" stroke-width="3" stroke-linejoin="round"/>`;
  pts.forEach((p,i)=>{h+=`<circle cx="${p[0]}" cy="${p[1]}" r="5" fill="#fff" stroke="${PALETTE.violet}" stroke-width="2.5"><title>${esc(labels[i])}: ${data[i]}</title></circle>`;
    h+=`<text x="${p[0]}" y="${p[1]-11}" text-anchor="middle" font-size="12" font-weight="600" fill="#1b1f4b">${Math.round(data[i])}</text>`;
    h+=`<text x="${p[0]}" y="${H-12}" text-anchor="middle" font-size="12" fill="${PALETTE.text}">${esc(_short(labels[i]))}</text>`;});
  box.innerHTML=h+"</svg>";
}
function barChart(id,labels,data,label,lowCut){
  const box=_svgBox(id);if(!box)return;const cut=lowCut===undefined?50:lowCut;
  const W=520,H=260,L=34,B=44,T=14,R=10,n=data.length,slot=(W-L-R)/n,bw=Math.min(46,slot*.6);
  let h=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="100%" role="img" aria-label="${esc(label)}">${_axes(W,H,L,B,T,R)}`;
  data.forEach((v,i)=>{const x=L+slot*i+(slot-bw)/2,y=T+(H-T-B)*(1-v/100),hh=H-B-y;
    h+=`<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(hh,0)}" rx="7" fill="${v<cut?PALETTE.pink:PALETTE.violet2}"><title>${esc(labels[i])}: ${v}</title></rect>`;
    h+=`<text x="${x+bw/2}" y="${y-5}" text-anchor="middle" font-size="12" font-weight="600" fill="#1b1f4b">${Math.round(v)}</text>`;
    const lab=_short(labels[i]).split(" ");h+=`<text text-anchor="middle" font-size="11" fill="${PALETTE.text}"><tspan x="${x+bw/2}" y="${H-24}">${esc(lab[0])}</tspan>${lab[1]?`<tspan x="${x+bw/2}" dy="13">${esc(lab.slice(1).join(" "))}</tspan>`:""}</text>`;});
  box.innerHTML=h+"</svg>";
}
function donutChart(id,labels,data,colors){
  const box=_svgBox(id);if(!box)return;colors=colors||[PALETTE.violet,PALETTE.cyan,"#f6c453",PALETTE.pink];
  const tot=data.reduce((a,b)=>a+b,0)||1,R=80,r=52,cx=110,cy=110;let a0=-Math.PI/2,h=`<div style="display:flex;align-items:center;gap:24px;height:100%;justify-content:center;flex-wrap:wrap"><svg viewBox="0 0 220 220" width="220" height="220" role="img">`;
  data.forEach((v,i)=>{if(!v)return;const a1=a0+2*Math.PI*v/tot,big=a1-a0>Math.PI?1:0,p=(rad,a)=>[cx+rad*Math.cos(a),cy+rad*Math.sin(a)];
    const [x1,y1]=p(R,a0),[x2,y2]=p(R,a1-.0001),[x3,y3]=p(r,a1-.0001),[x4,y4]=p(r,a0);
    h+=`<path d="M${x1},${y1} A${R},${R} 0 ${big} 1 ${x2},${y2} L${x3},${y3} A${r},${r} 0 ${big} 0 ${x4},${y4}Z" fill="${colors[i%colors.length]}" stroke="#fff" stroke-width="3"><title>${esc(labels[i])}: ${v}</title></path>`;a0=a1;});
  h+=`<text x="${cx}" y="${cy+2}" text-anchor="middle" font-size="30" font-weight="700" fill="#1b1f4b">${tot}</text><text x="${cx}" y="${cy+20}" text-anchor="middle" font-size="12" fill="${PALETTE.text}">students</text></svg><div>`;
  labels.forEach((l,i)=>{h+=`<div style="margin:7px 0;font-size:14px"><i style="display:inline-block;width:11px;height:11px;border-radius:3px;background:${colors[i%colors.length]};margin-right:8px"></i>${esc(l)} <b>${data[i]}</b></div>`;});
  box.innerHTML=h+"</div></div>";
}

/* ---------- AI copilot ---------- */
function initCopilot() {
  const box = document.getElementById("msgs"); if (!box) return;
  const input = document.getElementById("chat-input"), form = document.getElementById("chat-form");
  const chipBox = document.getElementById("chat-chips");
  function add(text, who) {
    const d = document.createElement("div"); d.className = "msg " + who; d.innerHTML = md(text);
    box.appendChild(d); box.scrollTop = box.scrollHeight; return d;
  }
  function setChips(list) {
    chipBox.innerHTML = "";
    (list || []).forEach(c => { const b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.textContent = c;
      b.onclick = () => ask(c); chipBox.appendChild(b); });
  }
  async function ask(text) {
    if (!text.trim()) return;
    add(text, "me"); input.value = "";
    const wait = add("Thinking...", "bot");
    try {
      const r = await fetch("/api/copilot", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: text})});
      const d = await r.json(); wait.innerHTML = md(d.text); setChips(d.chips);
    } catch (e) { wait.textContent = "Sorry, I couldn't reach the server. Please try again."; }
    box.scrollTop = box.scrollHeight;
  }
  form.addEventListener("submit", e => { e.preventDefault(); ask(input.value); });
  document.querySelectorAll("[data-ask]").forEach(b => b.addEventListener("click", () => ask(b.dataset.ask)));
  add(window.COPILOT_HELLO || "Hi! Ask me anything.", "bot");
}

/* ---------- MCQ timer ---------- */
function initTimer(minutes, formId) {
  const el = document.getElementById("timer"); if (!el) return;
  let left = minutes * 60;
  const tick = () => {
    const m = String(Math.floor(left / 60)).padStart(2, "0"), s = String(left % 60).padStart(2, "0");
    el.textContent = "Time left " + m + ":" + s;
    if (left-- <= 0) { clearInterval(t); document.getElementById(formId).submit(); }
  };
  const t = setInterval(tick, 1000); tick();
}

/* ---------- coding exam IDE ---------- */
function initIDE(problems) {
  const ta = document.getElementById("code"); if (!ta) return;
  const out = document.getElementById("console"), results = document.getElementById("results");
  const scorebox = document.getElementById("scorebox");
  const runBtn = document.getElementById("run"), subBtn = document.getElementById("submit");
  const drafts = {}; let cur = problems[0];

  function select(p) {
    if (cur) drafts[cur.id] = ta.value;
    cur = p; ta.value = drafts[p.id] ?? p.starter;
    document.getElementById("ptitle").textContent = p.title;
    document.getElementById("pstate").textContent = p.points + " points";
    document.getElementById("pstatement").textContent = p.statement;
    document.getElementById("psamples").innerHTML = p.sample.map((c, i) =>
      `<div class="case"><b>Sample ${i + 1}</b><pre>Input:\n${esc(c.in)}\nExpected output:\n${esc(c.out)}</pre></div>`).join("");
    document.querySelectorAll(".plist button").forEach(b => b.classList.toggle("on", +b.dataset.id === p.id));
    results.innerHTML = ""; out.textContent = "Output appears here."; scorebox.style.display = "none";
  }
  document.querySelectorAll(".plist button").forEach(b => b.addEventListener("click", () => select(problems.find(p => p.id === +b.dataset.id))));
  ta.addEventListener("keydown", e => {
    if (e.key === "Tab") { e.preventDefault(); const s = ta.selectionStart; ta.setRangeText("    ", s, ta.selectionEnd, "end"); }
  });

  function show(data, submitted) {
    results.innerHTML = ""; out.textContent = "";
    if (data.error) { out.textContent = data.error; return; }
    if (data.compile_error) { out.textContent = "Compilation error:\n" + data.compile_error; return; }
    out.textContent = submitted ? "Judged against all test cases." : "Ran against the sample test cases.";
    (data.results || []).forEach(r => {
      const d = document.createElement("div");
      const state = r.passed === null || r.passed === undefined ? "" : (r.passed ? "pass" : "fail");
      d.className = "case " + state;
      let h = `<b>${esc(r.label)}</b> ${r.passed === true ? "✔ passed" : r.passed === false ? "✘ failed" : ""} <span class="muted tiny">${r.ms ?? 0} ms${r.status === "timeout" ? " · time limit exceeded" : ""}</span>`;
      if (r.input !== undefined) h += `<pre>Input:\n${esc(r.input)}</pre>`;
      if (r.expected !== undefined) h += `<pre>Expected:\n${esc(r.expected)}</pre>`;
      if (r.output !== undefined) h += `<pre>Your output:\n${esc(r.output)}</pre>`;
      if (r.stderr) h += `<pre style="color:#b3282d">${esc(r.stderr)}</pre>`;
      d.innerHTML = h; results.appendChild(d);
    });
  }
  async function call(url, body) {
    runBtn.disabled = subBtn.disabled = true; out.textContent = "Running...";
    try {
      const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
      return await r.json();
    } catch (e) { return {error: "Could not reach the server."}; }
    finally { runBtn.disabled = subBtn.disabled = false; }
  }
  runBtn.addEventListener("click", async () => {
    const custom = document.getElementById("stdin").value;
    show(await call("/api/code/run", {problem_id: cur.id, code: ta.value, stdin: custom}), false);
  });
  subBtn.addEventListener("click", async () => {
    const d = await call("/api/code/submit", {problem_id: cur.id, code: ta.value});
    show(d, true);
    if (d.score !== undefined) {
      const gain = (d.success_after - d.success_before).toFixed(1);
      scorebox.style.display = "block";
      scorebox.innerHTML = `<b>${d.passed}/${d.total} test cases passed</b> · scored ${d.score}/${d.points} (best ${d.best}).<br>` +
        `Coding readiness: <b>${d.coding}</b> · Success score: <b>${d.success_after}</b>` + (gain > 0 ? ` <b style="color:#7be3b5">(+${gain})</b>` : "");
      const badge = document.querySelector(`.plist button[data-id="${cur.id}"] .sc`);
      if (badge) badge.textContent = d.best + "/" + d.points;
    }
  });
  select(cur);
}

/* ---------- faculty: dynamic coding problem rows ---------- */
function toggleTestKind() {
  const kind = document.getElementById("kind"); if (!kind) return;
  const mcq = document.getElementById("mcq-box"), code = document.getElementById("code-box");
  mcq.style.display = kind.value === "mcq" ? "block" : "none";
  code.style.display = kind.value === "coding" ? "block" : "none";
}
function addProblem() {
  const tpl = document.getElementById("problem-tpl"); const holder = document.getElementById("problems");
  holder.appendChild(tpl.content.cloneNode(true));
}
document.addEventListener("DOMContentLoaded", () => {
  const k = document.getElementById("kind");
  if (k) { k.addEventListener("change", toggleTestKind); toggleTestKind(); if (!document.querySelector("#problems .card")) addProblem(); }
});
