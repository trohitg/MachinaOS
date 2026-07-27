"""Apify Actor — Wave 11.D.8 inlined.

Runs Apify actors (Instagram, TikTok, X, LinkedIn, Google, Crawler) via
the official apify-client SDK. Quick-input helpers merge into the raw
``actorInput`` JSON for common actors.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from core.logging import get_logger
from services.plugin import ActionNode, NodeContext, NodeUserError, Operation, TaskQueue

from .._credentials import ApifyCredential
from ._inputs import build_actor_input
from ._params import ApifyActorParams

logger = get_logger(__name__)


async def _get_apify_client():
    """Return an authenticated Apify client, or None if no token saved."""
    from apify_client import ApifyClientAsync  # lazy — optional dep

    from services.plugin.deps import get_auth_service

    auth_service = get_auth_service()
    api_token = await auth_service.get_api_key("apify", "default")
    if not api_token:
        return None
    return ApifyClientAsync(api_token)


async def validate_apify_token(api_token: str) -> dict[str, Any]:
    """Validate an Apify API token by fetching /users/me.

    Used by the websocket ``validate_apify_key`` handler and by the
    Credentials modal. Lives on the plugin so there's no handler-file
    ghost left behind after Wave 11.D.8.
    """
    try:
        from apify_client import ApifyClientAsync  # lazy — optional dep

        client = ApifyClientAsync(api_token)
        user_info = await client.user("me").get()
        if not user_info:
            return {"valid": False, "error": "Could not fetch user info"}
        plan = user_info.get("plan")
        return {
            "valid": True,
            "username": user_info.get("username", ""),
            "email": user_info.get("email", ""),
            "plan": plan.get("id", "free") if isinstance(plan, dict) else "free",
        }
    except Exception as error:  # noqa: BLE001 - credential probes must return transport errors
        logger.error(f"[Apify] Token validation error: {error}")
        msg = str(error)
        if "401" in msg or "Unauthorized" in msg:
            return {"valid": False, "error": "Invalid API token"}
        return {"valid": False, "error": msg}


class ApifyActorOutput(BaseModel):
    run_id: str | None = None
    actor_id: str | None = None
    status: str | None = None
    items: list[dict[str, Any]] | None = None
    item_count: int | None = None
    dataset_id: str | None = None
    compute_units: float | None = None
    started_at: str | None = None
    finished_at: str | None = None

    model_config = ConfigDict(extra="allow")


class ApifyActorNode(ActionNode):
    type = "apifyActor"
    display_name = "Apify Actor"
    subtitle = "Web Scraper"
    group = ("api", "scraper", "tool")
    description = "Run Apify actors for Instagram, TikTok, X, LinkedIn, etc."
    component_kind = "square"
    tool_name = "apify_actor"
    tool_description = (
        "Run Apify actors (pre-built web scrapers) for Instagram, TikTok, X posts and "
        "audiences, LinkedIn, Facebook, YouTube, Google Search, Google Maps, and websites. "
        "Specify actor_id and actor_input (JSON)."
    )
    handles = (
        {"name": "input-main", "kind": "input", "position": "left", "label": "Input", "role": "main"},
        {"name": "output-main", "kind": "output", "position": "right", "label": "Output", "role": "main"},
    )
    annotations: ClassVar[dict[str, bool]] = {
        "destructive": False,
        "readonly": True,
        "open_world": True,
    }
    credentials = (ApifyCredential,)
    task_queue = TaskQueue.REST_API
    usable_as_tool = True

    Params = ApifyActorParams
    Output = ApifyActorOutput

    @Operation("run")
    async def run(self, ctx: NodeContext, params: ApifyActorParams) -> ApifyActorOutput:
        client = await _get_apify_client()
        if not client:
            raise NodeUserError(
                "Apify API token not configured. Please add your token in Credentials.",
            )

        actor_id = params.actor_id
        if actor_id == "custom":
            actor_id = params.custom_actor_id
        if not actor_id:
            raise NodeUserError("Actor ID is required")

        actor_input = build_actor_input(params.model_dump())
        timeout_secs = params.timeout
        max_results = params.max_results
        memory_mbytes = int(params.memory)

        logger.info(
            f"[Apify] Running actor {actor_id} timeout={timeout_secs}s memory={memory_mbytes}MB",
        )
        call_options: dict[str, Any] = {
            "run_input": actor_input,
            "run_timeout": timedelta(seconds=timeout_secs),
            "memory_mbytes": memory_mbytes,
        }
        if params.max_total_charge_usd is not None:
            call_options["max_total_charge_usd"] = Decimal(str(params.max_total_charge_usd))

        run_info = await client.actor(actor_id).call(
            **call_options,
        )

        if run_info is None:
            raise NodeUserError("Actor run failed - no result returned")

        status = run_info.get("status", "UNKNOWN")
        run_id = run_info.get("id", "")
        dataset_id = run_info.get("defaultDatasetId", "")

        if status == "FAILED":
            raise NodeUserError(run_info.get("errorMessage", "Actor run failed"))
        if status == "TIMED-OUT":
            raise NodeUserError("Actor timed out. Try increasing the timeout.")
        if status == "ABORTED":
            raise NodeUserError("Actor run was aborted")

        items: list[dict[str, Any]] = []
        if dataset_id:
            listing = await client.dataset(dataset_id).list_items(limit=max_results)
            items = listing.items if listing else []
            logger.info(f"[Apify] Actor {actor_id} completed: {len(items)} items")

        return ApifyActorOutput(
            run_id=run_id,
            actor_id=actor_id,
            status=status,
            items=items,
            item_count=len(items),
            dataset_id=dataset_id,
            compute_units=run_info.get("usageTotalUsd", 0),
            started_at=run_info.get("startedAt", ""),
            finished_at=run_info.get("finishedAt", ""),
        )
