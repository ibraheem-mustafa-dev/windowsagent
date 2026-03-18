# Contributing a Community App Profile

Community profiles extend WindowsAgent to automate additional Windows applications.

## Quick Start

1. **Inspect the app's UIA tree:**

   ```
   windowsagent observe --window "Your App" --json-output > app_tree.json
   ```

   This gives you the element names, AutomationIds, and control types.

2. **Copy the templates:**

   ```
   cp _template.py your_app.py
   cp _template_meta.yml your_app_meta.yml
   ```

3. **Fill in your profile class:**
   - Set `app_names` to the process name(s) shown in Task Manager
   - Set `window_titles` to partial title strings
   - Add verified UIA element names to `known_elements`
   - Add keyboard shortcuts to `shortcuts`
   - Implement `is_match()` to identify your app's windows
   - Override strategy methods if the defaults don't work

4. **Run the tests:**

   ```
   pytest tests/ -m "not integration" -q
   ```

5. **Submit a pull request** with your `.py` and `_meta.yml` files.

## Guidelines

- **Verify UIA names live.** Run `windowsagent observe` on a real instance. Don't guess names from documentation — they vary by version and locale.
- **Note your locale.** Button names like "Colour" vs "Color" depend on Windows language settings. Document which locale you tested in the `_meta.yml`.
- **Include common phrasings.** Map multiple natural-language descriptions to the same UIA name (e.g. "search", "search bar", "search box" all pointing to the same element).
- **Test scroll and text input.** Not all apps respond to UIA ScrollPattern or ValuePattern. Try each strategy and pick the one that works.
- **Keep files under 250 lines.** Split complex profiles if needed.

## File Naming

- Profile: `your_app.py` (lowercase, underscores)
- Metadata: `your_app_meta.yml`
- Files starting with `_` are ignored by auto-discovery

## What Makes a Good Profile

- 10+ known_elements covering the most-used UI elements
- 5+ keyboard shortcuts for common actions
- Correct scroll and text input strategies (tested, not guessed)
- Clear `is_match()` that won't false-positive on similar apps
