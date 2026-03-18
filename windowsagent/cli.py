"""
Command-line interface for WindowsAgent.

Provides direct access to observe, act, serve, and config operations
from the Windows command prompt or PowerShell.

Usage:
    windowsagent windows
    windowsagent observe --window "Notepad"
    windowsagent act --window "Notepad" --action type --element "Text Editor" --text "Hello"
    windowsagent serve
    windowsagent version
    windowsagent config show
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from windowsagent import __version__


@click.group()
@click.version_option(version=__version__, prog_name="windowsagent")
def cli() -> None:
    """WindowsAgent — open-source AI agent for Windows desktop automation."""


# ── windowsagent windows ─────────────────────────────────────────────────────


@cli.command()
@click.option("--json-output", is_flag=True, help="Output as JSON")
def windows(json_output: bool) -> None:
    """List all visible top-level windows."""
    from windowsagent.observer.uia import get_windows

    try:
        wins = get_windows()
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if json_output:
        click.echo(json.dumps([
            {
                "title": w.title,
                "app_name": w.app_name,
                "pid": w.pid,
                "hwnd": w.hwnd,
            }
            for w in wins
        ], indent=2))
        return

    if not wins:
        click.echo("No visible windows found.")
        return

    click.echo(f"{'Title':<50} {'App':<25} {'PID':>8}")
    click.echo("-" * 85)
    for w in wins:
        title = w.title[:48] + ".." if len(w.title) > 50 else w.title
        app = w.app_name[:23] + ".." if len(w.app_name) > 25 else w.app_name
        click.echo(f"{title:<50} {app:<25} {w.pid:>8}")


# ── windowsagent window ──────────────────────────────────────────────────────


@cli.command(name="window")
@click.option("--title", "-w", required=True, help="Window title (partial match)")
@click.option("--action", "-a", required=True,
              type=click.Choice([
                  "activate", "minimise", "maximise", "restore", "close",
                  "geometry", "bring-to-front", "send-to-back",
              ]),
              help="Window management action")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def window_manage(title: str, action: str, json_output: bool) -> None:
    """Manage window state — activate, minimise, maximise, restore, close."""
    from windowsagent import window_manager

    try:
        win = window_manager.find_window(title)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    action_clean = action.replace("-", "_")

    if action_clean == "geometry":
        geom = window_manager.get_geometry(win)
        if json_output:
            click.echo(json.dumps({
                "left": geom.left, "top": geom.top,
                "width": geom.width, "height": geom.height,
            }, indent=2))
        else:
            click.echo(
                f"{win.title}: {geom.width}x{geom.height} at ({geom.left}, {geom.top})"
            )
        return

    fn_map = {
        "activate": window_manager.activate,
        "minimise": window_manager.minimise,
        "maximise": window_manager.maximise,
        "restore": window_manager.restore,
        "close": window_manager.close,
        "bring_to_front": window_manager.bring_to_front,
        "send_to_back": window_manager.send_to_back,
    }

    fn = fn_map.get(action_clean)
    if fn is None:
        click.echo(f"Unknown action: {action}", err=True)
        sys.exit(1)

    result = fn(win)
    if json_output:
        click.echo(json.dumps({"success": result, "action": action, "window": title}))
    elif result:
        click.echo(f"[OK] {action} on {title!r}")
    else:
        click.echo(f"[FAIL] {action} on {title!r}", err=True)
        sys.exit(1)


# ── windowsagent observe ─────────────────────────────────────────────────────


@cli.command()
@click.option("--window", "-w", required=True, help="Window title (partial match)")
@click.option("--depth", "-d", default=8, show_default=True, help="Max UIA tree depth")
@click.option("--output-dir", type=click.Path(), default=None, help="Save screenshot to directory")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def observe(window: str, depth: int, output_dir: str | None, json_output: bool) -> None:
    """Capture UIA tree and screenshot for a window."""
    from windowsagent.agent import Agent
    from windowsagent.config import load_config

    config = load_config()
    agent = Agent(config)

    try:
        state = agent.observe(window)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        screenshot_path = out_path / f"{window.replace(' ', '_')}_screenshot.png"
        try:
            state.screenshot.image.save(str(screenshot_path))
            click.echo(f"Screenshot saved: {screenshot_path}")
        except Exception as exc:
            click.echo(f"Warning: could not save screenshot: {exc}", err=True)

    if json_output:
        from windowsagent.server import _serialise_app_state
        data = _serialise_app_state(state)
        click.echo(json.dumps(data, indent=2))
        return

    # Human-readable output
    click.echo(f"\nWindow: {state.window_title!r}")
    click.echo(f"App:    {state.app_name} (PID {state.pid})")
    click.echo(f"WebView2: {state.is_webview2_app}")
    click.echo(f"Screenshot: {state.screenshot.logical_width}x{state.screenshot.logical_height} "
               f"@ {state.screenshot.dpi_scale:.0%} DPI")
    click.echo(f"\nUIA Tree (depth {depth}):")
    _print_tree(state.uia_tree.root, indent=0)


def _print_tree(element: Any, indent: int) -> None:
    """Recursively print the UIA tree."""
    prefix = "  " * indent
    name_str = f" {element.name!r}" if element.name else ""
    value_str = f" = {element.value!r}" if element.value else ""
    patterns_str = f" [{', '.join(element.patterns)}]" if element.patterns else ""
    enabled_str = "" if element.is_enabled else " [disabled]"
    click.echo(f"{prefix}{element.control_type}{name_str}{value_str}{patterns_str}{enabled_str}")
    for child in element.children:
        _print_tree(child, indent + 1)


# ── windowsagent act ─────────────────────────────────────────────────────────


@cli.command()
@click.option("--window", "-w", required=True, help="Window title (partial match)")
@click.option("--action", "-a", required=True,
              type=click.Choice([
                  "click", "type", "scroll", "key", "expand", "toggle", "select",
                  "activate", "minimise", "maximise", "restore",
              ]),
              help="Action to perform")
@click.option("--element", "-e", default="", help="Target element description")
@click.option("--text", "-t", default=None, help="Text to type (for --action type)")
@click.option("--key", "-k", default=None, help="Key to press (for --action key)")
@click.option("--keys", default=None, help="Hotkey combo, comma-separated (e.g. ctrl,s)")
@click.option("--direction", default="down",
              type=click.Choice(["up", "down", "left", "right"]),
              help="Scroll direction (for --action scroll)")
@click.option("--amount", default=3, show_default=True, help="Scroll amount")
@click.option("--json-output", is_flag=True, help="Output result as JSON")
def act(
    window: str,
    action: str,
    element: str,
    text: str | None,
    key: str | None,
    keys: str | None,
    direction: str,
    amount: int,
    json_output: bool,
) -> None:
    """Execute a single action on a window element."""
    from windowsagent.agent import Agent
    from windowsagent.config import load_config

    config = load_config()
    agent = Agent(config)

    # Build params dict
    params: dict[str, Any] = {}
    if text is not None:
        params["text"] = text
    if key is not None:
        params["key"] = key
    if keys is not None:
        params["keys"] = [k.strip() for k in keys.split(",")]
    if action == "scroll":
        params["direction"] = direction
        params["amount"] = amount

    try:
        result = agent.act(window, action, element, params)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if json_output:
        click.echo(json.dumps({
            "success": result.success,
            "action": result.action,
            "target": result.target,
            "error": result.error,
            "diff_pct": result.diff_pct,
            "duration_ms": result.duration_ms,
        }, indent=2))
        return

    if result.success:
        diff_str = f" ({result.diff_pct:.0%} change)" if result.diff_pct > 0 else ""
        click.echo(f"[OK] {action} on {element!r} succeeded{diff_str} in {result.duration_ms:.0f}ms")
    else:
        click.echo(f"[FAIL] {action} on {element!r} failed: {result.error}", err=True)
        if not json_output:
            sys.exit(1)


# ── windowsagent serve ───────────────────────────────────────────────────────


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host")
@click.option("--port", default=7862, show_default=True, help="Bind port")
@click.option("--record", is_flag=True, default=False, help="Record all actions to JSONL replay files")
def serve(host: str, port: int, record: bool) -> None:
    """Start the WindowsAgent HTTP server."""
    if record:
        from windowsagent.config import load_config
        from windowsagent.recorder import start_recording
        config = load_config()
        path = start_recording(config.replay_dir)
        click.echo(f"Recording enabled: {path}")

    from windowsagent.server import run_server
    click.echo(f"Starting WindowsAgent server on http://{host}:{port}")
    click.echo("Press Ctrl+C to stop")
    run_server(host=host, port=port)


# ── windowsagent version ─────────────────────────────────────────────────────


@cli.command(name="version")
def show_version() -> None:
    """Show WindowsAgent version."""
    click.echo(f"WindowsAgent v{__version__}")


# ── windowsagent config ───────────────────────────────────────────────────────


@cli.group(name="config")
def config_group() -> None:
    """Manage WindowsAgent configuration."""


@config_group.command(name="show")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def config_show(json_output: bool) -> None:
    """Show the current resolved configuration."""
    from dataclasses import asdict

    from windowsagent.config import load_config

    config = load_config()

    if json_output:
        data = {
            k: v for k, v in asdict(config).items()
            if k != "vision_api_key"  # Never show API keys
        }
        data["vision_api_key"] = "***" if config.vision_api_key else "(not set)"
        click.echo(json.dumps(data, indent=2))
        return

    click.echo("WindowsAgent Configuration")
    click.echo("=" * 40)
    for key, value in asdict(config).items():
        if key == "vision_api_key":
            display_value = "***" if config.vision_api_key else "(not set)"
        else:
            display_value = repr(value)
        click.echo(f"  {key:<30} {display_value}")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the windowsagent CLI."""
    cli()


if __name__ == "__main__":
    main()
