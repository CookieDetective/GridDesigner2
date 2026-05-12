import tkinter as tk

from .base import BaseMode


class SceneMode(BaseMode):
    mode_id = "scene"
    label = "Scene"

    def build(self, app, parent):
        super().build(app, parent)

        # Eyedropper tool
        app._eyedropper_var = tk.StringVar(value="OFF")
        drop_row = tk.Frame(parent)
        drop_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Label(drop_row, text="Eyedropper:").pack(side=tk.LEFT)
        tk.Label(drop_row, textvariable=app._eyedropper_var).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(drop_row, text="Toggle (E)", command=app.toggle_eyedropper).pack(side=tk.RIGHT)

        box = tk.LabelFrame(parent, text="Scene (Animation Connections)")
        box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        info = tk.Label(
            box,
            text="Connect animations into a scene sequence.\nThis mode does not use the per-frame dialog.",
            justify=tk.LEFT,
            wraplength=220,
        )
        info.pack(anchor="w", padx=6, pady=(6, 4))

        list_frame = tk.Frame(box)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        app._scene_listbox = tk.Listbox(list_frame, height=8)
        app._scene_listbox.pack(fill=tk.BOTH, expand=True)

        row1 = tk.Frame(box)
        row1.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(row1, text="Add Current Animation", command=app.scene_add_current_animation).pack(side=tk.LEFT)

        row2 = tk.Frame(box)
        row2.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(row2, text="Load Animation Into Scene...", command=app.scene_load_animation_into_scene).pack(
            side=tk.LEFT)


        row3 = tk.Frame(box)
        row3.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(row3, text="Move Up", command=app.scene_move_selected_up).pack(side=tk.LEFT)
        tk.Button(row3, text="Move Down", command=app.scene_move_selected_down).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(row3, text="Remove", command=app.scene_remove_selected).pack(side=tk.RIGHT)

        row4 = tk.Frame(box)
        row4.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(row4, text="Load Scene...", command=app.load_scene_dialog).pack(side=tk.LEFT)
        tk.Button(row4, text="Save Scene...", command=app.save_scene_dialog).pack(side=tk.RIGHT)

        frame_group_box = tk.LabelFrame(parent, text="Frame Repeat Groups")
        frame_group_box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        tk.Label(
            frame_group_box,
            text="Select contiguous frames and apply group repeats (e.g., G1R7).",
            justify=tk.LEFT,
            wraplength=220,
        ).pack(anchor="w", padx=6, pady=(6, 4))

        app._scene_frame_listbox = tk.Listbox(frame_group_box, height=6, selectmode=tk.EXTENDED)
        app._scene_frame_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        app._scene_frame_listbox.bind("<<ListboxSelect>>", app.on_scene_frame_select)

        group_row = tk.Frame(frame_group_box)
        group_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Label(group_row, text="Group ID:").pack(side=tk.LEFT)
        app._group_id_var = tk.IntVar(value=1)
        tk.Spinbox(group_row, from_=1, to=999, width=5, textvariable=app._group_id_var).pack(side=tk.LEFT, padx=(4, 6))
        tk.Label(group_row, text="Group repeats:").pack(side=tk.LEFT)
        app._group_repeat_var = tk.IntVar(value=0)
        tk.Spinbox(group_row, from_=0, to=99999, width=6, textvariable=app._group_repeat_var).pack(side=tk.LEFT, padx=(4, 6))
        tk.Button(group_row, text="Apply", command=app.apply_group_to_selected_scene_frames).pack(side=tk.LEFT)
        tk.Button(group_row, text="Clear", command=app.clear_group_from_selected_scene_frames).pack(side=tk.RIGHT)

        play_row = tk.Frame(frame_group_box)
        play_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(play_row, text="Play", command=app.play_animation).pack(side=tk.LEFT)
        tk.Button(play_row, text="Pause", command=app.pause_animation).pack(side=tk.LEFT, padx=(6, 0))
        tk.Checkbutton(play_row, text="Loop animation", variable=app._loop_animation_var).pack(side=tk.LEFT, padx=(8, 0))

        app.refresh_scene_ui()
        app.refresh_scene_frame_ui()

    def on_enter(self, app):
        app.set_joint_overlay_visible(False)
        app.enable_joint_editing(False)
        app.pause_animation()
        app.refresh_scene_frame_ui()

    def on_leave(self, app):
        app.eyedropper_enabled = False



