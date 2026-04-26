#!/usr/bin/env python3
"""Modern Tkinter GUI runner for Emergence Tactician levels."""

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from playtest_levels import eval_goal, rect_cells, step

ROOT = Path(__file__).resolve().parents[1]
LEVELS_FILE = ROOT / "levels" / "levels_01_10.json"

CELL_SIZE = 30
BOARD_PAD = 20

PALETTE = {
    "bg": "#0B1020",
    "panel": "#121A2D",
    "panel_2": "#18233B",
    "text": "#EAF0FF",
    "muted": "#9FB0D0",
    "accent": "#6EA8FE",
    "success": "#38D996",
    "warning": "#FFB86B",
    "cell_empty": "#1A2540",
    "cell_grid": "#273455",
    "cell_alive": "#35C883",
    "cell_preset": "#4B95FF",
    "cell_block": "#64748B",
}


class ModernGameApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cell Commander · Emergence Tactician")
        self.root.configure(bg=PALETTE["bg"])
        self.root.geometry("1280x820")
        self.root.minsize(1080, 720)

        data = json.loads(LEVELS_FILE.read_text(encoding="utf-8"))
        self.levels = data["levels"]
        self.level_map = {lv["id"]: lv for lv in self.levels}

        self.current_level = self.levels[0]
        self.user_placements = set()

        self.level_var = tk.StringVar()
        self.status_var = tk.StringVar(value="欢迎，先选择关卡并点击棋盘放置细胞。")
        self.budget_var = tk.StringVar(value="")

        self._configure_style()
        self._build_layout()
        self._load_level(self.current_level["id"])

    def _configure_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Top.TFrame", background=PALETTE["panel"])
        style.configure("Body.TFrame", background=PALETTE["bg"])
        style.configure("Card.TFrame", background=PALETTE["panel"])

        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 16, "bold"))
        style.configure("Sub.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 10))
        style.configure("Head.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 11, "bold"))

        style.configure(
            "Game.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=PALETTE["text"],
            background=PALETTE["panel_2"],
            padding=(10, 8),
            borderwidth=0,
        )
        style.map("Game.TButton", background=[("active", "#223152")])

    def _build_layout(self):
        top = ttk.Frame(self.root, style="Top.TFrame", padding=(16, 14))
        top.pack(fill="x")

        left_top = ttk.Frame(top, style="Top.TFrame")
        left_top.pack(side="left", fill="x", expand=True)

        ttk.Label(left_top, text="Emergence Tactician", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left_top, text="点击放置细胞，运行模拟，完成目标。", style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        right_top = ttk.Frame(top, style="Top.TFrame")
        right_top.pack(side="right")

        self.level_combo = ttk.Combobox(
            right_top,
            textvariable=self.level_var,
            state="readonly",
            width=28,
            values=[f"{lv['id']} · {lv['title']}" for lv in self.levels],
        )
        self.level_combo.pack(side="left", padx=(0, 8))
        self.level_combo.bind("<<ComboboxSelected>>", self.on_level_change)

        ttk.Button(right_top, text="加载设计解", style="Game.TButton", command=self.load_solution).pack(side="left", padx=4)
        ttk.Button(right_top, text="重置", style="Game.TButton", command=self.reset_placements).pack(side="left", padx=4)
        ttk.Button(right_top, text="运行模拟", style="Game.TButton", command=self.run_level).pack(side="left", padx=4)

        body = ttk.Frame(self.root, style="Body.TFrame", padding=(16, 14, 16, 16))
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # Board card
        board_card = tk.Frame(body, bg=PALETTE["panel"], bd=0, highlightthickness=0)
        board_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.canvas = tk.Canvas(board_card, bg=PALETTE["panel"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Info card
        info = tk.Frame(body, bg=PALETTE["panel"], bd=0, highlightthickness=0)
        info.grid(row=0, column=1, sticky="nsew")

        self._section(info, "关卡说明", "intro")
        self._section(info, "目标", "goals")
        self._section(info, "提示", "hints")

        footer = tk.Frame(info, bg=PALETTE["panel_2"])
        footer.pack(fill="x", padx=12, pady=(8, 12))

        self.budget_label = tk.Label(
            footer,
            textvariable=self.budget_var,
            bg=PALETTE["panel_2"],
            fg=PALETTE["text"],
            anchor="w",
            justify="left",
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=8,
        )
        self.budget_label.pack(fill="x")

        self.status_label = tk.Label(
            footer,
            textvariable=self.status_var,
            bg=PALETTE["panel_2"],
            fg=PALETTE["accent"],
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
            wraplength=420,
            padx=10,
            pady=8,
        )
        self.status_label.pack(fill="x")

    def _section(self, parent, title, key):
        frame = tk.Frame(parent, bg=PALETTE["panel"])
        frame.pack(fill="x", padx=12, pady=(10, 0))

        tk.Label(frame, text=title, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")

        label = tk.Label(
            frame,
            text="",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            justify="left",
            anchor="nw",
            font=("Segoe UI", 10),
            wraplength=430,
            padx=2,
            pady=4,
        )
        label.pack(fill="x")
        setattr(self, f"{key}_label", label)

    def on_level_change(self, _evt=None):
        level_id = self.level_var.get().split(" · ")[0]
        self._load_level(level_id)

    def _load_level(self, level_id):
        self.current_level = self.level_map[level_id]
        self.user_placements = set()

        lv = self.current_level
        self.level_var.set(f"{lv['id']} · {lv['title']}")

        self.intro_label.config(text=lv["tutorial"]["intro"])

        goal_lines = []
        for g in lv["goals"]:
            ch = g["check"]
            goal_lines.append(f"• {g['id']}：{ch['type']}")
        self.goals_label.config(text="\n".join(goal_lines))

        hint_lines = [f"• {h}" for h in lv["tutorial"]["hints"]]
        self.hints_label.config(text="\n".join(hint_lines))

        b = lv["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 0）")
        self.status_var.set("已载入关卡，点击棋盘放置细胞。")

        self.draw_board()

    def _board_sets(self):
        lv = self.current_level
        blocked = {(c["x"], c["y"]) for c in lv.get("blocked_cells", [])}
        preset = {(c["x"], c["y"]) for c in lv.get("preset_alive", [])}
        return blocked, preset

    def draw_board(self, show_alive=None):
        lv = self.current_level
        w = lv["board"]["width"]
        h = lv["board"]["height"]
        blocked, preset = self._board_sets()
        user = set(self.user_placements) if show_alive is None else set(show_alive)

        width_px = BOARD_PAD * 2 + w * CELL_SIZE
        height_px = BOARD_PAD * 2 + h * CELL_SIZE
        self.canvas.config(width=width_px, height=height_px)
        self.canvas.delete("all")

        self.canvas.create_rectangle(0, 0, width_px, height_px, fill=PALETTE["panel"], outline=PALETTE["panel"])

        for y in range(h):
            for x in range(w):
                x0 = BOARD_PAD + x * CELL_SIZE
                y0 = BOARD_PAD + y * CELL_SIZE
                x1 = x0 + CELL_SIZE - 1
                y1 = y0 + CELL_SIZE - 1

                cell = (x, y)
                if cell in blocked:
                    fill = PALETTE["cell_block"]
                elif cell in preset:
                    fill = PALETTE["cell_preset"]
                elif cell in user:
                    fill = PALETTE["cell_alive"]
                else:
                    fill = PALETTE["cell_empty"]

                self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=PALETTE["cell_grid"])

    def on_canvas_click(self, evt):
        lv = self.current_level
        w = lv["board"]["width"]
        h = lv["board"]["height"]
        x = (evt.x - BOARD_PAD) // CELL_SIZE
        y = (evt.y - BOARD_PAD) // CELL_SIZE

        if not (0 <= x < w and 0 <= y < h):
            return

        blocked, preset = self._board_sets()
        c = (x, y)
        if c in blocked or c in preset:
            self.status_var.set("该格不可编辑（障碍或预置细胞）。")
            return

        if c in self.user_placements:
            self.user_placements.remove(c)
        else:
            self.user_placements.add(c)

        b = lv["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 {len(self.user_placements)}）")
        self.status_var.set(f"已更新放置：({x}, {y})")
        self.draw_board()

    def reset_placements(self):
        self.user_placements.clear()
        b = self.current_level["placement_budget"]
        self.budget_var.set(f"放置预算：{b['min']} ~ {b['max']}（当前 0）")
        self.status_var.set("已重置玩家放置。")
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
        self.draw_board(show_alive=final_alive)

        if failures:
            self.status_var.set(f"未过关：失败目标 {', '.join(failures)}")
            messagebox.showinfo("结果", f"未过关。失败目标：{', '.join(failures)}")
        else:
            self.status_var.set("🎉 过关！全部目标达成。")
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
            for yy in range(h):
                for xx in range(w):
                    if (xx, yy) in alive_now and (xx, yy) not in excluded:
                        alive_now.remove((xx, yy))
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
    ModernGameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
