import math
import sys
import time
import unittest
from unittest.mock import MagicMock

# Mock homeassistant and zeroconf dependencies before importing custom component
sys.modules["zeroconf"] = MagicMock()
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.http"] = MagicMock()
sys.modules["homeassistant.components.network"] = MagicMock()
sys.modules["homeassistant.components.network.const"] = MagicMock()
sys.modules["homeassistant.components.zeroconf"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()

from custom_components.ecotracker_emulator.api import _apply_power_filter_and_offset
from custom_components.ecotracker_emulator.const import (
    CONF_POWER_FAST_DROP_THRESHOLD,
    CONF_POWER_FILTER_SECONDS,
    CONF_POWER_OFFSET,
)


class TestPowerFilterAndOffset(unittest.TestCase):
    def test_disabled_filter_and_zero_offset(self):
        options = {
            CONF_POWER_FILTER_SECONDS: 0,
            CONF_POWER_FAST_DROP_THRESHOLD: 0,
            CONF_POWER_OFFSET: 0,
        }
        filter_state = {}
        now = 1000.0

        res = _apply_power_filter_and_offset("power", 200.0, options, filter_state, now)
        self.assertEqual(res, 200)

        # Subsequent call with no filter and no offset
        res2 = _apply_power_filter_and_offset("power", 150.0, options, filter_state, now + 1.0)
        self.assertEqual(res2, 150)

    def test_offset_only(self):
        options = {
            CONF_POWER_FILTER_SECONDS: 0,
            CONF_POWER_FAST_DROP_THRESHOLD: 0,
            CONF_POWER_OFFSET: 15.0,
        }
        filter_state = {}
        now = 1000.0

        res = _apply_power_filter_and_offset("power", 200.0, options, filter_state, now)
        self.assertEqual(res, 215)

        res2 = _apply_power_filter_and_offset("power", -50.0, options, filter_state, now + 1.0)
        self.assertEqual(res2, -35)

    def test_lowpass_filter_smoothing(self):
        # 10s filter time constant
        options = {
            CONF_POWER_FILTER_SECONDS: 10,
            CONF_POWER_FAST_DROP_THRESHOLD: 0,
            CONF_POWER_OFFSET: 0,
        }
        filter_state = {}
        now = 1000.0

        # Step 1: initial reading = 200W
        res1 = _apply_power_filter_and_offset("power", 200.0, options, filter_state, now)
        self.assertEqual(res1, 200)

        # Step 2: raw increases to 300W after 2s
        now += 2.0
        # alpha = 1 - exp(-2/10) = 1 - exp(-0.2) ≈ 0.181269
        # expected = 200 + 0.181269 * (300 - 200) = 218.1269...
        res2 = _apply_power_filter_and_offset("power", 300.0, options, filter_state, now)
        expected = 200.0 + (1.0 - math.exp(-0.2)) * 100.0
        self.assertAlmostEqual(res2, round(expected, 1), places=1)

    def test_fast_drop_threshold_bypass(self):
        # 10s filter, 20W fast drop threshold
        options = {
            CONF_POWER_FILTER_SECONDS: 10,
            CONF_POWER_FAST_DROP_THRESHOLD: 20,
            CONF_POWER_OFFSET: 0,
        }
        filter_state = {}
        now = 1000.0

        # Step 1: 200W initial
        _apply_power_filter_and_offset("power", 200.0, options, filter_state, now)

        # Step 2: Small drop of 10W (from 200W to 190W) -> filter SHOULD apply
        now += 2.0
        res_small_drop = _apply_power_filter_and_offset("power", 190.0, options, filter_state, now)
        # Drop is 10W < 20W threshold -> filtered
        self.assertNotEqual(res_small_drop, 190)

        # Step 3: Fast drop of 50W (from 190W to 140W) -> SHOULD bypass filter immediately!
        now += 2.0
        res_fast_drop = _apply_power_filter_and_offset("power", 140.0, options, filter_state, now)
        self.assertEqual(res_fast_drop, 140)

        # State should be reset to 140
        self.assertEqual(filter_state["power"]["last_raw"], 140.0)
        self.assertEqual(filter_state["power"]["last_filtered"], 140.0)

    def test_combination_filter_drop_and_offset(self):
        options = {
            CONF_POWER_FILTER_SECONDS: 10,
            CONF_POWER_FAST_DROP_THRESHOLD: 20,
            CONF_POWER_OFFSET: 5.0,
        }
        filter_state = {}
        now = 1000.0

        # Initial: 200W -> with offset = 205W
        res1 = _apply_power_filter_and_offset("power", 200.0, options, filter_state, now)
        self.assertEqual(res1, 205)

        # Drop by 50W (to 150W) -> Fast drop triggers -> 150 + offset 5 = 155W
        now += 1.0
        res2 = _apply_power_filter_and_offset("power", 150.0, options, filter_state, now)
        self.assertEqual(res2, 155)


if __name__ == "__main__":
    unittest.main()
