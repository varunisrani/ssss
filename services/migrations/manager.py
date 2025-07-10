from typing import List, Type
import sqlite3
from services.migrations.v1_initial_schema import V1InitialSchema
from services.migrations.v2_add_canvases import V2AddCanvases
from services.migrations.v3_add_comfy_workflow import V3AddComfyWorkflow
from . import Migration

# Database version
CURRENT_VERSION = 3

ALL_MIGRATIONS = [
    {
        'version': 1,
        'migration': V1InitialSchema,
    },
    {
        'version': 2,
        'migration': V2AddCanvases,
    },
    {
        'version': 3,
        'migration': V3AddComfyWorkflow,
    },
]
class MigrationManager:
    def get_migrations_to_apply(self, current_version: int, target_version: int) -> List[Type[Migration]]:
        """Get list of migrations to apply"""
        return [m for m in ALL_MIGRATIONS
                if m['version'] > current_version and m['version'] <= target_version]

    def get_migrations_to_rollback(self, current_version: int, target_version: int) -> List[Type[Migration]]:
        """Get list of migrations to rollback"""
        return [m for m in reversed(ALL_MIGRATIONS)
                if m['version'] <= current_version and m['version'] > target_version]

    def migrate(self, conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
        """Apply or rollback migrations to reach target version"""
        if from_version < to_version:
            # Apply migrations forward
            print('🦄 Applying migrations forward', from_version, '->', to_version)
            migrations_to_apply = self.get_migrations_to_apply(from_version, to_version)
            print('🦄 Migrations to apply', migrations_to_apply)
            for migration in migrations_to_apply:
                migration_class = migration['migration']
                migration = migration_class()
                print(f"Applying migration {migration.version}: {migration.description}")
                migration.up(conn)
                conn.execute("UPDATE db_version SET version = ?", (migration.version,))
        # Do not do rollback migrations
        # else:
        #     # Rollback migrations
        #     print('🦄 Rolling back migrations', from_version, '->', to_version)
        #     migrations_to_rollback = self.get_migrations_to_rollback(from_version, to_version)
        #     print('🦄 Migrations to rollback', migrations_to_rollback)
        #     for migration_class in migrations_to_rollback:
        #         migration = migration_class()
        #         print(f"Rolling back migration {migration.version}: {migration.description}")
        #         migration.down(conn)
        #         conn.execute("UPDATE db_version SET version = ?", (migration.version - 1,)) 