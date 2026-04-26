#!/usr/bin/env python3
"""Graphical level runner for Emergence Tactician (Tkinter)."""

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from playtest_levels import eval_goal, rect_cells, step

ROOT = Path(__file__).resolve().parents[1]
LEVELS_FILE = ROOT / "levels" / "levels_01_10.json"

CELL_SIZE = 28
PADDING = 18

BG = "#10131a"
PANEL = "#171d2a"
GRID = "#2a3348"
ALIVE = "#59d185"
PRESET = "#49a3ff"
BLOCK = "#6b7280"
EMPTY = "#1e2535"
TEXT = "#e6edf7"
MUTED = "#a6b0c3"
ACCENT = "#8b5cf6"


class GameApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cell Commander · Emergence Tactician")
        self.root.configure(bg=BG)

        self.data = json.loads(LEVELS_FILE.read_text(encoding="utf-8"))
        self.levels = self.data["levels"]
        self.level_map = {lv["id"]: lv for lv in self.levels}

        self.level_var = tk.StringVar(value=self.levels[0]["id"])
        self.status_var = tk.StringVar(value="欢迎！先选关并点击棋盘放置细胞。")
        self.budget_var = tk.StringVar(value="")

        self.user_placements = set()
        self.current_level = self.levels[0]

        self._build_ui()
        self._load_level(self.current_level["id"])

    def _build_ui(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=14, pady=10)

        tk.Label(top, text="关卡", fg=TEXT, bg=BG, font=("Segoe UI", 11, "bold")).pack(side="left")

        picker = ttk.Combobox(
            top,
            textvariable=self.level_var,
            values=[f"{lv['id']} · {lv['title']}" for lv in self.levels],
            state="readonly",
            width=26,
        )
        picker.pack(side="left", padx=10)
        picker.bind("<<ComboboxSelected>>", self.on_level_change)

        ttk.Button(top, text="加载设计解", command=self.load_solution).pack(side="left", padx=4)
        ttk.Button(top, text="重置", command=self.reset_placements).pack(side="left", padx=4)
        ttk.Button(top, text="运行", command=self.run_level).pack(side="left", padx=4)

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.canvas = tk.Canvas(main, bg=PANEL, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=False)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        side = tk.Frame(main, bg=PANEL)
        side.pack(side="left", fill="both", expand=True, padx=(12, 0))

        tk.Label(side, text="关卡说明", fg=TEXT, bg=PANEL, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 4))

        self.intro_text = tk.Text(side, height=4, wrap="word", bg=PANEL, fg=MUTED, bd=0)
        self.intro_text.pack(fill="x", padx=10)
        self.intro_text.configure(state="disabled")

        tk.Label(side, text="目标", fg=TEXT, bg=PANEL, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.goal_text = tk.Text(side, height=8, wrap="word", bg=PANEL, fg=MUTED, bd=0)
        self.goal_text.pack(fill="x", padx=10)
        self.goal_text.configure(state="disabled")

        tk.Label(side, text="提示", fg=TEXT, bg=PANEL, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.hint_text = tk.Text(side, height=6, wrap="word", bg=PANEL, fg=MUTED, bd=0)
        self.hint_text.pack(fill="x", padx=10)
        self.hint_text.configure(state="disabled")

        tk.Label(side, textvariable=self.budget_var, fg=TEXT, bg=PANEL, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=10)

        tk.Label(side, textvariable=self.status_var, fg=ACCENT, bg=PANEL, wraplength=420, justify="left").pack(anchor="w", padx=10, pady=(4, 10))

    def on_level_change(self, _evt=None):
        token = self.level_var.get().split(" · ")[0]
        self._load_level(token)

    def _load_level(self, level_id):
        lv = self.level_map[level_id]
        self.current_level = lv
        self.user_placements = set()

        w = lv["board"]["width"]
        h = lv["board"]["height"]
        self.canvas.config(width=w * CELL_SIZE + PADDING * 2, height=h * CELL_SIZE + PADDING * 2)

        self._set_text(self.intro_text, lv["tutorial"]["intro"])

        goals = []
        for g in lv["goals"]:
            ch = g["check"]
            goals.append(f"- {g['id']}: {ch['type']}")
        self._set_text(self.goal_text, "\n".join(goals))
        self._set_text(self.hint_text, "\n".join(f"- {h}" for h in lv["tutorial"]["hints"]))

        b = lv["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 {len(self.user_placements)}）")
        self.status_var.set("已载入关卡，点击左侧棋盘放置细胞。")
        self.draw_board()

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def draw_board(self, alive_override=None):
        lv = self.current_level
        w = lv["board"]["width"]
        h = lv["board"]["height"]

        blocked = {(c["x"], c["y"]) for c in lv.get("blocked_cells", [])}
        preset = {(c["x"], c["y"]) for c in lv.get("preset_alive", [])}
        user = set(self.user_placements) if alive_override is None else set(alive_override)

        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, w * CELL_SIZE + PADDING * 2, h * CELL_SIZE + PADDING * 2, fill=PANEL, outline=PANEL)

        for y in range(h):
            for x in range(w):
                x0 = PADDING + x * CELL_SIZE
                y0 = PADDING + y * CELL_SIZE
                x1 = x0 + CELL_SIZE - 1
                y1 = y0 + CELL_SIZE - 1

                c = (x, y)
                if c in blocked:
                    fill = BLOCK
                elif c in preset:
                    fill = PRESET
                elif c in user:
                    fill = ALIVE
                else:
                    fill = EMPTY

                self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=GRID)

    def on_canvas_click(self, evt):
        lv = self.current_level
        w = lv["board"]["width"]
        h = lv["board"]["height"]
        x = (evt.x - PADDING) // CELL_SIZE
        y = (evt.y - PADDING) // CELL_SIZE
        if not (0 <= x < w and 0 <= y < h):
            return

        blocked = {(c["x"], c["y"]) for c in lv.get("blocked_cells", [])}
        preset = {(c["x"], c["y"]) for c in lv.get("preset_alive", [])}
        cell = (x, y)

        if cell in blocked or cell in preset:
            self.status_var.set("该格不可编辑（障碍或预置细胞）。")
            return

        if cell in self.user_placements:
            self.user_placements.remove(cell)
        else:
            self.user_placements.add(cell)

        b = lv["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 {len(self.user_placements)}）")
        self.draw_board()

    def reset_placements(self):
        self.user_placements = set()
        b = self.current_level["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 0）")
        self.status_var.set("已清空玩家放置。")
        self.draw_board()

    def load_solution(self):
        self.user_placements = {(c["x"], c["y"]) for c in self.current_level["designer_solution"]["placements"]}
        b = self.current_level["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 {len(self.user_placements)}）")
        self.status_var.set("已加载设计者解法。")
        self.draw_board()

    def run_level(self):
        lv = self.current_level
        b = lv["placement_budget"]
        n = len(self.user_placements)
        if not (b["min"] <= n <= b["max"]):
            messagebox.showwarning("放置数量不符", f"当前 {n} 个，需要 {b['min']}~{b['max']} 个。")
            return

        states, failures = self._simulate(lv, self.user_placements)
        final_alive = states[lv["turns"]]
        self.draw_board(alive_override=final_alive)

        if failures:
            self.status_var.set(f"未达成目标：{', '.join(failures)}")
            messagebox.showinfo("结果", f"本次未过关，失败目标：{', '.join(failures)}")
        else:
            self.status_var.set("🎉 恭喜，全部目标达成！")
            messagebox.showinfo("结果", "过关！全部目标达成。")

    def _simulate(self, level, placements):
        w = level["board"]["width"]
        h = level["board"]["height"]
        blocked = {(c["x"], c["y"]) for c in level.get("blocked_cells", [])}
        preset = {(c["x"], c["y"]) for c in level.get("preset_alive", [])}
        alive = set(preset | set(placements))
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


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TButton", padding=6)
    app = GameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
