import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from interactivegrid import InteractiveGrid
from mode import CreateAnimationMode, ExportAnimationMode, FrameEditorMode, SceneMode
from setStickFigure import SetStickFigure


class StickAnimationGUI(SetStickFigure):
    """Mode-driven stick animation editor with a shared canvas."""

    DEFAULT_FRAME_DURATION_MS = 120
    DEFAULT_FRAME_REPEAT_COUNT = 0

    def __init__(self, root, **kwargs):
        self.frames = []
        self.current_frame_index = 0

        self._timeline_syncing = False
        self._timeline_listbox = None
        self._frame_duration_var = None
        self._frame_repeat_count_var = None
        self._frame_repeat_forever_var = None
        self._scene_listbox = None
        self._scene_frame_listbox = None
        self._group_id_var = None
        self._group_repeat_var = None

        self.scene_animations = []

        self._joint_overlay_visible = True
        self._joint_editing_enabled = True

        self._play_job = None
        self._is_playing = False
        self._loop_animation_var = tk.BooleanVar(value=False)
        self._play_frame_index = 0
        self._play_repeat_progress = 0
        self._play_group_loop_done = {}

        self._scene_play_index = 0
        self._scene_play_anim_frames = []
        self._scene_play_frame_map = {}

        self._mode_panel_host = None
        self._mode_var = tk.StringVar(value="frame_editor")
        self._current_mode = None
        self._mode_registry = {
            "frame_editor": FrameEditorMode(),
            "create_animation": CreateAnimationMode(),
            "scene": SceneMode(),
            "export_animation": ExportAnimationMode(),
        }

        super().__init__(root, **kwargs)

        self._build_mode_switcher()
        self._init_timeline_from_current_canvas()
        self.switch_mode("frame_editor")

    # -------------------------
    # Sidebar and mode shell
    # -------------------------
    def build_sidebar(self, parent):
        title = tk.Label(parent, text="Stick Animation", font=("TkDefaultFont", 12, "bold"))
        title.pack(anchor="w", padx=8, pady=(8, 6))

        tools_box = tk.LabelFrame(parent, text="Zoom Info")
        tools_box.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._zoom_label_var = tk.StringVar(value=f"Cell size: {self.cell_size}px")
        zoom_row = tk.Frame(tools_box)
        zoom_row.pack(fill=tk.X, padx=6, pady=(6, 6))
        tk.Label(zoom_row, textvariable=self._zoom_label_var).pack(side=tk.LEFT)

        self._mode_panel_host = tk.LabelFrame(parent, text="Mode Controls")
        self._mode_panel_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _build_mode_switcher(self):
        mode_row = tk.Frame(self.root)
        mode_row.pack(fill=tk.X, padx=6, pady=(6, 4), before=self.main_frame)

        tk.Label(mode_row, text="Mode:").pack(side=tk.LEFT)
        for mode_id in ("frame_editor", "create_animation", "scene", "export_animation"):
            mode = self._mode_registry[mode_id]
            tk.Radiobutton(
                mode_row,
                text=mode.label,
                value=mode_id,
                variable=self._mode_var,
                command=lambda mid=mode_id: self.switch_mode(mid),
            ).pack(side=tk.LEFT, padx=(8, 0))

    def switch_mode(self, mode_id: str):
        if mode_id not in self._mode_registry:
            return

        self._store_current_frame()

        if self._current_mode is not None:
            self._current_mode.on_leave(self)

        for child in self._mode_panel_host.winfo_children():
            child.destroy()

        self._clear_mode_widget_refs()

        mode = self._mode_registry[mode_id]
        mode.build(self, self._mode_panel_host)
        mode.on_enter(self)
        self._current_mode = mode
        self._mode_var.set(mode_id)
        self.draw_grid()

    def _clear_mode_widget_refs(self):
        self._timeline_listbox = None
        self._frame_duration_var = None
        self._frame_repeat_count_var = None
        self._frame_repeat_forever_var = None
        self._scene_listbox = None
        self._scene_frame_listbox = None
        self._group_id_var = None
        self._group_repeat_var = None
        self._joint_listbox = None
        self._current_joint_var = None
        self._eyedropper_var = None
        self._active_color_var = None



    # -------------------------
    # Draw behavior
    # -------------------------
    def draw_grid(self):
        InteractiveGrid.draw_grid(self)
        if self._joint_overlay_visible:
            self._draw_joint_overlays()
        self._refresh_joint_list()

    def set_joint_overlay_visible(self, visible: bool):
        self._joint_overlay_visible = bool(visible)
        self.draw_grid()

    def enable_joint_editing(self, enabled: bool):
        self._joint_editing_enabled = bool(enabled)
        if hasattr(self, "_joint_listbox"):
            try:
                if self._joint_listbox.winfo_exists():
                    self._joint_listbox.config(state=(tk.NORMAL if enabled else tk.DISABLED))
            except Exception:
                pass

    def on_right_click_set_joint(self, event):
        if not self._joint_editing_enabled:
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

    def _normalize_frame_payload(self, payload):
        duration = int(payload.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS))
        repeat_count = int(payload.get("repeat_count", self.DEFAULT_FRAME_REPEAT_COUNT))
        repeat_forever = bool(payload.get("repeat_forever", False))
        return {
            "duration_ms": max(1, duration),
            "repeat_count": max(0, repeat_count),
            "repeat_forever": repeat_forever,
            "frame": payload.get("frame", self._blank_frame_data()),
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

        prev = self.frames[idx]
        self.frames[idx] = {
            "duration_ms": int(duration),
            "repeat_count": int(prev.get("repeat_count", 0)),
            "repeat_forever": bool(prev.get("repeat_forever", False)),
            "group_id": prev.get("group_id"),
            "group_repeat": int(prev.get("group_repeat", 0)),
            "source_name": str(prev.get("source_name", "")),
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
            if self._scene_frame_listbox is not None:
                try:
                    if self._scene_frame_listbox.winfo_exists():
                        self._scene_frame_listbox.selection_clear(0, tk.END)
                        self._scene_frame_listbox.selection_set(index)
                        self._scene_frame_listbox.see(index)
                except Exception:
                    pass
            self._refresh_timeline_ui()
        finally:
            self._timeline_syncing = False

    def _refresh_timeline_ui(self):
        if self._timeline_listbox is None:
            return
        try:
            if not self._timeline_listbox.winfo_exists():
                return
        except Exception:
            return

        self._timeline_listbox.delete(0, tk.END)
        for idx, payload in enumerate(self.frames):
            source = str(payload.get("source_name", "")).strip()
            gid = payload.get("group_id")
            grepeat = int(payload.get("group_repeat", 0))

            label_parts = [f"{idx + 1:02d}"]
            if source:
                label_parts.append(source)
            if gid is not None:
                label_parts.append(f"G{int(gid)}R{grepeat}")
            label = " ".join(label_parts)
            self._timeline_listbox.insert(tk.END, label)

        if self.frames:
            self._timeline_listbox.select_clear(0, tk.END)
            self._timeline_listbox.select_set(self.current_frame_index)
            self._timeline_listbox.see(self.current_frame_index)

        self.refresh_scene_frame_ui()

    def _init_timeline_from_current_canvas(self):
        self.frames = [
            {
                "duration_ms": self.DEFAULT_FRAME_DURATION_MS,
                "repeat_count": self.DEFAULT_FRAME_REPEAT_COUNT,
                "repeat_forever": False,
                "group_id": None,
                "group_repeat": 0,
                "source_name": "",
                "frame": self._collect_current_frame_data(),
            }
        ]
        self.current_frame_index = 0
        if self._frame_duration_var is not None:
            self._frame_duration_var.set(self.DEFAULT_FRAME_DURATION_MS)
        self._refresh_timeline_ui()
        self.draw_grid()

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

    def on_repeat_settings_changed(self):
        if self._timeline_syncing:
            return
        if not self.frames or self._frame_repeat_count_var is None or self._frame_repeat_forever_var is None:
            return

        try:
            repeat_count = max(0, int(self._frame_repeat_count_var.get()))
        except (TypeError, ValueError, tk.TclError):
            repeat_count = self.DEFAULT_FRAME_REPEAT_COUNT
            self._frame_repeat_count_var.set(repeat_count)

        repeat_forever = bool(self._frame_repeat_forever_var.get())
        cur = self.frames[self.current_frame_index]
        cur["repeat_count"] = int(repeat_count)
        cur["repeat_forever"] = bool(repeat_forever)
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
                "repeat_count": self.DEFAULT_FRAME_REPEAT_COUNT,
                "repeat_forever": False,
                "group_id": None,
                "group_repeat": 0,
                "source_name": "",
                "frame": self._blank_frame_data(),
            },
        )
        self._load_frame_at_index(insert_at)

    def duplicate_frame(self):
        self._store_current_frame()
        src = self.frames[self.current_frame_index]
        clone = {
            "duration_ms": int(src.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS)),
            "repeat_count": int(src.get("repeat_count", self.DEFAULT_FRAME_REPEAT_COUNT)),
            "repeat_forever": bool(src.get("repeat_forever", False)),
            "group_id": src.get("group_id"),
            "group_repeat": int(src.get("group_repeat", 0)),
            "source_name": str(src.get("source_name", "")),
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
                    "repeat_count": int(payload.get("repeat_count", self.DEFAULT_FRAME_REPEAT_COUNT)),
                    "repeat_forever": bool(payload.get("repeat_forever", False)),
                    "group_id": payload.get("group_id"),
                    "group_repeat": int(payload.get("group_repeat", 0)),
                    "source_name": str(payload.get("source_name", "")),
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
                repeat_count = int(item.get("repeat_count", self.DEFAULT_FRAME_REPEAT_COUNT))
                repeat_forever = bool(item.get("repeat_forever", False))
                group_id = item.get("group_id")
                group_repeat = int(item.get("group_repeat", 0))
                source_name = str(item.get("source_name", item.get("name", "")))
                frame_data = dict(item)
                frame_data.pop("duration_ms", None)
                frame_data.pop("repeat_count", None)
                frame_data.pop("repeat_forever", None)
                frame_data.pop("group_id", None)
                frame_data.pop("group_repeat", None)
                frame_data.pop("source_name", None)
                loaded_frames.append(
                    {
                        "duration_ms": max(1, duration),
                        "repeat_count": max(0, repeat_count),
                        "repeat_forever": repeat_forever,
                        "group_id": (int(group_id) if group_id is not None else None),
                        "group_repeat": max(0, group_repeat),
                        "source_name": source_name,
                        "frame": frame_data,
                    }
                )

        # Single-frame file format fallback.
        elif isinstance(data.get("joints"), dict):
            loaded_frames.append(
                {
                    "duration_ms": self.DEFAULT_FRAME_DURATION_MS,
                    "repeat_count": self.DEFAULT_FRAME_REPEAT_COUNT,
                    "repeat_forever": False,
                    "group_id": None,
                    "group_repeat": 0,
                    "source_name": str(data.get("name", "")),
                    "frame": data,
                }
            )

        if not loaded_frames:
            raise ValueError("Invalid animation JSON: expected 'frames' list or a single frame JSON")

        self.frames = loaded_frames
        self._load_frame_at_index(0)

    # -------------------------
    # Playback
    # -------------------------
    def play_animation(self):
        if not self.frames:
            return
        self._store_current_frame()
        self._is_playing = True
        self._play_frame_index = self.current_frame_index
        self._play_repeat_progress = 0
        self._play_group_loop_done = {}
        self._cancel_play_job()
        self._play_tick()

    def pause_animation(self):
        self._is_playing = False
        self._cancel_play_job()

    def stop_playback(self):
        self.pause_animation()

    def _cancel_play_job(self):
        if self._play_job is not None:
            try:
                self.root.after_cancel(self._play_job)
            except Exception:
                pass
        self._play_job = None

    def _play_tick(self):
        if not self._is_playing or not self.frames:
            return

        idx = max(0, min(self._play_frame_index, len(self.frames) - 1))
        payload = self.frames[idx]
        self._load_frame_at_index(idx)

        delay = max(1, int(payload.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS)))
        self._play_frame_index = idx + 1

        group_run = self._group_run_ending_at(idx)
        if group_run is not None:
            key = (group_run["start"], group_run["end"], group_run["group_id"])
            done = int(self._play_group_loop_done.get(key, 0))
            if done < group_run["group_repeat"]:
                self._play_group_loop_done[key] = done + 1
                self._play_frame_index = group_run["start"]
            else:
                self._play_group_loop_done[key] = 0

        if self._play_frame_index >= len(self.frames):
            if self._loop_animation_var.get():
                self._play_frame_index = 0
            else:
                self.pause_animation()
                return

        self._play_job = self.root.after(delay, self._play_tick)

    def play_scene(self):
        """Play all animations in the scene sequence."""
        if not self.scene_animations:
            return
        self._is_playing = True
        self._scene_play_index = 0
        self._play_group_loop_done = {}
        self._cancel_play_job()
        self._load_scene_animation(0)

    def _load_scene_animation(self, anim_index: int):
        """Load animation frames from scene at given index."""
        if not (0 <= anim_index < len(self.scene_animations)):
            self.pause_animation()
            return
        anim_data = self.scene_animations[anim_index].get("animation", {})
        self._scene_play_anim_frames = anim_data.get("frames", [])
        self._scene_play_frame_map = {}
        self._scene_play_index = anim_index
        self._play_frame_index = 0
        self._play_group_loop_done = {}
        if self._scene_play_anim_frames:
            self._play_scene_tick()

    def _play_scene_tick(self):
        """Play one frame of current scene animation."""
        if not self._is_playing or not self._scene_play_anim_frames:
            return

        idx = max(0, min(self._play_frame_index, len(self._scene_play_anim_frames) - 1))
        payload = self._scene_play_anim_frames[idx]

        # Load this frame's data to canvas
        frame_data = {k: v for k, v in payload.items() if k not in ("duration_ms", "repeat_count", "repeat_forever", "group_id", "group_repeat", "source_name")}
        self.load_frame_json_dict(frame_data)

        delay = max(1, int(payload.get("duration_ms", self.DEFAULT_FRAME_DURATION_MS)))
        self._play_frame_index = idx + 1

        # Handle group loops within this animation
        group_run = self._group_run_ending_at_in_list(idx, self._scene_play_anim_frames)
        if group_run is not None:
            key = (self._scene_play_index, group_run["start"], group_run["end"], group_run["group_id"])
            done = int(self._play_group_loop_done.get(key, 0))
            if done < group_run["group_repeat"]:
                self._play_group_loop_done[key] = done + 1
                self._play_frame_index = group_run["start"]
            else:
                self._play_group_loop_done[key] = 0

        if self._play_frame_index >= len(self._scene_play_anim_frames):
            # Move to next animation in scene
            next_anim_idx = self._scene_play_index + 1
            if next_anim_idx < len(self.scene_animations):
                self._load_scene_animation(next_anim_idx)
                return
            else:
                # All animations done
                if self._loop_animation_var.get():
                    self._load_scene_animation(0)
                    return
                else:
                    self.pause_animation()
                    return

        self._play_job = self.root.after(delay, self._play_scene_tick)

    def _group_run_ending_at_in_list(self, end_index: int, frame_list: list):
        """Find group loop info in a specific frame list."""
        if not (0 <= end_index < len(frame_list)):
            return None
        gid = frame_list[end_index].get("group_id")
        if gid is None:
            return None
        start = end_index
        while start - 1 >= 0 and frame_list[start - 1].get("group_id") == gid:
            start -= 1
        if start == end_index:
            return None
        grepeat = max(0, int(frame_list[start].get("group_repeat", 0)))
        return {"start": start, "end": end_index, "group_id": int(gid), "group_repeat": grepeat}

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

    def _append_animation_suffix(self, path: str) -> str:
        folder, file_name = os.path.split(path)
        base, ext = os.path.splitext(file_name)
        if "animation" not in base.lower():
            base = f"{base}_animation"
        return os.path.join(folder, f"{base}{ext}")

    def export_animation_dialog(self):
        path = filedialog.asksaveasfilename(
            title="Export Animation JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        path = self._append_animation_suffix(path)
        try:
            data = self.to_animation_json_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Exported", f"Exported animation:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # -------------------------
    # Scene I/O and editing
    # -------------------------
    def to_scene_json_dict(self):
        return {
            "version": 1,
            "type": "stick_scene",
            "animations": self.scene_animations,
        }

    def load_scene_json_dict(self, data: dict):
        if not isinstance(data, dict) or not isinstance(data.get("animations"), list):
            raise ValueError("Invalid scene JSON: expected 'animations' list")

        out = []
        for item in data["animations"]:
            if not isinstance(item, dict):
                continue
            if "animation" not in item or not isinstance(item["animation"], dict):
                continue
            out.append(
                {
                    "name": str(item.get("name", f"animation_{len(out) + 1}")),
                    "animation": item["animation"],
                }
            )
        self.scene_animations = out
        self.refresh_scene_ui()

    def refresh_scene_ui(self):
        if self._scene_listbox is None:
            return
        try:
            if not self._scene_listbox.winfo_exists():
                return
        except Exception:
            return

        self._scene_listbox.delete(0, tk.END)
        for i, item in enumerate(self.scene_animations, start=1):
            name = str(item.get("name", f"animation_{i}"))
            self._scene_listbox.insert(tk.END, f"{i:02d}: {name}")

    def scene_add_current_animation(self):
        data = self.to_animation_json_dict()
        idx = len(self.scene_animations) + 1
        self.scene_animations.append({"name": f"animation_{idx}", "animation": data})
        self.refresh_scene_ui()

    def scene_load_animation_into_scene(self):
        path = filedialog.askopenfilename(
            title="Load Animation Into Scene",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or not isinstance(data.get("frames"), list):
                raise ValueError("Expected animation JSON with 'frames' list")
            name = os.path.splitext(os.path.basename(path))[0]
            self.scene_animations.append({"name": name, "animation": data})
            self.refresh_scene_ui()
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _scene_selected_index(self):
        if self._scene_listbox is None:
            return None
        try:
            if not self._scene_listbox.winfo_exists():
                return None
            selection = self._scene_listbox.curselection()
        except Exception:
            return None
        if not selection:
            return None
        return int(selection[0])

    def scene_move_selected_up(self):
        idx = self._scene_selected_index()
        if idx is None or idx <= 0:
            return
        self.scene_animations[idx - 1], self.scene_animations[idx] = self.scene_animations[idx], self.scene_animations[idx - 1]
        self.refresh_scene_ui()
        self._scene_listbox.select_set(idx - 1)

    def scene_move_selected_down(self):
        idx = self._scene_selected_index()
        if idx is None or idx >= len(self.scene_animations) - 1:
            return
        self.scene_animations[idx + 1], self.scene_animations[idx] = self.scene_animations[idx], self.scene_animations[idx + 1]
        self.refresh_scene_ui()
        self._scene_listbox.select_set(idx + 1)

    def scene_remove_selected(self):
        idx = self._scene_selected_index()
        if idx is None:
            return
        del self.scene_animations[idx]
        self.refresh_scene_ui()

    def save_scene_dialog(self):
        path = filedialog.asksaveasfilename(
            title="Save Scene JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            data = self.to_scene_json_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Saved scene:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def load_scene_dialog(self):
        path = filedialog.askopenfilename(
            title="Load Scene JSON",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.load_scene_json_dict(data)
            messagebox.showinfo("Loaded", f"Loaded scene:\n{path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def load_frame_dialog(self):
        """Override to prevent loading animation files in frame editor mode."""
        path = filedialog.askopenfilename(
            title="Load Model/Template JSON",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            _, filename = os.path.split(path)
            if "_animation" in filename.lower():
                messagebox.showerror(
                    "Cannot load",
                    f"Cannot load animation file in Frame Editor.\nUse 'Create Animation' mode instead.\n\nFile: {filename}",
                )
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.load_frame_json_dict(data)
            if self.frames and 0 <= self.current_frame_index < len(self.frames):
                self.frames[self.current_frame_index]["source_name"] = os.path.splitext(filename)[0]
                self._refresh_timeline_ui()
            messagebox.showinfo("Loaded", f"Loaded frame:\n{path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

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
            source_name = os.path.splitext(os.path.basename(path))[0]
            for payload in self.frames:
                if not str(payload.get("source_name", "")).strip():
                    payload["source_name"] = source_name
            self._refresh_timeline_ui()
            messagebox.showinfo("Loaded", f"Loaded animation:\n{path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    # -------------------------
    # Group helpers (Scene)
    # -------------------------
    def _selected_scene_frame_indices(self):
        if self._scene_frame_listbox is None:
            return [self.current_frame_index]
        try:
            selection = list(self._scene_frame_listbox.curselection())
        except Exception:
            selection = []
        if not selection:
            return [self.current_frame_index]
        return sorted(int(i) for i in selection)

    def refresh_scene_frame_ui(self):
        if self._scene_frame_listbox is None:
            return
        try:
            if not self._scene_frame_listbox.winfo_exists():
                return
        except Exception:
            return

        self._scene_frame_listbox.delete(0, tk.END)
        for idx, payload in enumerate(self.frames):
            source = str(payload.get("source_name", "")).strip()
            gid = payload.get("group_id")
            grepeat = int(payload.get("group_repeat", 0))
            label_parts = [f"{idx + 1:02d}"]
            if source:
                label_parts.append(source)
            if gid is not None:
                label_parts.append(f"G{int(gid)}R{grepeat}")
            self._scene_frame_listbox.insert(tk.END, " ".join(label_parts))

    def on_scene_frame_select(self, event):
        if self._timeline_syncing or self._scene_frame_listbox is None:
            return
        selection = self._scene_frame_listbox.curselection()
        if not selection:
            return
        new_index = int(selection[0])
        if new_index == self.current_frame_index:
            return
        self._store_current_frame()
        self._load_frame_at_index(new_index)

    def apply_group_to_selected_scene_frames(self):
        if not self.frames or self._group_id_var is None or self._group_repeat_var is None:
            return
        indices = self._selected_scene_frame_indices()
        if not indices:
            return
        if indices[-1] - indices[0] + 1 != len(indices):
            messagebox.showerror("Invalid selection", "Group selection must be contiguous frames.")
            return
        group_id = max(1, int(self._group_id_var.get()))
        group_repeat = max(0, int(self._group_repeat_var.get()))
        for idx in indices:
            self.frames[idx]["group_id"] = group_id
            self.frames[idx]["group_repeat"] = group_repeat
        self._refresh_timeline_ui()
        self.refresh_scene_frame_ui()

    def clear_group_from_selected_scene_frames(self):
        if not self.frames:
            return
        for idx in self._selected_scene_frame_indices():
            self.frames[idx]["group_id"] = None
            self.frames[idx]["group_repeat"] = 0
        self._refresh_timeline_ui()
        self.refresh_scene_frame_ui()

    def _group_run_ending_at(self, end_index: int):
        if not (0 <= end_index < len(self.frames)):
            return None
        gid = self.frames[end_index].get("group_id")
        if gid is None:
            return None
        start = end_index
        while start - 1 >= 0 and self.frames[start - 1].get("group_id") == gid:
            start -= 1
        if start == end_index:
            return None
        grepeat = max(0, int(self.frames[start].get("group_repeat", 0)))
        return {"start": start, "end": end_index, "group_id": int(gid), "group_repeat": grepeat}


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

