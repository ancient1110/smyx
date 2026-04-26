#!/usr/bin/env python3
"""Minimal terminal game runner for levels_01_10.json.

Usage:
  python tools/play_game.py --list
  python tools/play_game.py --level L01
"""

import argparse
import json
from pathlib import Path

from playtest_levels import rect_cells, step, eval_goal

ROOT = Path(__file__).resolve().parents[1]
LEVELS_FILE = ROOT / "levels" / "levels_01_10.json"


def load_levels():
    data = json.loads(LEVELS_FILE.read_text(encoding="utf-8"))
    return data["levels"]


def render(level, alive):
    w = level["board"]["width"]
    h = level["board"]["height"]
    blocked = {(c["x"], c["y"]) for c in level.get("blocked_cells", [])}
    print("   " + " ".join(f"{x:02d}" for x in range(w)))
    for y in range(h):
        row = []
        for x in range(w):
            c = (x, y)
            if c in blocked:
                row.append("#")
            elif c in alive:
                row.append("O")
            else:
                row.append(".")
        print(f"{y:02d} " + "  ".join(row))


def run_sim(level, placements):
    w = level["board"]["width"]
    h = level["board"]["height"]
    blocked = {(c["x"], c["y"]) for c in level.get("blocked_cells", [])}
    preset = {(c["x"], c["y"]) for c in level.get("preset_alive", [])}
    alive = set(preset | placements)
    states = {0: set(alive)}

    disturbances = {d["turn"]: d for d in level.get("disturbances", [])}
    goal_regions = []
    for g in level["goals"]:
        ch = g["check"]
        if "region" in ch:
            goal_regions.append(ch["region"])

    def apply_disturbance(alive_now, d):
        if d["type"] != "remove_first_by_scan":
            return alive_now
        excluded = set()
        if d.get("scope", {}).get("exclude_goal_regions"):
            for r in goal_regions:
                excluded.update(rect_cells(r))
        for y in range(h):
            for x in range(w):
                if (x, y) in alive_now and (x, y) not in excluded:
                    alive_now.remove((x, y))
                    return alive_now
        return alive_now

    for t in range(1, level["turns"] + 1):
        alive = step(alive, blocked, w, h)
        if t in disturbances:
            alive = apply_disturbance(alive, disturbances[t])
        states[t] = set(alive)

    failures = []
    for g in level["goals"]:
        if not eval_goal(states, g):
            failures.append(g["id"])

    return states, failures


def interactive(level):
    budget = level["placement_budget"]
    placements = set()

    print(f"\n=== {level['id']} {level['title']} ===")
    print(level["tutorial"]["intro"])
    print("提示:")
    for h in level["tutorial"]["hints"]:
        print(f"- {h}")
    print(f"可放置数量: {budget['min']}~{budget['max']}\n")

    while True:
        preset = {(c["x"], c["y"]) for c in level.get("preset_alive", [])}
        render(level, preset | placements)
        print(f"当前放置: {len(placements)} -> {sorted(placements)}")
        cmd = input("命令(add x y | del x y | clear | solve | run | hint | quit): ").strip()
        if not cmd:
            continue
        parts = cmd.split()
        op = parts[0].lower()

        if op == "quit":
            return
        if op == "hint":
            for item in level["tutorial"]["hints"]:
                print("提示:", item)
            continue
        if op == "clear":
            placements.clear()
            continue
        if op == "solve":
            placements = {(c["x"], c["y"]) for c in level["designer_solution"]["placements"]}
            print("已填入设计者解法。")
            continue
        if op in ("add", "del") and len(parts) == 3:
            try:
                x, y = int(parts[1]), int(parts[2])
            except ValueError:
                print("坐标必须是整数")
                continue
            if op == "add":
                placements.add((x, y))
            else:
                placements.discard((x, y))
            continue
        if op == "run":
            if not (budget["min"] <= len(placements) <= budget["max"]):
                print(f"数量不符：需要 {budget['min']}~{budget['max']} 个。")
                continue
            states, failures = run_sim(level, placements)
            final_alive = states[level["turns"]]
            print(f"\n模拟结束（第 {level['turns']} 步）:")
            render(level, final_alive)
            if failures:
                print("未达成目标:", ", ".join(failures))
            else:
                print("🎉 过关！全部目标达成。")
            print()
            continue

        print("无效命令。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List available levels")
    parser.add_argument("--level", type=str, help="Play a specific level id, e.g. L01")
    args = parser.parse_args()

    levels = load_levels()
    if args.list:
        for lv in levels:
            print(f"{lv['id']}: {lv['title']} ({lv['difficulty']})")
        return

    if args.level:
        target = next((lv for lv in levels if lv["id"] == args.level), None)
        if not target:
            print("Level not found")
            raise SystemExit(1)
        interactive(target)
        return

    print("请使用 --list 查看关卡，或 --level L01 开始游玩。")


if __name__ == "__main__":
    main()
