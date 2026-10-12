"""HTTP view that serves the EcoTracker-compatible /v1/json payload."""
from __future__ import annotations

import logging
import math
import time

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    API_PATH,
    CONF_POWER_FAST_DROP_THRESHOLD,
    CONF_POWER_FILTER_SECONDS,
    CONF_POWER_OFFSET,
    DEFAULT_POWER_FAST_DROP_THRESHOLD,
    DEFAULT_POWER_FILTER_SECONDS,
    DEFAULT_POWER_OFFSET,
    DEFAULT_VALUES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Fields that are expected in watts / watt-hours according to the EcoTracker
# spec. Sensors mapped here may report in a different unit (especially kWh for
# energy meters in Home Assistant) – we normalise on the fly so the JSON output
# always matches the spec the EcoFlow inverters expect.
_POWER_FIELDS: frozenset[str] = frozenset(
    {"power", "powerAvg", "powerPhase1", "powerPhase2", "powerPhase3"}
)
_ENERGY_FIELDS: frozenset[str] = frozenset(
    {"energyCounterIn", "energyCounterOut"}
)

# Multipliers to bring a sensor reading to the spec unit. Keys are
# unit_of_measurement strings as Home Assistant exposes them.
_POWER_TO_W: dict[str, float] = {
    "W": 1.0,
    "kW": 1_000.0,
    "MW": 1_000_000.0,
    "mW": 0.001,
}
_ENERGY_TO_WH: dict[str, float] = {
    "Wh": 1.0,
    "kWh": 1_000.0,
    "MWh": 1_000_000.0,
}


def _convert(key: str, value: float, unit: str | None) -> float:
    """Convert ``value`` to the spec unit (W for power, Wh for energy).

    Unknown / missing units are passed through unchanged with a debug log; this
    keeps sensors with non-standard units usable while making mismatches
    diagnosable from the log.
    """
    if key in _POWER_FIELDS:
        table = _POWER_TO_W
    elif key in _ENERGY_FIELDS:
        table = _ENERGY_TO_WH
    else:
        return value

    if unit is None:
        return value
    factor = table.get(unit)
    if factor is None:
        _LOGGER.debug(
            "Unknown unit %r for field %s; passing value through unchanged",
            unit,
            key,
        )
        return value
    return value * factor


def _apply_power_filter_and_offset(
    key: str,
    raw_value: float,
    options: dict,
    filter_state: dict,
    now: float | None = None,
) -> float | int:
    """Apply low-pass filtering, fast-drop threshold, and power offset to power fields."""
    if key not in _POWER_FIELDS:
        return raw_value

    try:
        filter_seconds = float(
            options.get(CONF_POWER_FILTER_SECONDS, DEFAULT_POWER_FILTER_SECONDS)
        )
    except (ValueError, TypeError):
        filter_seconds = float(DEFAULT_POWER_FILTER_SECONDS)

    try:
        fast_drop_threshold = float(
            options.get(
                CONF_POWER_FAST_DROP_THRESHOLD, DEFAULT_POWER_FAST_DROP_THRESHOLD
            )
        )
    except (ValueError, TypeError):
        fast_drop_threshold = float(DEFAULT_POWER_FAST_DROP_THRESHOLD)

    try:
        power_offset = float(options.get(CONF_POWER_OFFSET, DEFAULT_POWER_OFFSET))
    except (ValueError, TypeError):
        power_offset = float(DEFAULT_POWER_OFFSET)

    if now is None:
        now = time.monotonic()

    state = filter_state.get(key)

    if state is None:
        filtered_value = raw_value
    else:
        last_raw = state["last_raw"]
        last_filtered = state["last_filtered"]
        last_time = state["timestamp"]
        dt = max(0.0, now - last_time)

        drop_amount = last_raw - raw_value

        # If consumption decreases by >= fast_drop_threshold (when configured > 0),
        # immediately adopt raw_value (bypass low-pass filter and reset filter state).
        if fast_drop_threshold > 0 and drop_amount >= fast_drop_threshold:
            filtered_value = raw_value
        elif filter_seconds > 0 and dt > 0:
            alpha = 1.0 - math.exp(-dt / filter_seconds)
            filtered_value = last_filtered + alpha * (raw_value - last_filtered)
        else:
            filtered_value = raw_value

    filter_state[key] = {
        "last_raw": raw_value,
        "last_filtered": filtered_value,
        "timestamp": now,
    }

    result = filtered_value + power_offset
    if result.is_integer():
        return int(result)
    return round(result, 1)


class EcotrackerJsonView(HomeAssistantView):
    url = API_PATH
    name = "ecotracker_emulator:json"
    requires_auth = False

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]
        entry = self._get_entry(hass)
        if not entry:
            return self.json({"error": "not configured"}, status=500)

        options = entry.options
        filter_state = self._get_filter_state(hass, entry)
        now = time.monotonic()
        data: dict[str, float | int] = {}

        for key in DEFAULT_VALUES:
            val = None
            entity_id = options.get(f"{key}_entity")
            if entity_id:
                state = hass.states.get(entity_id)
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        raw = float(state.state)
                    except (ValueError, TypeError):
                        pass
                    else:
                        unit = state.attributes.get("unit_of_measurement")
                        val = _convert(key, raw, unit)

            if val is None:
                # No usable sensor value. Check omit setting or fallback.
                if options.get(f"{key}_omit", False):
                    continue
                try:
                    val = float(options.get(f"{key}_fallback", 0))
                except (ValueError, TypeError):
                    val = 0.0

            if key in _POWER_FIELDS:
                val = _apply_power_filter_and_offset(
                    key, val, options, filter_state, now
                )

            data[key] = val

        return self.json(data)

    def _get_entry(self, hass: HomeAssistant):
        entries = hass.config_entries.async_entries(DOMAIN)
        return entries[0] if entries else None

    def _get_filter_state(self, hass: HomeAssistant, entry) -> dict:
        domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        return domain_data.setdefault("filter_state", {})
