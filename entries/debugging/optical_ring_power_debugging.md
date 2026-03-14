---
title: "Optical Ring Power Debugging — Systematic Approach to Signal Tracing"
type: debugging
tags: [optical, power, debugging, edfa, wss, polatis]
domain: optical-networking
created: 2026-02-28
updated: 2026-02-28
confidence: high
complexity: medium
related: [ila_bidirectional_amplifier_ring_topology, digital_twin_optical_network]
---

## Problem

When optical power levels are wrong after topology changes, the root cause can be at any point in a long chain: ROADM booster → Polatis XC → fiber → ILA → fiber → Polatis XC → ROADM preamp → WSS DEMUX → loopback → WSS MUX → booster. Debugging requires systematic signal tracing with the right measurement points and knowing which readings to trust.

## Context

- 3-node ring with ILA: R10 → R11 → R8 → R10
- Multiple measurement points: EDFA input/output, WSS per-channel, Polatis OPM
- Per-channel target: 0 dBm launch power into fiber
- 7 signal channels (ch46-58) among 95 WSS-configured channels

## Solution

Use a systematic multi-point measurement approach: Polatis OPM readings (most reliable) at each hop, WSS per-channel power for signal vs noise discrimination, and EDFA input/output as a rough guide. Always check your actual signal channels, not just the first few.

## Approach

### Measurement Hierarchy (most to least reliable)

1. **Polatis OPM** at ingress ports — direct fiber power, no EDFA/WSS in the path
2. **WSS per-channel input/output power** — individual channel visibility, but includes WSS insertion loss
3. **EDFA input/output power** — total power only, unreliable below ~0 dBm

### Debugging Flowchart

```
Signal missing at downstream ROADM?
├── Check Polatis OPM at ROADM line input port
│   ├── Power present → Problem is internal to ROADM (WSS/EDFA)
│   └── No power → Problem is upstream (fiber, ILA, XC)
│       ├── Check Polatis OPM at each hop backward
│       └── First hop with power = problem is between this hop and next
│
Signal present but wrong level?
├── Check per-channel power at WSS DEMUX input (signal channels only!)
│   ├── All channels at same level as noise → Only ASE, no signal
│   └── Signal channels 10+ dB above noise → Signal present
├── Check per-channel power at WSS MUX output
│   ├── Signal channels at noise floor → Express path broken (WSS config or loopback cable)
│   └── Signal present → Booster gain needs adjustment
└── Check EDFA booster output
    ├── Shows -50 dBm → Unreliable meter (use Polatis OPM instead)
    └── Shows reasonable value → Power leaving ROADM OK, check downstream
```

## Key Code

### Multi-point power survey

```python
# WHY: Polatis OPM readings at each XC ingress port give unambiguous
# power levels at each point in the path. No EDFA/WSS artifacts.
points = {
    'R10 line out': 137,      # After R10 booster, entering fiber
    'After fiber_20': 65,      # After 50km fiber, before ILA
    'ILA ab out': 277,         # After ILA amplification
    'After fiber_36': 86,      # After 27km fiber, entering R11
    'R11 line out': 258,       # After R11 booster
    'After fiber_28': 70,      # After 40km fiber, entering R8
    'R8 line out': 210,        # After R8 booster
}
for label, port in points.items():
    power = polatis.get_port_power(port)
    print(f'{label}: {power:.1f} dBm')
```

### Per-channel vs total power conversion

```python
# WHY: EDFA output is total power. With N channels, per-channel is:
# per_ch = total - 10*log10(N)
# With 7 channels: per_ch = total - 8.45 dBm
n_channels = 7
per_ch = total_power_dBm - 10 * math.log10(n_channels)  # ~8.45 for 7ch
```

### Checking signal channels specifically (not just ch1-10)

```python
# WHY: WSS has 95 configured channels but only 7 carry signal.
# Checking ch1-10 shows noise floor (-50 dBm) and looks broken.
# Must check actual signal channels (46, 48, 50, 52, 54, 56, 58).
mux_out = roadm.wss_get_connections_output_power('mux')
signal_powers = {ch: p for ch, p in mux_out if ch in [46, 48, 50, 52, 54, 56, 58]}
noise_powers = {ch: p for ch, p in mux_out if ch not in [46, 48, 50, 52, 54, 56, 58]}
# Signal should be 10-20 dB above noise
```

## Pitfalls & Gotchas

1. **EDFA output_power = -50 dBm doesn't mean no output**: The ROADM-20 EDFA output power meter has a high noise floor. At low total output (<0 dBm), it reads -50.0. Meanwhile, Polatis OPM reads -8.7 dBm (real power). Always cross-check with Polatis.

2. **Looking at wrong channels**: WSS power queries return ALL 95 channels. If you only print ch1-10 (first 10), you see noise floor and conclude "no signal." The signal is on ch46-58. Always filter for your active channels.

3. **Express vs ADD/DROP confusion**: At an express ROADM (R11, R8), the signal path is: preamp → DEMUX → loopback cable → MUX → booster. If MUX shows no signal but DEMUX does, the loopback cable or WSS port assignment is the issue, not the EDFA.

4. **Span loss includes Polatis**: Polatis OPM-to-OPM loss includes: switch fabric (~1 dB) + patch cables + fiber + connectors. The fiber-only loss is less. Don't compare directly to fiber spec sheet.

5. **WSS insertion loss**: MUX input to MUX output has ~4.0-4.5 dB insertion loss. This is normal and varies slightly across channels (causing up to 1 dB flatness spread).

## Recipe

When signal levels are wrong after a topology change:

1. Run `nav.trace_path(polatis, hops)` — instant multi-hop power check
2. Identify the first hop where power drops unexpectedly
3. If signal present at DEMUX but not MUX → check WSS channel configuration
4. If signal present at MUX but EDFA output reports -50 → ignore EDFA meter, use Polatis
5. If per-channel power wrong but total is OK → WSS equalization needed
6. Adjust gains upstream-first, re-measure after each change

## Verification

```python
# Quick ring health check
for label, hops in [("Span 1", SPAN1), ("Span 2", SPAN2), ("Span 3", SPAN3)]:
    trace = nav.trace_path(polatis, hops)
    for hop in trace:
        status = "OK" if hop["power_dBm"] > -30 else "LOW"
        print(f"[{status}] {hop['src']} → {hop['dst']}: {hop['power_dBm']:.1f} dBm")
```
