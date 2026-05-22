try:
    from .app_control import APP_ALIASES
    from .registry import SKILLS
except ImportError:
    SKILLS = {}
    APP_ALIASES = {}

__all__ = ["SKILLS", "APP_ALIASES"]
