---
title: "Topology Navigator — Agent-Friendly Path Planning for Optical Cross-Connects"
type: pattern
tags: [topology, optical, polatis, path-planning, agent-tooling]
domain: optical-networking
created: 2026-02-28
updated: 2026-02-28
confidence: high
complexity: medium
related: [digital_twin_optical_network, openroadm_netconf_driver_evolution]
---

## Problem

Agents working with optical switches (Polatis) waste significant time on port lookups. The physical port mapping has an unintuitive inversion (device TX maps to `Out_Port` column, called `get_inport`), device names in the database don't match shorthand names agents use, and multi-hop paths through pass-through devices (ILAs) need special handling to avoid generating bogus cross-connects for internal optical paths.

## Context

- Polatis Series 7000 optical cross-connect switch (640 ports)
- MySQL database (`device_table`) maps device names to port numbers
- Port naming inversion: `get_inport(name)` queries `Out_Port` column (device output → Polatis ingress)
- Agents repeatedly struggle with: which port is TX, which is RX, which direction to connect
- ILAs have internal optical paths (fwd→bck) that should NOT generate Polatis cross-connects
- Ring topologies require multi-hop path planning with 10+ cross-connects

## Approach

Three-layer abstraction:

1. **PortMapper** (low-level) — MySQL queries, caching, fuzzy name resolution
2. **TopologyNavigator** (agent API) — unambiguous naming (`get_tx_port`/`get_rx_port`), bulk lookup, path planning
3. **TopologySetup skill** (recorded) — applies plans to hardware with audit trail

## Key Decisions

- **Rename, don't replace**: `get_tx_port()` wraps `get_inport()` — the confusing name stays in PortMapper for backward compat, the clear name is what agents use.
- **Pass-through tuples**: `("ila_fwd", "ila_bck")` syntax for devices with internal optical paths. The tuple means "signal enters first device, exits second, no Polatis XC between them."
- **Fuzzy prefix matching**: `fiber_20` resolves to `fiber_20_50450m` via `name + "_"` prefix search. Using underscore delimiter prevents `fiber_2` from matching `fiber_20`.

## Key Code

### Pass-through tuple normalization

```python
@staticmethod
def _normalize_hops(hops: list[str | tuple[str, str]]) -> tuple[list[str], set[int]]:
    """Flatten hops, expanding pass-through tuples.

    WHY: ILAs route signal internally (fwd→bck). If we naively generate
    XCs for every adjacent pair, we'd create a Polatis loopback XC between
    the ILA's two ports — which is wrong and could damage equipment.

    Returns (flat_hops, skip_indices) where skip_indices marks internal links.
    """
    flat: list[str] = []
    skip: set[int] = set()
    for item in hops:
        if isinstance(item, tuple):
            if len(item) != 2:
                raise ValueError(f"Pass-through tuple must have exactly 2 elements, got {item}")
            link_idx = len(flat)  # index of the link between the two
            flat.append(item[0])
            skip.add(link_idx)  # mark this link as internal
            flat.append(item[1])
        else:
            flat.append(item)
    return flat, skip
```

### Path planning with pass-through support

```python
def plan_path(self, hops: list[str | tuple[str, str]]) -> list[tuple[int, int]]:
    """Compute Polatis cross-connect pairs for a multi-hop path.

    WHY: Agents describe paths logically: ["roadm_10", "fiber_20", ("ila_fwd", "ila_bck"), "fiber_36", "roadm_11"]
    This translates to Polatis XC pairs, skipping internal ILA hops.

    Usage:
        nav.plan_path(["roadm_10_line", "fiber_20",
                        ("ila_11_fwd", "ila_11_bck"),  # internal pass-through
                        "fiber_36", "roadm_11_line"])
        # Returns: [(137, 385), (65, 581), (277, 406), (86, 578)]
        # Note: no XC between ila_11_fwd and ila_11_bck
    """
    flat, skip = self._normalize_hops(hops)
    if len(flat) < 2:
        raise ValueError("plan_path requires at least 2 hops")
    pairs: list[tuple[int, int]] = []
    for i in range(len(flat) - 1):
        if i in skip:
            continue  # internal hop — no Polatis XC
        ingress = self.get_tx_port(flat[i])
        egress = self.get_rx_port(flat[i + 1])
        pairs.append((ingress, egress))
    return pairs
```

### Fuzzy name resolution in PortMapper

```python
def _resolve_name(self, device_name: str) -> str:
    """Resolve a device name, trying exact match first then prefix match.

    WHY: Database uses full names like "fiber_20_50450m" (includes fiber length).
    Agents use short names like "fiber_20". Prefix matching bridges the gap.

    The underscore delimiter in the prefix prevents "fiber_2" from matching
    "fiber_20", "fiber_21", etc. — only "fiber_2_*" would match.
    """
    # ... exact match first, then:
    prefix = device_name + "_"
    cursor.execute(
        "SELECT polatis_name FROM device_table WHERE polatis_name LIKE %s",
        (prefix + "%",),
    )
    matches = [row[0] for row in cursor.fetchall()]
    if len(matches) == 1:
        return matches[0]  # unambiguous
    elif len(matches) == 0:
        raise ValueError(f"Device '{device_name}' not found in port map")
    else:
        raise ValueError(f"Ambiguous prefix '{device_name}': matches {matches}")
```

### Pretty-print path table

```python
def print_path(self, hops: list[str | tuple[str, str]]) -> str:
    """Human-readable table. Pass-through hops show [internal].

    Output:
    Hop   Source                    Destination               Ingress    Egress
    -------------------------------------------------------------------------------
    1     roadm_10_line             fiber_20                  137        385
    2     fiber_20                  ila_11_fwd                65         581
    3     ila_11_fwd                ila_11_bck                [internal] [internal]
    4     ila_11_bck                fiber_36                  277        406
    5     fiber_36                  roadm_11_line             86         578
    """
```

## Pitfalls & Gotchas

1. **Port direction inversion**: Polatis "ingress" (ports 1-320) = where device TX arrives. "Egress" (ports 321-640) = what feeds device RX. The database column names (`In_Port`, `Out_Port`) refer to the device perspective, not the switch perspective. `get_inport()` returns ingress (device output). This confusion is why TopologyNavigator exists.

2. **Pass-through generates no XC**: If you forget the tuple syntax and write `["dev_a", "ila_fwd", "ila_bck", "dev_b"]`, you get a bogus XC between ila_fwd and ila_bck that creates a Polatis loopback. Use `["dev_a", ("ila_fwd", "ila_bck"), "dev_b"]`.

3. **Fuzzy matching is one-level only**: `fiber_20` resolves to `fiber_20_50450m`, but `fiber` would match ALL fibers and raise ambiguity. The underscore delimiter is key.

4. **verify_and_clean vs apply_patch_list**: Always prefer `verify_and_clean(expected_xcs, fix=True)` over raw `apply_patch_list()`. It handles stale XCs (same ingress, wrong egress) that would otherwise silently coexist.

## Recipe

1. Create `PortMapper` (needs MySQL access to testbed DB)
2. Create `TopologyNavigator(port_mapper)`
3. Define path as list of device names with ILA tuples
4. `nav.plan_path(hops)` → XC pairs
5. `nav.print_path(hops)` → verify visually
6. `TopologySetup(polatis).verify_and_clean(xc_pairs, fix=True)` → apply to hardware
7. `nav.trace_path(polatis, hops)` → verify with live OPM power readings

## Verification

```bash
pytest tests/test_topology/test_navigator.py -v  # 18 tests covering all cases
```

```python
# Live verification
nav = TopologyNavigator(PortMapper())
pairs = nav.plan_path(["roadm_10_line", "fiber_20",
                        ("ila_11_fwd", "ila_11_bck"),
                        "fiber_36", "roadm_11_line"])
print(nav.print_path(["roadm_10_line", "fiber_20",
                       ("ila_11_fwd", "ila_11_bck"),
                       "fiber_36", "roadm_11_line"]))
```
