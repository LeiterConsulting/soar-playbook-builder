"""Offline tutor lane — lessons, quizzes, datapath explain (no MCP required)."""

from __future__ import annotations

import re
from typing import Any

LESSON_INDEX: list[dict[str, str]] = [
    {"slug": "curriculum", "title": "Curriculum map"},
    {"slug": "concepts/datapaths", "title": "Datapaths"},
    {"slug": "concepts/containers", "title": "Containers & cases"},
    {"slug": "concepts/blocks", "title": "Blocks & callbacks"},
    {"slug": "lessons/01-hello-playbook", "title": "Your first playbook"},
    {"slug": "lessons/02-collect-artifacts", "title": "Collect artifacts"},
    {"slug": "lessons/05-packaging-import", "title": "Packaging and import"},
    {"slug": "lessons/06-debug-and-test", "title": "Debug and test"},
    {"slug": "patterns/es-notable-response", "title": "ES notable response"},
    {"slug": "patterns/phishing-enrichment", "title": "Phishing enrichment"},
]

LESSON_CONTENT: dict[str, str] = {
    "curriculum": (
        "**SOAR Playbook Builder curriculum**\n\n"
        "1. Hello playbook — `on_start`, notes, `on_finish`\n"
        "2. Collect artifacts — datapaths and `phantom.collect2`\n"
        "3. Decision blocks — severity and branching\n"
        "4. Action blocks — `phantom.act` and assets\n"
        "5. Packaging & import — `.tgz` for SOAR 8.x\n"
        "6. Debug & test — Run on a case, read action results\n\n"
        "Try: `lesson 01-hello-playbook` or `quiz datapaths`"
    ),
    "concepts/datapaths": (
        "**Datapaths** tell SOAR where to read data on a case.\n\n"
        "- `artifact:*.cef.sourceAddress` — all source IPs from artifacts\n"
        "- `container:severity` — case severity\n"
        "- `playbook_input:my_param` — playbook input\n\n"
        "CEF field names are **camelCase** (`sourceAddress`, not `source_address`).\n\n"
        "Try: `explain artifact:*.cef.sourceAddress`"
    ),
    "concepts/containers": (
        "**Containers** are SOAR cases. Playbooks receive a `container` dict in callbacks.\n\n"
        "ES export creates a container with artifacts carrying CEF fields from the notable.\n"
        "Playbook auto-run often matches on **container label** — keep ES export labels consistent."
    ),
    "concepts/blocks": (
        "**Classic Python playbooks** use callbacks: `on_start(container)` is the entry point.\n\n"
        "Visual Editor blocks map to `phantom.collect2` (collect) and `phantom.act` (action).\n"
        "Every playbook should call `on_finish(container)` when done."
    ),
    "lessons/01-hello-playbook": (
        "**Lesson 1 — Hello playbook**\n\n"
        "```python\n"
        "import phantom.app as phantom\n\n"
        "def on_start(container):\n"
        "    phantom.add_note(container=container, content='Hello', title='Demo')\n"
        "    on_finish(container)\n\n"
        "def on_finish(container):\n"
        "    phantom.debug('done')\n"
        "```\n\n"
        "Load the **Hello World** template in Build → Import → Run on case **9005**."
    ),
    "lessons/02-collect-artifacts": (
        "**Lesson 2 — Collect artifacts**\n\n"
        "Use `phantom.collect2` with a datapath list to gather IOCs before acting:\n\n"
        "`datapath=['artifact:*.cef.sourceAddress']`\n\n"
        "Validate camelCase — wrong casing yields empty collections."
    ),
    "lessons/05-packaging-import": (
        "**Lesson 5 — Packaging and import**\n\n"
        "SOAR 8.x imports playbooks as **base64-encoded `.tgz`** (gzip tar).\n"
        "The sidecar **Import to SOAR** action packages your draft automatically.\n\n"
        "After import, open the Visual Editor or run on a linked case."
    ),
    "lessons/06-debug-and-test": (
        "**Lesson 6 — Debug and test**\n\n"
        "1. Link a case (`container_id` in the URL)\n"
        "2. Readiness → fix placeholders\n"
        "3. Import → Run on this case\n"
        "4. Inspect action results on the case timeline\n\n"
        "Use Help → Demo Data for sample cases 9001–9005."
    ),
    "patterns/es-notable-response": (
        "**ES notable response** — note-only playbook for Mission Control / ES exports.\n"
        "Use when you need documentation on the case without destructive actions."
    ),
    "patterns/phishing-enrichment": (
        "**Phishing enrichment** — collect URL/hash artifacts and enrich before response.\n"
        "Pair with sample case **9002** on the Run tab."
    ),
}

QUIZ_BANK: dict[str, list[dict[str, str]]] = {
    "datapaths": [
        {
            "question": "Which datapath collects all source IP addresses from artifacts?",
            "choices": "a) artifact:*.cef.source_address\nb) artifact:*.cef.sourceAddress\nc) container:sourceAddress",
            "answer": "b",
            "explanation": "CEF uses camelCase: sourceAddress. Use artifact:* for all artifacts.",
        },
    ],
    "containers": [
        {
            "question": "Which container field do playbooks often match for ES auto-run?",
            "choices": "a) owner_id\nb) label\nc) name\nd) id",
            "answer": "b",
            "explanation": "Playbook triggers use container label; ES export must set the same label.",
        },
    ],
    "packaging": [
        {
            "question": "What format does SOAR 8.x import_playbook expect?",
            "choices": "a) Raw .py\nb) Base64 gzipped TAR\nc) JSON COA only",
            "answer": "b",
            "explanation": "SOAR 8.x requires .tgz, base64-encoded in the REST body.",
        },
    ],
    "blocks": [
        {
            "question": "Which function runs when a classic playbook starts?",
            "choices": "a) on_finish\nb) main\nc) on_start",
            "answer": "c",
            "explanation": "Classic playbooks use on_start as the entry callback.",
        },
    ],
    "fundamentals": [
        {
            "question": "What holds IOCs like IPs on a SOAR case?",
            "choices": "a) Events\nb) Artifacts\nc) Actions",
            "answer": "b",
            "explanation": "Artifacts carry CEF fields from alerts.",
        },
    ],
}

TOPIC_ALIASES: dict[str, str] = {
    "cef": "datapaths",
    "datapath": "datapaths",
    "events": "fundamentals",
    "callbacks": "blocks",
    "import": "packaging",
    "debug": "packaging",
    "hello": "blocks",
}


def list_lessons_payload() -> dict[str, Any]:
    return {"status": "success", "lessons": LESSON_INDEX, "count": len(LESSON_INDEX)}


def get_lesson_payload(slug: str) -> dict[str, Any]:
    key = (slug or "").strip().strip("/")
    if not key:
        return {"status": "error", "error": "lesson slug required"}
    if key in LESSON_CONTENT:
        return {
            "status": "success",
            "slug": key,
            "title": next((r["title"] for r in LESSON_INDEX if r["slug"] == key), key),
            "content": LESSON_CONTENT[key],
            "tutor_lane": "lesson",
        }
    # Partial match
    for row in LESSON_INDEX:
        if key in row["slug"] or row["slug"].endswith(key):
            return get_lesson_payload(row["slug"])
    return {
        "status": "error",
        "error": f"Unknown lesson `{key}`. Try `lesson 01-hello-playbook` or list_lessons.",
    }


def explain_datapath(datapath: str) -> dict[str, Any]:
    parts = datapath.split(".")
    explanation: list[str] = []

    if datapath.startswith("artifact:"):
        explanation.append("Reads from container artifacts.")
        if "*." in datapath:
            explanation.append("`*` means all artifacts on the case.")
    elif datapath.startswith("container:"):
        explanation.append("Reads a field from the container (case) object.")
    elif datapath.startswith("playbook_input:"):
        explanation.append("Reads a playbook input parameter.")
    elif datapath.startswith("action_result:"):
        explanation.append("Reads output from a prior action block.")
    else:
        explanation.append("Verify against SOAR datapath documentation.")

    if "cef" in datapath:
        explanation.append("CEF segment uses camelCase (e.g. sourceAddress).")

    warnings: list[str] = []
    if "_address" in datapath and "Address" not in datapath:
        warnings.append("Likely wrong casing — use sourceAddress not source_address")

    return {
        "datapath": datapath,
        "segments": parts,
        "explanation": " ".join(explanation),
        "warnings": warnings,
    }


def _resolve_quiz_topic(raw: str) -> str:
    topic = (raw or "fundamentals").strip().lower()
    return TOPIC_ALIASES.get(topic, topic)


def quiz_payload(topic: str) -> dict[str, Any]:
    key = _resolve_quiz_topic(topic)
    questions = QUIZ_BANK.get(key) or QUIZ_BANK.get("fundamentals", [])
    if not questions:
        return {"status": "error", "error": f"No quiz for topic `{topic}`"}
    q = questions[0]
    body = (
        f"**Quiz — {key}**\n\n"
        f"{q['question']}\n\n"
        f"{q['choices']}\n\n"
        f"_Answer: {q['answer']}_ — {q['explanation']}"
    )
    return {"status": "success", "content": body, "tutor_lane": "quiz", "topic": key}


def is_tutor_intent(message: str) -> bool:
    lower = (message or "").strip().lower()
    if not lower:
        return False
    if lower.startswith(("lesson ", "quiz ", "explain ", "help me understand ", "what is a datapath")):
        return True
    if lower.startswith("explain") and ("datapath" in lower or "artifact:" in lower or "container:" in lower):
        return True
    return False


def handle_tutor_message(message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return tutor-lane chat payload (content only — no scaffold)."""
    _ = context
    text = (message or "").strip()
    lower = text.lower()

    if lower in ("lessons", "list lessons", "curriculum"):
        lines = ["**Lessons** (try `lesson <slug>`):\n"]
        for row in LESSON_INDEX:
            lines.append(f"- `{row['slug']}` — {row['title']}")
        return {"status": "success", "content": "\n".join(lines), "tutor_lane": "index"}

    if lower.startswith("lesson "):
        slug = text.split(None, 1)[1] if len(text.split()) > 1 else "curriculum"
        payload = get_lesson_payload(slug)
        if payload.get("status") == "success":
            payload["content"] = payload.get("content", "")
        return payload

    if lower.startswith("quiz"):
        topic = text[4:].strip() if lower.startswith("quiz ") else "fundamentals"
        return quiz_payload(topic)

    dp_match = re.search(
        r"(artifact:[^\s]+|container:[^\s]+|playbook_input:[^\s]+|action_result:[^\s]+)",
        text,
    )
    if lower.startswith("explain ") or "datapath" in lower or dp_match:
        dp = dp_match.group(1) if dp_match else "artifact:*.cef.sourceAddress"
        info = explain_datapath(dp)
        warn = f"\n\n⚠️ {'; '.join(info['warnings'])}" if info["warnings"] else ""
        return {
            "status": "success",
            "content": f"**Datapath:** `{info['datapath']}`\n\n{info['explanation']}{warn}",
            "tutor_lane": "explain",
        }

    return {
        "status": "success",
        "content": (
            "I'm the **Explain** tutor. Try:\n"
            "- `lesson 01-hello-playbook`\n"
            "- `quiz datapaths`\n"
            "- `explain artifact:*.cef.sourceAddress`\n"
            "- `list lessons`"
        ),
        "tutor_lane": "help",
    }
