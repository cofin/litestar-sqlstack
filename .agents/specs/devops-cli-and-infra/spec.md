# Flow: devops-cli-and-infra

## Specification

### Overview
This flow introduces a unified DevOps CLI (`manage.py`) at the root of the project to orchestrate development environments, Docker/Podman containers, database lifecycle commands, and SQLSpec database migrations.

### Key Requirements
1. **Container Abstraction:** Auto-detect Docker or Podman runtime, allowing multi-platform setups without direct shell-script hardcoding.
2. **PostgreSQL/AlloyDB Lifecycle:** Introduce `tools/postgres/database.py` to boot, configure, health-check (using ADBC wire verification), and stop database containers.
3. **DevOps Commands:** Expose Click subcommands in `manage.py` for `init` (bootstrapping `.env`), `doctor` (diagnostics), `install` (prerequisites), `infra` (container lifecycle), and `database` (SQLSpec schema migrations).
4. **Makefile Redirection:** Refactor root `Makefile` targets to delegate to the new `manage.py` commands.

---

## Implementation Plan

### Phase 1: Container & Database Lifecycle Abstraction
- [x] **1.1 Implement container runtime detector**
  - Create `tools/lib/container.py` containing `ContainerRuntime` to detect Docker/Podman, execute checks, and run commands.
- [x] **1.2 Create DB URL helper**
  - Create `tools/lib/db_url.py` to build standard PostgreSQL connection strings.
- [x] **1.3 Implement PostgreSQL database lifecycle manager**
  - Create `tools/postgres/database.py` containing `DatabaseConfig` (container port: 15432, name: `sqlstack-db`) and `PostgreSQLDatabase` with `start`, `stop`, `restart`, `status`, and `remove` methods.

### Phase 2: DevOps Command Suite
- [x] **2.1 Implement init command**
  - Create `tools/cli/init.py` to copy `.env.example` to `.env` and set initial values.
- [x] **2.2 Implement doctor check command**
  - Create `tools/cli/doctor.py` to verify container runtime availability and network port availability.
- [x] **2.3 Implement install command**
  - Create `tools/cli/install.py` to sync Python dependencies, setup nodeenv, and verify pre-commit tools.
- [x] **2.4 Implement root manage.py CLI entry point**
  - Create click-based `manage.py` at the project root mapping `init`, `doctor`, `install`, `infra` commands.

### Phase 3: SQLSpec Migration Integration
- [x] **3.1 Port postgres cli subcommands**
  - Create `tools/postgres/cli/` subcommands (`connection.py`, `database.py`, `health.py`) for database administration.
- [x] **3.2 Wire SQLSpec migration CLI hooks**
  - In `manage.py`, import `add_migration_commands` from `sqlspec.cli` and attach it to the `database` group using `sqlstack.config.db` configuration.

### Phase 4: Makefile Cleanup & Verification
- [x] **4.1 Update Makefile targets**
  - Refactor `Makefile` targets `install`, `clean`, `destroy`, `start-infra`, `stop-infra`, and `wipe-infra` to call the new `manage.py` commands.
- [x] **4.2 Verify DevOps commands**
  - Test `python manage.py doctor`, `make start-infra`, and database migrations commands (`python manage.py database upgrade`) to verify functional parity.
