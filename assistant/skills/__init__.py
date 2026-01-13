try:
    from .skills import SKILLS, APP_ALIASES
except ImportError:
    SKILLS = {}
    APP_ALIASES = {}

__all__ = ['SKILLS', 'APP_ALIASES']