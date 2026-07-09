const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

// ---------- palette (Ocean Gradient, dark-committed for a premium technical feel)
const DEEP = "0A1A2F";     // deep navy background
const PANEL = "112B45";    // card panel
const TEAL = "1C7293";     // primary teal
const SEA = "2EC4B6";      // seafoam accent
const MINT = "7DE2D1";     // light mint
const ICE = "CFE8EF";      // ice text
const WHITE = "FFFFFF";
const MUTE = "8AA6B8";     // muted caption
const AMBER = "F4A259";    // sharp accent (used sparingly)
const RED = "E76F63";      // risk/danger accent

const HEAD = "Cambria";    // safe-list serif header
const BODY = "Calibri";    // safe-list sans body

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color, size: String(size) })
  );
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
const shadow = () => ({ type: "outer", color: "000000", blur: 8, offset: 3, angle: 90, opacity: 0.28 });

(async () => {
  const p = new pptxgen();
  p.layout = "LAYOUT_WIDE";        // 13.3 x 7.5
  p.author = "Abrar Ahnaf";
  p.title = "Hybrid Token-Efficient Routing Agent";
  const W = 13.33, H = 7.5;

  // pre-render icons
  const I = {
    bolt: await icon(fa.FaBolt, "#" + SEA),
    scale: await icon(fa.FaBalanceScale, "#" + SEA),
    route: await icon(fa.FaProjectDiagram, "#" + SEA),
    check: await icon(fa.FaCheckDouble, "#" + SEA),
    gem: await icon(fa.FaGem, "#" + MINT),
    ban: await icon(fa.FaBan, "#" + MINT),
    shield: await icon(fa.FaShieldAlt, "#" + MINT),
    gauge: await icon(fa.FaTachometerAlt, "#" + MINT),
    flask: await icon(fa.FaFlask, "#" + AMBER),
    question: await icon(fa.FaQuestionCircle, "#" + AMBER),
    trophy: await icon(fa.FaTrophy, "#" + AMBER),
    layers: await icon(fa.FaLayerGroup, "#" + SEA),
    server: await icon(fa.FaServer, "#" + MINT),
    lock: await icon(fa.FaLock, "#" + MINT),
  };

  const bg = (s, c = DEEP) => (s.background = { color: c });
  const num = (s, n) => s.addText(String(n).padStart(2, "0"), {
    x: W - 1.1, y: H - 0.6, w: 0.7, h: 0.3, fontFace: BODY, fontSize: 10,
    color: MUTE, align: "right"
  });
  const kicker = (s, t) => s.addText(t.toUpperCase(), {
    x: 0.7, y: 0.55, w: 8, h: 0.3, fontFace: BODY, fontSize: 13, bold: true,
    color: SEA, charSpacing: 3, margin: 0
  });
  const title = (s, t, y = 0.95) => s.addText(t, {
    x: 0.7, y, w: 11.9, h: 1.0, fontFace: HEAD, fontSize: 34, bold: true,
    color: WHITE, margin: 0
  });

  // card helper
  function card(s, x, y, w, h, fill = PANEL) {
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h, rectRadius: 0.09, fill: { color: fill }, shadow: shadow()
    });
  }
  function iconChip(s, data, x, y, d = 0.62, chip = TEAL) {
    s.addShape(p.shapes.OVAL, { x, y, w: d, h: d, fill: { color: chip }, shadow: shadow() });
    const pad = d * 0.26;
    s.addImage({ data, x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad });
  }

  // ============================================================ 1 TITLE
  let s = p.addSlide(); bg(s);
  // faint layered arcs motif (concentric ovals, low opacity) top-right
  [4.2, 3.2, 2.2].forEach((d, i) => s.addShape(p.shapes.OVAL, {
    x: W - 2.4 - d / 2, y: -d / 2 + 1.0, w: d, h: d,
    fill: { color: TEAL, transparency: 88 + i * 3 }
  }));
  s.addText("AMD DEVELOPER HACKATHON · ACT II — TRACK 1", {
    x: 0.8, y: 1.7, w: 11, h: 0.4, fontFace: BODY, fontSize: 15, bold: true,
    color: SEA, charSpacing: 3, margin: 0
  });
  s.addText("Hybrid Token-Efficient\nRouting Agent", {
    x: 0.8, y: 2.25, w: 11.6, h: 2.0, fontFace: HEAD, fontSize: 52, bold: true,
    color: WHITE, lineSpacingMultiple: 0.98, margin: 0
  });
  s.addText("Answer locally for free. Escalate only what you can prove is wrong.", {
    x: 0.82, y: 4.5, w: 11, h: 0.5, fontFace: BODY, fontSize: 20, italic: true,
    color: ICE, margin: 0
  });
  // stat chips
  const chips = [["8", "task categories"], ["0", "tokens for local answers"], ["10 min", "hard runtime budget"]];
  chips.forEach(([big, lab], i) => {
    const x = 0.8 + i * 3.9;
    card(s, x, 5.4, 3.6, 1.35);
    s.addText(big, { x: x + 0.25, y: 5.55, w: 3.1, h: 0.7, fontFace: HEAD, fontSize: 30, bold: true, color: SEA, margin: 0 });
    s.addText(lab, { x: x + 0.27, y: 6.22, w: 3.2, h: 0.4, fontFace: BODY, fontSize: 13, color: ICE, margin: 0 });
  });
  s.addNotes("Open here. This is a Track 1 submission for the AMD Developer Hackathon ACT II. In one line: the agent answers as many tasks as it can on a free local model, and only escalates to the paid Fireworks API the ones it can prove the local model got wrong. Hold the three numbers up: eight categories, zero cost for local answers, ten-minute cap.");

  // ============================================================ 2 THE SCORING
  s = p.addSlide(); bg(s);
  kicker(s, "Why this track is not what it looks like");
  title(s, "The leaderboard measures one thing: remote tokens avoided");
  // two-gate flow
  const gy = 2.35;
  card(s, 0.7, gy, 5.9, 1.7);
  iconChip(s, I.check, 0.95, gy + 0.28, 0.62, TEAL);
  s.addText("Gate 1 — Accuracy", { x: 1.75, y: gy + 0.28, w: 4.6, h: 0.4, fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, margin: 0 });
  s.addText("An LLM judge scores every answer. Below the threshold, the whole submission is excluded from the leaderboard — no partial credit.", {
    x: 0.95, y: gy + 0.78, w: 5.4, h: 0.8, fontFace: BODY, fontSize: 13.5, color: ICE, margin: 0 });

  card(s, 6.85, gy, 5.75, 1.7);
  iconChip(s, I.scale, 7.1, gy + 0.28, 0.62, TEAL);
  s.addText("Gate 2 — Token count", { x: 7.9, y: gy + 0.28, w: 4.5, h: 0.4, fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, margin: 0 });
  s.addText("Among submissions that pass, rank ascending by tokens metered at the Fireworks proxy. Fewer tokens = higher rank.", {
    x: 7.1, y: gy + 0.78, w: 5.3, h: 0.8, fontFace: BODY, fontSize: 13.5, color: ICE, margin: 0 });

  // the twist band
  card(s, 0.7, 4.4, 11.9, 1.75, TEAL);
  iconChip(s, I.bolt, 1.0, 4.72, 0.7, DEEP);
  s.addText("The twist: local tokens count as ZERO", {
    x: 1.95, y: 4.7, w: 10.3, h: 0.5, fontFace: HEAD, fontSize: 22, bold: true, color: WHITE, margin: 0 });
  s.addText("Only calls through the Fireworks API are metered. So the winning move isn't a bigger model or a cleverer prompt — it's answering as much as possible on a free local model and escalating as little as possible. Routing intelligence wins, not raw compute.", {
    x: 1.97, y: 5.3, w: 10.4, h: 0.8, fontFace: BODY, fontSize: 14.5, color: ICE, margin: 0 });
  num(s, 2);
  s.addNotes("The key mental model. Two gates. First accuracy — and it's binary and brutal: below the line and you score nothing at all. Second, token count, ascending. The twist that reframes everything: tokens on a local model in the container are free. So this is an arbitrage problem — a time budget locally versus a token budget remotely.");

  // ============================================================ 3 CASCADE VS ROUTER
  s = p.addSlide(); bg(s);
  kicker(s, "The core design decision");
  title(s, "A verify-then-escalate cascade, not a probabilistic router");
  // left: what others do
  card(s, 0.7, 2.4, 5.9, 3.7);
  s.addText("Off-the-shelf routers", { x: 1.0, y: 2.6, w: 5.3, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true, color: MUTE, margin: 0 });
  [
    "Built to save dollars, not to hit zero",
    "Predict strong-vs-weak before generating",
    "Route probabilistically, then trust the pick",
    "Never check if the answer was actually right",
  ].forEach((t, i) => s.addText(t, { x: 1.0, y: 3.15 + i * 0.62, w: 5.3, h: 0.55, fontFace: BODY, fontSize: 14, color: ICE, bullet: { indent: 14 }, margin: 0 }));
  s.addText("Wrong tool: our cheap tier costs zero, not \u201cless.\u201d", {
    x: 1.0, y: 5.72, w: 5.3, h: 0.4, fontFace: BODY, fontSize: 13, italic: true, color: RED, margin: 0 });

  // right: our cascade
  card(s, 6.85, 2.4, 5.75, 3.7, PANEL);
  s.addText("This agent's cascade", { x: 7.15, y: 2.6, w: 5.2, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true, color: SEA, margin: 0 });
  const steps = [
    ["Classify", "zero-token pattern match \u2192 1 of 8 categories"],
    ["Generate", "small local model answers, at zero cost"],
    ["Verify", "cheap deterministic check on that answer"],
    ["Escalate", "one minimal Fireworks call \u2014 only on failure"],
  ];
  steps.forEach(([h, d], i) => {
    const y = 3.1 + i * 0.72;
    s.addShape(p.shapes.OVAL, { x: 7.15, y, w: 0.44, h: 0.44, fill: { color: TEAL } });
    s.addText(String(i + 1), { x: 7.15, y: y + 0.02, w: 0.44, h: 0.4, align: "center", fontFace: HEAD, fontSize: 16, bold: true, color: WHITE, margin: 0 });
    s.addText([{ text: h + "  ", options: { bold: true, color: WHITE } }, { text: d, options: { color: ICE } }], {
      x: 7.75, y: y - 0.03, w: 4.7, h: 0.5, fontFace: BODY, fontSize: 13.5, valign: "middle", margin: 0 });
  });
  num(s, 3);
  s.addNotes("Why not just use RouteLLM or semantic-router? Because those optimize dollar cost and route blind — they never verify the answer. Both are wrong here: our cheap tier is free, not cheaper, and our whole edge is knowing when the local answer is good enough to keep. So instead: classify for free, generate locally for free, verify deterministically, and escalate only the proven failures. Remote tokens get spent only where we can prove the local model was wrong.");

  // ============================================================ 4 AGREEMENT (hero mechanism)
  s = p.addSlide(); bg(s);
  kicker(s, "The one mechanism worth remembering");
  title(s, "Agreement guards the accuracy gate on math & logic");
  s.addText("A small model's worst failure is a confident wrong answer. Re-checking its arithmetic can't catch a wrong setup \u2014 so math and logic are trusted locally only when two independent samples agree.", {
    x: 0.7, y: 1.95, w: 11.9, h: 0.8, fontFace: BODY, fontSize: 15.5, color: ICE, margin: 0 });

  // flow diagram: sample A / sample B -> agree? -> keep / escalate
  const fy = 3.15;
  function node(x, y, w, h, head, sub, fill, headColor = WHITE) {
    card(s, x, y, w, h, fill);
    s.addText(head, { x: x + 0.2, y: y + 0.18, w: w - 0.4, h: 0.45, fontFace: HEAD, fontSize: 16, bold: true, color: headColor, margin: 0 });
    if (sub) s.addText(sub, { x: x + 0.2, y: y + 0.72, w: w - 0.4, h: 0.7, fontFace: BODY, fontSize: 12.5, color: ICE, margin: 0 });
  }
  node(0.7, fy, 3.0, 1.5, "Sample A", "temperature 0\n(deterministic)", PANEL);
  node(0.7, fy + 1.75, 3.0, 1.5, "Sample B", "temperature 0.7\n(sampling noise)", PANEL);
  // diamond
  s.addShape(p.shapes.DIAMOND, { x: 4.4, y: fy + 0.62, w: 2.6, h: 2.0, fill: { color: TEAL }, shadow: shadow() });
  s.addText("Same final\nanswer?", { x: 4.4, y: fy + 1.15, w: 2.6, h: 0.9, align: "center", fontFace: HEAD, fontSize: 16, bold: true, color: WHITE, margin: 0 });
  // arrows
  s.addShape(p.shapes.LINE, { x: 3.7, y: fy + 0.75, w: 0.7, h: 0.75, line: { color: MUTE, width: 2, endArrowType: "triangle" } });
  s.addShape(p.shapes.LINE, { x: 3.7, y: fy + 2.5, w: 0.7, h: -0.75, line: { color: MUTE, width: 2, endArrowType: "triangle" } });
  // outcomes
  node(7.7, fy - 0.1, 4.9, 1.5, "Agree \u2192 keep, free", "Trusted local answer. Zero remote tokens.", "16513A");
  s.addText("YES", { x: 7.05, y: fy + 0.05, w: 0.7, h: 0.4, fontFace: BODY, fontSize: 12, bold: true, color: SEA, margin: 0 });
  node(7.7, fy + 1.7, 4.9, 1.5, "Disagree \u2192 escalate", "Sent to a strong remote model. A few tokens well spent.", "5A2A2A");
  s.addText("NO", { x: 7.1, y: fy + 1.85, w: 0.7, h: 0.4, fontFace: BODY, fontSize: 12, bold: true, color: RED, margin: 0 });
  s.addShape(p.shapes.LINE, { x: 7.0, y: fy + 0.9, w: 0.7, h: -0.15, line: { color: SEA, width: 2, endArrowType: "triangle" } });
  s.addShape(p.shapes.LINE, { x: 7.0, y: fy + 1.7, w: 0.7, h: 0.75, line: { color: RED, width: 2, endArrowType: "triangle" } });
  num(s, 4);
  s.addNotes("This is the mechanism to remember. Math and logic are where a small model produces confident nonsense, and a naive arithmetic re-check would wave a wrong setup straight through — which is exactly what fails the accuracy gate. So generate twice: once deterministic, once with noise. A genuinely understood problem reproduces its own answer; a lucky guess usually doesn't. Agree, keep it for free. Disagree, escalate. Trade a few tokens to protect the gate — because tokens cost rank, but a gate failure costs everything.");

  // ============================================================ 5 ROBUSTNESS (2x2)
  s = p.addSlide(); bg(s);
  kicker(s, "The engineering around the core");
  title(s, "Four decisions that make it robust");
  const cells = [
    [I.gem, "Category-conditional Gemma", "Language escalations route to Gemma \u2014 keeping the $1,000 \u201cBest Use of Gemma\u201d sub-prize in play. Hard tasks go to the strongest model."],
    [I.ban, "No reasoning models", "Thinking models emit chain-of-thought as billed output tokens. On a token-scored track that's poison \u2014 they're banned at model-selection time."],
    [I.gauge, "Adaptive degradation", "A startup throughput probe measures the local model. Slow hardware \u2192 hard tasks go remote. No model or far too slow \u2192 pure-Fireworks fallback."],
    [I.shield, "Portable & fail-safe", "Built with a conservative CPU instruction set (no illegal-instruction crash on unknown hardware). Always writes valid JSON and exits clean."],
  ];
  const cw = 5.9, ch = 1.85, gx = 0.7, gyy = 2.4, gapx = 0.15, gapy = 0.18;
  cells.forEach(([ic, h, d], i) => {
    const x = gx + (i % 2) * (cw + gapx);
    const y = gyy + Math.floor(i / 2) * (ch + gapy);
    card(s, x, y, cw, ch);
    iconChip(s, ic, x + 0.28, y + 0.28, 0.6, TEAL);
    s.addText(h, { x: x + 1.05, y: y + 0.3, w: cw - 1.25, h: 0.45, fontFace: HEAD, fontSize: 16.5, bold: true, color: WHITE, margin: 0 });
    s.addText(d, { x: x + 0.32, y: y + 0.92, w: cw - 0.6, h: 0.85, fontFace: BODY, fontSize: 12.5, color: ICE, margin: 0 });
  });
  num(s, 5);
  s.addNotes("Four supporting decisions. One: when we do escalate language tasks, we route to Gemma to stay eligible for the thousand-dollar sub-prize, while hard tasks go to the strongest model. Two: reasoning models are banned — their thinking tokens are billed output, fatal on a token-scored track. Three: the agent probes its own speed at startup and degrades — slow box moves hard tasks remote, no local model at all flips it to pure Fireworks. Four: portable build, always writes valid output, never crashes the run.");

  // ============================================================ 6 ROUTING TABLE
  s = p.addSlide(); bg(s);
  kicker(s, "Placement policy across all eight categories");
  title(s, "What runs local, what escalates, and how it's checked");
  const rows = [
    ["Category", "Default", "Local verification", "Escalation trigger"],
    ["Factual", "Local", "non-empty, no hedging", "empty / uncertain"],
    ["Math", "Local \u00d72", "sample agreement", "samples disagree"],
    ["Sentiment", "Local", "valid label + reason", "invalid label"],
    ["Summarization", "Local", "length/format check", "limit violated"],
    ["NER", "Local", "JSON schema valid", "invalid JSON"],
    ["Code debug", "Local", "parses / asserts run", "parse or test fail"],
    ["Logic", "Local \u00d72", "sample agreement", "samples disagree"],
    ["Code generation", "Local", "parses / asserts run", "parse or test fail"],
  ];
  const headFill = TEAL;
  const tblRows = rows.map((r, ri) => r.map((c, ci) => ({
    text: c,
    options: {
      fontFace: ri === 0 ? HEAD : BODY,
      fontSize: ri === 0 ? 13.5 : 12.5,
      bold: ri === 0 || ci === 0,
      color: ri === 0 ? WHITE : (ci === 1 && r[1].includes("\u00d72") ? MINT : ICE),
      fill: { color: ri === 0 ? headFill : (ri % 2 ? PANEL : "0E2238") },
      align: "left", valign: "middle", margin: [3, 6, 3, 6],
    }
  })));
  s.addTable(tblRows, {
    x: 0.7, y: 2.3, w: 11.9, colW: [2.7, 1.9, 3.7, 3.6],
    rowH: 0.44, border: { type: "solid", pt: 0.5, color: DEEP },
  });
  s.addText("\u201cLocal \u00d72\u201d = two independent samples must agree before the answer is trusted (the accuracy-gate guard).", {
    x: 0.7, y: 6.75, w: 11.9, h: 0.4, fontFace: BODY, fontSize: 12, italic: true, color: MINT, margin: 0 });
  num(s, 6);
  s.addNotes("The full placement policy. Every category starts local. The verification column is the free deterministic check that decides whether to keep the answer. Note the two categories marked times-two — math and logic — those are the agreement-guarded ones. Everything else keeps the local answer whenever its structural check passes, and escalates only on a concrete, detectable failure.");

  // ============================================================ 7 ARCHITECTURE FLOW
  s = p.addSlide(); bg(s);
  kicker(s, "End to end, inside the container");
  title(s, "How one task moves through the agent");
  const ax = [0.7, 3.35, 6.0, 8.65];
  const flow = [
    [I.layers, "Read tasks", "/input/tasks.json", TEAL],
    [I.route, "Classify", "8 categories, 0 tokens", TEAL],
    [I.server, "Local solve", "free, verified", TEAL],
    [I.check, "Verify", "deterministic", TEAL],
  ];
  const ry = 2.6;
  flow.forEach(([ic, h, d], i) => {
    card(s, ax[i], ry, 2.4, 1.7);
    iconChip(s, ic, ax[i] + 0.9, ry + 0.25, 0.6, TEAL);
    s.addText(h, { x: ax[i] + 0.1, y: ry + 0.95, w: 2.2, h: 0.35, align: "center", fontFace: HEAD, fontSize: 15, bold: true, color: WHITE, margin: 0 });
    s.addText(d, { x: ax[i] + 0.1, y: ry + 1.3, w: 2.2, h: 0.3, align: "center", fontFace: BODY, fontSize: 11.5, color: ICE, margin: 0 });
    if (i < 3) s.addShape(p.shapes.LINE, { x: ax[i] + 2.4, y: ry + 0.85, w: 0.25, h: 0, line: { color: SEA, width: 2.5, endArrowType: "triangle" } });
  });
  // branch down from verify
  s.addShape(p.shapes.LINE, { x: ax[3] + 1.2, y: ry + 1.7, w: 0, h: 0.55, line: { color: SEA, width: 2.5, endArrowType: "triangle" } });
  // pass vs fail
  card(s, 6.0, 4.85, 2.4, 1.5, "16513A");
  s.addText("Pass \u2192 keep", { x: 6.1, y: 5.05, w: 2.2, h: 0.4, align: "center", fontFace: HEAD, fontSize: 14.5, bold: true, color: MINT, margin: 0 });
  s.addText("zero remote tokens", { x: 6.1, y: 5.5, w: 2.2, h: 0.5, align: "center", fontFace: BODY, fontSize: 12, color: ICE, margin: 0 });
  card(s, 8.65, 4.85, 3.95, 1.5, "5A2A2A");
  iconChip(s, I.gem, 8.9, 5.12, 0.55, TEAL);
  s.addText("Fail \u2192 escalate once", { x: 9.6, y: 5.05, w: 2.9, h: 0.4, fontFace: HEAD, fontSize: 14.5, bold: true, color: WHITE, margin: 0 });
  s.addText("minimal Fireworks call: t=0, capped tokens, Gemma or strongest model", { x: 9.62, y: 5.48, w: 2.9, h: 0.7, fontFace: BODY, fontSize: 11.5, color: ICE, margin: 0 });
  s.addShape(p.shapes.LINE, { x: 8.4, y: ry + 2.55, w: 0.25, h: 0, line: { color: RED, width: 2.5, endArrowType: "triangle" } });
  // write out
  s.addText("\u2192  All answers written atomically to /output/results.json, exit 0, under 10 minutes.", {
    x: 0.7, y: 6.65, w: 11.9, h: 0.4, fontFace: BODY, fontSize: 13, italic: true, color: MUTE, margin: 0 });
  num(s, 7);
  s.addNotes("One task's journey, left to right. Read the batch, classify for free, solve locally, verify. If it passes, we keep it — zero tokens. If it fails, exactly one minimal remote call, temperature zero, tokens capped, routed to Gemma or the strongest model by category. At the end everything is written atomically and the container exits clean, well inside ten minutes.");

  // ============================================================ 8 OPEN QUESTIONS
  s = p.addSlide(); bg(s);
  kicker(s, "What we don't know \u2014 and design around");
  title(s, "Three honest unknowns, three built-in hedges");
  const risks = [
    [I.question, "Scoring hardware", "Standardized but unpublished \u2014 could be CPU-only or GPU.", "Startup throughput probe + graceful degradation to remote."],
    [I.server, "Is local inference fully allowed?", "Track rewards hybrid; one guide line is ambiguous.", "Pure-Fireworks fallback ships behind a single switch."],
    [I.flask, "Exact model list", "Allowed models are revealed only on launch day.", "Models parsed & ranked at runtime \u2014 never hardcoded."],
  ];
  const rry = 2.45;
  risks.forEach(([ic, h, d, hedge], i) => {
    const y = rry + i * 1.42;
    card(s, 0.7, y, 11.9, 1.28);
    iconChip(s, ic, 1.0, y + 0.33, 0.62, "7A4A1F");
    s.addText(h, { x: 1.85, y: y + 0.22, w: 5.0, h: 0.5, fontFace: HEAD, fontSize: 17, bold: true, color: WHITE, margin: 0 });
    s.addText(d, { x: 1.87, y: y + 0.72, w: 5.0, h: 0.5, fontFace: BODY, fontSize: 12.5, color: ICE, margin: 0 });
    // hedge on right
    s.addShape(p.shapes.LINE, { x: 7.1, y: y + 0.2, w: 0, h: 0.88, line: { color: TEAL, width: 1.5 } });
    s.addText("HEDGE", { x: 7.35, y: y + 0.24, w: 1.2, h: 0.3, fontFace: BODY, fontSize: 10, bold: true, color: SEA, charSpacing: 2, margin: 0 });
    s.addText(hedge, { x: 7.35, y: y + 0.55, w: 5.1, h: 0.6, fontFace: BODY, fontSize: 13, color: MINT, margin: 0 });
  });
  num(s, 8);
  s.addNotes("Credibility means naming your own risks. Three things are genuinely unknown at build time, and each has a built-in answer. Hardware is unpublished — so we probe and degrade. Whether local is fully allowed has one ambiguous line — so a pure-remote fallback ships behind a switch, confirmed on Discord day-of. The model list drops on launch day — so nothing is hardcoded; models are parsed and ranked at runtime. These aren't oversights. They're why the design is adaptive.");

  // ============================================================ 9 WHY IT WINS
  s = p.addSlide(); bg(s);
  kicker(s, "The case for this submission");
  title(s, "Why this wins on both scoring axes");
  card(s, 0.7, 2.4, 5.9, 3.8);
  iconChip(s, I.scale, 1.0, 2.65, 0.62, TEAL);
  s.addText("Token axis", { x: 1.85, y: 2.68, w: 4.5, h: 0.45, fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, margin: 0 });
  ["Most tasks resolve locally at zero cost", "Remote calls only on proven failures", "Minimal prompts, capped output, t = 0", "Reasoning models banned \u2014 no stray tokens"].forEach((t, i) =>
    s.addText(t, { x: 1.0, y: 3.4 + i * 0.66, w: 5.4, h: 0.55, fontFace: BODY, fontSize: 14, color: ICE, bullet: { indent: 14 }, margin: 0 }));

  card(s, 6.85, 2.4, 5.75, 3.8);
  iconChip(s, I.check, 7.15, 2.65, 0.62, TEAL);
  s.addText("Accuracy axis", { x: 8.0, y: 2.68, w: 4.5, h: 0.45, fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, margin: 0 });
  ["Every kept answer passed a real check", "Agreement guard on math & logic", "Verified-failure escalation to strong models", "Always ships valid, scoreable output"].forEach((t, i) =>
    s.addText(t, { x: 7.15, y: 3.4 + i * 0.66, w: 5.3, h: 0.55, fontFace: BODY, fontSize: 14, color: ICE, bullet: { indent: 14 }, margin: 0 }));
  num(s, 9);
  s.addNotes("Put together: on the token axis, most tasks never leave the container, remote calls happen only on proven failures, prompts are minimal and capped, and reasoning models are banned so no stray tokens leak in. On the accuracy axis, every answer we keep has passed a real check, math and logic are agreement-guarded, genuine failures escalate to strong models, and we always ship valid output so the run is scoreable. Both axes, by construction.");

  // ============================================================ 10 CLOSE
  s = p.addSlide(); bg(s);
  [4.6, 3.4, 2.2].forEach((d, i) => s.addShape(p.shapes.OVAL, {
    x: -d / 2 + 1.2, y: H - d / 2 - 0.6, w: d, h: d, fill: { color: TEAL, transparency: 88 + i * 3 }
  }));
  iconChip(s, I.trophy, 0.9, 1.5, 0.9, TEAL);
  s.addText("Treat the leaderboard for what it\nactually measures.", {
    x: 0.85, y: 2.7, w: 11.6, h: 1.6, fontFace: HEAD, fontSize: 38, bold: true, color: WHITE, lineSpacingMultiple: 1.0, margin: 0 });
  s.addText("Answer everything you can prove correct on a free local model. Escalate only verified failures. Guard the accuracy gate where it's most likely to break. Stay robust to an environment you can't see in advance.", {
    x: 0.87, y: 4.5, w: 11.2, h: 1.2, fontFace: BODY, fontSize: 17, color: ICE, margin: 0 });
  s.addText("Hybrid Token-Efficient Routing Agent  ·  AMD Developer Hackathon ACT II  ·  Track 1", {
    x: 0.87, y: 6.4, w: 11.6, h: 0.4, fontFace: BODY, fontSize: 13, italic: true, color: MUTE, margin: 0 });
  s.addNotes("Close on the thesis. The whole design comes from taking the scoring seriously: it measures remote tokens avoided without failing the accuracy gate. So answer what you can prove correct for free, escalate only verified failures, guard the gate where it breaks, and stay robust to an unseen environment. That's the submission. Thank you.");

  await p.writeFile({ fileName: "/home/claude/token-router/presentation/AMD_Hackathon_Track1_Deck.pptx" });
  console.log("deck written");
})();
