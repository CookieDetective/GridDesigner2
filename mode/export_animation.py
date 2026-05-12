import tkinter as tk

from .base import BaseMode


class ExportAnimationMode(BaseMode):
    mode_id = "export_animation"
    label = "Export"

    def build(self, app, parent):
        super().build(app, parent)

        box = tk.LabelFrame(parent, text="Export")
        box.pack(fill=tk.X, padx=6, pady=(0, 8))
        tk.Button(box, text="Export Animation JSON...", command=app.export_animation_dialog).pack(
            fill=tk.X, padx=6, pady=(6, 4)
        )
        tk.Label(
            box,
            text="If filename does not contain 'animation', '_animation' is appended.",
            wraplength=210,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=6, pady=(0, 6))

    def on_enter(self, app):
        app.set_joint_overlay_visible(False)
        app.enable_joint_editing(False)
        app.stop_playback()

    def on_leave(self, app):
        app._store_current_frame()

