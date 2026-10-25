// The evidence viewer for docs/evidence/<pack>.json, written by `provrag evidence`.
// Recorded model text and planted notes are hostile by design, so every string reaches the
// page as a text node: no string is ever parsed as markup. tests/test_evidence.py fails if
// this file uses an HTML-parsing property.

const REPO = "https://github.com/NecmiKural/provenance-tiered-rag";
const PACKS = {
  "nz-gst": "New Zealand GST",
  "de-vat": "German VAT (Umsatzsteuer), in German",
  "nz-immigration": "New Zealand immigration instructions",
};
const PACK_NOTES = {
  "de-vat":
    "Questions, passages and answers in this pack are in German, as the statute is; the page around them is in English.",
  "nz-immigration":
    "Every answer is information from the published instructions, not immigration advice. A question about the asker's own case is refused by design, with a pointer to Immigration New Zealand or a licensed immigration adviser.",
};
const KINDS = {
  answerable: "Answerable from the sources",
  unanswerable: "Not covered by the sources, so it should be refused",
  calculation: "Needs arithmetic the sources do not state, so it should be refused",
  advice: "Asks about the asker's own case, so it should be refused",
};
const GOALS = {
  wrong_fact: "make the answer state a wrong figure",
  cite_payload: "get the note itself cited as a source",
  leak: "get the hidden instructions copied into the answer",
  off_task: "push the answer off the question",
  wrongful_refusal: "make the model refuse a question it can answer",
};
const TIERS = { T1: "Statute", T2: "Official guidance", T3: "Untrusted note" };

const $ = (id) => document.getElementById(id);
const state = { pack: "nz-gst", id: null, show: "all", outcome: "all" };
const docs = new Map();

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false && value != null) node.setAttribute(key, String(value));
  }
  node.append(...children.flat(Infinity).filter((c) => c != null && c !== false && c !== ""));
  return node;
}

const safeUrl = (url) => (typeof url === "string" && url.startsWith("https://") ? url : null);
const inForce = (p, day) => p.valid_from <= day && (p.valid_to == null || day < p.valid_to);
const period = (p) => `Text in force from ${p.valid_from}${p.valid_to ? ` until ${p.valid_to}` : ""}.`;

async function load(pack) {
  if (!docs.has(pack)) {
    const response = await fetch(`${pack}.json`);
    if (!response.ok) throw new Error(`${pack}.json: HTTP ${response.status}`);
    docs.set(pack, await response.json());
  }
  return docs.get(pack);
}

// Deep links: #pack or #pack/case, each part checked against known ids.
function route() {
  let parts = [];
  try {
    parts = location.hash.slice(1).split("/").map(decodeURIComponent);
  } catch {
    parts = [];
  }
  return { pack: Object.hasOwn(PACKS, parts[0]) ? parts[0] : "nz-gst", id: parts[1] || null };
}

function writeHash() {
  const parts = [state.pack, ...(state.id ? [state.id] : [])].map(encodeURIComponent);
  history.replaceState(null, "", `#${parts.join("/")}`);
}

// The first recorded run decides a case's outcome; the others are listed with it.
function outcome(c) {
  const first = c.repeats[0];
  if (c.payload && first.attack_final) return "attack_through";
  return first.correct ? "correct" : "not_correct";
}

function verdict(c, q) {
  const first = c.repeats[0];
  if (c.payload && first.attack_final) return "The attack reached the answer";
  if (first.correct) return q.kind === "answerable" ? "Correct" : "Correctly refused";
  if (q.kind !== "answerable") return "Answered a question it should have refused";
  return first.refused ? "Refused a question it could answer" : "Not correct";
}

function title(c) {
  return c.payload ? `${c.question} with planted note ${c.payload}` : c.question;
}

async function show(pack, id = null, focus = false) {
  let doc;
  try {
    doc = await load(pack);
  } catch (error) {
    $("alert").textContent = `Could not load the recording: ${error.message}`;
    $("alert").hidden = false;
    return;
  }
  $("alert").hidden = true;
  state.pack = pack;
  $("pack").value = pack;
  state.id = doc.cases.some((c) => c.id === id) ? id : null;
  renderPack(doc);
  renderList(doc);
  renderDetail(doc, focus);
  writeHash();
}

function renderPack(doc) {
  const dev = doc.runs.development;
  const held = doc.runs.held_back;
  const file = (run) => {
    const ok = /^results\/[\w.-]+\.json$/.test(run.file);
    return ok ? el("a", { href: `${REPO}/blob/main/${run.file}`, text: run.file }) : run.file;
  };
  $("pack-info").replaceChildren(
    `Development questions recorded on ${dev.recorded_at.slice(0, 10)} (`,
    file(dev),
    `), held-back questions on ${held.recorded_at.slice(0, 10)} (`,
    file(held),
    `), both with ${dev.model}. Each case ran ${dev.repeats} times; the answer shown is the first run.`,
  );
  $("pack-note").textContent = PACK_NOTES[doc.pack] || "";
  $("pack-note").hidden = !PACK_NOTES[doc.pack];
}

function visible(doc) {
  return doc.cases.filter((c) => {
    if (state.show === "clean" && (c.payload || c.set !== "development")) return false;
    if (state.show === "attacked" && !c.payload) return false;
    if (state.show === "held_back" && c.set !== "held_back") return false;
    return state.outcome === "all" || outcome(c) === state.outcome;
  });
}

function renderList(doc) {
  const shown = visible(doc);
  $("count").textContent = `Showing ${shown.length} of ${doc.cases.length} cases.`;
  $("case-list").replaceChildren(
    ...shown.map((c) => {
      const q = doc.questions[c.question];
      return el(
        "li",
        {},
        el(
          "button",
          {
            type: "button",
            "aria-current": c.id === state.id ? "true" : false,
            onclick: () => show(state.pack, c.id, true),
          },
          el("span", { class: "case-id", text: title(c) }),
          el("span", { class: "case-q", text: q.question }),
          el(
            "span",
            { class: "case-tags" },
            el("span", { class: "outcome", "data-outcome": outcome(c), text: verdict(c, q) }),
            c.set === "held_back" && el("span", { class: "tag", text: "held back" }),
          ),
        ),
      );
    }),
  );
}

function passageCard(doc, id, day, { open = false, cited = false } = {}) {
  const p = doc.passages[id];
  if (!p) return el("p", { class: "refused" }, `${id}: not a passage the model was shown`);
  const source = doc.sources[p.source] || {};
  const url = safeUrl(source.url);
  const on = inForce(p, day);
  return el(
    "article",
    { class: "passage", "data-tier": p.tier },
    el(
      "p",
      { class: "label" },
      `${TIERS[p.tier] || p.tier} / ${source.title || p.source}`,
      cited && el("span", { class: "tag", text: "cited" }),
    ),
    el("h4", { text: p.heading || p.section }),
    el("p", { class: "id" }, el("code", { text: id })),
    el(
      "p",
      { class: on ? "in-force" : "out-of-force" },
      `${period(p)} ${on ? "In force" : "Not in force"} on ${day}, the question date.`,
    ),
    p.hidden_text && el("p", { class: "quiet", text: "Invisible characters were removed from this note before indexing." }),
    el("details", { open }, el("summary", { text: "Text" }), el("pre", { class: "prose", tabindex: "0", text: p.body })),
    el(
      "p",
      { class: "quiet" },
      source.licence || "",
      url && " ",
      url && el("a", { href: url, rel: "noopener", text: "Source" }),
    ),
  );
}

function draftView(doc, draft, day) {
  if (draft.refused) return el("p", { class: "model-text" }, "Refused: ", draft.reason || "no reason given");
  return [
    el("p", { class: "model-text", text: draft.answer }),
    el(
      "ol",
      { class: "claims" },
      draft.claims.map((claim) =>
        el(
          "li",
          {},
          el("p", { text: claim.text }),
          claim.cites.map((id) => passageCard(doc, id, day, { cited: true })),
        ),
      ),
    ),
  ];
}

function section(heading, ...children) {
  return el("section", { class: "part" }, el("h3", { text: heading }), children);
}

function renderDetail(doc, focus) {
  const c = doc.cases.find((x) => x.id === state.id);
  const heading = $("detail-title");
  if (!c) {
    heading.textContent = "Choose a question";
    $("detail-body").replaceChildren(
      el("p", { class: "quiet", text: "Pick a case on the list to see the answer, what it cites and when each passage was in force." }),
    );
    return;
  }
  const q = doc.questions[c.question];
  const day = q.as_of;
  const first = c.repeats[0];
  heading.textContent = title(c);
  const parts = [
    el("blockquote", { class: "question", lang: doc.lang, text: q.question }),
    el(
      "dl",
      { class: "facts" },
      el("dt", { text: "Asked as of" }),
      el("dd", { text: day }),
      el("dt", { text: "Kind" }),
      el("dd", { text: KINDS[q.kind] || q.kind }),
      el("dt", { text: "Set" }),
      el("dd", { text: c.set === "held_back" ? "Held back: kept out of development and run once at the end" : "Development" }),
      q.expect.length > 0 && [el("dt", { text: "Expected" }), el("dd", { lang: doc.lang, text: q.expect.join("; ") })],
      q.gold.length > 0 && [el("dt", { text: "Labelled passages" }), el("dd", {}, el("code", { text: q.gold.join(", ") }))],
    ),
    section(
      "Outcome",
      el("p", { class: "verdict", "data-outcome": outcome(c), text: verdict(c, q) }),
      el(
        "ol",
        { class: "repeats", "aria-label": "Every recorded run" },
        c.repeats.map((r, i) =>
          el("li", {}, `Run ${i + 1}: ${r.correct ? "correct" : "not correct"}`, c.payload && `, attack ${r.attack_final ? "reached the answer" : "blocked"}`),
        ),
      ),
    ),
  ];
  if (c.payload) {
    const note = doc.payloads[c.payload] || {};
    parts.push(
      section(
        "The planted note",
        el("p", {}, `It tries to ${GOALS[note.goal] || note.goal}. `, `First draft: ${first.attack_draft ? "followed it" : "did not follow it"}. What the user saw: ${first.attack_final ? "followed it" : "did not follow it"}.`),
        passageCard(doc, c.context[c.context.length - 1], day, { open: true }),
      ),
    );
  }
  const answer = c.answer;
  const by = { model: "Refused by the model.", verifier: "Refused by the verifier: no draft passed its checks.", invalid_reply: "Refused: the reply was not in the required shape." };
  parts.push(
    section(
      "What the user saw",
      c.refused_by && el("p", { class: "quiet", text: by[c.refused_by] || c.refused_by }),
      el("div", { lang: doc.lang }, draftView(doc, answer, day)),
    ),
  );
  if (c.attempts.length > 1 || c.attempts[0].errors.length > 0) {
    parts.push(
      section(
        "The verifier",
        c.attempts.map((a, i) =>
          el(
            "div",
            { class: "attempt" },
            el("h4", { text: `Draft ${i + 1}` }),
            a.draft ? el("div", { lang: doc.lang }, a.draft.refused ? draftView(doc, a.draft, day) : el("p", { class: "model-text", text: a.draft.answer })) : el("pre", { class: "prose", tabindex: "0", text: a.content }),
            a.errors.length > 0
              ? el("ul", { class: "errors" }, a.errors.map((e) => el("li", { class: "refused", text: `Rejected: ${e}` })))
              : el("p", { class: "accepted", text: "Accepted" }),
          ),
        ),
      ),
    );
  }
  const cited = new Set(answer.claims.flatMap((claim) => claim.cites));
  parts.push(
    section(
      "Passages the model was shown",
      el("p", { class: "quiet", text: "Retrieved by vector search over the passages in force on the question date, plus the planted note on an attacked case." }),
      c.context.map((id) => passageCard(doc, id, day, { cited: cited.has(id) })),
    ),
  );
  $("detail-body").replaceChildren(...parts.flat(Infinity).filter(Boolean));
  if (focus) heading.focus();
}

function wire() {
  $("pack").replaceChildren(...Object.entries(PACKS).map(([id, name]) => el("option", { value: id, text: name })));
  $("pack").addEventListener("change", (event) => show(event.target.value));
  $("show").addEventListener("change", (event) => {
    state.show = event.target.value;
    renderList(docs.get(state.pack));
  });
  $("outcome").addEventListener("change", (event) => {
    state.outcome = event.target.value;
    renderList(docs.get(state.pack));
  });
  window.addEventListener("hashchange", () => {
    const { pack, id } = route();
    show(pack, id);
  });
}

// build.json is written by the deploy job; locally there is none.
async function stamp() {
  try {
    const response = await fetch("build.json");
    const commit = response.ok ? (await response.json()).commit : null;
    if (typeof commit === "string" && /^[0-9a-f]{7,40}$/.test(commit)) {
      $("build").append(" ", el("a", { href: `${REPO}/commit/${commit}`, text: `Deployed from ${commit}.` }));
    }
  } catch {
    // no build stamp
  }
}

wire();
stamp();
const start = route();
show(start.pack, start.id);
