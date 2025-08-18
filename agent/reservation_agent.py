from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


from .tools import (
    load_catalog,
    ReservationStore,
    search_restaurants,
    check_availability,
    create_reservation,
    cancel_reservation,
    modify_reservation,
    recommend,
    check_reservations,
)

# ---- Provider wrappers -------------------------------------------------------

class ProviderConfig(BaseModel):
    """LLM provider settings."""
    provider: str = Field("gemini", description="gemini | openai | groq | openrouter")
    model: str = Field("gemini-2.5-flash", description="model name for the provider")
    api_key: str = Field("", description="API key for the provider")
    base_url: Optional[str] = Field(
        None,
        description="Optional base URL (OpenRouter etc.). If not set, uses provider defaults.",
    )


class LLMRouter:
    """Minimal wrapper to unify provider calls -> returns string content."""

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self._client = None  # lazily constructed

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        # Gemini-style single prompt (we’ll still send role tags for clarity)
        return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

    # -- Provider-specific senders --------------------------------------------

    def _ensure_gemini(self):
        import google.generativeai as genai

        api_key = self.cfg.api_key.strip() or os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("No Gemini API key. Provide it in the sidebar (or set GEMINI_API_KEY).")
        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(self.cfg.model)

    def _send_gemini(self, messages: List[Dict[str, str]]) -> str:
        if self._client is None:
            self._ensure_gemini()
        prompt = self._messages_to_prompt(messages)
        resp = self._client.generate_content(prompt)
        return getattr(resp, "text", "") or ""

    def _ensure_openai_like(self):
        # OpenAI + OpenRouter share an OpenAI-compatible client
        from openai import OpenAI

        api_key = (
            self.cfg.api_key.strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
            or os.getenv("OPENROUTER_API_KEY", "").strip()
        )
        if not api_key:
            raise ValueError("No OpenAI/OpenRouter API key. Provide it in the sidebar.")
        base_url = self.cfg.base_url or (
            "https://openrouter.ai/api/v1" if self.cfg.provider == "openrouter" else None
        )
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def _send_openai_like(self, messages: List[Dict[str, str]]) -> str:
        if self._client is None:
            self._ensure_openai_like()
        resp = self._client.chat.completions.create(model=self.cfg.model, messages=messages)
        return (resp.choices[0].message.content or "").strip()

    def _ensure_groq(self):
        from groq import Groq

        api_key = self.cfg.api_key.strip() or os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError("No Groq API key. Provide it in the sidebar (or set GROQ_API_KEY).")
        self._client = Groq(api_key=api_key)

    def _send_groq(self, messages: List[Dict[str, str]]) -> str:
        if self._client is None:
            self._ensure_groq()
        resp = self._client.chat.completions.create(model=self.cfg.model, messages=messages)
        return (resp.choices[0].message.content or "").strip()

    # -- Public entrypoint -----------------------------------------------------

    def send(self, messages: List[Dict[str, str]]) -> str:
        p = self.cfg.provider.lower()
        if p == "gemini":
            return self._send_gemini(messages)
        if p in ("openai", "openrouter"):
            return self._send_openai_like(messages)
        if p == "groq":
            return self._send_groq(messages)
        raise ValueError(f"Unsupported provider: {self.cfg.provider}")


# ---- Reservation Agent -------------------------------------------------------

TOOL_SPECS = [
    {"name": "search_restaurants", "description": "Search the restaurant catalog by filters"},
    {"name": "check_availability", "description": "Check availability for a restaurant and time"},
    {"name": "create_reservation", "description": "Create a reservation"},
    {"name": "cancel_reservation", "description": "Cancel an existing reservation"},
    {"name": "modify_reservation", "description": "Modify an existing reservation"},
    {"name": "recommend", "description": "Recommend venues for user intent"},
]


class ReservationAgent:
    """Tool-using conversational agent for reservations."""

    def __init__(self, catalog_path: str, provider: Optional[ProviderConfig] = None):
        self.df = load_catalog(catalog_path)
        self.store = ReservationStore()
        self.cfg = provider or ProviderConfig()
        self.llm = LLMRouter(self.cfg)

    # ---------- tools mapping (arguments should match tools.py names) ---------
    def _tool_router(self, name: str):
        return {
            "search_restaurants": lambda **kw: search_restaurants(self.df, **kw),
            "check_availability": lambda **kw: check_availability(self.df, self.store, **kw),
            "create_reservation": lambda **kw: create_reservation(self.df, self.store, **kw),
            "cancel_reservation": lambda **kw: cancel_reservation(self.store, **kw),
            "modify_reservation": lambda **kw: modify_reservation(self.df, self.store, **kw),
            "recommend": lambda **kw: recommend(self.df, kw),
        }.get(name)

    # ----------------- prompting & parsing helpers ----------------------------
    def system_prompt(self) -> str:
        return (
            "You are GoodFoods Reservation Assistant. You can call tools to search venues, "
            "check times, and manage bookings.\n\n"
            "TOOLS: " + ", ".join(t['name'] for t in TOOL_SPECS) + "\n\n"
            "If a tool is needed, reply **only** with JSON in this exact format:\n"
            '{ "tool": "<tool_name>", "arguments": { ... } }\n'
            "Use these argument names:\n"
            "- cancel_reservation: { reservation_id }\n"
            "- modify_reservation: { reservation_id, updates }\n"
            "- create_reservation: { restaurant_id, customer_name, phone, start_time, duration_mins, party_size, notes }\n"
            "- check_availability: { restaurant_id, start_time, duration_mins, party_size }\n"
            "- search_restaurants / recommend: relevant filters.\n"
            "If no tool is required, answer normally in plain text.\n"
            "Always confirm with the user before you actually create, modify, or cancel a reservation."
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Try hard to parse a tool call JSON from the model text."""
        # 1) direct JSON
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2) fenced ```json ... ```
        m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # 3) first {...} block
        m = re.search(r"(\{.*\})", text, flags=re.S)
        if m:
            block = m.group(1)
            # try to find a balanced-ish JSON block (quick heuristic)
            # trim after the last closing brace
            last = block.rfind("}")
            if last != -1:
                try:
                    return json.loads(block[: last + 1])
                except Exception:
                    pass
        return None

    # ------------------------------ chat loop ---------------------------------
    async def converse(
        self, user_input: str, history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        history = history or []
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [
            {"role": "user", "content": user_input}
        ]

        # 1) ask the model
        text = self.llm.send(messages)
        tool_outputs: List[Dict[str, Any]] = []

        # 2) tool call?
        parsed = self._extract_json(text)
        if isinstance(parsed, dict) and "tool" in parsed:
            fn = self._tool_router(parsed["tool"])
            if fn:
                try:
                    args = parsed.get("arguments", {}) or {}

                    # Execute tool
                    result = fn(**args)
                    tool_outputs.append({"tool": parsed["tool"], "result": result})

                    # 3) feed tool result back to model for final user-facing message
                    followup = self.llm.send(
                        messages
                        + [
                            {"role": "assistant", "content": text},
                            {"role": "tool", "content": json.dumps(tool_outputs)},
                        ]
                    )
                    return {"assistant": followup, "tool_outputs": tool_outputs}

                except Exception as e:
                    tool_outputs.append({"tool": parsed["tool"], "error": str(e)})

        # 4) no tool used: return model text directly
        return {"assistant": text, "tool_outputs": tool_outputs}
