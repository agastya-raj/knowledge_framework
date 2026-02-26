---
title: "Multi-Device Failure Injection Experiment with Concurrent Telemetry to Kafka"
type: integration
tags: [kafka, telemetry, failure-injection, experiment-orchestration, optical-networking, netconf, concurrent-polling]
domain: optical-networking
created: 2026-02-26
updated: 2026-02-26
confidence: low
complexity: high
related: [edfa_gain_modeling, digital_twin_optical_network]
---

# Multi-Device Failure Injection Experiment with Concurrent Telemetry to Kafka

## Problem

You need to run a multi-hour experiment on a live optical network testbed where you systematically inject failures (attenuation changes, EDFA degradation, fiber breaks, WSS signal loss) while continuously recording telemetry from all devices. The data must be published to Kafka in a structured format that collaborators can consume without access to the testbed itself.

Challenges: devices speak different protocols (NETCONF for ROADMs and transceivers, NETCONF for Polatis), polling all devices within a tight interval (10s) requires concurrency, and the data model must be self-describing so consumers can filter and analyse without testbed knowledge.

## Context

- **Testbed**: Open Ireland, TCD — 2 Lumentum ROADM-20s, 1 Polatis 6000 optical switch, 2 ADVA transceivers (TeraFlex + QuadFlex)
- **SDK**: Custom Python SDK (`oi_agentic_control`) with NETCONF drivers for all device types
- **Kafka**: Bitnami Kafka 3.7 (KRaft, no Zookeeper), SASL_PLAINTEXT auth, accessible via Tailscale
- **Python libraries**: `kafka-python` for Kafka (not `confluent-kafka`), `ncclient` for NETCONF
- **Scale**: 17 concurrent read tasks per poll cycle, 10s interval, 2.5 hours, 10,442 messages total
- **Constraint**: each device has a single NETCONF session — reads must be serialized per device but parallelized across devices

## Approach

### 1. Telemetry Collector — Concurrent Multi-Device Polling

Register read tasks per device, then poll all concurrently using `ThreadPoolExecutor`:

- **Per ROADM (×2)**: 5 tasks — `get_edfa_info()`, `wss_get_connections_input_power(mux)`, `wss_get_connections_output_power(mux)`, same for demux
- **Polatis**: 1 task that sequentially reads 20 ports via `get_port_power(port)` (~0.15s/port, ~3s total)
- **Per transceiver (×2)**: 3 tasks — `get_pm_data()`, `get_config()`, `get_operational_state()`

The `ThreadPoolExecutor(max_workers=8)` runs all 17 tasks concurrently. Tasks targeting the same device are serialized naturally because each device driver holds a single NETCONF session. Total poll cycle: ~4.8s.

A background thread runs `poll_once()` every `interval_sec` seconds. Failed reads are logged but don't crash the poll cycle — other devices continue.

### 2. Single-Topic Kafka Data Model

All telemetry goes into one topic. Every message carries enough context to be self-describing:

```json
{
  "experiment_id": "adtran-ofc-20260225",
  "timestamp_ns": 1772062910986946048,
  "device": "roadm_10",
  "data_type": "edfa",
  "data": { "booster": { "target_gain": 18.0, "output_power": 5.01, ... } },
  "context": { "scenario": "SF001", "phase": "injection", "params": {"delta_db": 2.0} },
  "tags": { "topology": "ring_2roadm_loopback" }
}
```

`data_type` values: `edfa`, `wss_mux_input`, `wss_mux_output`, `wss_demux_input`, `wss_demux_output`, `port_power`, `pm`, `config`, `status`, `event`.

Consumers filter by `device` + `data_type` + `context.scenario` + `context.phase`.

### 3. Experiment Orchestration — Timed Scenario Windows

Each of the 15 scenarios gets a 10-minute window:

1. **Baseline phase** (2 min) — set context to `phase=baseline`, poll normally
2. **Injection phase** (6 min) — call `scenario.inject()`, set `phase=injection`. For sweep scenarios (multiple severity steps), divide the 6 min equally among steps.
3. **Recovery phase** (2 min) — call `scenario.recover()`, set `phase=recovery`, poll normally

`ExperimentContext` is a shared object whose `scenario`, `phase`, and `params` fields automatically propagate to every Kafka message via the publisher.

`event` messages are published at every transition (`scenario_start`, `inject`, `inject_step`, `recover`, `scenario_end`) for time-alignment in post-processing.

### 4. Data Handover for Collaborators

- **README.md**: topology diagrams, scenario table, full data schema with sample payloads, consumer code examples. Replace internal identifiers (port numbers → device-relative labels like `r10_line_out`), remove all IPs and credentials.
- **kafka_credentials.md**: separate file with broker address, consumer username/password. Share via secure channel.
- Use a dedicated `device-consumer` Kafka user (read-only by convention).

## Key Decisions

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| One topic vs per-device topics | Single topic | 6 separate topics | Simpler to share and consume; `data_type` field provides equivalent filtering |
| `kafka-python` vs `confluent-kafka` | kafka-python | confluent-kafka | Pure Python, already installed, no C library dependency. API: `send()` + `flush()` vs `produce()` + `poll()` |
| ThreadPoolExecutor vs asyncio | ThreadPoolExecutor | asyncio with ncclient | ncclient is synchronous; wrapping in async adds complexity with no benefit since device sessions are inherently serialized |
| Polatis: per-port reads vs `get_all_power()` | Per-port (20 calls) | `get_all_power()` (1 call) | `get_all_power()` reads all 640 ports (~30s). Per-port for 20 ports takes ~3s. |
| Sweep step application | Each step from baseline | Cumulative (step N adds to step N-1) | From-baseline is cleaner for analysis — each step has a known absolute value |

## Pitfalls & Gotchas

1. **WSS power methods return `list[tuple[int, float]]`, not dicts.** `wss_get_connections_input_power()` returns `[(conn_id, power), ...]`. Must convert to `{str(ch_id): power for ch_id, power in tuples}` for JSON. The method name suggests a dict-like return but it's tuples.

2. **EDFA effective gain can be lower than target gain with few channels.** In constant-gain mode with 2 out of 95 channels active, the EDFA was already at ~15 dB effective gain even with target set to 18 dB. Reducing target from 18→15 showed no change in output power. You need to go well below the effective operating point or have more channels loaded to see EDFA gain degradation.

3. **Kafka Bitnami image has no ACL authorizer by default.** SASL_PLAINTEXT authenticates users, but every authenticated user has full read/write/delete. "Read-only" consumer access is convention only. For real enforcement, add `authorizer.class.name=kafka.security.authorizer.AclAuthorizer` and create ACL rules.

4. **Polatis `get_all_power()` is a trap for polling.** It reads every port on the switch (640 ports). At ~0.05s/port that's ~30s — blows a 10s polling budget. Always use `get_port_power(port)` for the specific ports you need.

5. **`confluent-kafka` requires `librdkafka` C library** and won't pip-install cleanly in all environments. `kafka-python` is pure Python and works everywhere. The API is different: confluent uses callbacks (`produce(..., callback=cb)` + `poll(0)`), kafka-python uses futures (`send().get(timeout=10)`).

6. **Fiber break signature**: the upstream port (transmitter side) shows unchanged power because it's still transmitting into a disconnected path. Only the downstream port drops. Don't check the wrong end.

## Recipe

1. **Register read tasks** for each device — one callable per telemetry type. Each callable takes no arguments and returns a `dict` suitable for JSON serialization.

2. **Create a `TelemetryCollector`** with `ThreadPoolExecutor`. Call `register(device, data_type, read_fn)` for all tasks. Call `start(interval_sec=10)` to begin background polling.

3. **Create an `ExperimentKafkaPublisher`** wrapping `kafka.KafkaProducer`. The publisher reads `scenario`/`phase`/`params` from an `ExperimentContext` object and injects them into every message.

4. **Define scenarios as dataclasses** with `inject(devices, baseline, step_index)` and `recover(devices, baseline)` methods. Store sweep steps as a list of `(description, params)` tuples.

5. **Run the experiment loop**: for each scenario, set context → wait baseline → inject (possibly multiple sweep steps) → wait → recover → wait recovery. Publish `event` messages at each transition.

6. **For handover**: write a README with topology, scenario table, full message schema with sample payloads, and consumer code examples. Strip internal identifiers. Put credentials in a separate file.

## Verification

- **Poll health**: every poll cycle logs `Poll #N: X/Y tasks OK in Z.Zs`. All Y tasks should succeed; Z should be well under the polling interval.
- **Kafka message count**: `N_scenarios × polls_per_scenario × tasks_per_poll + event_count`. For 15 scenarios at 10-min windows with 10s polls: ~610 polls × 17 tasks + ~71 events ≈ 10,441 messages.
- **Phase transitions visible**: filter by `data_type=event` and verify `scenario_start`, `inject`, `recover`, `scenario_end` appear in order for each scenario.
- **Failure signature check**: during injection, compare the target device's telemetry to baseline. WSS attenuation should show exact dB delta. Fiber break should show -50 dBm at the downstream Polatis port. EDFA APR should show output drop to ~3 dBm.
- **Recovery check**: after recovery phase, telemetry values should return within ±0.5 dB of baseline readings.
