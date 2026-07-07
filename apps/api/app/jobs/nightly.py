import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def run() -> None:
    # Imported here, not at module level: importing content_gen loads Settings
    # (DATABASE_URL etc.), and the skip guard must work without any env config.
    from app.jobs import content_gen

    shared_pool = await content_gen.generate_shared_pool(count=10)
    logger.info("nightly_shared_pool_done", extra={"result": shared_pool})
    daily = await content_gen.run_daily(batch_size=25)
    logger.info("nightly_enrichment_done", extra={"result": daily})
    personalized = await content_gen.generate_personalized_for_all(count=5)
    logger.info("nightly_personalized_done", extra={"result": personalized})


def should_run() -> bool:
    return (
        os.environ.get("RAILWAY_ENVIRONMENT_NAME") == "production"
        or os.environ.get("NIGHTLY_FORCE") == "1"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if should_run():
        asyncio.run(run())
    else:
        logger.info("nightly_skipped_non_production_environment")
