"""Optional AI tender summaries via OpenAI or Groq (configurable). Falls back
to a deterministic extractive stub when no API key is configured."""
import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_PROMPT = (
    "Summarize this Indian government tender in exactly 3 short bullet points "
    "covering: what is being procured, who is procuring it, and key dates/value. "
    "Reply with one bullet per line, no numbering.\n\n{text}"
)


def summarize_tender(title: str, description: str | None, organisation: str | None,
                     closing: str | None, value: str | None) -> tuple[str, list[str]]:
    text = (
        f"Title: {title}\nOrganisation: {organisation or 'N/A'}\n"
        f"Closing date: {closing or 'N/A'}\nEstimated value: {value or 'N/A'}\n"
        f"Description: {(description or '')[:4000]}"
    )

    provider = settings.ai_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        bullets = _chat_completion(
            "https://api.openai.com/v1/chat/completions",
            settings.openai_api_key, "gpt-4o-mini", text)
        if bullets:
            return "openai", bullets
    elif provider == "groq" and settings.groq_api_key:
        bullets = _chat_completion(
            "https://api.groq.com/openai/v1/chat/completions",
            settings.groq_api_key, "llama-3.1-8b-instant", text)
        if bullets:
            return "groq", bullets

    return "stub", _stub_summary(title, organisation, closing, value)


def _chat_completion(url: str, api_key: str, model: str, text: str) -> list[str] | None:
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": _PROMPT.format(text=text)}],
                "max_tokens": 200,
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        bullets = [b.strip("•-* \t") for b in content.splitlines() if b.strip()]
        return bullets[:3] or None
    except Exception as exc:
        logger.warning("AI summary call failed: %s", exc)
        return None


def _stub_summary(title: str, organisation: str | None, closing: str | None,
                  value: str | None) -> list[str]:
    return [
        f"Procurement: {title[:140]}",
        f"Procuring entity: {organisation or 'See tender document'}",
        f"Closing date: {closing or 'See portal'} · Estimated value: {value or 'Not disclosed'}",
    ]
