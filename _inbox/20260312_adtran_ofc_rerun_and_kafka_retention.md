---
title: "Kafka retention defaults and experiment re-run on live shared testbed"
tags: [kafka, experiment-ops, optical-networking, adva-netconf, testbed-ops]
source_project: "/home/ajag/oi_agentic_control"
drafted: 2026-03-12
---

## What I Did

Re-ran the ADTRAN OFC 2026 failure injection experiment (15 scenarios, ~2.5 hours)
after discovering that ALL original Kafka telemetry data (10,442 messages) was lost
due to the default 7-day retention policy. Set retention to infinite on all 52 topics,
restored the 2-ROADM ring topology from the post-deadline 3-ROADM+ILA configuration,
and successfully regenerated the dataset (11,053 messages, 15/15 PASS).

## What I Learned

### Kafka Retention — Check Immediately After Deployment
- Default `retention.ms=604800000` (7 days) and `retention.bytes=1073741824` (1 GB)
  silently delete data. For experiment data that must persist, set both to `-1` (infinite)
  at topic creation time.
- Use `kafka-configs.sh --alter --entity-type topics --add-config retention.ms=-1,retention.bytes=-1`
  to fix existing topics. Apply to ALL topics, not just the one you care about today.
- The `kafka-python` AdminClient API for describing configs is version-sensitive:
  `DescribeConfigsResponse_v2` returns `.resources` list, not `.items()`. Always
  specify `api_version=(3, 0)` explicitly to avoid `IncompatibleBrokerVersion`.

### ADVA NETCONF Lockout — Critical Timing Between Sessions
- The TeraFlex (10.10.10.92) and QuadFlex (10.10.10.120) shelves enforce SSH connection
  rate limiting. Too many NETCONF connections in rapid succession triggers auth lockout
  lasting 3-5 minutes.
- **The gap between closing sessions (dry run teardown) and opening new ones (full run
  setup) must be at least 3-4 minutes.** The experiment crashed on first attempt because
  the dry run had just finished.
- Within an experiment run, the runner correctly reuses a single NETCONF session per
  device for the entire duration — no mid-run lockout risk.

### Restoring a Shared Testbed Topology
- Polatis optical switch is a shared resource. When restoring a previous experiment's
  topology, only touch cross-connects allocated to your experiment's devices.
- WSS `wss_add_connections()` (batch upsert) fails when input_port assignments conflict
  with existing config from a different topology. Must `wss_delete_connection(wss_id, 'all')`
  first, then re-add from baseline.
- EDFA recovery is always 3-step: `edfa_config()` + `disable_als(86400)` + `set_apr(False)`
  for BOTH booster and preamp modules. Missing any step leaves the EDFA in a degraded state.

### Baseline Sanity Checking
- Before running a multi-hour experiment, verify: (1) link budget — Polatis XC losses
  should be 1-2 dB, fiber spans 5-10 dB; (2) EDFA operating points — actual gain near
  target (low channel loading causes 2-3 dB shortfall, which is expected); (3) transceiver
  BER — should be well below FEC threshold with 0 uncorrected blocks; (4) WSS channel
  powers — active channels should show signal, not noise floor.

### SDK Backward Compatibility
- The OI SDK remained fully backward-compatible across weeks of heavy development
  (ILA support, new drivers, signal_quality module, shelf_manager, exception hierarchy).
  All changes were additive or internal refactors (`connect` → `_connect` with retry wrapper).
  The experiment config, scenarios, and runner worked unmodified.

## Pitfalls

1. **Kafka data loss is silent and irreversible.** No warnings, no logs. The messages
   simply age out. Always set retention to infinite for experiment data.

2. **ADVA lockout between sequential runs.** If you run dry_run.py immediately followed
   by run.py, the second will fail with "Error reading SSH protocol banner". Add a 4-minute
   sleep or manual pause between runs touching the same ADVA shelf.

3. **WSS batch upsert with conflicting input_ports.** If the current WSS config has
   channel X on input_port A and your baseline has it on input_port B, the batch upsert
   silently fails. Always delete-all first when switching between topologies.

4. **qf_2 line_port matters.** qf_1 uses `1/1/n1`, qf_2 uses `1/1/n2`. Wrong line_port
   causes DISABLED state. When swapping transceivers, update config.yaml AND verify
   the baseline snapshot reflects the correct line_port.

5. **Baseline.take_baseline() is an instance method.** Must instantiate `Baseline()` first,
   not call as classmethod. Easy to trip over when scripting ad-hoc baseline captures.

## Tags Suggestion

Suggest category: integration | debugging | domain
Suggest domain: optical-networking | devops
