# Background Worker System Guide

> **Purpose**: Complete guide to litestar-sqlstack's background worker system for async job processing and scheduled tasks
> **Audience**: Developers building async features, scheduled jobs, and background operations
> **Last Updated**: 2025-11-02
> **Status**: ✅ Current

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Creating Jobs](#creating-jobs)
  - [Ad-hoc Jobs](#ad-hoc-jobs)
  - [Scheduled Jobs (Cron)](#scheduled-jobs-cron)
  - [Scheduled Jobs (Interval)](#scheduled-jobs-interval)
- [Worker Configuration](#worker-configuration)
- [Job Monitoring](#job-monitoring)
- [Deployment Modes](#deployment-modes)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Sources](#sources)

---

## Overview

The background worker system enables asynchronous job processing and scheduled tasks in litestar-sqlstack applications. It provides:

- **Database-backed job queue** using PostgreSQL
- **Decorator-based job registration** (`@register_job`)
- **Cron and interval-based scheduling**
- **Automatic retry logic** with exponential backoff
- **Job deduplication** via unique keys
- **Graceful shutdown** with task completion
- **Dishka integration** for dependency injection

**Architecture:**

```
Routes → TaskService → job table → Worker → JobRegistry → Execute
```

The worker polls the `job` table every 3 seconds, claims available jobs atomically, executes registered functions, and updates job status.

---

## Quick Start

### 1. Define a Job Function

Create a job function in `sqlstack/server/jobs/`:

```python
# sqlstack/server/jobs/emails.py
from sqlstack.lib.jobs import register_job
import structlog

logger = structlog.get_logger()

@register_job("send_welcome_email")
async def send_welcome_email(user_id: str, email: str) -> dict:
    """Send welcome email to new user."""
    await logger.ainfo("sending welcome email", user_id=user_id, email=email)

    # Email sending logic here
    # ...

    return {"status": "sent", "user_id": user_id}
```

### 2. Queue the Job

From a route handler or service:

```python
from sqlstack.services import TaskService
from sqlstack.lib.di import Inject

async def create_user_route(
    data: UserCreate,
    task_service: Inject[TaskService],
) -> User:
    """Create user and queue welcome email."""
    user = await user_service.create(data)

    # Queue background job
    await task_service.create_task(
        function="send_welcome_email",
        data={
            "user_id": str(user.id),
            "email": user.email,
        },
    )

    return user
```

### 3. Start the Worker

The worker starts automatically with the Litestar app when configured in development mode:

```python
# sqlstack/server/plugins.py
from sqlstack.server.worker_plugin import WorkerPlugin

worker = WorkerPlugin(
    start_worker=True,  # Run worker in-process
    job_packages=["sqlstack.server.jobs"],
    auto_discover=True,
)
```

For production, run the worker separately (see [Deployment Modes](#deployment-modes)).

---

## Creating Jobs

### Ad-hoc Jobs

Ad-hoc jobs are triggered programmatically (from routes, services, etc.):

```python
from sqlstack.lib.jobs import register_job

@register_job("process_upload")
async def process_upload(file_path: str, user_id: str) -> dict:
    """Process uploaded file in background."""
    # Processing logic
    result = await process_file(file_path)

    return {
        "status": "completed",
        "processed_items": result.count,
    }

# Queue from route
await task_service.create_task(
    function="process_upload",
    data={"file_path": "/uploads/file.csv", "user_id": "123"},
    priority=10,  # Higher priority
)
```

**Job Deduplication:**

Use the `key` parameter to prevent duplicate jobs:

```python
# Only one job per user per day
await task_service.create_task(
    function="daily_report",
    data={"user_id": user_id},
    key=f"daily-report-{user_id}-{date.today()}",
)
```

### Scheduled Jobs (Cron)

Scheduled jobs run automatically based on cron expressions:

```python
from sqlstack.lib.jobs import register_job

@register_job(cron="0 2 * * *")  # Daily at 2 AM
async def cleanup_old_sessions() -> dict:
    """Clean up sessions older than 30 days."""
    count = await session_service.cleanup_old(days=30)
    return {"cleaned": count}

@register_job(cron="0 */6 * * *")  # Every 6 hours
async def sync_external_data() -> dict:
    """Sync data from external API."""
    result = await external_api.sync()
    return {"synced": result.count}

@register_job(cron="0 0 * * 0")  # Weekly on Sunday
async def weekly_report() -> dict:
    """Generate weekly analytics report."""
    report = await analytics_service.generate_weekly()
    return {"report_id": str(report.id)}
```

**Cron Expression Format:**

```
minute hour day month weekday
 0-59  0-23 1-31  1-12  0-7 (0=Sunday, 7=Sunday)

Examples:
  "0 2 * * *"     - Daily at 2 AM
  "*/15 * * * *"  - Every 15 minutes
  "0 0 1 * *"     - Monthly on the 1st
  "0 9-17 * * 1-5" - Mon-Fri, 9 AM to 5 PM
```

**Special Cron Aliases:**

```python
@register_job(cron="@hourly")   # Same as "0 * * * *"
@register_job(cron="@daily")    # Same as "0 0 * * *"
@register_job(cron="@weekly")   # Same as "0 0 * * 0"
@register_job(cron="@monthly")  # Same as "0 0 1 * *"
@register_job(cron="@yearly")   # Same as "0 0 1 1 *"
```

### Scheduled Jobs (Interval)

Interval-based jobs run repeatedly at fixed intervals:

```python
from sqlstack.lib.jobs import register_job

@register_job(interval=3600)  # Every hour (in seconds)
async def hourly_sync() -> dict:
    """Sync data every hour."""
    result = await sync_service.run()
    return {"synced_at": datetime.now(UTC).isoformat()}

@register_job(interval=300, initial_delay=60)  # Every 5 minutes, start after 1 minute
async def health_check() -> dict:
    """Health check every 5 minutes."""
    status = await check_service_health()
    return {"status": status}

@register_job(interval=86400, jitter=3600)  # Daily with 1-hour jitter
async def daily_backup() -> dict:
    """Daily backup with random jitter to avoid thundering herd."""
    await backup_service.run()
    return {"backup_completed": True}
```

**Interval Parameters:**

- `interval` (int): Seconds between executions
- `initial_delay` (int, optional): Seconds to wait before first execution
- `jitter` (int, optional): Random seconds added to prevent thundering herd

**Timezone Support:**

```python
@register_job(cron="0 9 * * *", timezone="America/New_York")
async def market_open_report() -> dict:
    """Run at 9 AM Eastern Time."""
    return await generate_report()
```

---

## Worker Configuration

### Development Mode (In-Process)

Run worker alongside the web server:

```python
# sqlstack/server/plugins.py
from sqlstack.server.worker_plugin import WorkerPlugin

worker = WorkerPlugin(
    start_worker=True,  # Enable worker
    job_packages=["sqlstack.server.jobs"],
    auto_discover=True,
    poll_interval=3.0,  # Poll every 3 seconds
    batch_size=10,      # Process up to 10 jobs per poll
)
```

### Production Mode (Separate Process)

Disable worker in the web server:

```python
# sqlstack/server/plugins.py
worker = WorkerPlugin(
    start_worker=False,  # Disable worker
    job_packages=["sqlstack.server.jobs"],
    auto_discover=True,
)
```

Start worker separately:

```bash
# CLI command (when implemented)
sqlstack worker start

# Or run Python script
uv run python -c "
from sqlstack.lib.worker import Worker
import asyncio

async def main():
    worker = Worker()
    await worker.start()

asyncio.run(main())
"
```

### Configuration Options

```python
WorkerPlugin(
    start_worker=True,               # Run worker in-process
    job_packages=["sqlstack.server.jobs"],  # Packages to scan for jobs
    auto_discover=True,              # Auto-import job modules
    poll_interval=3.0,               # Polling interval (seconds)
    batch_size=10,                   # Max jobs per poll
    shutdown_timeout=30.0,           # Graceful shutdown timeout
)
```

---

## Job Monitoring

### TaskService API

The `TaskService` provides methods for job management:

```python
from sqlstack.services import TaskService
from sqlstack.lib.di import Inject

async def monitor_jobs(task_service: Inject[TaskService]):
    # Get job statistics
    stats = await task_service.get_statistics()
    # Returns: {"pending": 5, "running": 2, "completed": 100, "failed": 1}

    # List pending jobs
    pending = await task_service.list_pending_tasks(limit=20)

    # Get specific job
    job = await task_service.get_task(job_id)

    # Check job status
    if job.status == "failed":
        logger.error("job failed", job_id=str(job.id), error=job.error)

    # Cancel pending job
    await task_service.cancel_task(job_id)
```

### Job Statuses

- `pending`: Waiting to be executed
- `scheduled`: Scheduled for future execution
- `running`: Currently executing
- `completed`: Successfully completed
- `failed`: Failed after all retries
- `cancelled`: Manually cancelled

### Logging

All job execution is logged with structured logging:

```python
# Worker logs
await logger.ainfo(
    "task started",
    task_id=str(task_id),
    function=function_name,
)

await logger.ainfo(
    "task completed",
    task_id=str(task_id),
    duration_ms=duration,
)

await logger.aerror(
    "task failed",
    task_id=str(task_id),
    error=str(error),
    retry_count=retry_count,
)
```

---

## Deployment Modes

### Development (In-Process Worker)

**Pros:**
- Simple setup
- Easy debugging
- Single process

**Cons:**
- Worker shares resources with web server
- Long-running jobs can impact HTTP performance
- No horizontal scaling

**Use when:**
- Local development
- Testing
- Low job volume

### Production (Separate Worker Process)

**Pros:**
- Isolation from web server
- Independent scaling
- Resource control
- Better fault tolerance

**Cons:**
- More complex deployment
- Additional process management

**Use when:**
- Production environment
- High job volume
- Long-running jobs
- Multiple worker instances

### Docker Compose Example

```yaml
version: '3.8'

services:
  web:
    image: sqlstack:latest
    environment:
      - WORKER_ENABLED=false
    ports:
      - "8000:8000"
    command: litestar run

  worker:
    image: sqlstack:latest
    environment:
      - WORKER_ENABLED=true
    command: sqlstack worker start
    deploy:
      replicas: 2  # Multiple workers for concurrency
```

### Multiple Workers

The system supports multiple worker processes safely:

- **Atomic job claiming** via `FOR UPDATE SKIP LOCKED`
- **No job duplication** - each job claimed by exactly one worker
- **Horizontal scaling** - add more workers for higher throughput

---

## Troubleshooting

### Jobs Not Executing

**Symptom:** Jobs stay in `pending` status

**Checks:**
1. Is worker running?
   ```bash
   # Check logs for "worker started"
   ```

2. Are jobs registered?
   ```python
   from sqlstack.lib.jobs import get_job_registry
   print(get_job_registry().keys())
   ```

3. Is job package auto-discovered?
   ```python
   # Ensure job_packages includes your module
   WorkerPlugin(job_packages=["sqlstack.server.jobs"])
   ```

### Jobs Failing with Retries

**Symptom:** Jobs retry multiple times then fail

**Solution:**
1. Check job logs for error details
2. Add error handling in job function:
   ```python
   @register_job("risky_operation")
   async def risky_operation(data: dict) -> dict:
       try:
           result = await external_api.call(data)
           return {"status": "success", "result": result}
       except APIError as e:
           await logger.aerror("api call failed", error=str(e))
           raise  # Will retry
   ```

### Scheduled Jobs Not Running

**Symptom:** Cron/interval jobs not executing

**Checks:**
1. Is job registered with schedule?
   ```python
   from sqlstack.lib.jobs import get_schedule_registry
   print(get_schedule_registry())
   ```

2. Was worker restarted after schedule change?
   - Schedule changes require worker restart to take effect

3. Check timezone settings:
   ```python
   @register_job(cron="0 9 * * *", timezone="UTC")
   ```

### Database Connection Issues

**Symptom:** Worker fails to connect to database

**Solution:**
1. Verify database config in environment
2. Check connection pool settings
3. Ensure database is accessible from worker process
4. Review `sqlstack/config.py` for database configuration

### High Job Latency

**Symptom:** Jobs take too long to start

**Causes:**
- Polling interval too high (default 3 seconds)
- Too many pending jobs
- Worker overloaded

**Solutions:**
1. Reduce polling interval (but increases DB load):
   ```python
   WorkerPlugin(poll_interval=1.0)
   ```

2. Add more worker processes

3. Increase batch size:
   ```python
   WorkerPlugin(batch_size=20)
   ```

---

## Performance Tuning

### Worker Configuration

```python
# High-throughput configuration
WorkerPlugin(
    poll_interval=1.0,    # More frequent polling
    batch_size=20,        # Process more jobs per poll
)

# Low-latency configuration
WorkerPlugin(
    poll_interval=0.5,    # Very frequent polling (higher DB load)
    batch_size=5,         # Smaller batches for faster processing
)

# Resource-constrained configuration
WorkerPlugin(
    poll_interval=5.0,    # Less frequent polling
    batch_size=5,         # Smaller batches
)
```

### Database Optimization

The job table includes optimized indexes:

```sql
-- Efficient pending job queries
CREATE INDEX idx_job_status ON job (status)
    WHERE status IN ('pending', 'scheduled');

-- Efficient scheduled job queries
CREATE INDEX idx_job_scheduled_at ON job (scheduled_at)
    WHERE status = 'scheduled';
```

### Job Priority

Use priority to ensure critical jobs run first:

```python
# High priority
await task_service.create_task(
    function="critical_operation",
    data={...},
    priority=100,  # Higher = more important
)

# Normal priority
await task_service.create_task(
    function="normal_operation",
    data={...},
    priority=0,  # Default
)
```

### Cleanup Old Jobs

Prevent unbounded growth of job table:

```python
@register_job(cron="0 3 * * *")  # Daily at 3 AM
async def cleanup_old_jobs() -> dict:
    """Remove completed jobs older than 30 days."""
    count = await task_service.cleanup_old_jobs(days=30)
    return {"cleaned": count}
```

### Monitoring Metrics

Track these metrics for production:

- **Job queue depth** - pending job count
- **Job execution time** - p50, p95, p99
- **Job success rate** - completed / (completed + failed)
- **Worker uptime** - worker availability
- **Retry rate** - jobs requiring retries

---

## Sources

- **Implementation**: `/home/cody/code/litestar/litestar-sqlstack/sqlstack/lib/worker.py`
- **Implementation**: `/home/cody/code/litestar/litestar-sqlstack/sqlstack/lib/jobs.py`
- **Implementation**: `/home/cody/code/litestar/litestar-sqlstack/sqlstack/services/_tasks.py`
- **Reference**: dma/accelerator worker system (battle-tested production implementation)
- **PRD**: specs/active/add-litestar-worker-system/prd.md

---

## Changelog

### 2025-11-02

- Initial version
- Complete worker system documentation
- Examples for ad-hoc, cron, and interval jobs
- Deployment modes and troubleshooting
- Performance tuning guide
