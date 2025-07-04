# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a reference implementation of a Litestar application using SQLSpec (not SQLAlchemy or Advanced-Alchemy). The project is actively migrating to use `sqlspec` exclusively.

## Essential Commands

### Development Setup
```bash
# Install dependencies (uses uv)
make install

# Run single test
uv run pytest tests/path/to/test.py::test_name -v

# Run tests matching pattern
uv run pytest tests -k "pattern" -v
```

### Code Quality
```bash
# Run all linting and type checking
make lint

# Auto-fix code issues
make fix

# Type checking only
make type-check  # runs both mypy and pyright
```

### Testing
```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run specific test markers
uv run pytest tests -m "unit"  # or "integration"
```

### Local Development
```bash
# Start infrastructure (PostgreSQL, Redis, etc.)
make start-infra

# Stop infrastructure
make stop-infra

# Run the application
uv run litestar run

# Or use the entry point
sqlstack
```

## Architecture & Key Patterns

### SQLSpec Migration
The codebase is migrating from SQLAlchemy/Advanced-Alchemy to SQLSpec. Key differences:
- Uses `sqlspec.extensions.litestar.SQLSpec` plugin instead of Advanced-Alchemy
- Configuration through `sqlspec.adapters.asyncpg.AsyncpgConfig`
- Services inherit patterns from `sqlstack.services._base`
- Models use SQLSpec's typing system (`ModelT`, `FilterTypeT`, etc.)

### Project Structure
```
sqlstack/
├── cli/          # CLI commands
├── config.py     # Central configuration (SQLSpec, CORS, logging)
├── db/           # Database migrations and fixtures
├── lib/          # Core utilities (crypto, logging, settings)
├── schemas/      # Pydantic/msgspec schemas (DTOs)
├── server/       # Litestar application
│   ├── routes/   # API endpoints
│   ├── events/   # Event handlers
│   ├── jobs/     # Background jobs
│   └── plugins.py # Plugin configurations
├── services/     # Business logic layer
└── utils/        # Shared utilities
```

### Service Layer Pattern
Services in `sqlstack/services/` follow a consistent pattern:
- Inherit from base service classes
- Use SQLSpec's `StatementFilter` for queries
- Return `OffsetPagination` for paginated results
- Handle type conversions through SQLSpec's typing utilities

### Schema Patterns
- Base schemas in `schemas/_base.py` using both Pydantic and msgspec
- `BaseStruct` for msgspec structures
- `CamelizedBaseSchema` for API responses with camelCase
- Consistent use of `model_config` for Pydantic models

### Configuration
- Settings loaded from environment via `lib.settings.get_settings()`
- Database configuration through SQLSpec's `DatabaseConfig`
- Structured logging with structlog
- CORS, CSRF, and compression middleware configured

### Authentication & Security
- JWT-based authentication
- Role-based access control (RBAC)
- Default roles: "User" and "Superuser"
- Password hashing with argon2

### Testing Approach
- Tests use pytest with async support
- Database tests use `pytest-databases[postgres]`
- Parallel test execution with pytest-xdist
- Coverage tracking with pytest-cov

## Development Guidelines

### When Working with SQLSpec
- Use `sqlspec` imports, not `sqlalchemy` or `advanced-alchemy`
- Follow the service patterns in `services/_base.py`
- Use SQLSpec's filter system for queries
- Handle pagination with `OffsetPagination`

### Code Style
- Python 3.12+ with type hints
- Ruff for linting and formatting
- Line length: 120 characters
- Import sorting enforced

### Performance Considerations
- Async/await patterns throughout
- Connection pooling configured via AsyncpgPoolConfig
- Granian ASGI server with uvloop
- Structured logging to minimize overhead