from __future__ import annotations

import subprocess
from dataclasses import dataclass, field


@dataclass
class AssistantState:
    cfg: dict = field(default_factory=dict)
    hotkey: str = "right shift"
    mic_device: int | str | None = None
    last_text: str = ""
    ollama_process: subprocess.Popen | None = None
