"""
setstickfigure.py (GridDesigner2)

Paint + joints workflow:
- Left click/drag paints pixels (InteractiveGrid behavior).
- Right click sets the *currently selected* joint name to that cell.
- Sidebar lets you pick which joint you’re setting next.
- Sidebar also shows a live list of all joints and their current (x,y).

JSON per frame contains:
- joints (local coordinates)
- optional shoulder_center / hip_center (derived if missing)
- offset (world translation for later composition)
"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from interactivegrid import InteractiveGrid


class SetStickFigure(InteractiveGrid):
    # -------------------------
    # CONFIG (edit later easily)
    # -------------------------
    LOCAL_GRID_SIZE = 20
    DEFAULT_CELL_SIZE = 28

    FIGURE_COLOR_INDEX_DEFAULT = 1
    DEFAULT_COLOR_INDEX = 0

    # Mandatory joints
    MANDATORY_JOINTS = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]

    # Optional (derived midpoint if missing)
    OPTIONAL_CENTER_JOINTS = ["shoulder_center", "hip_center"]

    # Joint list (UI selection order)
    JOINT_ORDER = [
        "head",
        "left_shoulder", "right_shoulder", "shoulder_center",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist",
        "left_hand", "right_hand",
        "left_hip", "right_hip", "hip_center",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle",
        "left_foot", "right_foot"
    ]

    # Compatibility aliases for external model/template files.
    JOINT_ALIASES = {
        "l_shoulder": "left_shoulder",
        "r_shoulder": "right_shoulder",
        "l_elbow": "left_elbow",
        "r_elbow": "right_elbow",
        "l_wrist": "left_wrist",
        "r_wrist": "right_wrist",
        "l_hand": "left_hand",
        "r_hand": "right_hand",
        "l_hip": "left_hip",
        "r_hip": "right_hip",
        "l_knee": "left_knee",
        "r_knee": "right_knee",
        "l_ankle": "left_ankle",
        "r_ankle": "right_ankle",
        "l_foot": "left_foot",
        "r_foot": "right_foot",
        "hip": "hip_center",
        "neck": "shoulder_center",
        "head_c": "head",
    }

    # Startup template/model to preload when available
    DEFAULT_TEMPLATE_FILENAME = "secondModel.json"

    # GUI-only joint marker colors (never serialized to JSON)
    JOINT_GUI_COLORS = {
        "default": "red",
    }

    def __init__(
        self,
        root,
        *,
        grid_size=None,
        cell_size=None,
        default_color=None,
        figure_color_index=None,
        show_sidebar=True,
    ):
        self.grid_size = int(grid_size or self.LOCAL_GRID_SIZE)
        self.figure_color_index = int(
            figure_color_index if figure_color_index is not None else self.FIGURE_COLOR_INDEX_DEFAULT
        )

        # World translation for later composition
        self.offset_x = 0
        self.offset_y = 0

        # Joint model: name -> {"x": int, "y": int}
        self.joints = {}

        # Which joint right-click sets next
        self.current_joint_index = 0

        super().__init__(
            root,
            grid_width=self.grid_size,
            grid_height=self.grid_size,
            cell_size=int(cell_size or self.DEFAULT_CELL_SIZE),
            default_color=int(default_color if default_color is not None else self.DEFAULT_COLOR_INDEX),
            show_sidebar=show_sidebar,
            color_map={
                0: "white",
                1: "black",
                2: "red",
                3: "green",
                4: "blue",
            },
        )

        # Default drawing color
        self.set_active_color(self.figure_color_index)

        # Right-click sets current joint position
        self.canvas.bind("<Button-3>", self.on_right_click_set_joint)
        self.canvas.bind("<Control-Button-1>", self.on_right_click_set_joint)  # alternative

        # Keyboard helpers: cycle current joint
        self.root.bind("<KeyPress-bracketleft>", lambda e: self.prev_joint())
        self.root.bind("<KeyPress-bracketright>", lambda e: self.next_joint())

        # Initial draw
        self.draw_grid()

        # Preload a default template/model when present.
        self._load_default_template_if_available()

    # -------------------------
    # Sidebar
    # -------------------------
    def build_sidebar(self, parent):
        title = tk.Label(parent, text="Stick Figure (Paint + Joints)", font=("TkDefaultFont", 12, "bold"))
        title.pack(anchor="w", padx=8, pady=(8, 6))

        # Reuse InteractiveGrid tools (palette, eyedropper, zoom label)
        super().build_sidebar(parent)

        # Joint tools
        joint_box = tk.LabelFrame(parent, text="Joints")
        joint_box.pack(fill=tk.BOTH, expand=False, padx=8, pady=(8, 8))

        # Current joint selection
        self._current_joint_var = tk.StringVar(value=self.current_joint_name())
        cur_row = tk.Frame(joint_box)
        cur_row.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(cur_row, text="Current (right-click sets):").pack(side=tk.LEFT)
        tk.Label(cur_row, textvariable=self._current_joint_var).pack(side=tk.LEFT, padx=(6, 0))

        btn_row = tk.Frame(joint_box)
        btn_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Button(btn_row, text="Prev  [", command=self.prev_joint).pack(side=tk.LEFT)
        tk.Button(btn_row, text="Next  ]", command=self.next_joint).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(btn_row, text="Clear joints", command=self.clear_joints).pack(side=tk.RIGHT)

        # Live joint position list and selection
        tk.Label(joint_box, text="Positions:").pack(anchor="w", padx=6)
        self._joint_listbox = tk.Listbox(joint_box, height=10, width=28)
        self._joint_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
        self._joint_listbox.bind('<<ListboxSelect>>', self.on_joint_select)

        # Offset controls
        off_box = tk.LabelFrame(parent, text="World translation (saved in JSON)")
        off_box.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._offset_x_var = tk.IntVar(value=self.offset_x)
        self._offset_y_var = tk.IntVar(value=self.offset_y)

        ox_row = tk.Frame(off_box)
        ox_row.pack(fill=tk.X, padx=6, pady=(4, 2))
        tk.Label(ox_row, text="offset_x:").pack(side=tk.LEFT)
        tk.Spinbox(
            ox_row, from_=-999, to=999, width=6,
            textvariable=self._offset_x_var,
            command=self._sync_offset_from_ui
        ).pack(side=tk.LEFT, padx=(6, 0))

        oy_row = tk.Frame(off_box)
        oy_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Label(oy_row, text="offset_y:").pack(side=tk.LEFT)
        tk.Spinbox(
            oy_row, from_=-999, to=999, width=6,
            textvariable=self._offset_y_var,
            command=self._sync_offset_from_ui
        ).pack(side=tk.LEFT, padx=(6, 0))

        # Save/load
        io_box = tk.LabelFrame(parent, text="Frame JSON")
        io_box.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Button(io_box, text="Load Model/Template...", command=self.load_frame_dialog).pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Button(io_box, text="Save Frame...", command=self.save_frame_dialog).pack(fill=tk.X, padx=6, pady=(2, 6))

        # Populate joint list initially
        self._refresh_joint_list()

    def _sync_offset_from_ui(self):
        if hasattr(self, "_offset_x_var"):
            self.offset_x = int(self._offset_x_var.get())
        if hasattr(self, "_offset_y_var"):
            self.offset_y = int(self._offset_y_var.get())

    # -------------------------
    # Startup template loading
    # -------------------------
    def _default_template_path(self) -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, self.DEFAULT_TEMPLATE_FILENAME)

    def _load_default_template_if_available(self):
        path = self._default_template_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.load_frame_json_dict(data)
        except Exception as e:
            messagebox.showwarning("Default model not loaded", f"Could not load default model:\n{path}\n\n{e}")

    # -------------------------
    # Joint selection + setting
    # -------------------------
    def current_joint_name(self) -> str:
        return self.JOINT_ORDER[self.current_joint_index]

    def _update_joint_ui(self):
        if hasattr(self, "_current_joint_var"):
            self._current_joint_var.set(self.current_joint_name())

    def next_joint(self):
        self.current_joint_index = (self.current_joint_index + 1) % len(self.JOINT_ORDER)
        self._update_joint_ui()

    def prev_joint(self):
        self.current_joint_index = (self.current_joint_index - 1) % len(self.JOINT_ORDER)
        self._update_joint_ui()

    def on_joint_select(self, event):
        if not hasattr(self, "_joint_listbox"):
            return
        selection = self._joint_listbox.curselection()
        if not selection:
            return
        idx = int(selection[0])
        self.current_joint_index = idx
        self._update_joint_ui()

    def clear_joints(self):
        self.joints = {}
        self.draw_grid()
        self._refresh_joint_list()

    def on_right_click_set_joint(self, event):
        """Right-click (or Ctrl+LeftClick) sets the current joint position."""
        cell = self._event_to_cell(event)
        if not cell:
            return
        row, col = cell  # row=y, col=x

        name = self.current_joint_name()
        self.joints[name] = {"x": int(col), "y": int(row)}

        # Update overlay + list
        self.draw_grid()
        self._refresh_joint_list()

    # -------------------------
    # Joint marker overlay (GUI only)
    # -------------------------
    def _joint_gui_color(self, joint_name: str) -> str:
        return self.JOINT_GUI_COLORS.get(joint_name, self.JOINT_GUI_COLORS["default"])

    def _joint_points_for_overlay(self):
        points = dict(self.joints)
        if "shoulder_center" not in points and all(j in self.joints for j in ("left_shoulder", "right_shoulder")):
            points["shoulder_center"] = self.get_shoulder_center()
        if "hip_center" not in points and all(j in self.joints for j in ("left_hip", "right_hip")):
            points["hip_center"] = self.get_hip_center()
        return points

    def _draw_joint_overlays(self):
        ox = getattr(self, "_draw_offset_x", 0)
        oy = getattr(self, "_draw_offset_y", 0)
        r = max(2, int(self.cell_size * 0.22))

        for name, pt in self._joint_points_for_overlay().items():
            x = int(pt.get("x", -1))
            y = int(pt.get("y", -1))
            if not (0 <= x < self.grid_width and 0 <= y < self.grid_height):
                continue

            cx = ox + x * self.cell_size + (self.cell_size / 2)
            cy = oy + y * self.cell_size + (self.cell_size / 2)
            color = self._joint_gui_color(name)

            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")

    # -------------------------
    # Derived centers
    # -------------------------
    def _validate_mandatory_joints(self):
        missing = [j for j in self.MANDATORY_JOINTS if j not in self.joints]
        if missing:
            raise ValueError(f"Missing mandatory joints: {', '.join(missing)}")

    def _derived_center(self, left_name: str, right_name: str):
        lx, ly = self.joints[left_name]["x"], self.joints[left_name]["y"]
        rx, ry = self.joints[right_name]["x"], self.joints[right_name]["y"]
        return {"x": int(round((lx + rx) / 2)), "y": int(round((ly + ry) / 2))}

    def get_shoulder_center(self):
        if "shoulder_center" in self.joints:
            return self.joints["shoulder_center"]
        return self._derived_center("left_shoulder", "right_shoulder")

    def get_hip_center(self):
        if "hip_center" in self.joints:
            return self.joints["hip_center"]
        return self._derived_center("left_hip", "right_hip")

    # -------------------------
    # Joint list UI
    # -------------------------
    def _refresh_joint_list(self):
        """Populate listbox with joint info and select current joint."""
        if not hasattr(self, "_joint_listbox"):
            return

        # Clear existing items
        self._joint_listbox.delete(0, tk.END)

        for name in self.JOINT_ORDER:
            if name in self.joints:
                x = int(self.joints[name]["x"])
                y = int(self.joints[name]["y"])
                display = f"{name:16s} : ({x:2d}, {y:2d})"
            else:
                if name == "shoulder_center" and all(j in self.joints for j in ("left_shoulder", "right_shoulder")):
                    pt = self.get_shoulder_center()
                    display = f"{ 'shoulder_center*':16s } : ({pt['x']:2d}, {pt['y']:2d})"
                elif name == "hip_center" and all(j in self.joints for j in ("left_hip", "right_hip")):
                    pt = self.get_hip_center()
                    display = f"{'hip_center*':16s} : ({pt['x']:2d}, {pt['y']:2d})"
                else:
                    display = f"{name:16s} : (  -,   -)"
            self._joint_listbox.insert(tk.END, display)

        # Add offset info as a separate item
        self._joint_listbox.insert(tk.END, "")
        self._joint_listbox.insert(tk.END, f"offset_x/y : ({self.offset_x}, {self.offset_y})")

        # Select current joint in listbox
        try:
            self._joint_listbox.select_clear(0, tk.END)
            self._joint_listbox.select_set(self.current_joint_index)
            self._joint_listbox.see(self.current_joint_index)
        except Exception:
            pass

    # -------------------------
    # Redraw hook
    # -------------------------
    def draw_grid(self):
        """Draw grid + refresh list (so positions update even after zoom)."""
        super().draw_grid()
        self._draw_joint_overlays()
        self._refresh_joint_list()

    # -------------------------
    # JSON I/O
    # -------------------------
    def _clear_grid_to_default(self):
        self.grid = [[self.default_color for _ in range(self.grid_width)] for _ in range(self.grid_height)]

    def _boxes_from_grid(self):
        boxes = {}
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                val = int(self.grid[y][x])
                if val != self.default_color:
                    boxes[f"{x},{y}"] = val
        return boxes

    def _apply_boxes_to_grid(self, boxes):
        if not isinstance(boxes, dict):
            return
        for key, raw_val in boxes.items():
            if not isinstance(key, str) or "," not in key:
                continue
            x_str, y_str = key.split(",", 1)
            try:
                x = int(x_str.strip())
                y = int(y_str.strip())
                val = int(raw_val)
            except (TypeError, ValueError):
                continue
            if 0 <= x < self.grid_width and 0 <= y < self.grid_height:
                self.grid[y][x] = val

    def _normalize_joint_name(self, name: str) -> str:
        s = str(name)
        return self.JOINT_ALIASES.get(s, s)

    def _normalize_joint_point(self, pt):
        if isinstance(pt, dict) and "x" in pt and "y" in pt:
            return {"x": int(pt["x"]), "y": int(pt["y"])}
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            return {"x": int(pt[0]), "y": int(pt[1])}
        return None

    def to_frame_json_dict(self):
        self._sync_offset_from_ui()
        self._validate_mandatory_joints()

        boxes = self._boxes_from_grid()
        # Export joints in external-template-friendly [x, y] format.
        joints_xy = {
            name: [int(pt["x"]), int(pt["y"])]
            for name, pt in self.joints.items()
        }

        return {
            "version": 1,
            "name": "frame",
            "grid": {"width": int(self.grid_width), "height": int(self.grid_height)},
            "grid_width": int(self.grid_width),
            "grid_height": int(self.grid_height),
            "default_color": int(self.default_color),
            "offset": {"x": int(self.offset_x), "y": int(self.offset_y)},
            "joints": joints_xy,
            "boxes": boxes,
            "style": {"color_index": int(self.figure_color_index)},
        }

    def load_frame_json_dict(self, data: dict):
        joints = data.get("joints")
        if not isinstance(joints, dict):
            raise ValueError("Invalid JSON: missing 'joints' dict")

        # Parse + normalize joints so GUI math is always int-safe.
        parsed_joints = {}
        for name, pt in joints.items():
            canonical = self._normalize_joint_name(name)
            normalized_pt = self._normalize_joint_point(pt)
            if normalized_pt is None:
                continue
            parsed_joints[canonical] = normalized_pt
        self.joints = parsed_joints

        grid_info = data.get("grid") or {}
        new_w = self.grid_width
        new_h = self.grid_height
        if isinstance(grid_info, dict):
            new_w = int(grid_info.get("width", new_w))
            new_h = int(grid_info.get("height", new_h))
        if "grid_width" in data:
            new_w = int(data["grid_width"])
        if "grid_height" in data:
            new_h = int(data["grid_height"])

        if "default_color" in data:
            self.default_color = int(data["default_color"])

        if new_w > 0 and new_h > 0 and (new_w != self.grid_width or new_h != self.grid_height):
            self.grid_width = new_w
            self.grid_height = new_h
            self._update_scrollregion()

        self._clear_grid_to_default()
        self._apply_boxes_to_grid(data.get("boxes"))

        off = data.get("offset") or {}
        self.offset_x = int(off.get("x", 0))
        self.offset_y = int(off.get("y", 0))

        if hasattr(self, "_offset_x_var"):
            self._offset_x_var.set(self.offset_x)
        if hasattr(self, "_offset_y_var"):
            self._offset_y_var.set(self.offset_y)

        style = data.get("style") or {}
        if "color_index" in style:
            self.figure_color_index = int(style["color_index"])
            self.set_active_color(self.figure_color_index)

        self.draw_grid()

    def save_frame_dialog(self):
        path = filedialog.asksaveasfilename(
            title="Save Frame JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            data = self.to_frame_json_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Saved frame:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def load_frame_dialog(self):
        path = filedialog.askopenfilename(
            title="Load Model/Template JSON",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.load_frame_json_dict(data)
            messagebox.showinfo("Loaded", f"Loaded frame:\n{path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    root.title("SetStickFigure (paint + right-click joints)")

    app = SetStickFigure(
        root,
        grid_size=30,
        cell_size=28,
        show_sidebar=True,
    )

    root.mainloop()