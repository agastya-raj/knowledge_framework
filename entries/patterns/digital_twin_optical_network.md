---
title: "Digital Twin Architecture for Optical Networks"
type: pattern
tags: [digital-twin, optical-network, dlm, digital-link-model, ila, monitoring, testbed]
domain: optical-networking
created: 2026-02-20
updated: 2026-02-20
confidence: high
complexity: high
related: [edfa_gain_modeling]
---

# Digital Twin Architecture for Optical Networks

## Problem
Operating optical networks requires continuous monitoring and prediction of signal quality across all links. A digital twin that mirrors the physical network in software enables what-if analysis, fault prediction, and autonomous provisioning. The challenge is building a DT that stays synchronized with the physical network, handles the complexity of cascaded amplifiers and fiber spans, and is accurate enough to trust for operational decisions.

## Context
Built for the Open Ireland testbed at TCD in collaboration with NTT. The testbed uses ADTRAN FSP3000 ROADMs and ILAs. The DT was developed for OFC 2026 demonstration. Needed to model end-to-end lightpath quality (OSNR, power) across multi-span links with ILAs.

## Approach
1. **Digital Link Model (DLM)**: Each fiber span + amplifier pair is modeled as a "digital link." The DLM predicts output power spectrum and OSNR given input conditions. This is the atomic unit of the twin.
2. **Cascaded composition**: End-to-end path quality is computed by cascading DLMs along the lightpath. Each DLM's output feeds the next DLM's input.
3. **Model types within a DLM**:
   - EDFA gain model (ML-based, see related entry)
   - Fiber propagation model (analytical GN-model or learned)
   - ROADM filtering model (wavelength-dependent loss)
4. **Synchronization**: The DT periodically ingests live telemetry (OCM readings, amplifier settings) from the physical network via NETCONF/YANG or vendor APIs. Model parameters are updated to match observed behavior.
5. **What-if engine**: With a synchronized DT, run hypothetical scenarios — "what happens if I add channel X?" — without touching the physical network.

## Key Decisions
- **Per-link modeling over end-to-end black box**: Cascading per-link models is more complex but compositional — adding/removing links doesn't require retraining.
- **Hybrid analytical + ML**: Use analytical models (GN-model) for fiber propagation where physics is well-understood, ML models for amplifiers where device-specific behavior matters.
- **NTT DLM standard alignment**: Following NTT's DLM framework for interoperability and publication positioning.
- **Telemetry-driven calibration over periodic retraining**: Continuously adjust model parameters based on incoming telemetry rather than batch retraining. This keeps the twin synchronized with physical drift.

## Pitfalls & Gotchas
- **Telemetry gaps**: OCM (optical channel monitor) readings may have gaps, delays, or limited spectral resolution. The DT must handle partial observability gracefully.
- **Amplifier transients**: When channels are added/dropped, amplifiers go through transient states. The DT's steady-state models will be temporarily inaccurate. Need either transient models or a settling-time buffer.
- **Cascaded error accumulation**: Small errors in per-link models compound over multi-span paths. A 0.3 dB error per span becomes >1 dB over 4+ spans. Calibrate against end-to-end measurements.
- **ROADM filtering**: Wavelength-dependent loss through ROADMs varies with port, direction, and WSS (wavelength selective switch) configuration. Often overlooked but can be 1-3 dB of unmodeled loss.
- **Power excursion events**: Sudden power changes (fiber cuts, protection switching) can push the DT out of sync. Need event detection and rapid re-synchronization logic.
- **Vendor API rate limits**: FSP3000 NETCONF interface has throughput limits. Design telemetry polling to stay within bounds while maintaining adequate update frequency.

## Recipe
To build an optical network digital twin:

1. **Define the network graph**: Represent the physical topology as a directed graph. Nodes = ROADMs, amplifier sites. Edges = fiber spans with metadata (length, fiber type, loss).
2. **Build DLM per link type**:
   - ILA link: fiber loss model + EDFA gain model
   - Booster link: ROADM loss + booster gain model
   - Preamp link: preamp gain + ROADM loss
3. **Implement cascade engine**: Given a lightpath (ordered list of links), cascade DLMs to compute end-to-end power and OSNR. OSNR cascading: 1/OSNR_total = sum(1/OSNR_i).
4. **Connect telemetry source**: Poll OCM readings and amplifier configurations from the physical network. Store in a time-series structure. Use NETCONF for FSP3000 or vendor-specific APIs.
5. **Calibration loop**: Compare DT predictions with measured telemetry. Adjust model parameters (fiber loss coefficients, amplifier offsets) to minimize residual error.
6. **What-if API**: Expose an interface that accepts hypothetical changes (add channel, change power, reroute) and returns predicted quality metrics.
7. **Visualization**: Dashboard showing physical vs. digital twin state, highlighting discrepancies above threshold.

## Verification
- Per-link power prediction error should be <0.5 dB for calibrated links
- End-to-end OSNR prediction within 1 dB of measured values
- What-if predictions should be validated against actual provisioning outcomes
- Synchronization latency: DT should reflect physical changes within 1-2 telemetry polling cycles
- Test with channel add/drop events to verify the cascade engine updates correctly
