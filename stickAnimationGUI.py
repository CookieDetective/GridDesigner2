import json
import tkinter as tk
from tkinter import filedialog, messagebox

from interactivegrid import InteractiveGrid
from setStickFigure import SetStickFigure


class StickAnimationGUI(SetStickFigure):
    """
    Timeline editor built on top of SetStickFigure.

    - Edit frame content exactly like SetStickFigure (paint + joints)
    - Assign per-frame duration (ms)
    - Switch view modes:
        * edit_single: shows joint overlays for precise joint placement
        * compare_sequence: hides joint overlays for clean frame comparison
    """

    DEFAULT_FRAME_DURATION_MS = 120

    def __init__(self, root, **kwargs):
        self.frames = []
        self.current_frame_index = 0
        self._timeline_syncing = False
        self._frame_duration_var = None
        self._timeline_listbox = None
        self._view_mode_var = None

        super().__init__(root, **kwargs)

        # Seed timeline with whatever is currently loaded (default template or blank).
        self._init_timeline_from_current_canvas()

    # -------------------------
    # Sidebar
    # -------------------------
    def build_sidebar(self, parent):
        super().build_sidebar(parent)

        anim_box = tk.LabelFrame(parent, text="Animation Timeline")
        anim_box.pack(fill=tk.X, padx=8, pady=(0, 8))

        # Mode switch controls whether joints are visible.
        self._view_mode_var = tk.StringVar(value="edit_single")
        mode_row = tk.Frame(anim_box)
        mode_row.pack(fill=tk.X, padx=6, pady=(6, 4))
        tk.Label(mode_row, text="Mode:").pack(side=tk.LEFT)
        tk.Radiobutton(
            mode_row,
            text="Edit frame",
            value="edit_single",
            variable=self._view_mode_var,
            command=self.on_view_mode_change,
        ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Radiobutton(
            mode_row,
            text="Compare",
            value="compare_sequence",
            variable=self._view_mode_var,
            command=self.on_view_mode_change,
        ).pack(side=tk.LEFT, padx=(6, 0))

        nav_row = tk.Frame(anim_box)
        nav_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(nav_row, text="Prev frame", command=self.prev_frame).pack(side=tk.LEFT)
        tk.Button(nav_row, text="Next frame", command=self.next_frame).pack(side=tk.LEFT, padx=(6, 0))

        edit_row = tk.Frame(anim_box)
        edit_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(edit_row, text="Add blank", command=self.add_blank_frame).pack(side=tk.LEFT)
        tk.Button(edit_row, text="Duplicate", command=self.duplicate_frame).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(edit_row, text="Delete", command=self.delete_frame).pack(side=tk.RIGHT)

        tk.Label(anim_box, text="Frames:").pack(anchor="w", padx=6)
        self._timeline_listbox = tk.Listbox(anim_box, height=7)
        self._timeline_listbox.pack(fill=tk.X, padx=6, pady=(2, 6))
        self._timeline_listbox.bind("<<ListboxSelect>>", self.on_timeline_select)

        dur_row = tk.Frame(anim_box)
        dur_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Label(dur_row, text="Duration (ms):").pack(side=tk.LEFT)
        self._frame_duration_var = tk.IntVar(value=self.DEFAULT_FRAME_DURATION_MS)
        tk.Spinbox(
            dur_row,
            from_=1,
            to=99999,
            width=8,
            textvariable=self._frame_duration_var,
            command=self.on_duration_changed,
        ).pack(side=tk.LEFT, padx=(6, 0))

        io_row = tk.Frame(anim_box)
        io_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(io_row, text="Load Animation...", command=self.load_animation_dialog).pack(side=tk.LEFT)
        tk.Button(io_row, text="Save Animation...", command=self.save_animation_dialog).pack(side=tk.RIGHT)

    # -------------------------
    # Draw behavior
    # -------------------------
    def is_compare_mode(self) -> bool:
        if self._view_mode_var is None:
            return False
        return self._view_mode_var.get() == "compare_sequence"

    def draw_grid(self):
        InteractiveGrid.draw_grid(self)
        if not self.is_compare_mode():
            self._draw_joint_overlays()
        self._refresh_joint_list()

    def on_view_mode_change(self):
        if hasattr(self, "_joint_listbox"):
            state = tk.DISABLED if self.is_compare_mode() else tk.NORMAL
            self._joint_listbox.config(state=state)
        self.draw_grid()

    def on_right_click_set_joint(self, event):
        # In compare mode we hide joint editing to avoid accidental invisible edits.
        if self.is_compare_mode():
            return
        super().on_right_click_set_joint(event)

    # -------------------------
    # Timeline helpers
    # -------------------------
    def _blank_frame_data(self):
        return {
            "version": 1,
            "name": "frame",
            "grid": {"width": int(self.grid_width), "height": int(self.grid_height)},
            "grid_width": int(self.grid_width),
            "grid_height": int(self.grid_height),
            "default_color": int(self.default_color),
            "offset": {"x": 0, "y": 0},
            "joints": {},
            "boxes": {},
            "style": {"color_index": int(self.figure_color_index)},
        }

    def _collect_current_frame_data(self):
        self._sync_offset_from_ui()
        return {
            "version": 1,
            "name": "frame",
            "grid": {"width": int(self.grid_width), "height": int(self.grid_height)},
            "grid_width": int(self.grid_width),
            "grid_height": int(self.grid_height),
            "default_color": int(self.default_color),
            "offset": {"x": int(self.offset_x), "y": int(self.offset_y)},
            "joints": {
                name: [int(pt["x"]), int(pt["y"])]
                for name, pt in self.joints.items()
            },
            "boxes": self._boxes_from_grid(),
            "style": {"color_index": int(self.figure_color_index)},
        }

    def _store_current_frame(self):
        if not self.frames:
            return
        idx = self.current_frame_index
        if not (0 <= idx < len(self.frames)):
            return

        duration = self.DEFAULT_FRAME_DURATION_MS
        if self._frame_duration_var is not None:
            try:
                duration = max(1, int(self._frame_duration_var.get()))
            except (TypeError, ValueError, tk.TclError):
                duration = self.DEFAULT_FRAME_DURATION_MS

        self.frames[idx] = {
            "duration_ms": int(duration),
            "frame": self._collect_current_frame_data(),
        }

    def _load_frame_at_index(self, index: int):
        if not (0 <= index < len(self.frames)):
            return

        self._timeline_syncing = True
        try:
            payload = self.frames[index]
            self.current_frame_index = index
            self.load_frame_json_dict(payload["frame"])
            if self._frame_duration_var is not None:
                self._frame_duration_var.set(int(payload.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS)))
            self._refresh_timeline_ui()
        finally:
            self._timeline_syncing = False

    def _refresh_timeline_ui(self):
        if self._timeline_listbox is None:
            return

        self._timeline_listbox.delete(0, tk.END)
        for idx, payload in enumerate(self.frames):
            ms = int(payload.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS))
            self._timeline_listbox.insert(tk.END, f"{idx + 1:02d}: {ms} ms")

        if self.frames:
            self._timeline_listbox.select_clear(0, tk.END)
            self._timeline_listbox.select_set(self.current_frame_index)
            self._timeline_listbox.see(self.current_frame_index)

    def _init_timeline_from_current_canvas(self):
        self.frames = [
            {
                "duration_ms": self.DEFAULT_FRAME_DURATION_MS,
                "frame": self._collect_current_frame_data(),
            }
        ]
        self.current_frame_index = 0
        if self._frame_duration_var is not None:
            self._frame_duration_var.set(self.DEFAULT_FRAME_DURATION_MS)
        self._refresh_timeline_ui()
        self.on_view_mode_change()

    # -------------------------
    # Timeline actions
    # -------------------------
    def on_timeline_select(self, event):
        if self._timeline_syncing or self._timeline_listbox is None:
            return
        selection = self._timeline_listbox.curselection()
        if not selection:
            return

        new_index = int(selection[0])
        if new_index == self.current_frame_index:
            return

        self._store_current_frame()
        self._load_frame_at_index(new_index)

    def on_duration_changed(self):
        if self._timeline_syncing:
            return
        if not self.frames:
            return

        try:
            duration = max(1, int(self._frame_duration_var.get()))
        except (TypeError, ValueError, tk.TclError):
            duration = self.DEFAULT_FRAME_DURATION_MS
            self._frame_duration_var.set(duration)

        self.frames[self.current_frame_index]["duration_ms"] = int(duration)
        self._refresh_timeline_ui()

    def prev_frame(self):
        if not self.frames:
            return
        self._store_current_frame()
        new_index = (self.current_frame_index - 1) % len(self.frames)
        self._load_frame_at_index(new_index)

    def next_frame(self):
        if not self.frames:
            return
        self._store_current_frame()
        new_index = (self.current_frame_index + 1) % len(self.frames)
        self._load_frame_at_index(new_index)

    def add_blank_frame(self):
        self._store_current_frame()
        insert_at = self.current_frame_index + 1
        self.frames.insert(
            insert_at,
            {
                "duration_ms": self.DEFAULT_FRAME_DURATION_MS,
                "frame": self._blank_frame_data(),
            },
        )
        self._load_frame_at_index(insert_at)

    def duplicate_frame(self):
        self._store_current_frame()
        src = self.frames[self.current_frame_index]
        clone = {
            "duration_ms": int(src.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS)),
            "frame": json.loads(json.dumps(src.get("frame", {}))),
        }
        insert_at = self.current_frame_index + 1
        self.frames.insert(insert_at, clone)
        self._load_frame_at_index(insert_at)

    def delete_frame(self):
        if not self.frames:
            return
        if len(self.frames) == 1:
            messagebox.showinfo("Cannot delete", "At least one frame is required.")
            return

        del self.frames[self.current_frame_index]
        new_index = min(self.current_frame_index, len(self.frames) - 1)
        self._load_frame_at_index(new_index)

    # -------------------------
    # Animation JSON I/O
    # -------------------------
    def to_animation_json_dict(self):
        self._store_current_frame()
        if not self.frames:
            raise ValueError("Animation has no frames")

        out_frames = []
        for payload in self.frames:
            out_frames.append(
                {
                    "duration_ms": int(payload.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS)),
                    **payload.get("frame", {}),
                }
            )

        return {
            "version": 1,
            "type": "stick_animation",
            "frames": out_frames,
        }

    def load_animation_json_dict(self, data: dict):
        loaded_frames = []

        # Animation file format.
        if isinstance(data.get("frames"), list):
            for item in data["frames"]:
                if not isinstance(item, dict):
                    continue
                duration = int(item.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS))
                frame_data = dict(item)
                frame_data.pop("duration_ms", None)
                loaded_frames.append({"duration_ms": max(1, duration), "frame": frame_data})

        # Single-frame file format fallback.
        elif isinstance(data.get("joints"), dict):
            loaded_frames.append({"duration_ms": self.DEFAULT_FRAME_DURATION_MS, "frame": data})

        if not loaded_frames:
            raise ValueError("Invalid animation JSON: expected 'frames' list or a single frame JSON")

        self.frames = loaded_frames
        self._load_frame_at_index(0)

    def save_animation_dialog(self):
        path = filedialog.asksaveasfilename(
            title="Save Animation JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            data = self.to_animation_json_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Saved animation:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def load_animation_dialog(self):
        path = filedialog.askopenfilename(
            title="Load Animation JSON",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.load_animation_json_dict(data)
            messagebox.showinfo("Loaded", f"Loaded animation:\n{path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    root.title("StickAnimationGUI")

    app = StickAnimationGUI(
        root,
        grid_size=30,
        cell_size=18,
        show_sidebar=True,
    )

    root.mainloop()

