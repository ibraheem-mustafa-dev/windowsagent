"""
Browser grounding module for WindowsAgent.

Provides structured browser control via Chrome DevTools Protocol (CDP).
Instead of screenshots + vision models, extracts a virtual page from the
browser's accessibility tree and DOM layout — 3.3x faster than screenshot-based
approaches (68s vs 225s per task, based on browser-use/Stagehand v3 research).

Known limitations:
1. Canvas/WebGL content — screenshot fallback only.
2. Closed shadow DOM — inaccessible with any external tool.
3. Accessibility.getFullAXTree is "Experimental" in CDP spec — stable since 2017.
4. AX tree inaccurate on poorly-authored sites (no ARIA labels) — fallback to
   JS heuristics in future versions.
5. backendDOMNodeId invalidated by navigation and React remounts — re-extract
   each step (never cache VirtualPage across steps).
6. Cross-origin iframes need Target.attachToTarget (v2 — skipped in v1).
"""

from windowsagent.browser.grounder import BrowserGrounding
from windowsagent.browser.virtual_page import VirtualElement, VirtualPage

__all__ = ["BrowserGrounding", "VirtualElement", "VirtualPage"]
