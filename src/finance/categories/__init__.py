"""Category catalog use cases."""

from finance.categories.service import (
    CategoryAlreadyExists,
    CategoryInUse,
    CategoryNotFound,
    CategoryValidationError,
    SystemCategoryDeletionForbidden,
    create_category,
    delete_category,
    list_categories,
    missing_system_category_names,
    seed_system_categories,
    update_category,
)

__all__ = [
    "CategoryAlreadyExists",
    "CategoryInUse",
    "CategoryNotFound",
    "CategoryValidationError",
    "SystemCategoryDeletionForbidden",
    "create_category",
    "delete_category",
    "list_categories",
    "missing_system_category_names",
    "seed_system_categories",
    "update_category",
]
