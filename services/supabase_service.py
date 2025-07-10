"""
Supabase Database Service
Handles all database operations using Supabase PostgreSQL
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class DatabaseLogger:
    """Console logger for database operations"""
    
    @staticmethod
    def log_operation(operation: str, table: str, details: Dict[str, Any] = None):
        """Log database operation with details"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"\n🗄️  SUPABASE [{timestamp}] {operation.upper()}")
        print(f"   📋 Table: {table}")
        if details:
            for key, value in details.items():
                if isinstance(value, (dict, list)):
                    print(f"   📊 {key}: {json.dumps(value, indent=2)}")
                else:
                    print(f"   📊 {key}: {value}")
        print(f"   {'─' * 50}")
    
    @staticmethod
    def log_result(success: bool, operation: str, result: Any = None, error: str = None):
        """Log operation result"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        status = "✅ SUCCESS" if success else "❌ ERROR"
        print(f"🗄️  SUPABASE [{timestamp}] {operation.upper()} - {status}")
        
        if success and result:
            if isinstance(result, list):
                print(f"   📈 Records: {len(result)}")
                if result and isinstance(result[0], dict):
                    print(f"   📋 Sample: {json.dumps(result[0], indent=2)}")
            elif isinstance(result, dict):
                print(f"   📋 Result: {json.dumps(result, indent=2)}")
            else:
                print(f"   📋 Result: {result}")
        elif error:
            print(f"   ⚠️  Error: {error}")
        print(f"   {'─' * 50}\n")

class SupabaseService:
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not all([self.supabase_url, self.supabase_anon_key]):
            raise ValueError("Missing required Supabase configuration. Check SUPABASE_URL and SUPABASE_ANON_KEY environment variables.")
        
        # Use service role key for backend operations (bypasses RLS)
        key_to_use = self.supabase_service_key if self.supabase_service_key else self.supabase_anon_key
        self.supabase: Client = create_client(self.supabase_url, key_to_use)

    # =============================================
    # CANVAS OPERATIONS
    # =============================================
    
    def create_canvas(self, canvas_id: str, name: str, description: str = "", thumbnail: str = "") -> Dict[str, Any]:
        """Create a new canvas"""
        canvas_data = {
            "id": canvas_id,
            "name": name,
            "data": {},
            "description": description,
            "thumbnail": thumbnail
        }
        
        DatabaseLogger.log_operation("CREATE", "canvases", {
            "canvas_id": canvas_id,
            "name": name,
            "description": description,
            "thumbnail": thumbnail[:50] + "..." if len(thumbnail) > 50 else thumbnail
        })
        
        try:
            result = self.supabase.table("canvases").insert(canvas_data).execute()
            success_result = result.data[0] if result.data else None
            DatabaseLogger.log_result(True, "CREATE CANVAS", success_result)
            return success_result
        except Exception as e:
            DatabaseLogger.log_result(False, "CREATE CANVAS", error=str(e))
            raise

    def get_canvas(self, canvas_id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        DatabaseLogger.log_operation("GET", "canvases", {"canvas_id": canvas_id})
        
        try:
            result = self.supabase.table("canvases").select("*").eq("id", canvas_id).execute()
            success_result = result.data[0] if result.data else None
            DatabaseLogger.log_result(True, "GET CANVAS", success_result)
            return success_result
        except Exception as e:
            DatabaseLogger.log_result(False, "GET CANVAS", error=str(e))
            raise

    def update_canvas(self, canvas_id: str, **kwargs) -> Dict[str, Any]:
        """Update canvas data"""
        update_data = {k: v for k, v in kwargs.items() if k in ["name", "data", "description", "thumbnail"]}
        update_data["updated_at"] = datetime.now().isoformat()
        
        result = self.supabase.table("canvases").update(update_data).eq("id", canvas_id).execute()
        return result.data[0] if result.data else None

    def list_canvases(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all canvases"""
        DatabaseLogger.log_operation("LIST", "canvases", {"limit": limit, "offset": offset})
        
        try:
            result = self.supabase.table("canvases")\
                .select("*")\
                .order("updated_at", desc=True)\
                .range(offset, offset + limit - 1)\
                .execute()
            success_result = result.data or []
            DatabaseLogger.log_result(True, "LIST CANVASES", success_result)
            return success_result
        except Exception as e:
            DatabaseLogger.log_result(False, "LIST CANVASES", error=str(e))
            raise

    def delete_canvas(self, canvas_id: str) -> bool:
        """Delete canvas and all associated data"""
        result = self.supabase.table("canvases").delete().eq("id", canvas_id).execute()
        return len(result.data) > 0

    # =============================================
    # CHAT SESSION OPERATIONS
    # =============================================
    
    def create_chat_session(self, session_id: str, canvas_id: str, title: str = None, model: str = None, provider: str = None) -> Dict[str, Any]:
        """Create a new chat session"""
        session_data = {
            "id": session_id,
            "canvas_id": canvas_id,
            "title": title,
            "model": model,
            "provider": provider
        }
        
        DatabaseLogger.log_operation("CREATE", "chat_sessions", {
            "session_id": session_id,
            "canvas_id": canvas_id,
            "title": title,
            "model": model,
            "provider": provider
        })
        
        try:
            result = self.supabase.table("chat_sessions").insert(session_data).execute()
            success_result = result.data[0] if result.data else None
            DatabaseLogger.log_result(True, "CREATE CHAT SESSION", success_result)
            return success_result
        except Exception as e:
            DatabaseLogger.log_result(False, "CREATE CHAT SESSION", error=str(e))
            raise

    def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        result = self.supabase.table("chat_sessions").select("*").eq("id", session_id).execute()
        return result.data[0] if result.data else None

    def update_chat_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """Update chat session"""
        update_data = {k: v for k, v in kwargs.items() if k in ["title", "model", "provider", "canvas_id"]}
        update_data["updated_at"] = datetime.now().isoformat()
        
        result = self.supabase.table("chat_sessions").update(update_data).eq("id", session_id).execute()
        return result.data[0] if result.data else None

    def list_chat_sessions(self, canvas_id: str = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List chat sessions, optionally filtered by canvas"""
        query = self.supabase.table("chat_sessions").select("*")
        
        if canvas_id:
            query = query.eq("canvas_id", canvas_id)
        
        result = query.order("updated_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        return result.data or []

    def delete_chat_session(self, session_id: str) -> bool:
        """Delete chat session and all messages"""
        result = self.supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        return len(result.data) > 0

    # =============================================
    # CHAT MESSAGE OPERATIONS
    # =============================================
    
    def create_chat_message(self, session_id: str, role: str, message: str, metadata: Dict = None) -> Dict[str, Any]:
        """Create a new chat message"""
        message_data = {
            "session_id": session_id,
            "role": role,
            "message": message
        }
        
        DatabaseLogger.log_operation("CREATE", "chat_messages", {
            "session_id": session_id,
            "role": role,
            "message_preview": message[:100] + "..." if len(message) > 100 else message
        })
        
        try:
            result = self.supabase.table("chat_messages").insert(message_data).execute()
            success_result = result.data[0] if result.data else None
            DatabaseLogger.log_result(True, "CREATE CHAT MESSAGE", success_result)
            return success_result
        except Exception as e:
            DatabaseLogger.log_result(False, "CREATE CHAT MESSAGE", error=str(e))
            raise

    def get_chat_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        DatabaseLogger.log_operation("GET", "chat_messages", {
            "session_id": session_id,
            "limit": limit,
            "offset": offset
        })
        
        try:
            result = self.supabase.table("chat_messages")\
                .select("*")\
                .eq("session_id", session_id)\
                .order("created_at", desc=False)\
                .range(offset, offset + limit - 1)\
                .execute()
            success_result = result.data or []
            DatabaseLogger.log_result(True, "GET CHAT MESSAGES", success_result)
            return success_result
        except Exception as e:
            DatabaseLogger.log_result(False, "GET CHAT MESSAGES", error=str(e))
            raise

    def update_chat_message(self, message_id: int, message: str, metadata: Dict = None) -> Dict[str, Any]:
        """Update a chat message"""
        update_data = {
            "message": message,
            "updated_at": datetime.now().isoformat()
        }
        
        result = self.supabase.table("chat_messages").update(update_data).eq("id", message_id).execute()
        return result.data[0] if result.data else None

    def delete_chat_message(self, message_id: int) -> bool:
        """Delete a chat message"""
        result = self.supabase.table("chat_messages").delete().eq("id", message_id).execute()
        return len(result.data) > 0

    # =============================================
    # COMFY WORKFLOW OPERATIONS
    # =============================================
    
    def create_comfy_workflow(self, name: str, api_json: str = None, description: str = "", inputs: str = None, outputs: str = None) -> Dict[str, Any]:
        """Create a new ComfyUI workflow"""
        workflow_data = {
            "name": name,
            "api_json": api_json,
            "description": description,
            "inputs": inputs,
            "outputs": outputs
        }
        
        result = self.supabase.table("comfy_workflows").insert(workflow_data).execute()
        return result.data[0] if result.data else None

    def get_comfy_workflow(self, workflow_id: int) -> Optional[Dict[str, Any]]:
        """Get ComfyUI workflow by ID"""
        result = self.supabase.table("comfy_workflows").select("*").eq("id", workflow_id).execute()
        return result.data[0] if result.data else None

    def list_comfy_workflows(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all ComfyUI workflows"""
        result = self.supabase.table("comfy_workflows")\
            .select("*")\
            .order("updated_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        return result.data or []

    def update_comfy_workflow(self, workflow_id: int, **kwargs) -> Dict[str, Any]:
        """Update ComfyUI workflow"""
        update_data = {k: v for k, v in kwargs.items() if k in ["name", "api_json", "description", "inputs", "outputs"]}
        update_data["updated_at"] = datetime.now().isoformat()
        
        result = self.supabase.table("comfy_workflows").update(update_data).eq("id", workflow_id).execute()
        return result.data[0] if result.data else None

    def delete_comfy_workflow(self, workflow_id: int) -> bool:
        """Delete ComfyUI workflow"""
        result = self.supabase.table("comfy_workflows").delete().eq("id", workflow_id).execute()
        return len(result.data) > 0

    # =============================================
    # UTILITY METHODS
    # =============================================
    
    def health_check(self) -> Dict[str, Any]:
        """Check Supabase connection health"""
        try:
            # Simple query to test connection
            result = self.supabase.table("canvases").select("id").limit(1).execute()
            return {
                "status": "healthy",
                "database": "supabase",
                "timestamp": datetime.now().isoformat(),
                "tables_accessible": True
            }
        except Exception as e:
            return {
                "status": "error",
                "database": "supabase",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            canvases_count = len(self.supabase.table("canvases").select("id").execute().data)
            sessions_count = len(self.supabase.table("chat_sessions").select("id").execute().data)
            messages_count = len(self.supabase.table("chat_messages").select("id").execute().data)
            workflows_count = len(self.supabase.table("comfy_workflows").select("id").execute().data)
            
            return {
                "canvases": canvases_count,
                "chat_sessions": sessions_count,
                "chat_messages": messages_count,
                "comfy_workflows": workflows_count,
                "database": "supabase",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "error": str(e),
                "database": "supabase",
                "timestamp": datetime.now().isoformat()
            }

# Global instance
supabase_service = SupabaseService()