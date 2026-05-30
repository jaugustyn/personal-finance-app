"""Portfolio service facade used by FastAPI routers."""
from finance import assets as asset_quotes
from finance.assets.flow import sankey
from finance.assets.portfolio import (
    AssetView,
    PortfolioSummary,
    create_asset,
    delete_asset,
    list_assets,
    patch_asset,
    portfolio_summary,
    to_asset_view,
)
from finance.assets.snapshots import (
    RefreshResult,
    history,
    latest_snapshot,
    refresh_all,
    refresh_one,
)

__all__ = [
    "AssetView",
    "PortfolioSummary",
    "RefreshResult",
    "asset_quotes",
    "create_asset",
    "delete_asset",
    "history",
    "latest_snapshot",
    "list_assets",
    "patch_asset",
    "portfolio_summary",
    "refresh_all",
    "refresh_one",
    "sankey",
    "to_asset_view",
]
