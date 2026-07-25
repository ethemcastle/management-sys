"""Live AI implementation backed by a free LLM (Google Gemini by default).

`LiveAiService` extends `MockAiService`, overriding the *summarization* methods
(`summarize`, `assistant`) to call a real model. Everything else is inherited:
`create_pr` stays deterministic (a summarizer can't open a real PR), and `solve`
therefore produces a **real AI diagnosis** (via `summarize`) plus the mock PR.

Activated when `CADENCE_AI_API_KEY` is set (see `get_ai_service`). Every call
degrades gracefully: on any network/parse/quota error it falls back to the mock
response, so the UI never breaks.

Default endpoint is Gemini's `generateContent` (free tier). Point `CADENCE_AI_BASE_URL`
+ `CADENCE_AI_MODEL` at a local Ollama (`http://localhost:11434`) for a no-key,
fully-offline setup — see the README.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.models.issue import Issue
from app.schemas.requests import AssistantContext
from app.services.ai_service import MockAiService, Summary, _affected_files

log = logging.getLogger("cadence.ai")

_PRIORITY = ["Low", "Medium", "High", "Urgent"]


class LiveAiService(MockAiService):
    """Real summaries via a free LLM; mock behavior for everything else."""

    # --- overridden AI methods -------------------------------------------------
    def summarize(self, issue: Issue) -> Summary:
        prompt = (
            "You are risr/crm, an assistant for a software team's issue tracker. "
            "Summarize the issue below for a busy engineer skimming it. Be concise, "
            "specific, and grounded ONLY in the data given — do not invent facts.\n\n"
            f"{self._issue_context(issue)}\n\n"
            'Return JSON with this exact shape:\n'
            '{"bullets": ["3 to 5 short bullets: what it is, code/PR status, risks, '
            'and a final \\"Net: ...\\" bullet"], '
            '"resolution": "one or two sentences suggesting how to resolve it"}'
        )
        try:
            data = self._generate(prompt)
            bullets = [str(b).strip() for b in data.get("bullets", []) if str(b).strip()]
            resolution = str(data.get("resolution", "")).strip()
            if not bullets or not resolution:
                raise ValueError("model returned empty bullets/resolution")
            # `files` stays heuristic — a summarizer shouldn't fabricate real paths.
            return Summary(bullets=bullets[:5], summary=resolution, files=_affected_files(issue))
        except Exception as e:  # network, quota, malformed JSON, etc.
            log.warning("LiveAiService.summarize fell back to mock: %s", e)
            return super().summarize(issue)

    def assistant(self, question: str, context: AssistantContext) -> list[str]:
        prompt = (
            "You are risr/crm's workspace assistant. Answer the user's question in 2 to 4 "
            "short, practical bullets. End with a bullet starting 'Net:'. "
            f"The user is on the '{context.view}' view in the '{context.space.value}' space.\n\n"
            f"Question: {question}\n\n"
            'Return JSON: {"bullets": ["...", "..."]}'
        )
        try:
            data = self._generate(prompt)
            bullets = [str(b).strip() for b in data.get("bullets", []) if str(b).strip()]
            if not bullets:
                raise ValueError("model returned no bullets")
            return bullets[:5]
        except Exception as e:
            log.warning("LiveAiService.assistant fell back to mock: %s", e)
            return super().assistant(question, context)

    # --- helpers ---------------------------------------------------------------
    @staticmethod
    def _issue_context(issue: Issue) -> str:
        lines = [
            f'Issue {issue.key} — "{issue.title}"',
            f"Type: {issue.type.value} · Status: {issue.status.value} · "
            f"Priority: {_PRIORITY[issue.priority] if 0 <= issue.priority < 4 else issue.priority} · "
            f"{issue.points} points",
            f"Assignee: {issue.assignee.name if issue.assignee else 'Unassigned'}",
        ]
        if issue.labels:
            lines.append("Labels: " + ", ".join(issue.labels))
        if issue.blocked:
            lines.append("This issue is marked BLOCKED.")
        if issue.description:
            lines.append("\nDescription:\n" + issue.description.strip()[:1500])

        pr = issue.pr
        if pr:
            lines.append(
                f"\nPull request #{pr.num} on branch `{pr.branch}` — state {pr.state.value}, "
                f"CI {pr.checks.value}, +{pr.additions}/-{pr.deletions} across "
                f"{pr.files_changed} files."
            )
            if pr.reviewers:
                lines.append(
                    "Reviewers: " + ", ".join(r.member.name for r in pr.reviewers)
                )
        else:
            lines.append("\nNo branch or PR yet (unstarted from a code perspective).")

        comments = list(issue.comments or [])
        if comments:
            lines.append(f"\nThread ({len(comments)} entries):")
            for c in comments[:25]:
                who = c.author.name if c.author else c.author_initials
                tag = "commit" if c.kind == "commit" else "comment"
                lines.append(f"- [{who}, {tag}] {c.body.strip()[:400]}")
        return "\n".join(lines)

    @staticmethod
    def _generate(prompt: str) -> dict:
        """Call the LLM and return the parsed JSON object. Raises on any failure.

        Dispatches on `CADENCE_AI_PROVIDER`: 'gemini' (Google, native API) or
        'openai' (any OpenAI-compatible chat endpoint — Groq, OpenRouter, Mistral,
        local Ollama, OpenAI itself)."""
        if (settings.ai_provider or "gemini").lower() == "openai":
            return LiveAiService._generate_openai(prompt)
        return LiveAiService._generate_gemini(prompt)

    @staticmethod
    def _generate_gemini(prompt: str) -> dict:
        base = settings.ai_base_url.rstrip("/")
        url = f"{base}/models/{settings.ai_model}:generateContent"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        }
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": settings.ai_api_key or "", "Content-Type": "application/json"},
            json=body,
            timeout=45.0,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    @staticmethod
    def _generate_openai(prompt: str) -> dict:
        base = settings.ai_base_url.rstrip("/")
        body = {
            "model": settings.ai_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.ai_api_key or ''}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=45.0,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return json.loads(text)
