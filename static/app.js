/* ==========================================================================
   AI 面试陪练 — interaction & motion layer
   ========================================================================== */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const DIMS = ["专业能力", "逻辑表达", "沟通协作", "应变能力", "岗位匹配"];
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(url, opts = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || "请求失败");
  return data;
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmtTime(iso) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const typeName = (t) =>
  ({ technical: "专业题", behavioral: "行为题", situational: "情景题", general: "通用题" }[t] || "通用题");

/* 目标岗位为空时回退到方向名，避免出现「技术开发 · 技术开发」 */
const jobLabel = (s) => (s.target_job && s.target_job !== s.family_name ? s.target_job : s.family_name);
const metaLine = (s) =>
  [jobLabel(s) !== s.family_name ? s.family_name : null, s.level].filter(Boolean).join(" · ");

/* ---------- motion primitives ---------- */
function countUp(el, to, dur = 1100, suffix = "") {
  if (REDUCED) { el.textContent = to + suffix; return; }
  const t0 = performance.now();
  const tick = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    const e = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(to * e) + suffix;
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function paint(el) {
  if (el.dataset.meter) el.style.setProperty("--w", el.dataset.meter + "%");
  $$("[data-count]", el).forEach((n) => countUp(n, parseFloat(n.dataset.count), 1100, n.dataset.suffix || ""));
  $$("[data-final]", el).forEach((n) => countUp(n, parseFloat(n.dataset.final), 1200));
}

const io = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("is-in");
      paint(e.target);
      io.unobserve(e.target);
    });
  },
  { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
);

function initReveal(root = document) {
  if (!("IntersectionObserver" in window)) {
    $$(".reveal", root).forEach((el) => { el.classList.add("is-in"); paint(el); });
    return;
  }
  $$(".reveal", root).forEach((el) => io.observe(el));
  /* dynamic content that is already on screen */
  $$(".meter__fill", root).forEach((f) => {
    requestAnimationFrame(() => { f.style.width = (f.dataset.v || 0) + "%"; });
  });
}

/* ---------- chrome ---------- */
function initNav() {
  const nav = $("[data-nav]");
  if (!nav) return;
  const onScroll = () => nav.classList.toggle("is-stuck", window.scrollY > 8);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

function initTilt() {
  $$("[data-tilt]").forEach((t) => {
    t.addEventListener("pointermove", (e) => {
      const r = t.getBoundingClientRect();
      t.style.setProperty("--mx", ((e.clientX - r.left) / r.width) * 100 + "%");
      t.style.setProperty("--my", ((e.clientY - r.top) / r.height) * 100 + "%");
    });
  });
}

/* ==========================================================================
   Landing — the stage card loop
   ========================================================================== */
const SCENES = [
  {
    tag: "技术开发", idx: "01 / 05",
    q: "请讲一个你遇到的最有挑战的技术项目，你扮演什么角色，最后怎么解决的？",
    a: "项目背景是校园二手交易平台的高并发下单。我负责后端方案设计：用 Redis 缓存热点商品、消息队列削峰，并对订单表做了索引优化。上线后接口 P99 从 2.1 秒降到 280 毫秒。",
    score: 88,
    dims: [{ k: "专业能力", v: 92 }, { k: "逻辑表达", v: 86 }],
  },
  {
    tag: "产品经理", idx: "03 / 05",
    q: "产品上线后日活连续下降，你会怎么分析？",
    a: "先核对数据口径排除异常波动，再按渠道、版本、用户群拆分，观察留存与转化漏斗的变化。最后结合最近的版本改动和竞品动作定位原因，给出可验证的假设。",
    score: 82,
    dims: [{ k: "专业能力", v: 85 }, { k: "逻辑表达", v: 90 }],
  },
  {
    tag: "通用行为", idx: "05 / 05",
    q: "讲一次你和别人协作完成任务的经历，你做了什么？",
    a: "小组做课程项目时，我和队友在技术选型上分歧很大。我先对齐了共同目标，把两个方案的取舍列成表格，用一个小 demo 验证性能差异，最后团队达成一致。",
    score: 76,
    dims: [{ k: "沟通协作", v: 88 }, { k: "应变能力", v: 72 }],
  },
];

const DIAL_C = 2 * Math.PI * 34;

function setDial(score, animate = true) {
  const ring = $("#stageDial");
  const txt = $("#stageScore");
  if (!ring) return;
  ring.style.transition = animate && !REDUCED ? "stroke-dashoffset 1s cubic-bezier(.16,1,.3,1)" : "none";
  ring.style.strokeDashoffset = DIAL_C * (1 - score / 100);
  if (animate) countUp(txt, score, 1000);
  else txt.textContent = score;
}

async function typeInto(el, text, speed = 16) {
  el.innerHTML = "";
  const span = document.createElement("span");
  el.appendChild(span);
  if (REDUCED) { span.textContent = text; return; }
  const caret = document.createElement("span");
  caret.className = "stage__caret";
  el.appendChild(caret);
  for (let i = 0; i < text.length; i++) {
    span.textContent += text[i];
    if (i % 2 === 0) await sleep(speed);
    if (document.hidden) { span.textContent = text; break; }
  }
  await sleep(420);
  caret.remove();
}

function renderStageDims(dims) {
  const box = $("#stageDims");
  if (!box) return;
  box.innerHTML = dims.map((d) => `<div class="mini-bar"><span>${d.k}</span><i></i></div>`).join("");
  $$("i", box).forEach((bar, i) => {
    setTimeout(() => bar.style.setProperty("--w", dims[i].v + "%"), 130 * i + 60);
  });
}

async function runStage() {
  const q = $("#stageQ");
  if (!q) return;
  let i = 0;
  for (;;) {
    if (document.hidden) { await sleep(900); continue; }
    const s = SCENES[i % SCENES.length];
    $("#stageTag").textContent = s.tag;
    $("#stageIdx").textContent = s.idx;

    q.style.transition = "opacity .45s cubic-bezier(.16,1,.3,1)";
    q.style.opacity = "0";
    await sleep(REDUCED ? 0 : 380);
    q.textContent = s.q;
    q.style.opacity = "1";

    $("#stageDims").innerHTML = "";
    setDial(0, false);
    $("#stageA").innerHTML = "";
    if (REDUCED) {
      $("#stageA").textContent = s.a;
      setDial(s.score, false);
      renderStageDims(s.dims);
      await sleep(4000);
    } else {
      await typeInto($("#stageA"), s.a);
      setDial(s.score);
      renderStageDims(s.dims);
      await sleep(4200);
    }
    i++;
  }
}

/* ==========================================================================
   Pages
   ========================================================================== */
const page = document.body.dataset.page;

/* ---------- dashboard ---------- */
if (page === "dashboard") {
  let family = null;
  const tip = $("#save-tip");

  api("/api/profile").then(({ profile: p }) => {
    $("#pf-name").value = p.name || "";
    $("#pf-job").value = p.target_job || "";
    $("#pf-level").value = p.level || "校招";
    $("#pf-exp").value = p.experience || "";
    if (p.job_family) {
      const card = $(`.pick[data-family="${p.job_family}"]`);
      if (card) { card.classList.add("is-active"); family = p.job_family; $("#start-btn").disabled = false; }
    }
  }).catch(() => {});

  $$(".pick").forEach((card) => {
    card.addEventListener("click", () => {
      $$(".pick").forEach((c) => c.classList.remove("is-active"));
      card.classList.add("is-active");
      family = card.dataset.family;
      $("#start-btn").disabled = false;
    });
  });

  $("#save-profile").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      await api("/api/profile", {
        method: "POST",
        body: JSON.stringify({
          name: $("#pf-name").value,
          target_job: $("#pf-job").value,
          level: $("#pf-level").value,
          experience: $("#pf-exp").value,
          job_family: family || undefined,
        }),
      });
      tip.textContent = "已保存";
      tip.className = "badge badge--gold";
    } catch (err) {
      tip.textContent = "保存失败";
      tip.className = "badge";
    } finally {
      btn.disabled = false;
    }
  });

  $("#start-btn").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    const label = btn.innerHTML;
    btn.textContent = "正在生成题目…";
    try {
      const d = await api("/api/session/start", {
        method: "POST",
        body: JSON.stringify({ job_family: family || "general" }),
      });
      location.href = "/interview/" + d.session_id;
    } catch (err) {
      alert("开始失败：" + err.message);
      btn.disabled = false;
      btn.innerHTML = label;
    }
  });
}

/* ---------- interview ---------- */
if (page === "interview") {
  const sid = location.pathname.split("/").pop();
  const stage = $("#stage");

  function setHead(s) {
    $("#ivTitle").textContent =
      jobLabel(s) === s.family_name ? s.family_name : `${jobLabel(s)} · ${s.family_name}`;
    $("#ivMeta").innerHTML = `
      <span class="badge badge--gold mono">${esc(s.level)}</span>
      <span>第 ${s.current_index + 1} / ${s.total} 题</span>
      <span class="muted">已答 ${s.answered} 题</span>`;
    $("#progressFill").style.width = (s.answered / s.total) * 100 + "%";
  }

  async function load() {
    const d = await api("/api/session/" + sid);
    setHead(d.session);
    renderQuestion(d.question);
  }

  function renderQuestion(q) {
    if (!q) { stage.innerHTML = `<div class="panel empty">本场面试已结束</div>`; return; }
    stage.innerHTML = `
      <div class="panel qcard">
        <div class="qcard__meta">
          <span class="badge badge--gold mono">${typeName(q.type)}</span>
          <span class="badge badge--muted mono">难度 ${"★".repeat(q.difficulty)}${"☆".repeat(3 - q.difficulty)}</span>
        </div>
        <h2 class="qcard__title">${esc(q.title)}</h2>
      </div>
      <div class="answer-area">
        <textarea class="textarea" id="answer" rows="7" placeholder="组织好语言再作答：先说背景，再说你的动作，最后给出结果和数据…"></textarea>
        <span class="answer-area__count" id="answerCount">0 字</span>
      </div>
      <div class="cta-row" style="margin-top:1.25rem">
        <button class="btn btn--primary btn--lg" id="submit-btn" type="button">提交回答，获取点评</button>
      </div>`;
    const ta = $("#answer");
    ta.addEventListener("input", () => {
      $("#answerCount").textContent = ta.value.trim().length + " 字";
      ta.style.height = "auto";
      ta.style.height = Math.max(190, ta.scrollHeight) + "px";
    });
    $("#submit-btn").addEventListener("click", submit);
    ta.focus();
  }

  async function submit() {
    const content = $("#answer").value.trim();
    if (!content) { $("#answer").focus(); return; }
    const btn = $("#submit-btn");
    btn.disabled = true;
    btn.textContent = "面试官点评中…";
    try {
      const d = await api(`/api/session/${sid}/answer`, { method: "POST", body: JSON.stringify({ content }) });
      renderResult(d.result, d.finished, d);
    } catch (err) {
      alert("提交失败：" + err.message);
      btn.disabled = false;
      btn.textContent = "提交回答，获取点评";
    }
  }

  function renderResult(r, finished, d) {
    $("#progressFill").style.width = (d.answered / d.total) * 100 + "%";
    const meta = $("#ivMeta");
    if (meta.children[2]) meta.children[2].textContent = `已答 ${d.answered} 题`;
    stage.innerHTML = `
      <div class="verdict reveal">
        <div class="verdict__top">
          <div class="verdict__score">
            <span class="verdict__num num" data-final="${r.score}">0</span>
            <span class="badge ${r.graded_by === "ai" ? "badge--gold" : "badge--muted"} mono">
              ${r.graded_by === "ai" ? "AI 深度点评" : "离线规则点评"}
            </span>
            ${r.band ? `<span class="badge badge--gold mono">${esc(r.band)}</span>` : ""}
          </div>
          <p class="verdict__note"><strong>本题得分 ${r.score} / 100.</strong> 下面是这一次回答的拆解——先看优点，再看下一句该怎么改。</p>
        </div>
        <div class="cols2">
          <div class="fb fb--good">
            <div class="fb__head"><span class="fb__dot"></span>做得好的</div>
            <ul>${(r.strengths.length ? r.strengths : ["完成作答"]).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
          </div>
          <div class="fb fb--bad">
            <div class="fb__head"><span class="fb__dot"></span>可以改进的</div>
            <ul>${r.improvements.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
          </div>
        </div>
        ${(r.evidence && r.evidence.length) ? `<details class="drawer"><summary>面试官依据</summary><div class="drawer__body">${r.evidence.map((e) => `<p style="margin:0 0 .5rem">“${esc(e)}”</p>`).join("")}</div></details>` : ""}
        ${r.sample ? `<details class="drawer"><summary>查看更好的回答示例</summary><div class="drawer__body">${esc(r.sample)}</div></details>` : ""}
      </div>
      <div class="cta-row">
        ${finished
          ? `<a class="btn btn--primary btn--lg" href="/report/${sid}">查看完整面试报告 →</a>`
          : `<button class="btn btn--primary btn--lg" id="next-btn" type="button">下一题 →</button>`}
      </div>`;
    initReveal(stage);
    const next = $("#next-btn");
    if (next) next.addEventListener("click", () => load().catch((e) => alert("加载失败：" + e.message)));
    window.scrollTo({ top: 0, behavior: REDUCED ? "auto" : "smooth" });
  }

  load().catch((e) => { stage.innerHTML = `<div class="panel empty">加载失败：${esc(e.message)}</div>`; });
}

/* ---------- report ---------- */
if (page === "report") {
  const sid = location.pathname.split("/").pop();
  const root = $("#reportStage");

  const qaHtml = (a) => `
    <article class="panel reveal" style="margin-bottom:1rem">
      <div class="qcard__meta">
        <span class="badge badge--gold mono">${typeName(a.question_type)}</span>
        <span class="badge badge--muted mono">得分 ${a.score}</span>
        <span class="badge badge--muted mono">${a.graded_by === "ai" ? "AI" : "离线"}</span>
      </div>
      <h3 style="font-family:var(--serif);font-size:1.2rem;line-height:1.4;margin-bottom:1rem">${esc(a.question_title)}</h3>
      <div class="field__label" style="margin-bottom:0.5rem">你的回答</div>
      <div class="drawer__body" style="border-left-color:var(--line-2)">${esc(a.content)}</div>
      <div class="cols2">
        <div class="fb fb--good">
          <div class="fb__head"><span class="fb__dot"></span>做得好的</div>
          <ul>${(a.strengths || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
        </div>
        <div class="fb fb--bad">
          <div class="fb__head"><span class="fb__dot"></span>可以改进的</div>
          <ul>${(a.improvements || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
        </div>
      </div>
      ${a.sample ? `<details class="drawer"><summary>参考示例</summary><div class="drawer__body">${esc(a.sample)}</div></details>` : ""}
    </article>`;

  api(`/api/session/${sid}/result`).then((d) => {
    const s = d.session;
    const rank = [...DIMS].sort((a, b) => (s.dimensions[b] ?? 0) - (s.dimensions[a] ?? 0));
    const strongest = rank.slice(0, 2);
    const weakest = rank.slice(-2).reverse();
    root.innerHTML = `
      <header class="page-head">
        <a class="crumb" href="/history">← 返回历史</a>
        <span class="eyebrow" style="display:flex;margin-top:1.25rem">Interview Report</span>
        <h1 style="margin-top:1rem">${esc(jobLabel(s))} · 面试报告</h1>
        <p class="lede">${esc(metaLine(s))} · ${fmtTime(s.created_at)} · 共 ${d.answers.length} 题</p>
      </header>
      <section class="panel reveal" style="margin-bottom:2rem">
        <div class="verdict__top">
          <div class="verdict__score">
            <span class="verdict__num num" data-final="${s.total_score}">0</span>
            <span class="badge badge--gold mono">平均分</span>
          </div>
          <div style="min-width:0">
            <p class="verdict__note" style="margin:0 0 1rem;max-width:76ch">${esc(s.summary)}</p>
            <div class="chiprow">
              ${(d.report && d.report.band) ? `<span class="badge badge--gold mono">整体 · ${esc(d.report.band)}</span>` : ""}
              <span class="badge badge--muted mono">优势 · ${esc(strongest.join(" / "))}</span>
              <span class="badge badge--muted mono">待提升 · ${esc(weakest.join(" / "))}</span>
            </div>
          </div>
        </div>
        <div class="meters" style="margin-top:1.6rem">
          ${DIMS.map((dim) => `
            <div class="meter">
              <span class="meter__label">${dim}</span>
              <div class="meter__track"><div class="meter__fill" data-v="${s.dimensions[dim] ?? 0}"></div></div>
              <span class="meter__val">${s.dimensions[dim] ?? "-"}</span>
            </div>`).join("")}
        </div>
        ${(d.report && d.report.dimension_analysis && d.report.dimension_analysis.length) ? `
        <div class="panel__head" style="margin-top:2rem"><span class="panel__title">维度解读</span></div>
        <div class="tiplist">${d.report.dimension_analysis.map((x) => `<li><strong>${esc(x.dimension)} ${x.score} · ${esc(x.label)}</strong><br>${esc(x.note)}</li>`).join("")}</div>` : ""}
        ${(d.tips && d.tips.length) ? `
        <div class="panel__head" style="margin-top:2rem"><span class="panel__title">训练计划</span></div>
        <ol class="tiplist">${d.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ol>` : ""}
        <div class="cta-row no-print" style="margin-top:1.9rem">
          <a class="btn btn--primary" href="/dashboard">再来一场</a>
          <button class="btn" type="button" onclick="window.print()">打印 / 导出 PDF</button>
        </div>
      </section>
      <h2 class="h2" style="margin:0 0 1.25rem">逐题回顾</h2>
      ${d.answers.map(qaHtml).join("")}`;
    initReveal(root);
  }).catch((e) => { root.innerHTML = `<div class="panel empty">加载失败：${esc(e.message)}</div>`; });
}

/* ---------- history ---------- */
if (page === "history") {
  api("/api/history").then((d) => {
    const body = $("#historyBody");
    if (!d.sessions.length) {
      body.innerHTML = `<tr><td colspan="6"><div class="empty">
        <div class="empty__mark">◎</div>
        还没有面试记录，<a href="/dashboard">去练一场</a>
      </div></td></tr>`;
      return;
    }
    body.innerHTML = d.sessions.map((s) => `
      <tr>
        <td class="when">${fmtTime(s.created_at)}</td>
        <td>${esc(jobLabel(s))}</td>
        <td class="hide-sm muted">${jobLabel(s) === s.family_name ? "—" : esc(s.family_name)}</td>
        <td>${s.status === "finished"
          ? `<span class="badge badge--gold mono">已完成</span>`
          : `<span class="badge badge--muted mono">进行中</span>`}</td>
        <td>${s.status === "finished" ? `<span class="score">${s.total_score}</span>` : `<span class="muted">—</span>`}</td>
        <td style="text-align:right">${s.status === "finished"
          ? `<a class="btn btn--sm" href="/report/${s.id}">查看报告</a>`
          : `<a class="btn btn--sm btn--primary" href="/interview/${s.id}">继续作答</a>`}</td>
      </tr>`).join("");
  }).catch((e) => {
    $("#historyBody").innerHTML = `<tr><td colspan="6"><div class="empty">加载失败：${esc(e.message)}</div></td></tr>`;
  });
}

/* ---------- insights ---------- */
if (page === "insights") {
  const li = (s) => `<li>${esc(s)}</li>`;
  api("/api/insights").then((d) => {
    $("#kpiCount").textContent = d.sessions;
    $("#kpiAvg").textContent = d.sessions ? d.avg_total : "–";
    if (!d.sessions) return;

    const delta = d.trend_delta || 0;
    const trendEl = $("#kpiTrend");
    trendEl.textContent = (delta > 0 ? "+" : "") + delta;
    trendEl.dataset.dir = delta >= 0 ? "up" : "down";
    $("#insightTip").textContent = `最近 3 场平均 ${d.recent_avg} 分：首场 ${d.first_score} → 最新 ${d.last_score}。面积越饱满，说明该维度越稳。`;

    const strength = $("#strengthList");
    const weakness = $("#weaknessList");
    const plan = $("#planList");
    if (strength) strength.innerHTML = (d.strongest || []).map((n) => li(`${n} · ${d.dims[n] || 0} 分`)).join("") || li("暂无数据");
    if (weakness) weakness.innerHTML = (d.weakest || []).map((n) => li(`${n} · ${d.dims[n] || 0} 分`)).join("") || li("暂无数据");
    if (plan) plan.innerHTML = (d.recommendations || []).map(li).join("") || li("保持练习，积累更多数据后生成计划。");

    if (typeof echarts === "undefined") return;

    const chart = echarts.init($("#radar"), null, { renderer: "canvas" });
    chart.setOption({
      backgroundColor: "transparent",
      tooltip: {
        backgroundColor: "rgba(14,14,19,.96)",
        borderColor: "rgba(244,241,234,.14)",
        textStyle: { color: "#f4f1ea", fontSize: 12 },
      },
      radar: {
        center: ["50%", "54%"],
        radius: "68%",
        splitNumber: 4,
        axisName: { color: "rgba(244,241,234,.62)", fontSize: 12, fontFamily: "Inter" },
        indicator: DIMS.map((name) => ({ name, max: 100 })),
        splitLine: { lineStyle: { color: "rgba(244,241,234,.10)" } },
        splitArea: { areaStyle: { color: ["transparent", "rgba(244,241,234,.015)"] } },
        axisLine: { lineStyle: { color: "rgba(244,241,234,.12)" } },
      },
      series: [{
        type: "radar",
        symbolSize: 7,
        data: [{
          value: DIMS.map((n) => d.dims[n] || 0),
          name: "平均能力",
          lineStyle: { color: "#e4b054", width: 2 },
          itemStyle: { color: "#f7d78f" },
          areaStyle: {
            color: {
              type: "radial", x: 0.5, y: 0.5, r: 0.8,
              colorStops: [
                { offset: 0, color: "rgba(228,176,84,.42)" },
                { offset: 1, color: "rgba(228,176,84,.06)" },
              ],
            },
          },
        }],
        animationDuration: REDUCED ? 0 : 900,
        animationEasing: "cubicOut",
      }],
    });
    window.addEventListener("resize", () => chart.resize());
  }).catch((e) => { $("#insightTip").textContent = "加载失败：" + e.message; });
}

/* ---------- boot ---------- */
initNav();
initTilt();
initReveal();
if (page === "landing") runStage();
