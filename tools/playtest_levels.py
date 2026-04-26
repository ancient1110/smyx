#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS_FILE = ROOT / "levels" / "levels_01_10.json"


def in_bounds(x, y, w, h):
    return 0 <= x < w and 0 <= y < h


def rect_cells(r):
    for y in range(r["y"], r["y"] + r["h"]):
        for x in range(r["x"], r["x"] + r["w"]):
            yield (x, y)


def step(alive, blocked, w, h):
    nbr = {}
    for (x, y) in alive:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny, w, h):
                    continue
                if (nx, ny) in blocked:
                    continue
                nbr[(nx, ny)] = nbr.get((nx, ny), 0) + 1

    nxt = set()
    for cell, c in nbr.items():
        if cell in alive and c in (2, 3):
            nxt.add(cell)
        elif cell not in alive and c == 3:
            nxt.add(cell)
    return nxt


def apply_disturbance(alive, d, goal_regions):
    if d["type"] != "remove_first_by_scan":
        return alive
    scope = d.get("scope", {})
    excluded = set()
    if scope.get("exclude_goal_regions"):
        for r in goal_regions:
            excluded.update(rect_cells(r))
    for y in range(1000):
        row = [(x, y) for x in range(1000)]
        any_in_row = False
        for c in row:
            if c in alive:
                any_in_row = True
                if c not in excluded:
                    alive.remove(c)
                    return alive
        if not any_in_row and all((x, y) not in alive for x in range(20)):
            # coarse early break for sparse boards
            pass
    return alive


def get_goal_regions(goals):
    out = []
    for g in goals:
        ch = g["check"]
        if "region" in ch:
            out.append(ch["region"])
        if "regions" in ch:
            out.extend(ch["regions"])
    return out


def eval_goal(states, goal):
    ch = goal["check"]
    t = ch.get("turn")
    if ch["type"] == "cell_state_at_turn":
        alive = states[t]
        cell = (ch["cell"]["x"], ch["cell"]["y"])
        expected = ch["state"] == "alive"
        return (cell in alive) == expected

    if ch["type"] == "board_stability_window":
        for i in range(ch["from_turn"], ch["to_turn"]):
            if states[i] != states[i + 1]:
                return False
        return ch["stable"]

    if ch["type"] == "region_alive_count_at_turn":
        alive = states[t]
        cnt = sum((x, y) in alive for (x, y) in rect_cells(ch["region"]))
        return cnt >= ch["min_alive"]

    if ch["type"] == "region_oscillator_period_at_turn":
        r = list(rect_cells(ch["region"]))
        a = {(x, y) for (x, y) in r if (x, y) in states[t]}
        b = {(x, y) for (x, y) in r if (x, y) in states[t - 1]}
        c = {(x, y) for (x, y) in r if (x, y) in states[t - 2]}
        return a == c and a != b

    if ch["type"] == "all_regions_nonempty_at_turn":
        alive = states[t]
        for r in ch["regions"]:
            if sum((x, y) in alive for (x, y) in rect_cells(r)) == 0:
                return False
        return True

    raise ValueError(f"Unknown goal type: {ch['type']}")


def simulate_level(level):
    w = level["board"]["width"]
    h = level["board"]["height"]
    blocked = {(c["x"], c["y"]) for c in level.get("blocked_cells", [])}

    placements = {(c["x"], c["y"]) for c in level["designer_solution"]["placements"]}
    preset = {(c["x"], c["y"]) for c in level.get("preset_alive", [])}
    alive = set(preset | placements)

    if not (level["placement_budget"]["min"] <= len(placements) <= level["placement_budget"]["max"]):
        return False, "placement budget violated"

    for c in alive:
        if c in blocked:
            return False, "alive on blocked cell"
        if not in_bounds(c[0], c[1], w, h):
            return False, "alive out of bounds"

    states = {0: set(alive)}
    disturbances = {d["turn"]: d for d in level.get("disturbances", [])}
    goal_regions = get_goal_regions(level["goals"])
    for t in range(1, level["turns"] + 1):
        alive = step(alive, blocked, w, h)
        if t in disturbances:
            alive = apply_disturbance(alive, disturbances[t], goal_regions)
        states[t] = set(alive)

    for g in level["goals"]:
        if not eval_goal(states, g):
            return False, f"goal failed: {g['id']}"
    return True, "ok"


def main():
    # Always read as UTF-8 so Windows locales like GBK/CP936 don't fail on
    # Chinese tutorial strings in the level JSON.
    data = json.loads(LEVELS_FILE.read_text(encoding="utf-8"))
    print(f"Playtesting {len(data['levels'])} levels from {LEVELS_FILE}")
    all_ok = True
    for lv in data["levels"]:
        ok, msg = simulate_level(lv)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {lv['id']} {lv['title']} -> {msg}")
        all_ok &= ok
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
