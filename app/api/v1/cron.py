from fastapi import APIRouter, BackgroundTasks, Header, status

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services.aggregator_service import DEFAULT_AREA, aggregate_area_benchmarks

router = APIRouter(prefix="/cron", tags=["cron"])


async def _run_benchmark_update(area_name: str) -> None:
    await aggregate_area_benchmarks(area_name)


def _verify_cron_key(provided_key: str | None) -> None:
    expected_key = get_settings().cron_api_key
    if not expected_key:
        raise AppError(
            "CRON_API_KEY_NOT_CONFIGURED",
            "CRON_API_KEY must be configured before using cron endpoints.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if provided_key != expected_key:
        raise AppError(
            "INVALID_CRON_API_KEY",
            "Invalid cron API key.",
            status.HTTP_401_UNAUTHORIZED,
        )


@router.post("/update-benchmarks", status_code=status.HTTP_202_ACCEPTED)
async def update_benchmarks(
    background_tasks: BackgroundTasks,
    area_name: str = DEFAULT_AREA,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str]:
    _verify_cron_key(x_api_key)
    background_tasks.add_task(_run_benchmark_update, area_name)
    return {"status": "accepted", "area_name": area_name}
