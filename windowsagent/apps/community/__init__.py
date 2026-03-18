"""
Community app profiles — auto-discovered from this directory.

Any Python file in this directory (except files starting with '_') that contains
a class inheriting from BaseAppProfile will be automatically registered.

To add a new profile:
1. Copy _template.py to your_app.py
2. Copy _template_meta.yml to your_app_meta.yml
3. Implement the profile class (see _template.py for guidance)
4. Run tests: pytest tests/ -m "not integration" -q
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from windowsagent.apps.base import BaseAppProfile

logger = logging.getLogger(__name__)


def discover_profiles() -> list[type[BaseAppProfile]]:
    """Scan this directory for BaseAppProfile subclasses.

    Imports every public module (name not starting with '_') in the community
    directory and collects all classes that inherit from BaseAppProfile.

    Returns:
        List of profile classes, sorted by module name for deterministic order.
    """
    from windowsagent.apps.base import BaseAppProfile

    profiles: list[type[BaseAppProfile]] = []

    for importer, module_name, is_pkg in pkgutil.iter_modules(__path__):
        if module_name.startswith("_"):
            continue

        try:
            module = importlib.import_module(f"{__name__}.{module_name}")
        except Exception:
            logger.warning("Failed to import community profile %r", module_name, exc_info=True)
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseAppProfile)
                and obj is not BaseAppProfile
                and obj.__module__ == module.__name__
            ):
                profiles.append(obj)
                logger.debug("Discovered community profile: %s from %s", obj.__name__, module_name)

    profiles.sort(key=lambda cls: cls.__module__)
    return profiles
