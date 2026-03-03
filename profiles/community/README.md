# Community App Profiles

This directory contains app profiles contributed by the community.

Each profile teaches WindowsAgent how to handle a specific Windows application's quirks and provides convenience methods for common operations.

---

## How to submit a community profile

### 1. Create your profile file

Create a Python file at `profiles/community/<app_name>.py`:

```python
"""
App profile for [App Name].

[Brief description of any quirks or special handling]
"""

from windowsagent.apps.base import BaseAppProfile
from windowsagent.observer.uia import WindowInfo


class MyAppProfile(BaseAppProfile):
    app_names = ["myapp.exe"]
    window_titles = ["My App"]

    def is_match(self, window_info: WindowInfo) -> bool:
        return "myapp.exe" in window_info.app_name.lower()

    def get_scroll_strategy(self):
        return "keyboard"  # or "scroll_pattern" or "webview2"

    def requires_focus_restore(self) -> bool:
        return False  # Set True if app steals focus
```

### 2. Add a PROFILE.md file

Create `profiles/community/<app_name>-PROFILE.md` documenting:
- App name and supported versions
- Windows versions tested
- Known quirks handled by the profile
- Example usage

### 3. Add a test

Create `profiles/community/<app_name>-test.py` with at least one integration test:

```python
import pytest

@pytest.mark.integration
def test_open_and_observe():
    # Test that the app opens and the profile can observe it
    pass
```

### 4. Submit a pull request

Open a PR with the title `[App Profile] My App Name`.

---

## Profile conventions

- Class name: `<AppName>Profile` (e.g. `PaintProfile`, `TeamViewerProfile`)
- `app_names`: lowercase process names (e.g. `["mspaint.exe"]`)
- `window_titles`: partial strings that appear in the window title
- Override only the methods where the app needs special handling
- Add docstrings explaining *why* any override is needed

---

## Reviewing submitted profiles

All community profiles are reviewed for:
- Correctness (does it actually handle the app's quirks?)
- Safety (no destructive actions without confirmation)
- Code quality (type hints, docstrings, specific exceptions)
- Test coverage (at least one integration test)
