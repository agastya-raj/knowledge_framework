---
title: "OpenROADM NETCONF Driver Evolution — From Raw XML to Agent-Friendly API"
type: pattern
tags: [netconf, yang, openroadm, optical, sdk, driver-design]
domain: optical-networking
created: 2026-02-28
updated: 2026-02-28
confidence: high
complexity: high
related: [digital_twin_optical_network]
---

## Problem

Optical network devices (ILAs, ROADMs, transceivers) expose NETCONF/YANG interfaces that return deeply nested XML. Agents interacting with these devices waste significant time parsing raw xmltodict output, extracting values from OpenConfig namespace-prefixed enums, and handling the `{instant: "X"}` pattern used by OpenConfig PM counters. The gap between "device speaks XML" and "agent needs flat dicts" is a recurring source of friction.

## Context

- Juniper TCX-1000 ILA with OpenROADM + OpenConfig YANG models
- `ncclient` for NETCONF, `xmltodict` for XML→dict conversion
- OpenConfig uses namespace prefixes: `{"@xmlns:oc-opt-amp": "...", "#text": "oc-opt-amp:CONSTANT_GAIN"}`
- PM counters use `{instant: "10.01"}` dicts instead of plain floats
- Agent (Claude Code) needs clean Python dicts for reasoning and decision-making

## Approach

Layer the driver into three tiers:

1. **Raw NETCONF** — `_get_raw_amplifiers()`, `_get_config()`, `_edit_and_commit()` — direct XML interaction
2. **Parsing helpers** — `_instant()`, `_oc_enum()` — reusable across all OpenConfig devices
3. **Agent-friendly API** — `get_amplifier_status()`, `get_alarms()` — flat dicts, no XML knowledge needed

## Key Decisions

- **Flat dicts over nested**: `{"input_power_dBm": -13.5}` not `{"state": {"input-power-total": {"instant": "-13.52"}}}`. Agents reason better with flat structures.
- **Units in key names**: `target_gain_dB`, `pump_temp_C`, `laser_bias_mA` — eliminates ambiguity for agents that don't know optical conventions.
- **Backward compat**: `get_pm_data()` kept but now returns `{"ab": {...}, "ba": {...}}` keyed by amp name. New code should use `get_amplifier_status()`.
- **Constants as module-level**: `GAIN_RANGE_LOW`, `AMP_MODE_CONSTANT_GAIN` — importable, validatable, documented.

## Key Code

### OpenConfig `{instant: "X"}` extraction

```python
@staticmethod
def _instant(val: Any) -> float | None:
    """Extract float from an ``{instant: "X"}`` dict or plain string.

    WHY: OpenConfig PM counters wrap values in {instant: "10.01"} dicts.
    xmltodict preserves this structure. Every PM field needs unwrapping.
    Without this helper, every caller repeats the same dict-access + float cast.
    """
    if val is None:
        return None
    if isinstance(val, dict):
        val = val.get("instant")
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
```

### OpenConfig namespace-prefixed enum extraction

```python
@staticmethod
def _oc_enum(val: Any) -> str | None:
    """Extract bare enum name from OpenConfig xmlns-prefixed value.

    WHY: xmltodict preserves XML namespace attributes, giving us:
    {"@xmlns:oc-opt-amp": "http://openconfig.net/yang/optical-amplfier",
     "#text": "oc-opt-amp:CONSTANT_GAIN"}
    Agents need just "CONSTANT_GAIN", not the XML decoration.
    """
    if val is None:
        return None
    if isinstance(val, dict):
        val = val.get("#text", "")
    text = str(val)
    if ":" in text:
        return text.split(":", 1)[1]
    return text
```

### OpenConfig enum in NETCONF edit-config (setting values)

```xml
<!-- WHY: Setting an OpenConfig enum requires the xmlns prefix on the value.
     The namespace URI has a typo ("amplfier" not "amplifier") — this is in
     the actual OpenConfig YANG module and MUST be preserved exactly. -->
<config>
  <gain-range xmlns:oc-opt-amp="http://openconfig.net/yang/optical-amplfier"
    >oc-opt-amp:LOW_GAIN_RANGE</gain-range>
</config>
```

### Parsed amplifier status (agent-friendly output)

```python
def _parse_amplifier(self, raw: dict, amp: str) -> dict[str, Any]:
    """Parse a single amplifier's raw xmltodict data into a clean dict.

    WHY: Single source of truth for XML→agent-dict mapping.
    Adding a new field = one line here, not scattered across callers.
    """
    config = raw.get("config", {})
    state = raw.get("state", {})
    return {
        "name": amp,
        "operational_state": state.get("operational-state"),
        "enabled": config.get("enabled") == "true",  # str→bool
        "target_gain_dB": self._instant(config.get("target-gain")),
        "actual_gain_dB": self._instant(state.get("actual-gain")),
        "gain_range": self._oc_enum(config.get("gain-range")),
        "amp_mode": self._oc_enum(config.get("amp-mode")),
        "input_power_dBm": self._instant(state.get("input-power-total")),
        "output_power_dBm": self._instant(state.get("output-power-total")),
        # ... pump temps, laser bias, back-reflection ...
    }
```

### xmltodict single-vs-list normalization

```python
amps = parsed["data"]["open-optical-device"]["optical-amplifier"][
    "amplifiers"
]["amplifier"]
# WHY: xmltodict returns a dict for single item, list for multiple.
# This is a pervasive xmltodict footgun. Always normalize.
if isinstance(amps, dict):
    amps = [amps]
```

## Pitfalls & Gotchas

1. **xmltodict single-item trap**: When XML has exactly one `<amplifier>`, xmltodict returns a dict, not a list. With two, it's a list. ALWAYS normalize with `if isinstance(x, dict): x = [x]`.

2. **OpenConfig namespace typo**: The URI is `optical-amplfier` (missing 'i'). This is in the official YANG module. If you "fix" the typo, the device rejects your RPC.

3. **YANG constraint vs device constraint**: YANG model says gain range 6.00..35.00 dB. Device rejects anything below 10.0 at commit time with "Invalid argument". The edit-config succeeds (passes YANG validation) but commit fails (device-level check). Always test both steps.

4. **Candidate config pollution**: Failed `edit_config` + `commit` leaves dirty candidate. Must call `discard_changes()` before retrying, or next commit applies stale edits.

5. **EVOA doesn't affect output**: In constant-gain mode, the EDFA adjusts pump power to maintain target net gain. EVOA only affects noise figure, not signal output. This is counterintuitive — "variable optical attenuator" sounds like it should reduce output.

## Recipe

To add a new OpenConfig/OpenROADM device driver:

1. Connect and dump server capabilities: `ila._mgr.server_capabilities` — find YANG modules
2. Fetch raw operational data with `get` filter: build XML subtree filter, parse with xmltodict
3. Identify the `{instant: "X"}` pattern and namespace-prefixed enums in the response
4. Create `_instant()` and `_oc_enum()` helpers (or reuse from a base class)
5. Build `_parse_*()` method that produces flat, unit-annotated dicts
6. Create `_edit_and_commit()` wrapper for config changes (handles candidate datastore)
7. Add `discard_changes()` in error handling to prevent candidate pollution
8. Test with mock xmltodict-style dicts (no live device needed for unit tests)

## Verification

```bash
# Unit tests (mocked ncclient)
pytest tests/test_drivers/test_ila.py -v  # 40 tests

# Live device test
python3 -c "
from oi.drivers.ila import ILA
ila = ILA('ila_11', '10.10.10.18')
ila.connect()
status = ila.get_all_amplifier_status()
for amp, s in status.items():
    print(f'{amp}: gain={s[\"actual_gain_dB\"]} dB, in={s[\"input_power_dBm\"]} dBm')
ila.close()
"
```
