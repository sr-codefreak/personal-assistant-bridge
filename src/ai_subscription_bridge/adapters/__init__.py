"""Adapter factory."""

from __future__ import annotations

from ai_subscription_bridge.adapters.personal_assistant import PersonalAssistantAdapter


def build_adapter(name: str) -> PersonalAssistantAdapter:
    if name == "personal-assistant":
        return PersonalAssistantAdapter()
    raise ValueError("unsupported_adapter")


__all__ = ["PersonalAssistantAdapter", "build_adapter"]
