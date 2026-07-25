"""AI code-generation: turn a ticket into real edits on the connected repo.

Given an issue, the LLM (Groq/…) first extracts literal search strings to locate
the relevant code; those grep the repo's text files; then, seeing the *actual*
file contents, the LLM produces exact find/replace edits that are validated
against the file before being applied. Returns a list of {path, content} changed
files, or [] when it can't determine a concrete change — the caller then falls
back to a placeholder commit so the PR still opens.

This is intentionally scoped to targeted find/replace edits (UI copy, constants,
strings, small logic tweaks) — reliable and reviewable. Larger refactors are out
of scope for now; the change lands on a branch + PR, so it's always reviewed
before merge.
"""
from __future__ import annotations

import base64
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.models.issue import Issue

log = logging.getLogger("cadence.codegen")

_TEXT_EXT = (
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".htm", ".vue", ".svelte",
    ".css", ".scss", ".sass", ".less", ".md", ".mdx", ".txt", ".json", ".yml", ".yaml",
    ".astro", ".php", ".py", ".rb", ".go", ".java", ".kt", ".rs", ".c", ".h", ".cpp",
)
_MAX_FILES_SCAN = 80      # cap text files fetched when grepping
_MAX_FILE_BYTES = 80_000  # skip very large files
_MAX_EDIT_FILES = 3       # cap files sent to the edit LLM per PR


def build_edits(issue: Issue, github, repo) -> list[dict]:
    """Return [{path, content}] real edits for the ticket, or [] if none found."""
    if not settings.ai_api_key:
        return []  # code-gen needs an LLM configured
    if not (repo and repo.full_name):
        return []
    try:
        plan = _generate(_plan_prompt(issue))
    except Exception as e:
        log.warning("codegen: plan step failed: %s", e)
        return []
    terms = [t.strip() for t in (plan.get("search_terms") or []) if isinstance(t, str) and t.strip()]
    if not terms:
        log.info("codegen: no search terms for %s", issue.key)
        return []

    # allow_words so conceptual descriptions ("hero section sentence") still locate
    # the file (e.g. via `hero` in `hero-headline`).
    candidates = _grep(github, repo.full_name, repo.default_branch or "main", terms, allow_words=True)
    if not candidates:
        log.info("codegen: no files matched %s", terms)
        return []

    for path, content in candidates[:_MAX_EDIT_FILES]:
        try:
            edited = _edit_lines(issue, path, content)
        except Exception as e:
            log.warning("codegen: edit step failed for %s: %s", path, e)
            continue
        if edited and edited != content:
            return [{"path": path, "content": edited}]
    return []


def _edit_lines(issue: Issue, path: str, content: str) -> str | None:
    """Line-anchored edit: the LLM returns {line, new} replacements against the
    numbered file. We only touch the named lines (so unrelated code is never
    dropped) and take each new line's content verbatim from the model — robust and
    surgical, in a single call."""
    lines = content.split("\n")
    numbered = "\n".join(f"{i + 1}\t{ln}" for i, ln in enumerate(lines))[:16000]
    data = _generate(_line_edit_prompt(issue, path, numbered))
    result = list(lines)
    changed = 0
    for op in data.get("edits") or []:
        if not isinstance(op, dict):
            continue
        ln, new = op.get("line"), op.get("new")
        if not (isinstance(ln, int) and 1 <= ln <= len(result) and isinstance(new, str)):
            continue
        orig = result[ln - 1]
        # Preserve the original line's indentation if the model dropped it.
        if new and not new[:1].isspace():
            new = orig[: len(orig) - len(orig.lstrip())] + new
        if orig != new:
            result[ln - 1] = new
            changed += 1
    if changed == 0 or changed > 25:  # nothing, or suspiciously broad → bail
        return None
    return "\n".join(result)


def answer_question(issue: Issue, question: str, github=None, repo=None) -> str:
    """Answer a question left in a ticket comment, grounded in the repo's code.

    Researches the connected repo (search terms → grep relevant files) and asks the
    LLM to answer citing what it found. Degrades gracefully: no repo / no matches →
    answers from the ticket context; no LLM configured → a clear notice."""
    if not settings.ai_api_key:
        return "Set an AI key (`CADENCE_AI_API_KEY`) to enable @AI answers."

    parts: list[str] = []
    if github is not None and repo is not None and getattr(repo, "full_name", None):
        base = repo.default_branch or "main"
        # (a) the repo's file list — lets structural questions ("what pages exist?") be answered
        try:
            tree = github._api(f"/repos/{repo.full_name}/git/trees/{base}?recursive=1")
            paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
            if paths:
                parts.append("Repository files:\n" + "\n".join(f"- {p}" for p in paths[:150]))
        except Exception as e:
            log.warning("answer tree fetch failed: %s", e)
        # (b) the contents of the files most relevant to the question
        try:
            plan = _generate(_answer_search_prompt(issue, question))
            terms = [t.strip() for t in (plan.get("search_terms") or []) if isinstance(t, str) and t.strip()]
            if terms:
                files = _grep(github, repo.full_name, base, terms, allow_words=True)[:3]
                for p, c in files:
                    parts.append(f"File `{p}`:\n```\n{c[:4500]}\n```")
        except Exception as e:
            log.warning("answer research failed: %s", e)
    context = "\n\n".join(parts)

    try:
        data = _generate(_answer_prompt(issue, question, context))
        ans = str(data.get("answer") or "").strip()
        return ans or "I couldn't find enough in the code to answer that confidently."
    except Exception as e:
        log.warning("answer generation failed: %s", e)
        return "I hit an error researching that — please try again."


def _answer_search_prompt(issue: Issue, question: str) -> str:
    return (
        "A teammate asked a question about a codebase in a ticket comment. List likely LITERAL "
        "tokens as they'd appear in the source — identifiers, CSS class names (e.g. hero-headline), "
        "component/function names, or short visible UI strings — plus the key nouns from the "
        "question. Prefer real code-shaped tokens over natural-language phrases. Empty list if the "
        "question isn't about the code.\n\n"
        f"Ticket {issue.key}: {issue.title}\nQuestion: {question}\n\n"
        'Return JSON: {"search_terms": ["...", "..."]}'
    )


def _answer_prompt(issue: Issue, question: str, context: str) -> str:
    if context:
        ctx = f"\n\nRelevant code from the repository:\n{context}"
        rule = (
            "Base your answer ONLY on the code shown above and cite the exact file path(s) as "
            "written. Do NOT invent file names, variables, or components that aren't in the code."
        )
    else:
        ctx = ""
        rule = (
            "No repository code was found for this question. Say you couldn't locate the relevant "
            "code in the connected repo, answer from the ticket if you can, and do NOT guess file "
            "or variable names."
        )
    return (
        "You are Cadence AI, answering a question a teammate left in a ticket comment. Answer "
        f"clearly and concretely in a few sentences. {rule}\n\n"
        f"Ticket {issue.key}: {issue.title}\n{(issue.description or '').strip()}\n\n"
        f"Question: {question}{ctx}\n\n"
        'Return JSON: {"answer": "..."}'
    )


def _generate(prompt: str) -> dict:
    # Reuse the configured LLM client (Groq/Gemini/OpenAI-compatible).
    from app.services.ai_live import LiveAiService

    return LiveAiService._generate(prompt)


_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "your", "you", "are", "was",
    "where", "what", "when", "which", "code", "file", "page", "show", "does", "text",
    "have", "into", "here", "there", "would", "should", "about", "make", "made", "used",
}


def _needles(term: str, allow_words: bool = False) -> list[str]:
    """A term plus its shorter contiguous word-windows (longest first), so a phrase
    that's split across lines/markup in the source still matches on a sub-phrase.
    e.g. "Find where you live next" -> ... "you live next" ... which IS contiguous.
    With `allow_words`, also emit significant single words (for question-research,
    where the query is conceptual — e.g. "headline" finds `hero-headline`)."""
    words = term.split()
    n = len(words)
    floor = 3 if n >= 3 else n  # keep windows >= 3 words when possible (precision)
    out: list[str] = []
    for size in range(n, floor - 1, -1):
        for i in range(0, n - size + 1):
            ng = " ".join(words[i : i + size])
            if len(ng) >= 4:
                out.append(ng)
    if allow_words:
        for w in words:
            wl = w.strip(".,:;'\"()[]{}<>").lower()
            if len(wl) >= 4 and wl not in _STOPWORDS and wl not in out:
                out.append(wl)
    return out


def _grep(github, full: str, base: str, terms: list[str], allow_words: bool = False) -> list[tuple[str, str]]:
    """Fetch the repo's text files and return those containing any term (or a
    contiguous sub-phrase / significant word of it), ranked by the most specific
    (longest) match, then by how many distinct needles the file matches."""
    tree = github._api(f"/repos/{full}/git/trees/{base}?recursive=1")
    paths = [
        t["path"]
        for t in tree.get("tree", [])
        if t.get("type") == "blob" and t["path"].lower().endswith(_TEXT_EXT)
    ]
    needles: list[str] = []
    seen: set[str] = set()
    for term in terms:
        for ng in _needles(term, allow_words=allow_words):
            low = ng.lower()
            if low not in seen:
                seen.add(low)
                needles.append(low)

    def _fetch(path: str) -> tuple[str, str] | None:
        try:
            j = github._api(f"/repos/{full}/contents/{path}?ref={base}")
        except Exception:
            return None
        if not isinstance(j, dict) or j.get("encoding") != "base64":
            return None
        raw = base64.b64decode(j["content"])
        if len(raw) > _MAX_FILE_BYTES:
            return None
        return path, raw.decode("utf-8", "replace")

    # Fetch candidate files concurrently — the repo scan is the latency bottleneck.
    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = [r for r in ex.map(_fetch, paths[:_MAX_FILES_SCAN]) if r]

    scored: list[tuple[int, int, str, str]] = []
    for path, txt in fetched:
        low = txt.lower()
        matched = [ng for ng in needles if ng in low]
        if matched:
            scored.append((max(len(ng) for ng in matched), len(matched), path, txt))
    scored.sort(key=lambda s: (-s[0], -s[1]))  # longest match, then most matches
    return [(p, c) for _, _, p, c in scored]


def _plan_prompt(issue: Issue) -> str:
    return (
        "You are Cadence's code assistant. A ticket describes a change to make in a code "
        "repository. Extract literal search strings that would LOCATE the code to change — "
        "exact substrings likely present verbatim in the source (visible UI text, identifiers, "
        "constants). Prefer SHORT distinctive substrings of 2-4 words — long phrases "
        "may be split across lines or markup in the source and won't match. Give several.\n\n"
        f"Ticket {issue.key}: {issue.title}\n{(issue.description or '').strip()}\n\n"
        'Return JSON: {"search_terms": ["...", "..."]}'
    )


def _line_edit_prompt(issue: Issue, path: str, numbered: str) -> str:
    return (
        "You are a senior engineer editing a source file to satisfy a ticket. Each line below is "
        "prefixed with 'LINENUMBER<TAB>'. Apply REAL logic — edit the actual code (visible text, "
        "JSX, markup, values).\n"
        "Rules:\n"
        "- Return the minimal line replacements: for each changed line give its number and the FULL "
        "new content of that line, copying its exact leading indentation.\n"
        "- The result MUST stay valid: if the text you are changing spans several lines/tags, edit "
        "EVERY one of those lines together — put the new text on the element's opening line and set "
        "the leftover inner lines to \"\" — so tags stay balanced. Never orphan text or leave a tag "
        "unclosed.\n"
        "- For a headline/hero 'sentence', edit the <h1>/heading element (keep its tag and class).\n"
        "- Change ONLY what the ticket asks; do not touch unrelated lines.\n\n"
        f"Ticket {issue.key}: {issue.title}\n{(issue.description or '').strip()}\n\n"
        f"File: {path}\n{numbered}\n\n"
        'Return JSON: {"edits": [{"line": <number>, "new": "<full new line content>"}]}'
    )
