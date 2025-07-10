import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
import aiosqlite
from .config_service import USER_DATA_DIR
from .migrations.manager import MigrationManager, CURRENT_VERSION
from .supabase_service import supabase_service
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(USER_DATA_DIR, "localmanus.db")

class DatabaseService:
    def __init__(self):
        # Check if we should use Supabase
        self.use_supabase = os.getenv("USE_SUPABASE", "false").lower() == "true"
        
        if not self.use_supabase:
            # Initialize SQLite as before
            self.db_path = DB_PATH
            self._ensure_db_directory()
            self._migration_manager = MigrationManager()
            self._init_db()

    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _init_db(self):
        """Initialize the database with the current schema"""
        with sqlite3.connect(self.db_path) as conn:
            # Create version table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            # Get current version
            cursor = conn.execute("SELECT version FROM db_version")
            current_version = cursor.fetchone()
            print('local db version', current_version, 'latest version', CURRENT_VERSION)
            
            if current_version is None:
                # First time setup - start from version 0
                conn.execute("INSERT INTO db_version (version) VALUES (0)")
                self._migration_manager.migrate(conn, 0, CURRENT_VERSION)
            elif current_version[0] < CURRENT_VERSION:
                print('Migrating database from version', current_version[0], 'to', CURRENT_VERSION)
                # Need to migrate
                self._migration_manager.migrate(conn, current_version[0], CURRENT_VERSION)

    async def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        if self.use_supabase:
            return supabase_service.create_canvas(id, name)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO canvases (id, name)
                    VALUES (?, ?)
                """, (id, name))
                await db.commit()

    async def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        if self.use_supabase:
            return supabase_service.list_canvases()
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                cursor = await db.execute("""
                    SELECT id, name, description, thumbnail, created_at, updated_at
                    FROM canvases
                    ORDER BY updated_at DESC
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        if self.use_supabase:
            return supabase_service.create_chat_session(id, canvas_id, title, model, provider)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO chat_sessions (id, model, provider, canvas_id, title)
                    VALUES (?, ?, ?, ?, ?)
                """, (id, model, provider, canvas_id, title))
                await db.commit()

    async def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        if self.use_supabase:
            return supabase_service.create_chat_message(session_id, role, message)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO chat_messages (session_id, role, message)
                    VALUES (?, ?, ?)
                """, (session_id, role, message))
                await db.commit()

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        if self.use_supabase:
            messages_data = supabase_service.get_chat_messages(session_id)
            messages = []
            for row in messages_data:
                if row.get('message'):
                    try:
                        msg = json.loads(row['message'])
                        messages.append(msg)
                    except:
                        pass
            return messages
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                cursor = await db.execute("""
                    SELECT role, message, id
                    FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                """, (session_id,))
                rows = await cursor.fetchall()
                
                messages = []
                for row in rows:
                    row_dict = dict(row)
                    if row_dict['message']:
                        try:
                            msg = json.loads(row_dict['message'])
                            messages.append(msg)
                        except:
                            pass
                    
                return messages

    async def list_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """List all chat sessions"""
        if self.use_supabase:
            return supabase_service.list_chat_sessions(canvas_id=canvas_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                if canvas_id:
                    cursor = await db.execute("""
                        SELECT id, title, model, provider, created_at, updated_at
                        FROM chat_sessions
                        WHERE canvas_id = ?
                        ORDER BY updated_at DESC
                    """, (canvas_id,))
                else:
                    cursor = await db.execute("""
                        SELECT id, title, model, provider, created_at, updated_at
                        FROM chat_sessions
                        ORDER BY updated_at DESC
                    """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def create_session(self, session_id: str, canvas_id: str, title: str, model: str, provider: str):
        """Create a new chat session"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO chat_sessions (id, canvas_id, title, model, provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'), STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """, (session_id, canvas_id, title, model, provider))
            await db.commit()

    async def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        if self.use_supabase:
            return supabase_service.update_canvas(id, data=json.loads(data) if isinstance(data, str) else data, thumbnail=thumbnail)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE canvases 
                    SET data = ?, thumbnail = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE id = ?
                """, (data, thumbnail, id))
                await db.commit()

    async def get_canvas_data(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas data"""
        if self.use_supabase:
            canvas = supabase_service.get_canvas(id)
            if canvas:
                sessions = await self.list_sessions(id)
                return {
                    'data': canvas.get('data', {}),
                    'name': canvas.get('name', ''),
                    'sessions': sessions
                }
            return None
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                cursor = await db.execute("""
                    SELECT data, name
                    FROM canvases
                    WHERE id = ?
                """, (id,))
                row = await cursor.fetchone()

                sessions = await self.list_sessions(id)
                
                if row:
                    return {
                        'data': json.loads(row['data']) if row['data'] else {},
                        'name': row['name'],
                        'sessions': sessions
                    }
                return None

    async def delete_canvas(self, id: str):
        """Delete canvas and related data"""
        if self.use_supabase:
            return supabase_service.delete_canvas(id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM canvases WHERE id = ?", (id,))
                await db.commit()

    async def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        if self.use_supabase:
            return supabase_service.update_canvas(id, name=name)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("UPDATE canvases SET name = ? WHERE id = ?", (name, id))
                await db.commit()

    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        if self.use_supabase:
            return supabase_service.create_comfy_workflow(name, api_json, description, inputs, outputs)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO comfy_workflows (name, api_json, description, inputs, outputs)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, api_json, description, inputs, outputs))
                await db.commit()

    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        if self.use_supabase:
            return supabase_service.list_comfy_workflows()
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                cursor = await db.execute("SELECT id, name, description, api_json, inputs, outputs FROM comfy_workflows ORDER BY id DESC")
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        if self.use_supabase:
            return supabase_service.delete_comfy_workflow(id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM comfy_workflows WHERE id = ?", (id,))
                await db.commit()

    async def get_comfy_workflow(self, id: int):
        """Get comfy workflow dict"""
        if self.use_supabase:
            workflow = supabase_service.get_comfy_workflow(id)
            if workflow and workflow.get('api_json'):
                try:
                    workflow_json = (
                        workflow["api_json"]
                        if isinstance(workflow["api_json"], dict)
                        else json.loads(workflow["api_json"])
                    )
                    return workflow_json
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Stored workflow api_json is not valid JSON: {exc}")
            return None
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                cursor = await db.execute(
                    "SELECT api_json FROM comfy_workflows WHERE id = ?", (id,)
                )
                row = await cursor.fetchone()
            try:
                workflow_json = (
                    row["api_json"]
                    if isinstance(row["api_json"], dict)
                    else json.loads(row["api_json"])
                )
                return workflow_json
            except json.JSONDecodeError as exc:
                raise ValueError(f"Stored workflow api_json is not valid JSON: {exc}")

# Create a singleton instance
db_service = DatabaseService()
