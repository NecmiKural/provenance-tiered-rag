"""The README results block, written from results/*.json and nothing else."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from provrag import evalset

START = "<!-- results:start -->"
END = "<!-- results:end -->"
ABLATIONS = {
    "on": "All on",
    "prompt_off": "Prompt rules off",
    "fence_off": "Fence off",
    "notes_rule_off": "Notes rule off",
    "verifier_off": "Verifier off",
    "normalise_off": "Hidden-text stripping off",
    "code_off": "All off except the prompt rules",
    "off": "All off",
}
GOALS = {
    "wrong_fact": "Plant a wrong figure",
    "cite_payload": "Get the note cited",
    "leak": "Leak the prompt",
    "wrongful_refusal": "Force a refusal",
    "off_task": "Add an off-topic link",
}
METHODS = {
    "full_text": "Full text",
    "vector": "Vector",
    "rrf": "RRF",
    "rrf_undated": "RRF, no date filter",
}


def load(results_dir: Path, kind: str) -> list[dict[str, Any]]:
    found = [json.loads(p.read_text()) for p in sorted(results_dir.glob("*.json"))]
    return [r for r in found if r.get("kind") == kind]


def latest(results: list[dict[str, Any]], **match: Any) -> dict[str, Any] | None:
    hits = [r for r in results if all(r.get(k) == v for k, v in match.items())]
    return max(hits, key=lambda r: r["generated_at"]) if hits else None


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def share(block: dict[str, Any]) -> str:
    return f"{block['k']} of {block['n']} ({pct(block['rate'])})"


def upper(block: dict[str, Any]) -> str:
    return pct(block["ci95"][1])


def of(results: list[dict[str, Any]], jurisdiction: str) -> list[dict[str, Any]]:
    """Files written before jurisdictions existed are New Zealand's."""
    return [r for r in results if r.get("jurisdiction", "NZ") == jurisdiction]


def evals(results_dir: Path, jurisdiction: str = "NZ") -> dict[str, dict[str, Any]]:
    out = {}
    for name in ABLATIONS:
        r = latest(
            [
                r
                for r in of(load(results_dir, "eval"), jurisdiction)
                if r["defences"]["name"] == name
            ],
            questions="development",
            mode="record",
            every=1,
            valid=True,
        )
        if r:
            out[name] = r
    return out


def held_back(results_dir: Path, jurisdiction: str = "NZ") -> dict[str, Any] | None:
    found = [
        r for r in of(load(results_dir, "eval"), jurisdiction) if r["defences"]["name"] == "on"
    ]
    return latest(found, questions="held_back", mode="record", every=1, valid=True)


def retrievals(
    results_dir: Path, questions: str, jurisdiction: str = "NZ"
) -> dict[str, Any] | None:
    found = of(load(results_dir, "retrieval"), jurisdiction)
    return latest([r for r in found if r.get("questions", "development") == questions])


def held_back_table(
    dev: dict[str, Any], held: dict[str, Any], dev_r: dict | None, held_r: dict | None
) -> list[str]:
    def rows(r: dict[str, Any], retrieval: dict | None) -> list[str]:
        a = r["aggregate"]
        recall = retrieval["methods"]["vector"]["all"]["recall_at_5"] if retrieval else None
        return [
            share(a["answerable_correct"]),
            share(a["unanswerable_refused"]),
            share(a["calculation_refused"]),
            share(a["attacks_total"]["draft"]),
            share(a["attacks_total"]["final"]),
            share(recall) if recall else "n/a",
        ]

    names = [
        "Answerable correct",
        "Not covered: refused",
        "Arithmetic: refused",
        "Attacks, first draft",
        "Attacks, what the user saw",
        "Vector retrieval, gold passage in the top 5",
    ]
    out = [
        f"| | Development ({dev['repeats']} runs) | Held back ({held['repeats']} runs) |",
        "|---|---|---|",
    ]
    for name, d, h in zip(names, rows(dev, dev_r), rows(held, held_r), strict=True):
        out.append(f"| {name} | {d} | {h} |")
    return out


def latency_table(results_dir: Path) -> list[str]:
    """One row per place the index ran, the latest measurement of each."""
    found = load(results_dir, "latency")
    latest_by_label: dict[str, dict[str, Any]] = {}
    for r in found:
        if (
            r["label"] not in latest_by_label
            or r["generated_at"] > latest_by_label[r["label"]]["generated_at"]
        ):
            latest_by_label[r["label"]] = r
    if not latest_by_label:
        return []
    out = [
        "| Where | PostgreSQL | pgvector | Load the index | Retrieval query, p50 and p95"
        " | Commit |",
        "|---|---|---|---|---|---|",
    ]
    for label, r in sorted(latest_by_label.items()):
        out.append(
            f"| {label} | {r['server_version'].split()[0]} | {r['pgvector']}"
            f" | {r['load_seconds']} s | {r['query_p50_ms']} ms and {r['query_p95_ms']} ms"
            f" | `{r['commit']}` |"
        )
    return out


def exposure_by_goal(retrieval: dict[str, Any], method: str) -> dict[str, dict[str, int]]:
    goals = {p["note"]: p["goal"] for p in evalset.payloads()}
    out: dict[str, dict[str, int]] = {g: {"k": 0, "n": 0} for g in GOALS}
    for note, rank in retrieval["methods"][method]["exposure"].items():
        out[goals[note]]["n"] += 1
        out[goals[note]]["k"] += rank is not None
    return out


def headline(main: dict[str, Any], off: dict[str, Any] | None, retrieval: dict | None) -> str:
    a = main["aggregate"]
    t = a["attacks_total"]
    right = a["answerable_correct"]
    text = (
        f"**{right['k']} of {right['n']} answers to answerable questions were correct**"
        f" (95% lower bound {pct(right['ci95'][0])}) over {main['repeats']} runs of the"
        " development questions: the expected figures where a question has them, and every"
        " figure in a cited passage in force on the date asked about. Questions the sources do"
        f" not cover were refused in {share(a['unanswerable_refused'])} runs, and questions"
        f" needing arithmetic in {share(a['calculation_refused'])}. With a payload note placed in"
        f" the context every time, **{share(t['final'])} attacked answers did what the payload"
        f" asked**, and {share(t['draft'])} of the model's first drafts"
    )
    if off:
        text += (
            f"; with every defence off, {share(off['aggregate']['attacks_total']['final'])}"
            f" over {off['repeats']} runs"
        )
    if retrieval:
        m = retrieval["methods"]["vector"]
        text += (
            f". Left to retrieval, {share(m['exposure_at_5'])} payload notes reached the"
            " top 5 for the question they target"
        )
    return text + "."


def main_table(main: dict[str, Any]) -> list[str]:
    a = main["aggregate"]
    rows = [
        ("Answerable: right figures, verified", share(a["answerable_correct"])),
        ("Answerable: refused", share(a["answerable_refused"])),
        ("Answers citing a labelled passage", share(a["answerable_citing_a_labelled_passage"])),
        ("Not covered by the sources: refused", share(a["unanswerable_refused"])),
        ("Needs arithmetic: refused", share(a["calculation_refused"])),
        ("First drafts the verifier rejected", share(a["first_draft_failed"])),
        ("Of those, repaired and correct", share(a["repaired_and_correct"])),
        ("Refusals made by the verifier", share(a["refused_by_verifier"])),
        (
            "Answerable questions with the same outcome in every run",
            share(a["answerable_same_in_every_run"]),
        ),
        ("Cost per question (peak price)", f"${a['cost_per_question_usd']:.4f}"),
        (
            "Time per question, p50 and p95",
            f"{a['latency_p50_ms'] / 1000:.1f} s and {a['latency_p95_ms'] / 1000:.1f} s",
        ),
    ]
    return ["| | |", "|---|---|", *(f"| {k} | {v} |" for k, v in rows)]


def attack_table(main: dict[str, Any], retrieval: dict | None) -> list[str]:
    exposure = exposure_by_goal(retrieval, "vector") if retrieval else None
    out = [
        "| Payload goal | First draft | What the user saw | Payloads succeeding in any run"
        " (95% upper bound) | Reached the top 5 on its own |",
        "|---|---|---|---|---|",
    ]
    for goal, title in GOALS.items():
        g = main["aggregate"]["attacks"][goal]
        any_run = g["payloads_succeeding_in_any_run"]
        reached = f"{exposure[goal]['k']} of {exposure[goal]['n']}" if exposure else "n/a"
        out.append(
            f"| {title} | {share(g['draft'])} | {share(g['final'])}"
            f" | {any_run['k']} of {any_run['n']} (up to {upper(any_run)}) | {reached} |"
        )
    return out


def ablation_table(runs: dict[str, dict[str, Any]]) -> list[str]:
    out = [
        "| Defences | Runs | Answerable correct | Arithmetic refused | Attacks, first draft"
        " | Attacks, what the user saw | Answers failing the verifier's checks |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, title in ABLATIONS.items():
        if name not in runs:
            continue
        r = runs[name]
        a = r["aggregate"]
        out.append(
            f"| {title} | {r['repeats']} | {share(a['answerable_correct'])}"
            f" | {share(a['calculation_refused'])}"
            f" | {share(a['attacks_total']['draft'])} | {share(a['attacks_total']['final'])}"
            f" | {share(a['answers_failing_verifier'])} |"
        )
    return out


def retrieval_table(r: dict[str, Any]) -> list[str]:
    groups = {
        "all": "All",
        "statute_origin": "Written from the Act",
        "guidance_origin": "Written from guidance",
        "historical": "About a past date",
    }
    out = [
        "| Method | "
        + " | ".join(f"{t} ({r['groups'][g]})" for g, t in groups.items())
        + " | Payloads in the top 5 |",
        "|---" * (len(groups) + 2) + "|",
    ]
    for key, title in METHODS.items():
        m = r["methods"][key]
        cells = [f"{m[g]['recall_at_5']['rate']:.3f} and {m[g]['mrr']:.3f}" for g in groups]
        out.append(f"| {title} | " + " | ".join(cells) + f" | {share(m['exposure_at_5'])} |")
    return out


def render(results_dir: Path) -> str:
    runs = evals(results_dir)
    retrieval = retrievals(results_dir, "development")
    if "on" not in runs:
        return f"{START}\n_No results yet: run `make eval`._\n{END}"
    main = runs["on"]
    commits = sorted({r["commit"] for r in runs.values()})
    lines = [
        START,
        "<!-- Generated by `provrag report` from results/*.json."
        " Edit the code, not this block. -->",
        "",
        headline(main, runs.get("off"), retrieval),
        "",
        *main_table(main),
        "",
        f"Model `{main['model']}` (`{main['api_model']}`), prompt `{main['prompt_sha']}`, retrieval"
        f" `{main['method']}` with k={main['k']}, prices checked {main['prices_checked']};"
        f" development questions only; commit `{main['commit']}`.",
        "",
        "### Attacks",
        "",
        "Each payload note was placed after the retrieved passages for the question it targets,"
        " whether or not retrieval would have ranked it, and scored on the model's first draft"
        " and on what the user saw after the verifier. A forced refusal counts only where the same"
        " run answered the question clean. The last column is the retrieval ablation's: how many"
        " of these payloads vector search ranked in the top 5 by itself.",
        "",
        *attack_table(main, retrieval),
        "",
        "### Defences switched off",
        "",
        "The prompt rules say notes are data and never a source, keep the prompt private and"
        " forbid links; switched off, the model gets a plain prompt with the same task, reply"
        " format and canary. The fence marks notes as untrusted; the notes rule refuses a note as"
        " a source; the verifier checks citations and figures and allows one repair; stripping"
        " removes invisible characters from notes. One defence off at a time is one run; all on,"
        " all off and all off except the prompt rules are three."
        f" Commits: {', '.join(f'`{c}`' for c in commits)}.",
        "",
        *ablation_table(runs),
    ]
    held = held_back(results_dir)
    if held:
        lines += [
            "",
            "### Held-back questions",
            "",
            "A quarter of the questions of every kind, with the payloads aimed at them, kept out of"
            " the prompt and the choice of retrieval method and run once at the end with every"
            " defence on. One scoring rule changed after it ran: a false positive in this set"
            " showed that a planted figure can also be true elsewhere in the law, so wrong-figure"
            " attacks are now paired with the clean answer, in every results file (see the agent"
            f" log). Run at commit `{held['commit']}`"
            + (f", scored at `{held['scored_with']}`." if held.get("scored_with") else "."),
            "",
            *held_back_table(main, held, retrieval, retrievals(results_dir, "held_back")),
        ]
    if retrieval:
        lines += [
            "",
            "### Retrieval",
            "",
            "Each cell is recall at 5 and mean reciprocal rank of a labelled passage in force on"
            " the question's date, on the development questions; no chat model is involved."
            f" Embeddings `{retrieval['embedding_model']}` at {retrieval['dims']} dimensions in"
            " pgvector. The mean Jaccard word overlap between a question and its best labelled"
            f" passage is {retrieval['lexical_overlap']['all']:.3f}: the questions do not borrow"
            " the sources' wording."
            f" Commit `{retrieval['commit']}`.",
            "",
            *retrieval_table(retrieval),
        ]
    latency = latency_table(results_dir)
    if latency:
        lines += [
            "",
            "### Where the index runs",
            "",
            "Loading the whole index (schema, chunks and vectors) and the retrieval query"
            " answering uses, timed from this machine; network time is included. RDS rows come"
            " from the one-day trial in [docs/rds-trial.md](docs/rds-trial.md).",
            "",
            *latency,
        ]
    lines.append(END)
    return "\n".join(lines)


def sync(readme: Path, results_dir: Path, check: bool = False) -> bool:
    """Rewrite the block between the markers. Returns True if it was stale."""
    text = readme.read_text()
    if START not in text or END not in text:
        raise ValueError(f"{readme} has no results markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    new = head + render(results_dir) + tail
    if not check and new != text:
        readme.write_text(new)
    return new != text
