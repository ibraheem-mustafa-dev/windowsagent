"""
Grounder module — matches a natural language description to a UI element.

Components:
- uia_grounder.py: Match via the UIA accessibility tree (fast, no API cost)
- vision_grounder.py: Match via vision language model + screenshot (fallback)
- hybrid.py: Try UIA first, fall back to vision automatically
"""

from windowsagent.grounder.hybrid import ground
from windowsagent.grounder.uia_grounder import GroundedElement

__all__ = ["GroundedElement", "ground"]
