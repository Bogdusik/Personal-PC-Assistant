try:
    from .registry import SKILLS
    from .app_control import APP_ALIASES
except ImportError:
    SKILLS = {}
    APP_ALIASES = {}

__all__ = ["SKILLS", "APP_ALIASES"]
