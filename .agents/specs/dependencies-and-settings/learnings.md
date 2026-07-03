# Learnings: dependencies-and-settings

## 1. Unprefixed Fallback Precedence
When implementing configuration environment mapping with fallback support (e.g. allowing `SQLSTACK_` prefix but falling back to un-prefixed values), the lookup order must prioritize the prefixed key first to allow overrides:
1. `SQLSTACK_{KEY}`
2. `{KEY}`
3. Default value

## 2. PEP 562 Caching & Reset Hook
Python module-level `__getattr__(name: str)` only triggers if the attribute is absent from the module's `__dict__`.
- Once a lazy-initialized singleton is assigned to the module scope (e.g. `csrf = CSRFConfig(...)`), subsequent accesses bypass `__getattr__` entirely.
- To support test isolation via `_reset()`, we must explicitly delete the cached attributes from the module namespace (using `del globals()[name]`) and clear any internal config caches (e.g., `Settings.from_env.cache_clear()`).

## 3. Ruff PLW0603 Global Statement Warnings
Ruff flags modifying global variables with the `global` statement as a code smell (`PLW0603`).
- A clean, type-safe pattern to bypass this without introducing dummy container classes is to mutate `globals()` directly, e.g.:
  `globals()["_initialized"] = True`
  `globals()["db"] = db_manager.add_config(...)`
- To ensure editor autocomplete and type-checkers still recognize these attributes, use type annotations at the module top-level (e.g., `db: AsyncpgConfig`).
