# Contributing to WindowsAgent

Thank you for helping make Windows desktop automation more reliable.

---

## Ways to contribute

### 1. Report bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include:
- Windows version
- Python version
- Target app name and version
- What you expected vs what happened
- Full error output (if any)

### 2. Submit an app profile

Each app profile teaches WindowsAgent how to handle a specific Windows application's quirks.
See [profiles/community/README.md](../profiles/community/README.md) for the golden path.

**Good candidates:**
- Apps with virtualised lists (email clients, task managers)
- Apps that steal focus unexpectedly
- Apps with non-standard scroll behaviour
- WebView2 wrappers with custom UI

### 3. Fix bugs or add features

1. Fork the repository
2. Create a branch: `git checkout -b fix/brief-description`
3. Make your changes
4. Run the test suite: `pytest tests/ -m "not integration"`
5. Push and open a pull request

---

## Development setup

```bash
git clone https://github.com/ibraheem4/windowsagent.git
cd windowsagent
pip install -e ".[dev]"
```

Run unit tests (no Windows apps required):
```bash
pytest tests/ -m "not integration" -v
```

Run integration tests (Windows 10/11 with apps available):
```bash
pytest tests/ -v
```

Lint and type check:
```bash
ruff check windowsagent/
mypy windowsagent/
```

---

## Code standards

- Every public function must have a docstring
- Type hints on all function signatures
- No bare `except` clauses — catch specific exceptions
- Follow existing patterns in the codebase
- UK English in all comments and documentation

---

## Pull request guidelines

- Keep PRs focused on one change
- Write a clear description explaining *why*, not just *what*
- Integration tests for new app profiles are strongly encouraged
- Update ARCHITECTURE.md if you change a module's public interface

---

## Community app profiles

The most impactful contribution is a well-tested app profile for a new application.
Each profile extends WindowsAgent's reach without touching the core.

See [profiles/community/README.md](../profiles/community/README.md) for format and submission guidelines.
