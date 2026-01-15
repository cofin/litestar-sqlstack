"""Job function registry for background tasks."""

from __future__ import annotations

import functools
import inspect
import zoneinfo
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, overload

import structlog

from sqlstack.utils.sync_tools import ensure_async_

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

# Generic type variables for decorator type preservation
P = ParamSpec("P")
R = TypeVar("R")

logger = structlog.get_logger()

# Global registries
_job_registry: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
_schedule_registry: dict[str, ScheduleConfig] = {}

# Cron parser constants
MIN_CRON_FIELDS = 5
MAX_CRON_FIELDS = 6
WEEKDAY_SUNDAY_ALT = 7  # Alternative representation for Sunday
MONTH_NAME_LENGTH = 2  # Minimum characters for month abbreviation
RANGE_PARTS_COUNT = 2  # Number of parts in a range expression (start-end)


class CronParser:
    """Feature-complete cron expression parser.

    Supports standard cron format: minute hour day month weekday [year]
    - minute: 0-59
    - hour: 0-23
    - day: 1-31
    - month: 1-12 or JAN-DEC
    - weekday: 0-7 (0 and 7 are Sunday) or SUN-SAT
    - year: 1970-2099 (optional)

    Special characters:
    - * : any value
    - ? : no specific value (for day/weekday when the other is specified)
    - , : value list separator (e.g., 1,3,5)
    - - : range of values (e.g., 1-5)
    - / : step values (e.g., */5 for every 5, 10-30/5 for every 5 between 10 and 30)

    Also supports:
    - @yearly, @annually : Run once a year (0 0 1 1 *)
    - @monthly : Run once a month (0 0 1 * *)
    - @weekly : Run once a week (0 0 * * 0)
    - @daily, @midnight : Run once a day (0 0 * * *)
    - @hourly : Run once an hour (0 * * * *)
    - @reboot : Run at startup (special handling required)
    """

    MONTHS = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }

    WEEKDAYS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}

    ALIASES = {
        "@yearly": "0 0 1 1 *",
        "@annually": "0 0 1 1 *",
        "@monthly": "0 0 1 * *",
        "@weekly": "0 0 * * 0",
        "@daily": "0 0 * * *",
        "@midnight": "0 0 * * *",
        "@hourly": "0 * * * *",
    }

    def __init__(self, cron_expr: str) -> None:
        """Initialize with a cron expression."""
        # Handle aliases
        if cron_expr.startswith("@"):
            if cron_expr == "@reboot":
                self.is_reboot = True
                self.cron_expr = cron_expr
                return
            if cron_expr in self.ALIASES:
                cron_expr = self.ALIASES[cron_expr]

        self.is_reboot = False
        self.cron_expr = cron_expr
        parts = cron_expr.split()

        if len(parts) < MIN_CRON_FIELDS or len(parts) > MAX_CRON_FIELDS:
            msg = f"invalid cron expression: {cron_expr} (expected {MIN_CRON_FIELDS} or {MAX_CRON_FIELDS} fields)"
            raise ValueError(msg)

        self.minute_pattern = parts[0]
        self.hour_pattern = parts[1]
        self.day_pattern = parts[2]
        self.month_pattern = parts[3]
        self.weekday_pattern = parts[4]
        self.year_pattern = parts[5] if len(parts) == MAX_CRON_FIELDS else "*"

        # Validate patterns
        self._validate_patterns()

    def _validate_patterns(self) -> None:
        """Validate that patterns are syntactically correct."""
        try:
            self._parse_field(self.minute_pattern, 0, 59, "minute")
            self._parse_field(self.hour_pattern, 0, 23, "hour")
            self._parse_field(self.day_pattern, 1, 31, "day")
            self._parse_field(self.month_pattern, 1, 12, "month")
            self._parse_field(self.weekday_pattern, 0, 7, "weekday")
            if self.year_pattern != "*":
                self._parse_field(self.year_pattern, 1970, 2099, "year")
        except (ValueError, IndexError, KeyError) as e:
            msg = f"invalid cron expression: {self.cron_expr}"
            raise ValueError(msg) from e

    def _parse_field(self, field: str, min_val: int, max_val: int, field_type: str) -> set[int]:
        """Parse a single cron field into a set of valid values."""
        if field == "?":
            # ? means "no specific value" - used for day/weekday conflicts
            if field_type not in {"day", "weekday"}:
                msg = "? can only be used in day or weekday fields"
                raise ValueError(msg)
            return set(range(min_val, max_val + 1))

        if field == "*":
            return set(range(min_val, max_val + 1))

        values: set[int] = set()

        # Handle comma-separated values
        for part in field.split(","):
            values.update(self._parse_single_part(part, min_val, max_val, field_type))

        return values

    def _parse_single_part(self, part: str, min_val: int, max_val: int, field_type: str) -> set[int]:
        """Parse a single part of a field (handles ranges, steps, special chars)."""
        values: set[int] = set()

        # Handle step values (*/n or n-m/s)
        if "/" in part:
            range_part, step_str = part.split("/")

            # Validate step value
            try:
                step = int(step_str)
            except ValueError as e:
                msg = f"invalid step value: {step_str}"
                raise ValueError(msg) from e

            if step <= 0:
                msg = f"step value must be positive: {step}"
                raise ValueError(msg)

            # Determine start and end values
            if range_part == "*":
                start_val, end_val = min_val, max_val
            elif "-" in range_part:
                start_val, end_val = self._parse_range(range_part, field_type)
                # Clamp to valid range
                start_val = max(start_val, min_val)
                end_val = min(end_val, max_val)
            else:
                start_val = self._parse_value(range_part, field_type)
                # Clamp to valid range
                start_val = max(start_val, min_val)
                end_val = max_val

            # Generate step values directly
            current = start_val
            while current <= end_val:
                values.add(current)
                current += step

        # Handle ranges (n-m)
        elif "-" in part:
            start, end = self._parse_range(part, field_type)
            values.update(range(max(start, min_val), min(end + 1, max_val + 1)))

        # Single value
        else:
            val = self._parse_value(part, field_type)
            if val == WEEKDAY_SUNDAY_ALT and field_type == "weekday":
                # Allow 7 for Sunday in weekday field
                val = 0

            if not (min_val <= val <= max_val):
                msg = f"value {val} out of range [{min_val}-{max_val}] for {field_type}"
                raise ValueError(msg)

            values.add(val)

        return values

    def _parse_range(self, range_str: str, field_type: str) -> tuple[int, int]:
        """Parse a range string like '1-5' or 'MON-FRI'."""
        parts = range_str.split("-")
        if len(parts) != RANGE_PARTS_COUNT:
            msg = f"invalid range format: {range_str}"
            raise ValueError(msg)

        start_val = self._parse_value(parts[0], field_type)
        end_val = self._parse_value(parts[1], field_type)

        if start_val > end_val:
            msg = f"invalid range: start ({start_val}) > end ({end_val})"
            raise ValueError(msg)

        return start_val, end_val

    def _parse_value(self, value: str, field_type: str) -> int:
        """Parse a single value, handling month/weekday names."""
        if value.isdigit():
            return int(value)

        if field_type == "month" and value.upper() in self.MONTHS:
            return self.MONTHS[value.upper()]

        if field_type == "weekday" and value.upper() in self.WEEKDAYS:
            return self.WEEKDAYS[value.upper()]

        msg = f"invalid value: {value} for field type: {field_type}"
        raise ValueError(msg)

    def get_next_run(self, after: datetime | None = None) -> datetime:
        """Calculate the next run time after the given datetime."""
        if self.is_reboot:
            # Special case: @reboot runs immediately
            return datetime.now(UTC)

        if after is None:
            after = datetime.now(UTC)

        # Parse valid values for each field
        valid_minutes = self._parse_field(self.minute_pattern, 0, 59, "minute")
        valid_hours = self._parse_field(self.hour_pattern, 0, 23, "hour")
        valid_months = self._parse_field(self.month_pattern, 1, 12, "month")
        valid_years = self._parse_field(self.year_pattern, 1970, 2099, "year") if self.year_pattern != "*" else None

        # Start from the next minute
        current = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Limit search to 4 years
        max_iterations = 4 * 366 * 24 * 60
        for _ in range(max_iterations):
            # Check year first (if specified)
            if valid_years and current.year not in valid_years:
                # Jump to next valid year
                next_year = min(y for y in valid_years if y > current.year)
                current = current.replace(year=next_year, month=1, day=1, hour=0, minute=0)
                continue

            # Check month
            if current.month not in valid_months:
                current = current.replace(day=1, hour=0, minute=0) + timedelta(days=32)
                current = current.replace(day=1)  # First day of next month
                continue

            # Check day and weekday fields
            valid_days = self._parse_field(self.day_pattern, 1, 31, "day")
            valid_weekdays = self._parse_field(self.weekday_pattern, 0, 7, "weekday")

            # Simplified day/weekday matching (basic implementation)
            day_matches = self.day_pattern in {"*", "?"} or current.day in valid_days
            weekday_matches = self.weekday_pattern in {"*", "?"} or current.weekday() % 7 in valid_weekdays

            # If both are specified, either can match (OR logic)
            if self.day_pattern not in {"*", "?"} and self.weekday_pattern not in {"*", "?"}:
                if not (day_matches or weekday_matches):
                    current += timedelta(days=1)
                    current = current.replace(hour=0, minute=0)
                    continue
            elif not (day_matches and weekday_matches):
                current += timedelta(days=1)
                current = current.replace(hour=0, minute=0)
                continue

            # Check hour
            if current.hour not in valid_hours:
                current += timedelta(hours=1)
                current = current.replace(minute=0)
                continue

            # Check minute
            if current.minute in valid_minutes:
                return current

            current += timedelta(minutes=1)

        msg = f"could not find next run time for cron expression: {self.cron_expr}"
        raise ValueError(msg)


@dataclass
class ScheduleConfig:
    """Configuration for scheduled jobs."""

    function_name: str
    cron: str | None = None
    interval: int | None = None  # seconds
    timezone: str = "UTC"
    initial_delay: int = 0  # seconds to wait before first run
    jitter: int = 0  # random jitter in seconds
    max_instances: int = 1  # max concurrent instances
    timeout: int | None = None  # job timeout in seconds

    def get_next_run(self, after: datetime | None = None) -> datetime:
        """Calculate next run time."""
        base_time = after or datetime.now(UTC)
        tz = zoneinfo.ZoneInfo(self.timezone)
        # Convert to specified timezone if needed
        if self.timezone != "UTC":
            base_time = base_time.astimezone(tz)

        if self.cron:
            # Use our feature-complete cron parser
            parser = CronParser(self.cron)
            next_run = parser.get_next_run(base_time)
            # Convert back to UTC
            if self.timezone != "UTC":
                next_run = next_run.replace(tzinfo=tz).astimezone(UTC)
            return next_run
        if self.interval:
            return base_time + timedelta(seconds=self.interval)
        msg = "schedule must have either cron or interval"
        raise ValueError(msg)

    def should_run_now(self, last_run: datetime | None = None) -> bool:
        """Check if job should run now."""
        if not last_run:
            # Never run before - ready to run if no initial delay
            return self.initial_delay == 0

        next_run = self.get_next_run(after=last_run)
        return datetime.now(UTC) >= next_run


@overload
def register_job(name: Callable[P, R]) -> Callable[P, Coroutine[Any, Any, R]]: ...  # noqa: UP047


@overload
def register_job(
    name: str | None = None,
    *,
    cron: str | None = None,
    interval: int | None = None,
    timezone: str = "UTC",
    initial_delay: int = 0,
    jitter: int = 0,
    max_instances: int = 1,
    timeout: int | None = None,
) -> Callable[[Callable[P, R]], Callable[P, Coroutine[Any, Any, R]]]: ...


def register_job(  # noqa: UP047
    name: str | Callable[P, R] | None = None,
    *,
    cron: str | None = None,
    interval: int | None = None,
    timezone: str = "UTC",
    initial_delay: int = 0,
    jitter: int = 0,
    max_instances: int = 1,
    timeout: int | None = None,
) -> Callable[[Callable[P, R]], Callable[P, Coroutine[Any, Any, R]]] | Callable[P, Coroutine[Any, Any, R]]:
    """Decorator to register a job function with optional scheduling.

    Automatically converts synchronous functions to async using ensure_async_.

    Args:
        name: Job name (defaults to function name) or the decorated function
        cron: Optional cron expression (e.g., "0 2 * * *" for 2 AM daily)
        interval: Optional interval in seconds between runs
        timezone: Timezone for cron expressions (default: UTC)
        initial_delay: Seconds to wait before first run (for scheduled jobs)
        jitter: Random jitter in seconds (for scheduled jobs)
        max_instances: Maximum concurrent instances (for scheduled jobs)
        timeout: Job timeout in seconds (for scheduled jobs)

    Either cron or interval can be specified for scheduled jobs, not both.
    If neither is specified, the job is registered as an ad-hoc job only.

    Examples:
        @register_job()  # Ad-hoc job only
        async def process_data(data_id: str): ...

        @register_job(cron="0 2 * * *")  # Daily at 2 AM
        async def daily_cleanup(): ...

        @register_job(interval=3600)  # Every hour
        async def hourly_sync(): ...

        @register_job(name="custom_name", cron="*/5 * * * *")
        async def my_task(): ...
    """
    # Handle the case where decorator is used without parentheses
    if callable(name):
        func = name
        job_name = func.__name__

        # Ensure the function is async (converts if needed)
        async_func = ensure_async_(func) if not inspect.iscoroutinefunction(func) else func

        # Preserve the original function's metadata
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = async_func(*args, **kwargs)
            if inspect.iscoroutine(result):
                return await result
            return result

        # Store the wrapper in the registry
        _job_registry[job_name] = wrapper

        # Add metadata for inspection
        wrapper.__job_name__ = job_name  # type: ignore[attr-defined]

        return wrapper

    # Validate scheduling parameters
    if cron and interval:
        msg = "cannot specify both cron and interval"
        raise ValueError(msg)

    if cron:
        # Validate cron expression
        try:
            CronParser(cron)
        except ValueError as e:
            msg = f"invalid cron expression: {cron}"
            raise ValueError(msg) from e

    def decorator(func: Callable[P, R]) -> Callable[P, Coroutine[Any, Any, R]]:
        job_name = name if isinstance(name, str) else func.__name__

        # Ensure the function is async (converts if needed)
        async_func = ensure_async_(func) if not inspect.iscoroutinefunction(func) else func

        # Preserve the original function's metadata
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            result = async_func(*args, **kwargs)
            if inspect.iscoroutine(result):
                return await result
            return result

        # Store the wrapper in the registry
        _job_registry[job_name] = wrapper

        # Add metadata for inspection
        wrapper.__job_name__ = job_name  # type: ignore[attr-defined]

        # If scheduling parameters are provided, register the schedule
        if cron or interval:
            config = ScheduleConfig(
                function_name=job_name,
                cron=cron,
                interval=interval,
                timezone=timezone,
                initial_delay=initial_delay,
                jitter=jitter,
                max_instances=max_instances,
                timeout=timeout,
            )
            _schedule_registry[job_name] = config
            wrapper.__schedule_config__ = config  # type: ignore[attr-defined]

        return wrapper

    return decorator


def get_job_registry() -> dict[str, Callable[..., Coroutine[Any, Any, Any]]]:
    """Get the job registry.

    Returns:
        Dictionary of registered jobs
    """
    return _job_registry


def get_scheduled_jobs() -> dict[str, ScheduleConfig]:
    """Get all scheduled jobs.

    Returns:
        Dictionary of function name to schedule config
    """
    return _schedule_registry


# Cache for discovered modules to avoid re-importing
_discovered_modules: set[str] = set()


def discover_jobs(package_path: str = "sqlstack.server.jobs", force_reload: bool = False) -> None:
    """Auto-discover and load all job modules containing decorated functions.

    Args:
        package_path: Python package path to search for job modules
        force_reload: Force re-import of modules even if cached

    This function will:
    1. Find all Python modules in the specified package
    2. Import each module, which triggers the @register_job decorators
    3. Decorated functions are automatically registered in the global registry
    4. Cache imported modules to avoid duplicate imports
    """
    import importlib
    import pkgutil
    import sys

    # Skip if already discovered (unless forced)
    if package_path in _discovered_modules and not force_reload:
        logger.debug("package already discovered, skipping", package=package_path)
        return

    try:
        # Import the base package
        base_module = importlib.import_module(package_path)
        if not hasattr(base_module, "__path__"):
            logger.warning("package has no __path__, skipping", package=package_path)
            return

        # Walk through all modules in the package
        for _, modname, ispkg in pkgutil.walk_packages(base_module.__path__, prefix=f"{package_path}."):
            if not ispkg:  # Only import actual modules, not sub-packages
                # Check if module already imported
                if modname in _discovered_modules and not force_reload:
                    continue

                try:
                    if force_reload and modname in sys.modules:
                        importlib.reload(sys.modules[modname])
                    else:
                        importlib.import_module(modname)

                    # Mark as discovered
                    _discovered_modules.add(modname)

                    # The @register_job decorators will auto-register functions
                    logger.debug("loaded job module", module=modname)
                except (ImportError, AttributeError, SyntaxError, ModuleNotFoundError):
                    logger.exception("failed to load job module", module=modname)

        # Mark package as discovered
        _discovered_modules.add(package_path)

    except ImportError as e:
        logger.warning("jobs package not found", package=package_path, error=str(e))

    # Log summary of discovered jobs
    scheduled_jobs = [name for name in _job_registry if name in _schedule_registry]
    ad_hoc_jobs = [name for name in _job_registry if name not in _schedule_registry]

    if _job_registry:
        logger.info("discovered job functions", package=package_path, count=len(_job_registry))

        if scheduled_jobs:
            logger.info("scheduled jobs", count=len(scheduled_jobs))
            for job_name in scheduled_jobs:
                config = _schedule_registry[job_name]
                if config.cron:
                    logger.info("scheduled job", name=job_name, cron=config.cron, timezone=config.timezone)
                else:
                    logger.info("scheduled job", name=job_name, interval_seconds=config.interval)

        if ad_hoc_jobs:
            logger.info("ad-hoc jobs", count=len(ad_hoc_jobs), jobs=", ".join(ad_hoc_jobs))
    else:
        logger.warning("no job functions discovered", package=package_path)


def load_jobs() -> None:
    """Load all job modules to register functions.

    This is called during worker initialization to discover all available jobs.
    """
    discover_jobs("sqlstack.server.jobs")  # Default location
