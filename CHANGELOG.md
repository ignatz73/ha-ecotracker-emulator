# Change Log & Executed Commands

## Session: 2026-10-12

### Executed Commands
```bash
# Executed unit tests for power filter, fast drop threshold, and power offset
PYTHONPATH=. python3 -m unittest tests/test_power_filter.py

# Created git feature branch and committed changes
git checkout -b feat/power-filter-fast-drop-offset
git config user.name "walter" && git config user.email "walter@werther-web.de"
git add .
git commit -m "feat: add power low-pass filter, fast-drop threshold, and offset (v0.2.0)"
```

### Summary of Changes

1. **Version Bump**:
   - Bumped integration minor version in `manifest.json` from `0.1.1` to `0.2.0`.

2. **Global & Project Context Instructions**:
   - Created `GEMINI.md` and `AGENTS.md` in `/home/uwe/ai/ha` containing comprehensive local Home Assistant rules, anti-patterns, decision workflows, and validation scripts.
   - Updated global user memory `/home/uwe/.gemini/GEMINI.md` to persist rules for:
     - Creating logfiles with summaries of changes and commands across sessions.
     - Always planning proposed changes and asking for confirmation before executing.
     - Never posting or making requests outside the local network without user confirmation.

3. **EcoTracker Emulator (`ha-ecotracker-emulator`) Features**:
   - **`const.py`**: Added configuration keys and defaults for `power_filter_seconds`, `power_fast_drop_threshold`, and `power_offset`.
   - **`config_flow.py`**: Added fields in `EcotrackerOptionsFlow` for power low-pass filter time constant (s), fast-drop threshold (W), and power offset (W).
   - **`api.py`**: Implemented `_apply_power_filter_and_offset` function applying exponential low-pass smoothing, immediate filter bypass when power drops by $\ge$ threshold, and static power offset.
   - **`__init__.py`**: Added `filter_state` dictionary initialization to `hass.data[DOMAIN][entry.entry_id]`.
   - **Translations (`en.json`, `de.json`)**: Added English and German UI labels for the new option fields.
   - **Tests (`tests/test_power_filter.py`)**: Added unit tests covering disabled filter, offset calculation, low-pass smoothing, and fast-drop threshold bypass logic.
   - **Documentation (`README.md`, `README.de.md`, `TODO.md`, `MEMORY.md`)**: Updated documentation and workspace memory to reflect the new features.
