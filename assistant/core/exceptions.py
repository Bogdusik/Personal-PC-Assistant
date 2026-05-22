from __future__ import annotations


class AssistantError(Exception):
    pass


class OllamaError(AssistantError):
    pass


class ConfigError(AssistantError):
    pass


class SkillError(AssistantError):
    pass


class AudioError(AssistantError):
    pass
