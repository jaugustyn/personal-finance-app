"""APScheduler-based periodic jobs (in-process).

Currently registers a daily classifier retrain. Disabled unless
SCHEDULER_ENABLED=true to keep tests / dev runs lightweight.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.api.routers.ml import _retrain_job
from finance.config import get_settings
from finance.observability import get_logger

logger = get_logger("scheduler")

_scheduler: BackgroundScheduler | None = None


def start() -> BackgroundScheduler | None:
    global _scheduler
    s = get_settings()
    if not s.scheduler_enabled:
        logger.info("scheduler_disabled")
        return None
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        _retrain_job,
        kwargs={"estimator": s.retrain_estimator},
        trigger=CronTrigger(hour=s.retrain_cron_hour, minute=s.retrain_cron_minute),
        id="retrain_classifier",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "scheduler_started",
        retrain_cron=f"{s.retrain_cron_hour:02d}:{s.retrain_cron_minute:02d} UTC",
        estimator=s.retrain_estimator,
    )
    return sched


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler_stopped")
