from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from app.core.config import Settings
from app.db.session import get_session_factory
from app.services.participation_lifecycle_service import (
    run_participation_lifecycle_sweep,
)

logger = logging.getLogger(__name__)


async def run_lifecycle_worker(
    stop: asyncio.Event, *, sweep: Callable, interval_seconds: float
) -> None:
    """Run immediately and periodically; finish in-flight DB work on clean stop."""
    while not stop.is_set():
        try:
            # Each sweep owns its synchronous sessions within this thread.
            await asyncio.to_thread(sweep)
        except Exception:
            logger.exception("Participation lifecycle sweep failed; worker will retry")
        if not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


def lifecycle_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = asyncio.Event()
        task = None
        if settings.participation_lifecycle_worker_enabled:
            sweep = partial(
                run_participation_lifecycle_sweep,
                get_session_factory(settings.database_url),
            )
            task = asyncio.create_task(
                run_lifecycle_worker(
                    stop,
                    sweep=sweep,
                    interval_seconds=settings.participation_lifecycle_sweep_interval_seconds,
                ),
                name="participation-lifecycle",
            )
        app.state.participation_lifecycle_task = task
        try:
            yield
        finally:
            stop.set()
            if task is not None:
                # Cooperative stop avoids abandoning a to_thread transaction.
                await task

    return lifespan
