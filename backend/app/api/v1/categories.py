from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.schemas.activity import ACTIVITY_CATEGORIES, ActivityCategoryRead

router = APIRouter(prefix="/categories", tags=["Reference Data"])


@router.get(
    "",
    response_model=list[ActivityCategoryRead],
    summary="List activity categories",
    description=(
        "Return every canonical activity category. Each item contains `id`, the UUID "
        "to send as `ActivityCreate.category_id`; `name`, the human-readable label; "
        "and `slug`, the stable machine-readable name. Categories are fixed reference "
        "data in this milestone rather than rows in a separate database table."
    ),
    response_description="All supported activity categories in stable display order.",
)
def list_categories() -> list[ActivityCategoryRead]:
    return [
        ActivityCategoryRead(
            id=UUID(category.id.value),
            name=category.name,
            slug=category.slug,
        )
        for category in ACTIVITY_CATEGORIES.values()
    ]
