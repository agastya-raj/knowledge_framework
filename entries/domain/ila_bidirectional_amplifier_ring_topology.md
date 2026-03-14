---
title: "ILA Bidirectional Amplifier in Ring Topology — Bootstrap, Constraints, and Gain Tuning"
type: domain
tags: [ila, edfa, optical-amplifier, ring-topology, power-optimization]
domain: optical-networking
created: 2026-02-28
updated: 2026-02-28
confidence: high
complexity: high
related: [digital_twin_optical_network, openroadm_netconf_driver_evolution]
---

## Problem

Inserting an In-Line Amplifier (ILA) into an optical ring creates a bootstrap chicken-and-egg problem: the ILA has hardcoded Automatic Laser Shutdown (ALS) that requires light on BOTH directions to activate, but each direction's light depends on the other direction being active (via the ring). Additionally, the ILA's YANG model advertises gain ranges that the device firmware rejects, and the EVOA behavior is counterintuitive in constant-gain mode.

## Context

- Juniper TCX-1000 ILA, bidirectional: "ab" (forward), "ba" (backward)
- OpenROADM YANG model + OpenConfig optical-amplifier augmentation
- Ring topology: R10 → ILA(ab) → R11 → R8 → ILA(ba) → R10
- ILA sits on two spans simultaneously (ab on span 1, ba on span 2)
- 3 Lumentum ROADM-20 nodes in the ring
- 7 transceivers ADD/DROP at R10 (channels 46-58, 50 GHz grid)

## Approach

### Bootstrap Sequence

1. **Disable ALS on all ROADMs** (`disable_als(86400)`) — ROADM boosters output ASE (amplified spontaneous emission) even without signal input
2. **Wire all XCs** — create the full ring path through the ILA
3. **Wait 30 seconds** — ASE from ROADM boosters propagates through the ring, reaching both ILA directions
4. **ILA activates** — both ab and ba detect input light and begin amplifying
5. **Verify with OPM** — `trace_path()` reads Polatis port power at each hop

### Gain Tuning for Cascaded Ring

In a ring with EXPRESS nodes, changes cascade: R10 output → span 1 → R11 → span 3 → R8 → span 2 → R10. But R10 is ADD/DROP (transceiver-fed), so the ring doesn't feed back through the signal path.

Tuning order:
1. Set R10 booster (controls span 1 input) — independent of ring
2. Set ILA ab gain (compensates span 1 loss)
3. Measure R11 output, set R11 booster
4. Measure R8 input (from R11 via span 3), set R8 booster
5. ILA ba gain is constrained to minimum (10 dB), adjust R8 booster instead

## Key Decisions

- **ILA on two spans**: Using both ab and ba on different ring spans means both directions get light naturally once the ring is established. Alternative (ILA on one span only) would leave one direction unused.
- **ASE bootstrap over external light source**: ROADM boosters with ALS disabled produce enough ASE noise to trigger ILA activation. No need for a separate CW laser source.
- **Minimum ILA ba gain**: Can't go below 10 dB. For the short span (R8→R10), reduce R8 booster gain instead.

## Key Code

### ILA gain constraints (hardware-verified)

```python
# YANG model says: target-gain range "6.00..35.00"
# Device REJECTS at commit time: gains below 10.0 → "Invalid argument"
# edit_config succeeds (YANG validation passes), commit fails (device firmware check)

# WORKING:
ila.set_target_gain("ab", 17.0)  # OK — compensates long span
ila.set_target_gain("ba", 10.0)  # OK — minimum allowed

# FAILING:
ila.set_target_gain("ba", 8.0)   # RPCError: Invalid argument
ila.set_target_gain("ba", 6.0)   # RPCError: Invalid argument
# Must discard_changes() after failure to clean candidate datastore
```

### EVOA does NOT change output power in constant-gain mode

```python
# Counterintuitive behavior verified on live device:
# EVOA=5.0, target_gain=10.0: input=-13.5, output=-3.1 → net gain 10.4 dB
# EVOA=0.0, target_gain=10.0: input=-13.5, output=-3.1 → net gain 10.4 dB
# The EDFA adjusts pump power to maintain constant NET gain including EVOA.
# EVOA is purely a noise figure optimization parameter.
```

### Cascaded ring power budget

```python
# Final working configuration (0 dBm/ch target at all nodes):
# R10 booster: 18.0 dB (ADD/DROP, feeds 50km+27km span via ILA)
# ILA ab:      17.0 dB (compensates 77km total fiber + connector losses)
# R11 booster: 18.0 dB (express, restores after long span)
# R8 booster:   7.0 dB (express, short span from R11, ILA ba adds 10 dB)
# ILA ba:      10.0 dB (minimum, short span doesn't need more)
# All EVOA:     0.0 dB

# Result: all nodes within ±0.7 dB of 0 dBm/ch
# R10: -0.6 dBm/ch, R11: 0.0 dBm/ch, R8: -0.7 dBm/ch
```

## Pitfalls & Gotchas

1. **ALS cannot be disabled on TCX-1000**: `autolos`, `apr-enabled`, `plim-enabled` all rejected via NETCONF ("Invalid argument" or "Operation not supported"). ALS is hardcoded ON.

2. **YANG vs firmware constraints**: The YANG model allows 6.0-35.0 dB gain, but firmware rejects <10.0 dB. Always test with the actual device. The edit-config step passes YANG validation — the failure only surfaces at commit.

3. **Candidate config pollution**: A failed commit leaves dirty state. Always `discard_changes()` before retrying with a different value.

4. **Cascading gain changes**: In a ring, changing one EDFA affects all downstream nodes. R11 booster at 18 dB → R8 booster input jumps from -5 to +1 dBm → R8 output way too high. Must re-tune R8 after R11 changes.

5. **ROADM EDFA output_power unreliable**: At low signal levels, the ROADM reports `output_power = -50.0` even when the booster is amplifying. Use Polatis OPM as ground truth.

6. **ILA saturation**: At high input power (>+5 dBm), actual gain < target gain. The ILA ba showed 8.9 dB actual when target was 10.0, with +11.6 dBm input.

7. **Express ROADM WSS**: Signal channels may appear at -50 dBm in MUX output when looking at the wrong channels (1-10). Always check the actual signal channels (e.g., 46-58). The express path works — the WSS just has 95 channels of noise masking the 7 signal channels.

## Recipe

1. Define topology as hop lists with pass-through tuples for ILA
2. `nav.plan_path()` to compute XC pairs
3. Disable ALS on all ROADMs (`disable_als(86400)`)
4. Delete old span XCs, create new ones via `verify_and_clean()`
5. Wait 30s for ILA activation
6. `nav.trace_path()` to verify light at each hop
7. Tune gains: R10 first (independent), then ILA ab, then R11 booster, then R8 booster
8. Re-verify per-channel power with WSS reads
9. Iterate if nodes are >1 dB from target

## Verification

```python
# Quick health check
status = ila.get_all_amplifier_status()
for amp, s in status.items():
    print(f"{amp}: state={s['operational_state']}, "
          f"gain={s['actual_gain_dB']:.1f}/{s['target_gain_dB']:.1f} dB, "
          f"in={s['input_power_dBm']:.1f}, out={s['output_power_dBm']:.1f}")
# Both should show "in-service" with actual gain close to target

# Alarms (some are expected, e.g., OSC LOS when no OSC channel is provisioned)
alarms = ila.get_alarms()
for a in alarms:
    print(f"[{a['severity']}] {a['id']}: {a['cause']}")
```
