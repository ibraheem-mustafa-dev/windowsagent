"""Tests for JSONL workflow replay."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestReplayLoader:
    def test_loads_jsonl_file(self) -> None:
        from windowsagent.replay import load_workflow

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                json.dumps({"action": "click", "window": "Notepad", "element": "Save"})
                + "\n"
            )
            f.write(
                json.dumps({
                    "action": "type",
                    "window": "Notepad",
                    "element": "Editor",
                    "params": {"text": "Hello"},
                })
                + "\n"
            )
            path = f.name

        steps = load_workflow(path)
        assert len(steps) == 2
        assert steps[0]["action"] == "click"
        assert steps[1]["params"]["text"] == "Hello"
        Path(path).unlink()

    def test_skips_blank_lines(self) -> None:
        from windowsagent.replay import load_workflow

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"action": "click"}) + "\n")
            f.write("\n")
            f.write("   \n")
            f.write(json.dumps({"action": "type"}) + "\n")
            path = f.name

        steps = load_workflow(path)
        assert len(steps) == 2
        Path(path).unlink()

    def test_skips_invalid_json(self) -> None:
        from windowsagent.replay import load_workflow

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"action": "click"}) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps({"action": "type"}) + "\n")
            path = f.name

        steps = load_workflow(path)
        assert len(steps) == 2
        Path(path).unlink()


class TestVariableSubstitution:
    def test_substitutes_variables(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "Dear ${recipient}, here is the ${report}"}
        variables = {"recipient": "Amir", "report": "Q4 report"}
        result = substitute_variables(params, variables)
        assert result["text"] == "Dear Amir, here is the Q4 report"

    def test_missing_variable_raises(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "Dear ${recipient}"}
        with pytest.raises(ValueError, match="recipient"):
            substitute_variables(params, {})

    def test_non_string_values_passed_through(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "Hello ${name}", "amount": 5, "flag": True}
        result = substitute_variables(params, {"name": "Bean"})
        assert result["text"] == "Hello Bean"
        assert result["amount"] == 5
        assert result["flag"] is True

    def test_no_variables_returns_unchanged(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "No variables here"}
        result = substitute_variables(params, {})
        assert result["text"] == "No variables here"

    def test_multiple_same_variable(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "${name} and ${name}"}
        result = substitute_variables(params, {"name": "Bean"})
        assert result["text"] == "Bean and Bean"
