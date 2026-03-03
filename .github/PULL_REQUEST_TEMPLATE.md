## What does this PR do?

Brief description of the change and why it's needed.

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] New app profile
- [ ] Documentation update
- [ ] Refactoring (no behaviour change)

## Testing

- [ ] Unit tests pass: `pytest tests/ -m "not integration"`
- [ ] Integration tests pass on Windows 10/11 (if applicable)
- [ ] Lint passes: `ruff check windowsagent/`
- [ ] Type check passes: `mypy windowsagent/`

## App profile checklist (if submitting an app profile)

- [ ] Profile extends `BaseAppProfile`
- [ ] `is_match()` correctly identifies the target app
- [ ] Profile handles the app's known quirks
- [ ] Integration test exists in `tests/apps/`
- [ ] Profile documented in `profiles/community/`

## Screenshots / output

Paste relevant CLI output or screenshot here if helpful.
