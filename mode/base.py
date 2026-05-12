import tkinter as tk


class BaseMode:
    mode_id = "base"
    label = "Base"

    def build(self, app, parent):
        """Create mode-specific controls into parent."""
        self._build_offset_controls(app, parent)

    def _build_offset_controls(self, app, parent):
        """Shared world translation controls."""
        off_box = tk.LabelFrame(parent, text="World translation")
        off_box.pack(fill=tk.X, padx=6, pady=(0, 8))

        app._offset_x_var = tk.IntVar(value=app.offset_x)
        app._offset_y_var = tk.IntVar(value=app.offset_y)

        ox_row = tk.Frame(off_box)
        ox_row.pack(fill=tk.X, padx=6, pady=(4, 2))
        tk.Label(ox_row, text="offset_x:").pack(side=tk.LEFT)
        tk.Spinbox(
            ox_row,
            from_=-999,
            to=999,
            width=6,
            textvariable=app._offset_x_var,
            command=app._sync_offset_from_ui,
        ).pack(side=tk.LEFT, padx=(6, 0))

        oy_row = tk.Frame(off_box)
        oy_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Label(oy_row, text="offset_y:").pack(side=tk.LEFT)
        tk.Spinbox(
            oy_row,
            from_=-999,
            to=999,
            width=6,
            textvariable=app._offset_y_var,
            command=app._sync_offset_from_ui,
        ).pack(side=tk.LEFT, padx=(6, 0))

    def on_enter(self, app):
        """Hook called when this mode becomes active."""

    def on_leave(self, app):
        """Hook called before switching away from this mode."""

