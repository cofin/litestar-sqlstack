# Progress and Next Steps

## Completed Work

### 1. Analysis and Setup

- Reviewed the `DomainPlugin` utility in the `accelerator` project to understand the target architecture.
- Verified that the `DomainPlugin` is already wired into the project in `sqlstack/server/plugins.py` and `sqlstack/server/core.py`.

### 2. Schema Reorganization (Accounts Domain)

- Consolidated and cleaned up `sqlstack/domain/accounts/schemas/`.
- Created `_auth.py` for authentication-related schemas (`AccountLogin`, `AccountRegister`).
- Created `_user.py` for user-related schemas (`User`, `UserCreate`, `UserUpdate`, `ProfileUpdate`).
- Removed the redundant `_account.py` file.
- Updated `sqlstack/domain/accounts/schemas/__init__.py` to export all consolidated schemas.

### 3. Service Reorganization (Accounts Domain)

- Renamed `sqlstack/domain/accounts/services/user_oauth_account.py` to `_user_oauth_account.py` to follow the project's naming convention.
- Updated `sqlstack/domain/accounts/services/__init__.py` with the new import path.

### 4. Auth and Security Consolidation

- Created a dedicated auth package: `sqlstack/domain/accounts/auth/`.
- Moved `sqlstack/server/security.py` to `sqlstack/domain/accounts/auth/_security.py`.
- Moved `sqlstack/utils/oauth.py` to `sqlstack/domain/accounts/auth/_oauth.py`.
- Created `sqlstack/domain/accounts/auth/__init__.py` to provide a clean API for auth-related utilities.
- Updated system-wide imports in `sqlstack/server/core.py` and `sqlstack/server/plugins.py`.

### 5. Controller Consolidation and Standard naming

- Renamed all controllers in `sqlstack/domain/accounts/controllers/` to use the underscore prefix.
- Renamed `system` and `web` controllers to use the underscore prefix (`_system.py`, `_web.py`).
- Renamed `system` jobs to use the underscore prefix (`_system.py`).
- Renamed `accounts` events to use the underscore prefix (`_user.py`).
- Updated all `__init__.py` files in domain submodules to reflect the new naming and export appropriate modules.
- Updated all security and auth imports in account controllers to point to the new consolidated `auth` module.

### 6. Settings and Environment

- Fixed an issue in `sqlstack/lib/settings.py` where environment variable interpolation was failing due to `override=False` in `load_dotenv`. Enabled `override=True` to allow `.env` values to correctly supersede shell defaults.

### 7. Verification

- Ran all unit tests (`pytest tests/unit`) and confirmed that all 333 tests passed after the reorganization.

---

## Remaining Work

### 1. Dishka Configuration Update

- Update the Dishka configuration based on the project specifications to optimize dependency injection.

### 2. Wiring and Integration Verification

- Confirm that `DomainPlugin` is correctly auto-discovering all components in the new structure in a running environment.
- Verify that integration tests (`pytest tests/integration`) pass as well.

### 3. Final Cleanup

- Remove any stale `__pycache__` or `.mypy_cache` entries that might still reference old file paths.
