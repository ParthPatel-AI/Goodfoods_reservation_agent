from __future__ import annotations
import os, json, asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
# Lightweight shim so app.py can continue importing AgentRuntime, ProviderConfig
from .reservation_agent import ReservationAgent as AgentRuntime, ProviderConfig

from .tools import (
    load_catalog, ReservationStore,
    search_restaurants, check_availability,
    create_reservation, cancel_reservation,
    modify_reservation, recommend,
    add_reservation, remove_reservation, change_reservation_details
)

# Providers
import google.generativeai as genai
from openai import OpenAI
import requests

# ---- Tool specs ----
TOOL_SPECS = [
    {"name": "search_restaurants", "description": "Search the restaurant catalog by filters"},
    {"name": "check_availability", "description": "Check availability for a restaurant and time"},
    {"name": "create_reservation", "description": "Create a reservation"},
    {"name": "cancel_reservation", "description": "Cancel an existing reservation"},
    {"name": "modify_reservation", "description": "Modify an existing reservation"},
    {"name": "add_reservation", "description": "Add a new reservation"},
    {"name": "remove_reservation", "description": "Remove a reservation by ID"},
    {"name": "change_reservation_details", "description": "Update reservation details (time, party size, notes, etc.)"},
    {"name": "recommend", "description": "Recommend venues for user intent"} 
]

class ProviderConfig(BaseModel):
    provider: str = Field("gemini", description="Provider: gemini, groq, openai, openrouter")
    model: str = Field("gemini-2.5-flash", description="Model name")
    api_key: str = Field("", description="API key for provider")

class AgentRuntime:
    def __init__(self, catalog_path: str, provider: Optional[ProviderConfig]=None):
        self.df = load_catalog(catalog_path)
        self.store = ReservationStore()
        self.provider = provider or ProviderConfig()

        prov = self.provider.provider.lower()
        key = self.provider.api_key.strip() or os.getenv(
            {
                "gemini": "GEMINI_API_KEY",
                "openai": "OPENAI_API_KEY",
                "groq": "GROQ_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
            }.get(prov, ""),
            ""
        ).strip()

        if not key:
            raise ValueError(f"No {prov.title()} API key provided. Please paste it in the sidebar settings.")

        if prov == "gemini":
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel(self.provider.model)
            self._chat = self._chat_gemini

        elif prov == "openai":
            self.client = OpenAI(api_key=key)
            self._chat = self._chat_openai

        elif prov == "groq":
            # Groq also uses OpenAI-compatible API
            self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)
            self._chat = self._chat_openai

        elif prov == "openrouter":
            self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            self._chat = self._chat_openai

        else:
            raise ValueError(f"Provider {prov} not implemented.")

    # ---- Tool routing ----
    def _tool_router(self, name: str):
        return {
        "search_restaurants": lambda **kw: search_restaurants(self.df, **kw),
        "check_availability": lambda **kw: check_availability(self.df, self.store, **kw),
        "create_reservation": lambda **kw: create_reservation(self.df, self.store, **kw),
        "cancel_reservation": lambda **kw: cancel_reservation(self.store, **kw),
        "modify_reservation": lambda **kw: modify_reservation(self.df, self.store, **kw),
        "add_reservation": lambda **kw: add_reservation(self.df, self.store, **kw),
        "remove_reservation": lambda **kw: remove_reservation(self.store, **kw),
        "change_reservation_details": lambda **kw: change_reservation_details(self.df, self.store, **kw),
        "recommend": lambda **kw: recommend(self.df, kw),
        }.get(name)

    def system_prompt(self) -> str:
        return (
            "You are GoodFoods Reservation Assistant. Your goal is to understand user intent "
            "and decide when to call tools. Available tools: "
            + ", ".join([t["name"] for t in TOOL_SPECS]) +
            ".\n"
            "When you decide a tool is needed, respond strictly in JSON with:\n"
            "{ \"tool\": <tool_name>, \"arguments\": { ... } }\n"
            "If no tool is needed, just answer normally.\n"
            "Ask concise clarifying questions if crucial details are missing. Always confirm before booking."
        )

    # ---- LLM wrappers ----
    async def _chat_gemini(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        conversation = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        resp = self.model.generate_content(conversation)
        return {"content": resp.text}

    async def _chat_openai(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        resp = self.client.chat.completions.create(model=self.provider.model, messages=messages)
        return {"content": resp.choices[0].message.content}

    # ---- Main converse ----
    async def converse(self, user_input: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        history = history or []
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": user_input}]

        raw = await self._chat(messages)
        text = raw.get("content", "")
        tool_outputs = []

        try:
            parsed = json.loads(text)
            if "tool" in parsed:
                fn = self._tool_router(parsed["tool"])
                if fn:
                    try:
                        result = fn(**parsed.get("arguments", {}))
                        tool_outputs.append({"tool": parsed["tool"], "result": result})

                        followup = await self._chat(messages + [
                            {"role": "assistant", "content": text},
                            {"role": "tool", "content": json.dumps(tool_outputs)}
                        ])
                        return {"assistant": followup.get("content", ""), "tool_outputs": tool_outputs}

                    except Exception as e:
                        tool_outputs.append({"tool": parsed["tool"], "error": str(e)})

        except Exception:
            pass

        return {"assistant": text, "tool_outputs": tool_outputs}
