from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RDLRect:
    left: float
    top: float
    width: float
    height: float

    def to_rdl(self) -> dict[str, str]:
        return {
            "Left": f"{self.left:.4f}in",
            "Top": f"{self.top:.4f}in",
            "Width": f"{self.width:.4f}in",
            "Height": f"{self.height:.4f}in",
        }


@dataclass
class RDLPage:
    name: str
    break_location: str
    visuals: list


class RDLLayoutBuilder:
    PAGE_WIDTH = 11.0
    PAGE_HEIGHT = 8.5
    MARGIN = 0.25
    HEADER_HEIGHT = 0.5

    def compute_layout(self, dashboard, visuals: list) -> dict[str, RDLRect]:
        available_width = self.PAGE_WIDTH - 2 * self.MARGIN
        available_height = self.PAGE_HEIGHT - 2 * self.MARGIN - self.HEADER_HEIGHT

        n_visuals = len(visuals)
        if n_visuals == 0:
            return {}

        cols = min(3, n_visuals)
        rows = (n_visuals + cols - 1) // cols

        cell_width = available_width / cols
        cell_height = available_height / rows

        layout: dict[str, RDLRect] = {}
        for idx, visual in enumerate(visuals):
            col_idx = idx % cols
            row_idx = idx // cols
            layout[visual.id] = RDLRect(
                left=self.MARGIN + col_idx * cell_width,
                top=self.MARGIN + self.HEADER_HEIGHT + row_idx * cell_height,
                width=cell_width - 0.1,
                height=cell_height - 0.1,
            )

        return layout

    def compute_pagination(self, pages: list) -> list[RDLPage]:
        rdl_pages: list[RDLPage] = []
        for idx, page in enumerate(pages):
            break_location = "End" if idx < len(pages) - 1 else "None"
            rdl_pages.append(
                RDLPage(
                    name=page.name,
                    break_location=break_location,
                    visuals=page.visuals,
                )
            )
        return rdl_pages
