import tkinter as tk


class InteractiveGrid:
    """
    Interactive grid editor with:
      - Click + drag paint
      - Optional configurable sidebar (palette + tools)
      - Eyedropper tool (pick cell color)
      - Mouse wheel zoom toward pointer
      - Auto-centering when zoomed out

    Uses a scrollable Canvas with an inner "world" coordinate system:
      world size = grid_width * cell_size by grid_height * cell_size
    """

    def __init__(
        self,
        root,
        grid_width=120,
        grid_height=72,
        cell_size=10,
        default_color=0,
        *,
        show_sidebar=True,
        sidebar_width=240,
        color_map=None,
        sidebar_builder=None,
        zoom_min_cell_size=2,
        zoom_max_cell_size=60,
        zoom_step=1,
    ):
        self.root = root

        # Grid geometry/state
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.cell_size = cell_size
        self.default_color = default_color

        # Active paint color
        self.active_color = 1 if default_color == 0 else 0

        # Tool state
        self.eyedropper_enabled = False  # when True: click picks a color instead of painting

        # Zoom configuration
        self.zoom_min_cell_size = zoom_min_cell_size
        self.zoom_max_cell_size = zoom_max_cell_size
        self.zoom_step = zoom_step

        # Map color-index -> Tk color string
        self.color_map = color_map or {0: "white", 1: "black", 2: "red", 3: "green", 4: "blue"}

        # 2D grid values
        self.grid = [[self.default_color for _ in range(grid_width)] for _ in range(grid_height)]

        # ---- Layout: sidebar + canvas area ----
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar_frame = None
        if show_sidebar:
            self.sidebar_frame = tk.Frame(self.main_frame, width=sidebar_width)
            self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.sidebar_frame.pack_propagate(False)

        # Canvas container
        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbars (needed for pointer-anchored zoom)
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        # Ensure scrollregion is set
        self._update_scrollregion()

        # Sidebar content
        if self.sidebar_frame is not None:
            if sidebar_builder is not None:
                sidebar_builder(self.sidebar_frame, self)
            else:
                self.build_sidebar(self.sidebar_frame)

        # Drag paint state
        self._dragging = False
        self._drag_value = None
        self._last_drag_cell = None

        # ---- Bindings ----
        # Drawing
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Zoom: Windows/macOS
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        # Zoom: Linux
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)

        # Keyboard tools
        # (bind on root so it works even if focus changes)
        self.root.bind("<KeyPress-e>", self.toggle_eyedropper)
        self.root.bind("<KeyPress-E>", self.toggle_eyedropper)

        # Redraw on resize so centering can re-apply correctly
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Initial draw
        self.draw_grid()
        self._auto_center_if_needed()

    # -------------------------
    # Sidebar extension points
    # -------------------------
    def build_sidebar(self, parent):
        """
        Default sidebar. Subclasses can override and call super() to keep these tools.
        """
        title = tk.Label(parent, text="Tools", font=("TkDefaultFont", 12, "bold"))
        title.pack(anchor="w", padx=8, pady=(8, 4))

        # Active color indicator
        self._active_color_var = tk.StringVar(value=str(self.active_color))
        active_row = tk.Frame(parent)
        active_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(active_row, text="Active:").pack(side=tk.LEFT)
        tk.Label(active_row, textvariable=self._active_color_var).pack(side=tk.LEFT, padx=(6, 0))

        # Eyedropper indicator + button
        self._eyedropper_var = tk.StringVar(value="OFF")
        drop_row = tk.Frame(parent)
        drop_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(drop_row, text="Eyedropper:").pack(side=tk.LEFT)
        tk.Label(drop_row, textvariable=self._eyedropper_var).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(drop_row, text="Toggle (E)", command=self.toggle_eyedropper).pack(side=tk.RIGHT)

        tk.Label(parent, text="Palette:").pack(anchor="w", padx=8)
        palette = tk.Frame(parent)
        palette.pack(fill=tk.X, padx=8, pady=(4, 8))

        for idx, tk_color in sorted(self.color_map.items(), key=lambda kv: kv[0]):
            btn = tk.Button(
                palette,
                text=str(idx),
                width=4,
                bg=tk_color,
                command=lambda i=idx: self.set_active_color(i),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)

        # Zoom info
        tk.Label(parent, text="Zoom: mouse wheel over canvas").pack(anchor="w", padx=8, pady=(10, 0))
        self._zoom_label_var = tk.StringVar(value=f"Cell size: {self.cell_size}px")
        tk.Label(parent, textvariable=self._zoom_label_var).pack(anchor="w", padx=8, pady=(2, 0))

    def set_active_color(self, color_index: int):
        self.active_color = color_index
        if hasattr(self, "_active_color_var"):
            self._active_color_var.set(str(color_index))

    # -----------------
    # Eyedropper tool
    # -----------------
    def toggle_eyedropper(self, event=None):
        self.eyedropper_enabled = not self.eyedropper_enabled
        if hasattr(self, "_eyedropper_var"):
            self._eyedropper_var.set("ON" if self.eyedropper_enabled else "OFF")

    # -----------------------
    # Zoom / scrolling support
    # -----------------------
    def _world_size(self):
        return (self.grid_width * self.cell_size, self.grid_height * self.cell_size)

    def _update_scrollregion(self):
        """Set the scrollregion to match the world size."""
        w, h = self._world_size()
        self.canvas.configure(scrollregion=(0, 0, w, h))

    def _canvas_viewport_size(self):
        """Visible pixel size of the canvas widget."""
        return (max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))

    def _get_view_fractions(self):
        """Current x/y view fractions (0..1)."""
        x0, x1 = self.canvas.xview()
        y0, y1 = self.canvas.yview()
        return x0, x1, y0, y1

    def _set_view_by_world_anchor(self, world_x, world_y, canvas_px_x, canvas_px_y):
        """
        Adjust xview/yview so that the point (world_x, world_y) appears at
        (canvas_px_x, canvas_px_y) within the canvas.
        """
        world_w, world_h = self._world_size()
        view_w, view_h = self._canvas_viewport_size()

        # Target top-left world coords needed so anchor lands under cursor
        target_left = world_x - canvas_px_x
        target_top = world_y - canvas_px_y

        # Clamp
        max_left = max(0, world_w - view_w)
        max_top = max(0, world_h - view_h)
        target_left = max(0, min(max_left, target_left))
        target_top = max(0, min(max_top, target_top))

        # Convert to fractions for xview_moveto/yview_moveto
        if world_w > 0:
            self.canvas.xview_moveto(target_left / world_w)
        if world_h > 0:
            self.canvas.yview_moveto(target_top / world_h)

        # If content is smaller than viewport, center it instead
        self._auto_center_if_needed()

    def _auto_center_if_needed(self):
        """
        If the world is smaller than the visible canvas area, center it by
        setting xview/yview to 0.5 equivalent (implemented via moveto).
        """
        world_w, world_h = self._world_size()
        view_w, view_h = self._canvas_viewport_size()

        # When content is smaller than viewport, scrollbars don't really apply.
        # We emulate "centering" by moving view to 0, then shifting isn't possible
        # via xview/yview alone. The common Tk approach is to keep scrollregion and
        # just set view fractions to 0; visually, it will stick to top-left.
        #
        # So we do something slightly different: we create a canvas "origin offset"
        # by using canvas.scan_mark/scan_dragto is messy; instead we do centering
        # by drawing with an offset.
        #
        # For simplicity and reliability: we implement centering via draw offset.
        self._draw_offset_x = max(0, (view_w - world_w) // 2)
        self._draw_offset_y = max(0, (view_h - world_h) // 2)

        # Redraw so the offset is applied
        self.draw_grid()

    def _on_canvas_configure(self, event):
        # Recompute centering offset when the canvas widget resizes
        self._auto_center_if_needed()

    def on_mouse_wheel(self, event):
        """
        Zoom toward mouse pointer.
        Steps:
          1) Convert the mouse position to world coords under cursor (pre-zoom)
          2) Change cell_size
          3) Update scrollregion + redraw
          4) Reposition view so that same world point remains under cursor
        """
        direction = 0
        if hasattr(event, "delta") and event.delta:
            direction = 1 if event.delta > 0 else -1
        elif getattr(event, "num", None) == 4:
            direction = 1
        elif getattr(event, "num", None) == 5:
            direction = -1
        if direction == 0:
            return

        old_cell_size = self.cell_size
        new_cell_size = old_cell_size + direction * self.zoom_step
        new_cell_size = max(self.zoom_min_cell_size, min(self.zoom_max_cell_size, new_cell_size))
        if new_cell_size == old_cell_size:
            return

        # Mouse position inside canvas (pixels)
        cx = event.x
        cy = event.y

        # Convert canvas pixel -> world coordinate (pre-zoom)
        # canvasx/canvasy accounts for scrolling offset.
        world_x_before = self.canvas.canvasx(cx)
        world_y_before = self.canvas.canvasy(cy)

        # If we are currently centering via draw offsets, remove that to get real world coord
        ox = getattr(self, "_draw_offset_x", 0)
        oy = getattr(self, "_draw_offset_y", 0)
        world_x_before = max(0, world_x_before - ox)
        world_y_before = max(0, world_y_before - oy)

        # Change zoom
        self.cell_size = new_cell_size
        self._update_scrollregion()

        # Update zoom label if present
        if hasattr(self, "_zoom_label_var"):
            self._zoom_label_var.set(f"Cell size: {self.cell_size}px")

        # Redraw (will also re-center if needed)
        self.draw_grid()

        # The world coordinate we want to keep under cursor should scale with cell size change.
        # Since world coordinates are in pixels, we can scale by ratio:
        ratio = new_cell_size / old_cell_size
        world_x_after = world_x_before * ratio
        world_y_after = world_y_before * ratio

        # Re-anchor view
        self._set_view_by_world_anchor(world_x_after, world_y_after, cx, cy)

    # ----------------
    # Drawing routines
    # ----------------
    def draw_grid(self):
        """Redraw the entire grid."""
        self.canvas.delete("all")
        ox = getattr(self, "_draw_offset_x", 0)
        oy = getattr(self, "_draw_offset_y", 0)

        for row in range(self.grid_height):
            for col in range(self.grid_width):
                val = self.grid[row][col]
                tk_color = self.color_map.get(val, "magenta")

                x0 = ox + col * self.cell_size
                y0 = oy + row * self.cell_size
                x1 = x0 + self.cell_size
                y1 = y0 + self.cell_size

                self.canvas.create_rectangle(x0, y0, x1, y1, fill=tk_color, outline="gray")

    def draw_cell(self, row, col):
        """Simple cell redraw: for now we redraw whole grid (safe, easy)."""
        # You can optimize later by redrawing only one cell with offsets.
        self.draw_grid()

    # --------------------
    # Mouse -> cell helpers
    # --------------------
    def _event_to_cell(self, event):
        """
        Convert a mouse event to a grid cell (row,col), accounting for scrolling and centering offsets.
        """
        ox = getattr(self, "_draw_offset_x", 0)
        oy = getattr(self, "_draw_offset_y", 0)

        world_x = self.canvas.canvasx(event.x) - ox
        world_y = self.canvas.canvasy(event.y) - oy

        if world_x < 0 or world_y < 0:
            return None

        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)

        if 0 <= row < self.grid_height and 0 <= col < self.grid_width:
            return row, col
        return None

    def _set_cell(self, row, col, value):
        if self.grid[row][col] != value:
            self.grid[row][col] = value
            self.draw_cell(row, col)

    # -------------------------
    # Click / drag paint support
    # -------------------------
    def on_mouse_down(self, event):
        cell = self._event_to_cell(event)
        if not cell:
            return
        row, col = cell

        # Eyedropper mode: pick color and exit eyedropper
        if self.eyedropper_enabled:
            picked = self.grid[row][col]
            self.set_active_color(picked)
            self.eyedropper_enabled = False
            if hasattr(self, "_eyedropper_var"):
                self._eyedropper_var.set("OFF")
            return

        # Paint mode
        self._dragging = True
        self._drag_value = self.active_color
        self._last_drag_cell = None

        self._set_cell(row, col, self._drag_value)
        self._last_drag_cell = (row, col)

    def on_mouse_drag(self, event):
        if not self._dragging:
            return
        cell = self._event_to_cell(event)
        if not cell:
            return
        if cell == self._last_drag_cell:
            return

        row, col = cell
        self._set_cell(row, col, self._drag_value)
        self._last_drag_cell = (row, col)

    def on_mouse_up(self, event):
        self._dragging = False
        self._drag_value = None
        self._last_drag_cell = None

    # -----------------
    # Existing utilities
    # -----------------
    def check_cordinates(self, x, y):
        return 0 <= x < self.grid_width and 0 <= y < self.grid_height

    def get_diff_cells(self):
        diffs = {}
        for r in range(self.grid_height):
            for c in range(self.grid_width):
                if self.grid[r][c] != self.default_color:
                    diffs[(r, c)] = self.grid[r][c]
        return diffs


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Interactive Grid (Eyedropper + Pointer Zoom)")

    app = InteractiveGrid(
        root,
        grid_width=120,
        grid_height=72,
        cell_size=10,
        default_color=0,
        show_sidebar=True,
        color_map={
            0: "white",
            1: "black",
            2: "red",
            3: "green",
            4: "blue",
        },
        zoom_min_cell_size=2,
        zoom_max_cell_size=60,
        zoom_step=1,
    )

    root.mainloop()