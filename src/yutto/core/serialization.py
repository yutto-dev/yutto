from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yutto.core.result import ResolvedItem


def listing_item_to_wire(item: ResolvedItem) -> dict[str, object]:
    """Project one canonical listing snapshot onto the stable JSON-RPC v1 shape."""
    return item.model_dump(mode="json")
