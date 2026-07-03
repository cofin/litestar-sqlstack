# Learnings: DevOps CLI and Infra Flow

## Click Aliases and RichGroup Compatibility
During SQLSpec migration CLI hooks integration, we discovered that `sqlspec.cli.add_migration_commands` registers commands using aliases. Standard `click.Group` does not natively support the `aliases` parameter, raising a `TypeError` when the command decorator is evaluated.
To resolve this:
- We used `import rich_click as click` in `manage.py` and decorated the group definition with `@click.group(name="database")`.
- This ensures the group is instantiated as a `RichGroup`, which fully supports the `aliases` keyword, preventing decoration failures.

## Database Connection Verification
For PostgreSQL "wire verification" health checking, instead of installing additional heavy ADBC dependencies, we leveraged `psycopg` (which is already present in the workspace) to perform a direct sync connection verification:
- Running `SELECT 1` ensures not only that the socket port is open but that the full PostgreSQL wire handshake, authentication, and SQL execution layers are active and ready.
