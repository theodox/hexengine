from __future__ import annotations

import logging
from collections.abc import Iterable

from ..document import js
from ..hexes.shapes import rectangle_from_corners
from ..hexes.types import Cartesian, Hex
from ..state.game_state import LocationState
from .layout import (
    HexLayout,
    fit_hex_grid_canvas,
    fit_hex_grid_canvas_for_hexes,
    iter_map_grid_hex_col_rows,
)


class CanvasLayer:
    """
    The background bitmap canvas for drawing hexagons.
    """

    def __init__(
        self,
        canvas_element: str,
        hex_layout: HexLayout,
        hex_color: str,
        hex_stroke: int,
        *,
        skip_initial_grid: bool = False,
    ):
        self._canvas = canvas_element
        self._context = self._canvas.getContext("2d")
        self._hex_layout = hex_layout
        self.hex_color = hex_color
        self.hex_stroke = hex_stroke
        # (columns, rows, origin_col, origin_row) odd-q; or None = size canvas from CSS box
        self._scenario_grid: tuple[int, int, int, int] | None = None
        #: When set, canvas size and grid lines use this list (sparse map), not full rect.
        self._grid_hex_list: list[Hex] | None = None
        self._fixed_canvas_w: int | None = None
        self._fixed_canvas_h: int | None = None

        if not skip_initial_grid:
            self._sync_canvas_resolution_and_draw_grid()

    @property
    def canvas(self) -> js.HTMLCanvasElement:
        return self._canvas

    @property
    def context(self) -> js.CanvasRenderingContext2D:
        return self._context

    def draw_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        self._context.beginPath()
        self._context.strokeStyle = stroke
        self._context.lineWidth = stroke_width
        self._context.moveTo(x1, y1)
        self._context.lineTo(x2, y2)
        self._context.stroke()
        self._context.closePath()

    def draw_hex(
        self,
        hex: Hex,
        fill: str = "white",
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        corners = self._hex_layout.hex_corners(hex)
        if len(corners) < 3:
            return
        ctx = self._context
        ctx.beginPath()
        ctx.moveTo(corners[0][0], corners[0][1])
        for x, y in corners[1:]:
            ctx.lineTo(x, y)
        ctx.closePath()
        ctx.strokeStyle = stroke
        ctx.lineWidth = stroke_width
        ctx.fillStyle = fill
        ctx.fill()
        ctx.stroke()

    def draw_hexes(
        self,
        hexes: Iterable[Hex],
        fill: str = "white",
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        for hex in hexes:
            self.draw_hex(hex, fill=fill, stroke=stroke, stroke_width=stroke_width)

    def draw_hex_rect(
        self,
        top_left: Cartesian,
        bottom_right: Cartesian,
        fill: str = "white",
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        rect = rectangle_from_corners(top_left, bottom_right)
        for hex in rect:
            self.draw_hex(hex, fill=fill, stroke=stroke, stroke_width=stroke_width)

    def set_scenario_grid(
        self,
        spec: tuple[int, int, int, int] | None,
        hex_size: float,
        hex_margin: float,
        hex_stroke: int,
        *,
        grid_hexes: Iterable[Hex] | None = None,
    ) -> None:
        """
        Switch between scenario-sized grid and legacy CSS-fitted grid.

        `spec` is (columns, rows, origin_col, origin_row) odd-q anchors, or None for legacy.
        When `grid_hexes` is non-empty, canvas bounds and drawn grid use that set only
        (sparse maps). Otherwise `spec` selects the full `columns` × `rows` grid.
        """
        self.hex_stroke = int(hex_stroke)
        gh = list(grid_hexes) if grid_hexes is not None else []
        self._grid_hex_list = gh if gh else None
        self._scenario_grid = spec
        if self._grid_hex_list is not None:
            layout, cw, ch = fit_hex_grid_canvas_for_hexes(
                hex_size,
                self._grid_hex_list,
                margin_pad=hex_margin,
                stroke_pad=max(2.0, float(hex_stroke)),
            )
            self._hex_layout = layout
            self._fixed_canvas_w = cw
            self._fixed_canvas_h = ch
        elif spec is not None:
            cols, rows, oi, oj = spec
            layout, cw, ch = fit_hex_grid_canvas(
                hex_size,
                cols,
                rows,
                origin_col=oi,
                origin_row=oj,
                margin_pad=hex_margin,
                stroke_pad=max(2.0, float(hex_stroke)),
            )
            self._hex_layout = layout
            self._fixed_canvas_w = cw
            self._fixed_canvas_h = ch
        else:
            self._fixed_canvas_w = None
            self._fixed_canvas_h = None
            self._hex_layout = HexLayout(
                hex_size,
                hex_size + hex_margin,
                hex_size + hex_margin,
            )
        self._sync_canvas_resolution_and_draw_grid()

    def _sync_canvas_resolution_and_draw_grid(self) -> None:
        if self._grid_hex_list is not None:
            assert self._fixed_canvas_w is not None and self._fixed_canvas_h is not None
            self._canvas.width = self._fixed_canvas_w
            self._canvas.height = self._fixed_canvas_h
            self._canvas.style.width = f"{self._fixed_canvas_w}px"
            self._canvas.style.height = f"{self._fixed_canvas_h}px"
            if self._scenario_grid is not None:
                cols, rows, oi, oj = self._scenario_grid
                logging.getLogger().info(
                    "Scenario grid canvas (explicit %d hexes, rect %dx%d @ col=%s row=%s): %dx%d px",
                    len(self._grid_hex_list),
                    cols,
                    rows,
                    oi,
                    oj,
                    self._fixed_canvas_w,
                    self._fixed_canvas_h,
                )
            else:
                logging.getLogger().info(
                    "Scenario grid canvas (explicit %d hexes): %dx%d px",
                    len(self._grid_hex_list),
                    self._fixed_canvas_w,
                    self._fixed_canvas_h,
                )
        elif self._scenario_grid is not None:
            assert self._fixed_canvas_w is not None and self._fixed_canvas_h is not None
            self._canvas.width = self._fixed_canvas_w
            self._canvas.height = self._fixed_canvas_h
            self._canvas.style.width = f"{self._fixed_canvas_w}px"
            self._canvas.style.height = f"{self._fixed_canvas_h}px"
            cols, rows, oi, oj = self._scenario_grid
            logging.getLogger().info(
                "Scenario grid canvas: %dx%d hexes (origin col=%s row=%s), %dx%d px",
                cols,
                rows,
                oi,
                oj,
                self._fixed_canvas_w,
                self._fixed_canvas_h,
            )
        else:
            rect = self._canvas.getBoundingClientRect()
            self._canvas.width = int(rect.width)
            self._canvas.height = int(rect.height)
            hs = int(self._hex_layout.size)
            w = (self._canvas.width - (self._hex_layout.origin_x * 2)) // max(hs, 1)
            h = (self._canvas.height - (self._hex_layout.origin_y * 2)) // max(hs, 1)
            logging.getLogger().info(
                "Legacy canvas: %dx%d hexes (approx), %dx%d px",
                w,
                h,
                self._canvas.width,
                self._canvas.height,
            )

        self._context.clearRect(0, 0, self._canvas.width, self._canvas.height)

        if self._grid_hex_list is not None:
            for hx in self._grid_hex_list:
                self.draw_hex(
                    hx,
                    fill="#FFFFFF10",
                    stroke=self.hex_color,
                    stroke_width=self.hex_stroke,
                )
        elif self._scenario_grid is not None:
            cols, rows, oi, oj = self._scenario_grid
            for hx in iter_map_grid_hex_col_rows(
                cols, rows, origin_col=oi, origin_row=oj
            ):
                self.draw_hex(
                    hx,
                    fill="#FFFFFF10",
                    stroke=self.hex_color,
                    stroke_width=self.hex_stroke,
                )
        else:
            hs = int(self._hex_layout.size)
            w = (self._canvas.width - (self._hex_layout.origin_x * 2)) // max(hs, 1)
            h = (self._canvas.height - (self._hex_layout.origin_y * 2)) // max(hs, 1)
            start = Hex.from_cartesian(Cartesian(0, 0))
            br = Hex.from_cartesian(Cartesian(w, h))
            self.draw_hex_rect(
                start,
                br,
                fill="#FFFFFF10",
                stroke=self.hex_color,
                stroke_width=self.hex_stroke,
            )

    def redraw(self) -> None:
        """
        Redraw the canvas layer after a resize.
        Legacy mode: canvas follows CSS box. Scenario mode: fixed pixel size from grid.
        """
        self._sync_canvas_resolution_and_draw_grid()


class TerrainOverlayLayer(CanvasLayer):
    """Semi-transparent terrain tint between the grid and unit SVGs."""

    def __init__(
        self,
        canvas: js.HTMLCanvasElement,
        hex_layout: HexLayout,
        *,
        visible: bool = True,
        line_color: str = "#33443344",
        line_width: int = 2,
    ) -> None:
        super().__init__(
            canvas,
            hex_layout,
            "#000000",
            1,
            skip_initial_grid=True,
        )
        self._line_color = line_color
        self._line_width = int(line_width)
        self._visible = visible
        self._apply_visibility_style()

    def set_layout(self, layout: HexLayout) -> None:
        self._hex_layout = layout

    def set_line_style(self, color: str, width: int) -> None:
        self._line_color = str(color)
        self._line_width = int(width)

    @property
    def visible(self) -> bool:
        return self._visible

    def set_visible(self, visible: bool) -> None:
        self._visible = visible
        self._apply_visibility_style()

    def _apply_visibility_style(self) -> None:
        self._canvas.style.display = "" if self._visible else "none"

    def sync_size(self, width: int, height: int) -> None:
        """Match the main grid canvas pixel dimensions."""
        self._canvas.width = width
        self._canvas.height = height
        self._canvas.style.width = f"{width}px"
        self._canvas.style.height = f"{height}px"

    def redraw(self) -> None:
        """Do not run the base grid pass; terrain is painted via `redraw_terrain`."""
        pass

    def redraw_terrain(self, locations: Iterable[LocationState]) -> None:
        """Repaint tint + outline from state; use `display` style to hide without losing pixels."""
        ctx = self._context
        w, h = int(self._canvas.width), int(self._canvas.height)
        ctx.clearRect(0, 0, w, h)
        for loc in locations:
            hc = loc.hex_color
            if not hc:
                continue
            self.draw_hex(
                loc.position,
                fill=str(hc),
                stroke=self._line_color,
                stroke_width=self._line_width,
            )
