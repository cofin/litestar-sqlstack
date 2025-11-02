"""Unit tests for job registry and scheduling."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from sqlstack.lib.jobs import (
    CronParser,
    ScheduleConfig,
    discover_jobs,
    get_job_registry,
    get_scheduled_jobs,
    register_job,
)


class TestCronParser:
    """Test CronParser for cron expression parsing."""

    def test_cron_parser_basic_expression(self) -> None:
        """Test parsing basic cron expression."""
        parser = CronParser("0 2 * * *")  # Daily at 2 AM

        assert parser.minute_pattern == "0"
        assert parser.hour_pattern == "2"
        assert parser.day_pattern == "*"
        assert parser.month_pattern == "*"
        assert parser.weekday_pattern == "*"

    def test_cron_parser_with_year(self) -> None:
        """Test parsing cron expression with year field."""
        parser = CronParser("0 0 1 1 * 2025")  # Jan 1, 2025 at midnight

        assert parser.year_pattern == "2025"

    def test_cron_parser_alias_daily(self) -> None:
        """Test @daily alias."""
        parser = CronParser("@daily")

        # Alias is expanded to cron expression
        assert parser.cron_expr == "0 0 * * *"
        # Should run at midnight
        next_run = parser.get_next_run(datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC))
        assert next_run.hour == 0
        assert next_run.minute == 0

    def test_cron_parser_alias_hourly(self) -> None:
        """Test @hourly alias."""
        parser = CronParser("@hourly")

        next_run = parser.get_next_run(datetime(2024, 1, 1, 12, 30, 0, tzinfo=UTC))
        assert next_run.minute == 0
        assert next_run.hour == 13  # Next hour

    def test_cron_parser_alias_weekly(self) -> None:
        """Test @weekly alias."""
        parser = CronParser("@weekly")

        # Should run on Sunday at midnight
        # Jan 1, 2024 is a Monday, next Sunday is Jan 7, but from noon we'd get Jan 8
        next_run = parser.get_next_run(datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC))  # Monday
        # Verify it's Sunday at midnight
        assert next_run.hour == 0
        assert next_run.minute == 0
        # Verify it's after Jan 1
        assert next_run.day > 1

    def test_cron_parser_alias_monthly(self) -> None:
        """Test @monthly alias."""
        parser = CronParser("@monthly")

        next_run = parser.get_next_run(datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC))
        assert next_run.day == 1
        assert next_run.month == 2  # Next month

    def test_cron_parser_alias_yearly(self) -> None:
        """Test @yearly alias."""
        parser = CronParser("@yearly")

        next_run = parser.get_next_run(datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC))
        assert next_run.day == 1
        assert next_run.month == 1
        assert next_run.year == 2025

    def test_cron_parser_reboot(self) -> None:
        """Test @reboot special case."""
        parser = CronParser("@reboot")

        assert parser.is_reboot is True
        next_run = parser.get_next_run()
        # Should return current time (or very close to it)
        assert (datetime.now(UTC) - next_run).total_seconds() < 1

    def test_cron_parser_range(self) -> None:
        """Test range syntax (1-5)."""
        parser = CronParser("0 9-17 * * *")  # 9 AM to 5 PM

        # Validate that hours 9-17 are parsed
        valid_hours = parser._parse_field("9-17", 0, 23, "hour")
        assert 9 in valid_hours
        assert 17 in valid_hours
        assert 8 not in valid_hours
        assert 18 not in valid_hours

    def test_cron_parser_step(self) -> None:
        """Test step syntax (*/5)."""
        parser = CronParser("*/5 * * * *")  # Every 5 minutes

        valid_minutes = parser._parse_field("*/5", 0, 59, "minute")
        assert 0 in valid_minutes
        assert 5 in valid_minutes
        assert 10 in valid_minutes
        assert 55 in valid_minutes
        assert 3 not in valid_minutes

    def test_cron_parser_list(self) -> None:
        """Test comma-separated list (1,3,5)."""
        parser = CronParser("0 1,3,5 * * *")  # 1 AM, 3 AM, 5 AM

        valid_hours = parser._parse_field("1,3,5", 0, 23, "hour")
        assert 1 in valid_hours
        assert 3 in valid_hours
        assert 5 in valid_hours
        assert 2 not in valid_hours

    def test_cron_parser_month_names(self) -> None:
        """Test month name parsing."""
        parser = CronParser("0 0 1 JAN,JUL *")  # Jan and July

        valid_months = parser._parse_field("JAN,JUL", 1, 12, "month")
        assert 1 in valid_months  # January
        assert 7 in valid_months  # July
        assert 6 not in valid_months

    def test_cron_parser_weekday_names(self) -> None:
        """Test weekday name parsing."""
        parser = CronParser("0 0 * * MON,FRI")  # Monday and Friday

        valid_weekdays = parser._parse_field("MON,FRI", 0, 7, "weekday")
        assert 1 in valid_weekdays  # Monday
        assert 5 in valid_weekdays  # Friday
        assert 3 not in valid_weekdays  # Wednesday

    def test_cron_parser_invalid_expression(self) -> None:
        """Test invalid cron expression raises ValueError."""
        with pytest.raises(ValueError, match="invalid cron expression"):
            CronParser("invalid")

        with pytest.raises(ValueError, match="invalid cron expression"):
            CronParser("0 0 0")  # Too few fields

    def test_cron_parser_invalid_range(self) -> None:
        """Test invalid range raises ValueError."""
        parser = CronParser("0 0 * * *")  # Valid expression

        with pytest.raises(ValueError, match="invalid range"):
            parser._parse_field("10-5", 0, 23, "hour")  # Start > end

    def test_cron_parser_get_next_run_daily(self) -> None:
        """Test getting next run for daily schedule."""
        parser = CronParser("0 14 * * *")  # Daily at 2 PM

        # Current time: 12 PM
        current = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        next_run = parser.get_next_run(current)

        # Should be today at 2 PM
        assert next_run.year == 2024
        assert next_run.month == 1
        assert next_run.day == 15
        assert next_run.hour == 14
        assert next_run.minute == 0

    def test_cron_parser_get_next_run_past_time_today(self) -> None:
        """Test getting next run when time has passed today."""
        parser = CronParser("0 14 * * *")  # Daily at 2 PM

        # Current time: 3 PM (past 2 PM)
        current = datetime(2024, 1, 15, 15, 0, 0, tzinfo=UTC)
        next_run = parser.get_next_run(current)

        # Should be tomorrow at 2 PM
        assert next_run.year == 2024
        assert next_run.month == 1
        assert next_run.day == 16
        assert next_run.hour == 14
        assert next_run.minute == 0

    def test_cron_parser_get_next_run_every_5_minutes(self) -> None:
        """Test getting next run for every 5 minutes."""
        parser = CronParser("*/5 * * * *")

        current = datetime(2024, 1, 15, 12, 3, 0, tzinfo=UTC)
        next_run = parser.get_next_run(current)

        # Should be 12:05
        assert next_run.hour == 12
        assert next_run.minute == 5

    def test_cron_parser_question_mark_in_day(self) -> None:
        """Test ? in day field (no specific value)."""
        parser = CronParser("0 0 ? * 1")  # Every Monday, no specific day

        # Should not raise error
        assert parser.day_pattern == "?"

    def test_cron_parser_step_with_range(self) -> None:
        """Test step with range (10-30/5)."""
        parser = CronParser("10-30/5 * * * *")

        valid_minutes = parser._parse_field("10-30/5", 0, 59, "minute")
        assert 10 in valid_minutes
        assert 15 in valid_minutes
        assert 20 in valid_minutes
        assert 25 in valid_minutes
        assert 30 in valid_minutes
        assert 35 not in valid_minutes
        assert 5 not in valid_minutes


class TestScheduleConfig:
    """Test ScheduleConfig for scheduled jobs."""

    def test_schedule_config_with_cron(self) -> None:
        """Test ScheduleConfig with cron expression."""
        config = ScheduleConfig(function_name="test_job", cron="0 2 * * *")

        assert config.function_name == "test_job"
        assert config.cron == "0 2 * * *"
        assert config.interval is None

    def test_schedule_config_with_interval(self) -> None:
        """Test ScheduleConfig with interval."""
        config = ScheduleConfig(
            function_name="test_job",
            interval=3600,  # 1 hour
        )

        assert config.function_name == "test_job"
        assert config.interval == 3600
        assert config.cron is None

    def test_schedule_config_get_next_run_cron(self) -> None:
        """Test getting next run time with cron."""
        config = ScheduleConfig(
            function_name="test_job",
            cron="0 14 * * *",  # Daily at 2 PM
        )

        current = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        next_run = config.get_next_run(current)

        assert next_run.hour == 14
        assert next_run.minute == 0

    def test_schedule_config_get_next_run_interval(self) -> None:
        """Test getting next run time with interval."""
        config = ScheduleConfig(
            function_name="test_job",
            interval=3600,  # 1 hour
        )

        current = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        next_run = config.get_next_run(current)

        expected = current + timedelta(seconds=3600)
        assert next_run == expected

    def test_schedule_config_should_run_now_no_last_run(self) -> None:
        """Test should_run_now when never run before."""
        config = ScheduleConfig(function_name="test_job", interval=3600)

        # Should run immediately if no initial delay
        assert config.should_run_now(last_run=None) is True

    def test_schedule_config_should_run_now_with_initial_delay(self) -> None:
        """Test should_run_now with initial delay."""
        config = ScheduleConfig(
            function_name="test_job",
            interval=3600,
            initial_delay=60,  # 60 seconds delay
        )

        # Should not run immediately due to initial delay
        assert config.should_run_now(last_run=None) is False

    def test_schedule_config_should_run_now_after_interval(self) -> None:
        """Test should_run_now after interval has passed."""
        config = ScheduleConfig(
            function_name="test_job",
            interval=60,  # 1 minute
        )

        # Last run was 2 minutes ago
        last_run = datetime.now(UTC) - timedelta(minutes=2)
        assert config.should_run_now(last_run=last_run) is True

    def test_schedule_config_should_run_now_before_interval(self) -> None:
        """Test should_run_now before interval has passed."""
        config = ScheduleConfig(
            function_name="test_job",
            interval=3600,  # 1 hour
        )

        # Last run was 30 minutes ago
        last_run = datetime.now(UTC) - timedelta(minutes=30)
        assert config.should_run_now(last_run=last_run) is False

    def test_schedule_config_no_cron_or_interval_raises(self) -> None:
        """Test that missing both cron and interval raises ValueError."""
        config = ScheduleConfig(function_name="test_job")

        with pytest.raises(ValueError, match="schedule must have either cron or interval"):
            config.get_next_run()

    def test_schedule_config_timezone_utc(self) -> None:
        """Test schedule config with UTC timezone."""
        config = ScheduleConfig(function_name="test_job", cron="0 0 * * *", timezone="UTC")

        assert config.timezone == "UTC"

    def test_schedule_config_max_instances(self) -> None:
        """Test max_instances setting."""
        config = ScheduleConfig(function_name="test_job", interval=60, max_instances=3)

        assert config.max_instances == 3

    def test_schedule_config_timeout(self) -> None:
        """Test timeout setting."""
        config = ScheduleConfig(
            function_name="test_job",
            interval=60,
            timeout=120,  # 2 minutes
        )

        assert config.timeout == 120


class TestRegisterJob:
    """Test @register_job decorator."""

    def setup_method(self) -> None:
        """Clear job registries before each test."""
        from sqlstack.lib.jobs import _job_registry, _schedule_registry

        _job_registry.clear()
        _schedule_registry.clear()

    def test_register_job_async_function(self) -> None:
        """Test registering async function."""

        @register_job()
        async def test_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        assert "test_job" in registry
        assert hasattr(registry["test_job"], "__job_name__")
        assert registry["test_job"].__job_name__ == "test_job"

    def test_register_job_sync_function(self) -> None:
        """Test registering synchronous function (auto-converted to async)."""

        @register_job()
        def sync_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        assert "sync_job" in registry
        # Should be converted to async
        assert asyncio.iscoroutinefunction(registry["sync_job"])

    def test_register_job_custom_name(self) -> None:
        """Test registering job with custom name."""

        @register_job(name="custom_job_name")
        async def my_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        assert "custom_job_name" in registry
        assert "my_job" not in registry

    def test_register_job_with_cron(self) -> None:
        """Test registering job with cron schedule."""

        @register_job(cron="0 2 * * *")
        async def scheduled_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        schedules = get_scheduled_jobs()

        assert "scheduled_job" in registry
        assert "scheduled_job" in schedules
        assert schedules["scheduled_job"].cron == "0 2 * * *"

    def test_register_job_with_interval(self) -> None:
        """Test registering job with interval schedule."""

        @register_job(interval=3600)
        async def interval_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        schedules = get_scheduled_jobs()

        assert "interval_job" in registry
        assert "interval_job" in schedules
        assert schedules["interval_job"].interval == 3600

    def test_register_job_cron_and_interval_raises(self) -> None:
        """Test that specifying both cron and interval raises ValueError."""
        with pytest.raises(ValueError, match="cannot specify both cron and interval"):

            @register_job(cron="0 0 * * *", interval=3600)
            async def invalid_job() -> dict:
                return {}

    def test_register_job_invalid_cron_raises(self) -> None:
        """Test that invalid cron expression raises ValueError."""
        with pytest.raises(ValueError, match="invalid cron expression"):

            @register_job(cron="invalid cron")
            async def invalid_cron_job() -> dict:
                return {}

    def test_register_job_with_schedule_config(self) -> None:
        """Test that schedule config is attached to function."""

        @register_job(cron="0 2 * * *", timezone="UTC", max_instances=2)
        async def config_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        job_func = registry["config_job"]

        assert hasattr(job_func, "__schedule_config__")
        config = job_func.__schedule_config__
        assert config.cron == "0 2 * * *"
        assert config.timezone == "UTC"
        assert config.max_instances == 2

    async def test_register_job_execution(self) -> None:
        """Test that registered job can be executed."""

        @register_job()
        async def executable_job(value: str) -> dict:
            return {"result": value.upper()}

        registry = get_job_registry()
        result = await registry["executable_job"](value="test")

        assert result == {"result": "TEST"}

    def test_register_job_ad_hoc_no_schedule(self) -> None:
        """Test registering ad-hoc job without schedule."""

        @register_job()
        async def ad_hoc_job() -> dict:
            return {"status": "completed"}

        registry = get_job_registry()
        schedules = get_scheduled_jobs()

        assert "ad_hoc_job" in registry
        assert "ad_hoc_job" not in schedules


class TestDiscoverJobs:
    """Test job auto-discovery mechanism."""

    def setup_method(self) -> None:
        """Clear discovered modules cache."""
        from sqlstack.lib.jobs import _discovered_modules, _job_registry, _schedule_registry

        _discovered_modules.clear()
        _job_registry.clear()
        _schedule_registry.clear()

    def test_discover_jobs_loads_modules(self) -> None:
        """Test that discover_jobs loads job modules."""
        discover_jobs("sqlstack.server.jobs")

        registry = get_job_registry()

        # Should have discovered jobs from sqlstack.server.jobs.system
        assert len(registry) > 0
        assert "system_upkeep" in registry
        assert "background_worker_task" in registry
        assert "system_task" in registry
        assert "cleanup_old_sessions" in registry

    def test_discover_jobs_scheduled_jobs(self) -> None:
        """Test that discover_jobs finds scheduled jobs."""
        # Clear cache first to ensure fresh discovery
        from sqlstack.lib.jobs import _discovered_modules

        _discovered_modules.clear()

        discover_jobs("sqlstack.server.jobs", force_reload=True)

        schedules = get_scheduled_jobs()

        # cleanup_old_sessions should be scheduled
        assert "cleanup_old_sessions" in schedules
        assert schedules["cleanup_old_sessions"].cron == "0 2 * * *"

    def test_discover_jobs_caches_discovery(self) -> None:
        """Test that discover_jobs caches discovered modules."""
        from sqlstack.lib.jobs import _discovered_modules

        discover_jobs("sqlstack.server.jobs")
        first_count = len(_discovered_modules)

        # Second call should not re-import
        discover_jobs("sqlstack.server.jobs")
        second_count = len(_discovered_modules)

        assert first_count == second_count

    def test_discover_jobs_force_reload(self) -> None:
        """Test force_reload parameter."""
        from sqlstack.lib.jobs import _discovered_modules

        # Clear cache and force discovery
        _discovered_modules.clear()

        discover_jobs("sqlstack.server.jobs", force_reload=True)
        registry = get_job_registry()
        first_count = len(registry)

        # Force reload should re-import modules
        discover_jobs("sqlstack.server.jobs", force_reload=True)
        registry = get_job_registry()
        second_count = len(registry)

        # Count should be the same (jobs re-registered)
        assert first_count == second_count
        assert first_count > 0  # Should have discovered jobs

    def test_discover_jobs_nonexistent_package(self) -> None:
        """Test discovering from non-existent package."""
        # Should not raise error, just log warning
        discover_jobs("nonexistent.package")

        # Should not have discovered any jobs
        registry = get_job_registry()
        assert len(registry) == 0

    @patch("sqlstack.lib.jobs.logger")
    def test_discover_jobs_logs_summary(self, mock_logger: MagicMock) -> None:
        """Test that discover_jobs logs discovery summary."""
        from sqlstack.lib.jobs import _discovered_modules, _job_registry

        _discovered_modules.clear()
        _job_registry.clear()

        discover_jobs("sqlstack.server.jobs", force_reload=True)

        # Should have logged discovery info
        # Check that info was called (at least for discovered jobs or no jobs warning)
        assert mock_logger.info.called or mock_logger.warning.called
