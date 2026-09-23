"""Run the eval set against a local Ollama model and report what broke.

    OLLAMA_BASE_URL=http://nexusbody:11434 \
    OLLAMA_MODEL=qwen2.5:14b \
    python -m evals.run

Nothing about the box is hardcoded: base URL and model come from the
environment and the runner refuses to start without the model name, because a
silent default would produce a score for something nobody chose.

**Two call shapes, not one.** Ollama's `tools` constrains the assistant's tool
calls; `format` constrains its content. They answer different questions and it
is not safe to assume they compose, so tool categories are sent with `tools`
and extraction is sent with `format`. `--probe` asks the live box whether they
can be combined, which is worth knowing before anyone designs a turn that needs
both.

**Two run modes.** `--repeats N` sends the identical prompt N times: with
temperature 0 and a fixed seed those should be byte-identical, so a difference
is the machine, not the model. `--paraphrases` instead sends each case's
alternative phrasings once each, which is the one that tells you whether Qwen
holds up when John types it differently. They measure different things and the
default runs both.

**num_ctx is explicit and generous.** Ollama's default silently truncates, and
a truncated prompt does not error -- it comes back as a model that looks
stupid. A recipe plus three tool schemas passes the usual default easily.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from evals import prompts
from evals.extraction import RECIPE_SCHEMA
from evals.score import Reply, Verdict, score
from evals.tools import TOOLS

HERE = pathlib.Path(__file__).parent
CASES_DIR = HERE / "cases"
RESULTS_DIR = HERE / "results"

# Categories that hand the model tools. `extraction` is the odd one out: it is
# a constrained-output call with no tools at all.
TOOL_CATEGORIES = frozenset({"tool_select", "no_tool", "missing_info"})


@dataclass
class Config:
    base_url: str
    model: str
    num_ctx: int
    seed: int
    temperature: float
    timeout: float
    repeats: int
    paraphrases: bool
    few_shot: bool

    @classmethod
    def from_env(cls, args: argparse.Namespace) -> "Config":
        model = os.environ.get("OLLAMA_MODEL", "").strip()
        if not model:
            raise SystemExit(
                "OLLAMA_MODEL is not set. Name the model explicitly -- a default "
                "here would produce a score for something nobody chose."
            )
        return cls(
            base_url=os.environ.get("OLLAMA_BASE_URL", "").strip().rstrip("/")
            or "http://localhost:11434",
            model=model,
            num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "8192")),
            seed=int(os.environ.get("OLLAMA_SEED", "42")),
            temperature=float(os.environ.get("OLLAMA_TEMPERATURE", "0")),
            timeout=float(os.environ.get("OLLAMA_TIMEOUT", "180")),
            repeats=args.repeats,
            paraphrases=not args.no_paraphrases,
            few_shot=not args.no_few_shot,
        )


# --------------------------------------------------------------------------
# talking to Ollama
# --------------------------------------------------------------------------

# A transport is anything that takes a chat request and returns Ollama's JSON.
# Kept behind this one signature so the whole runner is exercisable offline --
# the same arrangement the app uses for `fetch_page` and `fetch_video`.
Transport = Callable[[dict[str, Any]], dict[str, Any]]


def http_transport(config: Config) -> Transport:
    import httpx

    client = httpx.Client(timeout=config.timeout)

    def send(body: dict[str, Any]) -> dict[str, Any]:
        response = client.post(f"{config.base_url}/api/chat", json=body)
        response.raise_for_status()
        return response.json()

    return send


def build_request(case: dict[str, Any], text: str, config: Config) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config.model,
        "messages": prompts.messages(text, few_shot=config.few_shot),
        "stream": False,
        "options": {
            "temperature": config.temperature,
            "seed": config.seed,
            # Explicit, always. See the module docstring.
            "num_ctx": config.num_ctx,
        },
    }
    if case["category"] in TOOL_CATEGORIES:
        body["tools"] = TOOLS
    elif case["category"] == "extraction":
        body["format"] = RECIPE_SCHEMA
    elif case["category"] == "injection":
        # Injection cases come in both shapes: one that hands over tools to see
        # whether the text can make it call one, and one that extracts.
        if case.get("expect_extraction"):
            body["format"] = RECIPE_SCHEMA
        else:
            body["tools"] = TOOLS
    return body


def to_reply(payload: dict[str, Any], latency_ms: float) -> Reply:
    message = (payload or {}).get("message") or {}
    calls = message.get("tool_calls") or []
    first = (calls[0].get("function") or {}) if calls else {}
    arguments = first.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"__unparsed__": arguments}
    return Reply(
        content=message.get("content") or "",
        tool_name=first.get("name"),
        tool_args=arguments if isinstance(arguments, dict) else {},
        extra_tool_names=[
            (call.get("function") or {}).get("name", "?") for call in calls[1:]
        ],
        latency_ms=latency_ms,
        raw=payload,
    )


# --------------------------------------------------------------------------
# running
# --------------------------------------------------------------------------


@dataclass
class Attempt:
    case_id: str
    category: str
    mode: str  # "repeat" or "paraphrase"
    prompt: str
    verdict: Verdict
    latency_ms: float
    reply: Reply


def load_cases(categories: Iterable[str] | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(CASES_DIR.glob("*.jsonl")):
        if categories and path.stem not in categories:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path.name}:{number} is not valid JSON: {exc}")
            case.setdefault("category", path.stem)
            case.setdefault("id", f"{path.stem}-{number}")
            cases.append(case)
    return cases


def variants(case: dict[str, Any], config: Config) -> list[tuple[str, str]]:
    """(mode, prompt) pairs for one case."""
    out = [("repeat", case["prompt"])] * max(1, config.repeats)
    if config.paraphrases:
        out += [("paraphrase", text) for text in case.get("paraphrases") or []]
    return out


def run(config: Config, transport: Transport, cases: list[dict[str, Any]]) -> list[Attempt]:
    attempts: list[Attempt] = []
    for case in cases:
        for mode, text in variants(case, config):
            body = build_request(case, text, config)
            started = time.perf_counter()
            try:
                payload = transport(body)
            except Exception as exc:  # noqa: BLE001 - the reason goes in the report
                elapsed = (time.perf_counter() - started) * 1000
                attempts.append(
                    Attempt(
                        case["id"], case["category"], mode, text,
                        Verdict(False, f"transport failed: {type(exc).__name__}: {exc}"),
                        elapsed, Reply(),
                    )
                )
                continue
            elapsed = (time.perf_counter() - started) * 1000
            reply = to_reply(payload, elapsed)
            attempts.append(
                Attempt(case["id"], case["category"], mode, text,
                        score(reply, case), elapsed, reply)
            )
            print(".", end="" if attempts.__len__() % 60 else "\n", flush=True)
    print()
    return attempts


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def write_failures(attempts: list[Attempt], path: pathlib.Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    failures = [a for a in attempts if not a.verdict.passed]
    with path.open("w") as handle:
        for attempt in failures:
            handle.write(
                json.dumps(
                    {
                        "case_id": attempt.case_id,
                        "category": attempt.category,
                        "mode": attempt.mode,
                        "prompt": attempt.prompt,
                        "reason": attempt.verdict.reason,
                        "issues": [
                            {"severity": i.severity, "field": i.field, "message": i.message}
                            for i in attempt.verdict.issues
                        ],
                        "output": {
                            "content": attempt.reply.content,
                            "tool_name": attempt.reply.tool_name,
                            "tool_args": attempt.reply.tool_args,
                        },
                        "latency_ms": round(attempt.latency_ms, 1),
                    }
                )
                + "\n"
            )
    return len(failures)


def report(attempts: list[Attempt]) -> str:
    """One table. Repeats and paraphrases are separate columns on purpose --
    they answer different questions and averaging them hides both."""
    categories = sorted({a.category for a in attempts})
    lines = [
        f"{'category':<14} {'repeat':>12} {'paraphrase':>12} {'p50 ms':>8} {'p95 ms':>8}",
        "-" * 58,
    ]
    for category in categories:
        rows = [a for a in attempts if a.category == category]
        latencies = sorted(a.latency_ms for a in rows)
        lines.append(
            f"{category:<14} {_rate(rows, 'repeat'):>12} {_rate(rows, 'paraphrase'):>12} "
            f"{_pct(latencies, 0.5):>8} {_pct(latencies, 0.95):>8}"
        )
    flaky = _flaky(attempts)
    if flaky:
        lines += [
            "",
            "Identical prompts that did not agree with each other "
            "(temperature 0 and a fixed seed should make this empty -- "
            "when it isn't, suspect the machine before the model):",
            *(f"  {case_id}" for case_id in flaky),
        ]
    return "\n".join(lines)


def _rate(rows: list[Attempt], mode: str) -> str:
    subset = [a for a in rows if a.mode == mode]
    if not subset:
        return "-"
    passed = sum(1 for a in subset if a.verdict.passed)
    return f"{passed}/{len(subset)} {passed / len(subset):.0%}"


def _pct(values: list[float], fraction: float) -> str:
    if not values:
        return "-"
    return f"{values[min(int(len(values) * fraction), len(values) - 1)]:.0f}"


def _flaky(attempts: list[Attempt]) -> list[str]:
    by_case: dict[str, list[bool]] = {}
    for attempt in attempts:
        if attempt.mode == "repeat":
            by_case.setdefault(attempt.case_id, []).append(attempt.verdict.passed)
    return sorted(case_id for case_id, outcomes in by_case.items() if len(set(outcomes)) > 1)


# --------------------------------------------------------------------------
# the probe
# --------------------------------------------------------------------------


def probe(config: Config, transport: Transport) -> str:
    """Ask the live box what it actually supports, before trusting a design.

    Three questions, in the order they would break something: does the model
    answer at all, does it call a tool, and -- the one nobody should assume --
    does passing `tools` and `format` together do anything sane.
    """
    findings: list[str] = []

    def attempt(label: str, body: dict[str, Any]) -> dict[str, Any] | None:
        try:
            payload = transport(body)
            findings.append(f"  {label}: ok")
            return payload
        except Exception as exc:  # noqa: BLE001
            findings.append(f"  {label}: FAILED {type(exc).__name__}: {exc}")
            return None

    base = {
        "model": config.model,
        "messages": [{"role": "user", "content": "Reply with the word: ready"}],
        "stream": False,
        "options": {"temperature": 0, "seed": config.seed, "num_ctx": config.num_ctx},
    }
    findings.append(f"probing {config.base_url} with model {config.model!r}")
    attempt("plain chat", dict(base))

    tool_body = dict(base)
    tool_body["messages"] = prompts.messages(
        "What chicken recipes do I have?", few_shot=config.few_shot
    )
    tool_body["tools"] = TOOLS
    payload = attempt("tools", tool_body)
    if payload:
        calls = ((payload.get("message") or {}).get("tool_calls")) or []
        findings.append(f"    -> {len(calls)} tool call(s): "
                        f"{[ (c.get('function') or {}).get('name') for c in calls ]}")

    format_body = dict(base)
    format_body["messages"] = prompts.messages(
        "Extract this recipe:\n\nToast\n\n2 slices bread\n\nToast the bread.",
        few_shot=config.few_shot,
    )
    format_body["format"] = RECIPE_SCHEMA
    payload = attempt("format (json schema)", format_body)
    if payload:
        content = ((payload.get("message") or {}).get("content")) or ""
        findings.append(f"    -> {content[:120]!r}")

    both = dict(format_body)
    both["tools"] = TOOLS
    payload = attempt("tools + format together", both)
    if payload:
        message = payload.get("message") or {}
        findings.append(
            f"    -> tool_calls={len(message.get('tool_calls') or [])}, "
            f"content={(message.get('content') or '')[:80]!r}"
        )
        findings.append(
            "    NOTE: it returned something. Read the above before assuming it "
            "means both constraints applied -- one of them silently winning is "
            "the outcome that would quietly break a design."
        )
    return "\n".join(findings)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=3,
                        help="identical runs per case (default 3)")
    parser.add_argument("--no-paraphrases", action="store_true",
                        help="skip the reworded prompts")
    parser.add_argument("--no-few-shot", action="store_true",
                        help="system prompt only, to measure what the examples buy")
    parser.add_argument("--category", action="append", dest="categories",
                        help="limit to a category (repeatable)")
    parser.add_argument("--probe", action="store_true",
                        help="check what the box supports and exit")
    args = parser.parse_args(argv)

    config = Config.from_env(args)
    transport = http_transport(config)

    if args.probe:
        print(probe(config, transport))
        return 0

    cases = load_cases(args.categories)
    if not cases:
        raise SystemExit("no cases matched")
    print(f"{len(cases)} cases against {config.model} at {config.base_url}")

    attempts = run(config, transport, cases)
    print(report(attempts))

    failures_path = RESULTS_DIR / "failures.jsonl"
    count = write_failures(attempts, failures_path)
    print(f"\n{count} failing attempt(s) written to {failures_path}")
    print("Read them. A score is a number; the reasons are the finding.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
