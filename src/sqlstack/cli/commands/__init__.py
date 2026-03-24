"""CLI command modules.

This package organizes CLI commands into logical modules:
- database: Database fixture loading and exporting
- users: User management commands
- server: Server and worker commands
- manage: System management commands
- assets: Asset management commands
- version: Version information

All command groups are exported here for registration with the main CLI.
"""

from sqlstack.cli.commands.assets import assets_group
from sqlstack.cli.commands.database import database_commands
from sqlstack.cli.commands.manage import manage_group
from sqlstack.cli.commands.server import server_group
from sqlstack.cli.commands.users import user_management_group
from sqlstack.cli.commands.version import version_cmd

__all__ = ["assets_group", "database_commands", "manage_group", "server_group", "user_management_group", "version_cmd"]
