import tkinter as tk

from .base import BaseMode


class FrameEditorMode(BaseMode):
    mode_id = "frame_editor"
    label = "Frame Editor"

    def build(self, app, parent):
        super().build(app, parent)

        # Palette tools
        palette_box = tk.LabelFrame(parent, text="Palette")
        palette_box.pack(fill=tk.X, padx=6, pady=(0, 8))

        active_row = tk.Frame(palette_box)
        active_row.pack(fill=tk.X, padx=6, pady=(6, 6))
        tk.Label(active_row, text="Active color:").pack(side=tk.LEFT)
        app._active_color_var = tk.StringVar(value=str(app.active_color))
        tk.Label(active_row, textvariable=app._active_color_var).pack(side=tk.LEFT, padx=(6, 0))

        palette = tk.Frame(palette_box)
        palette.pack(fill=tk.X, padx=6, pady=(0, 6))
        for idx, tk_color in sorted(app.color_map.items(), key=lambda kv: kv[0]):
            btn = tk.Button(
                palette,
                text=str(idx),
                width=4,
                bg=tk_color,
                command=lambda i=idx: app.set_active_color(i),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)

        # Eyedropper
        drop_box = tk.LabelFrame(parent, text="Tools")
        drop_box.pack(fill=tk.X, padx=6, pady=(0, 8))

        app._eyedropper_var = tk.StringVar(value="OFF")
        drop_row = tk.Frame(drop_box)
        drop_row.pack(fill=tk.X, padx=6, pady=(6, 6))
        tk.Label(drop_row, text="Eyedropper:").pack(side=tk.LEFT)
        tk.Label(drop_row, textvariable=app._eyedropper_var).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(drop_row, text="Toggle (E)", command=app.toggle_eyedropper).pack(side=tk.RIGHT)

        # Joint editor
        joint_box = tk.LabelFrame(parent, text="Joints")
        joint_box.pack(fill=tk.BOTH, expand=False, padx=6, pady=(0, 8))

        app._current_joint_var = tk.StringVar(value=app.current_joint_name())
        cur_row = tk.Frame(joint_box)
        cur_row.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(cur_row, text="Current (right-click sets):").pack(side=tk.LEFT)
        tk.Label(cur_row, textvariable=app._current_joint_var).pack(side=tk.LEFT, padx=(6, 0))

        btn_row = tk.Frame(joint_box)
        btn_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Button(btn_row, text="Prev  [", command=app.prev_joint).pack(side=tk.LEFT)
        tk.Button(btn_row, text="Next  ]", command=app.next_joint).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(btn_row, text="Clear joints", command=app.clear_joints).pack(side=tk.RIGHT)

        tk.Label(joint_box, text="Positions:").pack(anchor="w", padx=6)
        app._joint_listbox = tk.Listbox(joint_box, height=8, width=28)
        app._joint_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
        app._joint_listbox.bind("<<ListboxSelect>>", app.on_joint_select)

        # Frame I/O
        io_box = tk.LabelFrame(parent, text="Frame Editor")
        io_box.pack(fill=tk.X, padx=6, pady=(0, 8))
        tk.Button(io_box, text="Load Model/Template...", command=app.load_frame_dialog).pack(
            fill=tk.X, padx=6, pady=(6, 2)
        )
        tk.Button(io_box, text="Save Frame...", command=app.save_frame_dialog).pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Label(
            io_box,
            text="Paint black pixels, then right-click to place joints.",
            justify=tk.LEFT,
            wraplength=210,
        ).pack(anchor="w", padx=6, pady=(0, 6))

    def on_enter(self, app):
        app.set_joint_overlay_visible(True)
        app.enable_joint_editing(True)
        app.eyedropper_enabled = False
        if hasattr(app, "_eyedropper_var"):
            app._eyedropper_var.set("OFF")
        app._refresh_joint_list()

    def on_leave(self, app):
        app.eyedropper_enabled = False

