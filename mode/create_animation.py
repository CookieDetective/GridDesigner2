import tkinter as tk

from .base import BaseMode


class CreateAnimationMode(BaseMode):
    mode_id = "create_animation"
    label = "Create Animation"

    def build(self, app, parent):
        super().build(app, parent)

        box = tk.LabelFrame(parent, text="Create Animation")
        box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        nav_row = tk.Frame(box)
        nav_row.pack(fill=tk.X, padx=6, pady=(6, 4))
        tk.Button(nav_row, text="Prev frame", command=app.prev_frame).pack(side=tk.LEFT)
        tk.Button(nav_row, text="Next frame", command=app.next_frame).pack(side=tk.LEFT, padx=(6, 0))

        edit_row = tk.Frame(box)
        edit_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(edit_row, text="Add blank", command=app.add_blank_frame).pack(side=tk.LEFT)
        tk.Button(edit_row, text="Duplicate", command=app.duplicate_frame).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(edit_row, text="Delete", command=app.delete_frame).pack(side=tk.RIGHT)

        tk.Label(box, text="Frames:").pack(anchor="w", padx=6)
        app._timeline_listbox = tk.Listbox(box, height=7)
        app._timeline_listbox.pack(fill=tk.X, padx=6, pady=(2, 6))
        app._timeline_listbox.bind("<<ListboxSelect>>", app.on_timeline_select)

        dur_row = tk.Frame(box)
        dur_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Label(dur_row, text="Duration (ms):").pack(side=tk.LEFT)
        app._frame_duration_var = tk.IntVar(value=app.DEFAULT_FRAME_DURATION_MS)
        tk.Spinbox(
            dur_row,
            from_=1,
            to=99999,
            width=8,
            textvariable=app._frame_duration_var,
            command=app.on_duration_changed,
        ).pack(side=tk.LEFT, padx=(6, 0))

        play_row = tk.Frame(box)
        play_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(play_row, text="Play", command=app.play_animation).pack(side=tk.LEFT)
        tk.Button(play_row, text="Pause", command=app.pause_animation).pack(side=tk.LEFT, padx=(6, 0))
        tk.Checkbutton(play_row, text="Loop animation", variable=app._loop_animation_var).pack(side=tk.LEFT, padx=(8, 0))

        frame_io_row = tk.Frame(box)
        frame_io_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(frame_io_row, text="Load Frame...", command=app.load_frame_dialog).pack(side=tk.LEFT)
        tk.Button(frame_io_row, text="Save Frame...", command=app.save_frame_dialog).pack(side=tk.RIGHT)

        anim_io_row = tk.Frame(box)
        anim_io_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Button(anim_io_row, text="Load Animation...", command=app.load_animation_dialog).pack(side=tk.LEFT)
        tk.Button(anim_io_row, text="Save Animation...", command=app.save_animation_dialog).pack(side=tk.RIGHT)

        export_row = tk.Frame(box)
        export_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(export_row, text="Export This Animation...", command=app.export_animation_dialog).pack(side=tk.LEFT)

        app._refresh_timeline_ui()

    def on_enter(self, app):
        app.set_joint_overlay_visible(False)
        app.enable_joint_editing(False)
        app.stop_playback()

    def on_leave(self, app):
        app._store_current_frame()






