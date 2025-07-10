#!/usr/bin/env python3
"""
Supabase Integration Test Script
Tests all database operations to verify Supabase is working correctly
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Add the backend directory to the path so we can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.supabase_service import supabase_service
from services.db_service import db_service

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*50}")
    print(f"🧪 {test_name}")
    print(f"{'='*50}")

def print_success(message):
    """Print success message"""
    print(f"✅ {message}")

def print_error(message):
    """Print error message"""
    print(f"❌ {message}")

def print_info(message):
    """Print info message"""
    print(f"ℹ️  {message}")

async def test_supabase_direct():
    """Test Supabase service directly"""
    print_test_header("Direct Supabase Service Tests")
    
    try:
        # Test 1: Health Check
        print_info("Testing health check...")
        health = supabase_service.health_check()
        if health['status'] == 'healthy':
            print_success(f"Health check passed: {health}")
        else:
            print_error(f"Health check failed: {health}")
            return False
        
        # Test 2: Create Canvas
        print_info("Testing canvas creation...")
        canvas_id = f"test-canvas-{int(datetime.now().timestamp())}"
        canvas = supabase_service.create_canvas(
            canvas_id=canvas_id,
            name="Test Canvas",
            description="Test canvas for Supabase integration"
        )
        if canvas:
            print_success(f"Canvas created: {canvas['id']}")
        else:
            print_error("Failed to create canvas")
            return False
        
        # Test 3: Get Canvas
        print_info("Testing canvas retrieval...")
        retrieved_canvas = supabase_service.get_canvas(canvas_id)
        if retrieved_canvas and retrieved_canvas['id'] == canvas_id:
            print_success(f"Canvas retrieved: {retrieved_canvas['name']}")
        else:
            print_error("Failed to retrieve canvas")
            return False
        
        # Test 4: Update Canvas
        print_info("Testing canvas update...")
        updated_canvas = supabase_service.update_canvas(
            canvas_id=canvas_id,
            data={"elements": [{"type": "rectangle", "x": 100, "y": 100}]},
            thumbnail="data:image/png;base64,..."
        )
        if updated_canvas:
            print_success(f"Canvas updated: {updated_canvas['updated_at']}")
        else:
            print_error("Failed to update canvas")
            return False
        
        # Test 5: Create Chat Session
        print_info("Testing chat session creation...")
        session_id = f"test-session-{int(datetime.now().timestamp())}"
        session = supabase_service.create_chat_session(
            session_id=session_id,
            canvas_id=canvas_id,
            title="Test Chat Session",
            model="gpt-4o",
            provider="openai"
        )
        if session:
            print_success(f"Chat session created: {session['id']}")
        else:
            print_error("Failed to create chat session")
            return False
        
        # Test 6: Create Chat Messages
        print_info("Testing chat message creation...")
        messages = [
            {"role": "user", "content": "Hello, test message 1"},
            {"role": "assistant", "content": "Hello! This is a test response"}
        ]
        
        for msg in messages:
            message = supabase_service.create_chat_message(
                session_id=session_id,
                role=msg["role"],
                message=json.dumps(msg),
                metadata={"test": True}
            )
            if message:
                print_success(f"Message created: {msg['role']}")
            else:
                print_error(f"Failed to create message: {msg['role']}")
                return False
        
        # Test 7: Get Chat Messages
        print_info("Testing message retrieval...")
        retrieved_messages = supabase_service.get_chat_messages(session_id)
        if len(retrieved_messages) >= 2:
            print_success(f"Retrieved {len(retrieved_messages)} messages")
        else:
            print_error(f"Expected 2+ messages, got {len(retrieved_messages)}")
            return False
        
        # Test 8: Create ComfyUI Workflow
        print_info("Testing ComfyUI workflow creation...")
        workflow = supabase_service.create_comfy_workflow(
            name="Test Workflow",
            api_json=json.dumps({"test": "workflow"}),
            description="Test workflow for integration",
            inputs="test_input",
            outputs="test_output"
        )
        if workflow:
            print_success(f"Workflow created: {workflow['id']}")
            workflow_id = workflow['id']
        else:
            print_error("Failed to create workflow")
            return False
        
        # Test 9: List Operations
        print_info("Testing list operations...")
        canvases = supabase_service.list_canvases(limit=10)
        sessions = supabase_service.list_chat_sessions(canvas_id=canvas_id)
        workflows = supabase_service.list_comfy_workflows(limit=10)
        
        print_success(f"Found {len(canvases)} canvases")
        print_success(f"Found {len(sessions)} sessions for canvas")
        print_success(f"Found {len(workflows)} workflows")
        
        # Test 10: Get Statistics
        print_info("Testing statistics...")
        stats = supabase_service.get_stats()
        if 'canvases' in stats:
            print_success(f"Stats retrieved: {stats}")
        else:
            print_error(f"Failed to get stats: {stats}")
            return False
        
        # Test 11: Cleanup
        print_info("Testing cleanup (delete operations)...")
        
        # Delete workflow
        workflow_deleted = supabase_service.delete_comfy_workflow(workflow_id)
        if workflow_deleted:
            print_success("Workflow deleted")
        else:
            print_error("Failed to delete workflow")
        
        # Delete canvas (this should cascade delete session and messages)
        canvas_deleted = supabase_service.delete_canvas(canvas_id)
        if canvas_deleted:
            print_success("Canvas deleted (cascade should delete session and messages)")
        else:
            print_error("Failed to delete canvas")
        
        print_success("All direct Supabase tests passed! 🎉")
        return True
        
    except Exception as e:
        print_error(f"Direct Supabase test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_db_service_integration():
    """Test database service with Supabase integration"""
    print_test_header("Database Service Integration Tests")
    
    try:
        # Verify we're using Supabase
        if not db_service.use_supabase:
            print_error("Database service is not configured to use Supabase")
            print_info("Make sure USE_SUPABASE=true in your environment")
            return False
        
        print_success("Database service is configured to use Supabase")
        
        # Test 1: Create Canvas via DB Service
        print_info("Testing canvas creation via db_service...")
        canvas_id = f"db-test-canvas-{int(datetime.now().timestamp())}"
        await db_service.create_canvas(canvas_id, "DB Service Test Canvas")
        print_success("Canvas created via db_service")
        
        # Test 2: List Canvases
        print_info("Testing canvas listing...")
        canvases = await db_service.list_canvases()
        if any(c['id'] == canvas_id for c in canvases):
            print_success(f"Canvas found in list ({len(canvases)} total canvases)")
        else:
            print_error("Canvas not found in list")
            return False
        
        # Test 3: Create Chat Session
        print_info("Testing chat session creation...")
        session_id = f"db-test-session-{int(datetime.now().timestamp())}"
        await db_service.create_chat_session(
            id=session_id,
            model="gpt-4o",
            provider="openai",
            canvas_id=canvas_id,
            title="DB Service Test Session"
        )
        print_success("Chat session created via db_service")
        
        # Test 4: Create Messages
        print_info("Testing message creation...")
        test_messages = [
            {"role": "user", "content": "Test message from db_service"},
            {"role": "assistant", "content": "Response from db_service test"}
        ]
        
        for msg in test_messages:
            await db_service.create_message(session_id, msg["role"], json.dumps(msg))
        print_success("Messages created via db_service")
        
        # Test 5: Get Chat History
        print_info("Testing chat history retrieval...")
        history = await db_service.get_chat_history(session_id)
        if len(history) >= 2:
            print_success(f"Chat history retrieved: {len(history)} messages")
        else:
            print_error(f"Expected 2+ messages in history, got {len(history)}")
            return False
        
        # Test 6: Save Canvas Data
        print_info("Testing canvas data save...")
        test_canvas_data = {
            "elements": [
                {"type": "rectangle", "x": 50, "y": 50, "width": 100, "height": 100}
            ],
            "version": "1.0"
        }
        await db_service.save_canvas_data(canvas_id, json.dumps(test_canvas_data), "test_thumbnail")
        print_success("Canvas data saved via db_service")
        
        # Test 7: Get Canvas Data
        print_info("Testing canvas data retrieval...")
        canvas_data = await db_service.get_canvas_data(canvas_id)
        if canvas_data and 'data' in canvas_data and 'elements' in canvas_data['data']:
            print_success(f"Canvas data retrieved: {len(canvas_data['data']['elements'])} elements")
        else:
            print_error("Failed to retrieve canvas data")
            return False
        
        # Test 8: List Sessions
        print_info("Testing session listing...")
        sessions = await db_service.list_sessions(canvas_id)
        if any(s['id'] == session_id for s in sessions):
            print_success(f"Session found in list ({len(sessions)} total sessions)")
        else:
            print_error("Session not found in list")
            return False
        
        # Test 9: ComfyUI Workflow Tests
        print_info("Testing ComfyUI workflow operations...")
        await db_service.create_comfy_workflow(
            name="DB Service Test Workflow",
            api_json=json.dumps({"nodes": {}, "links": []}),
            description="Test workflow from db_service",
            inputs="test_input",
            outputs="test_output"
        )
        
        workflows = await db_service.list_comfy_workflows()
        if workflows:
            print_success(f"ComfyUI workflows: {len(workflows)} found")
            # Test get workflow
            first_workflow = workflows[0]
            workflow_data = await db_service.get_comfy_workflow(first_workflow['id'])
            if workflow_data:
                print_success("ComfyUI workflow data retrieved")
                # Cleanup
                await db_service.delete_comfy_workflow(first_workflow['id'])
                print_success("ComfyUI workflow deleted")
        else:
            print_error("No ComfyUI workflows found")
            return False
        
        # Test 10: Cleanup
        print_info("Testing cleanup operations...")
        await db_service.delete_canvas(canvas_id)
        print_success("Canvas deleted via db_service")
        
        print_success("All database service integration tests passed! 🎉")
        return True
        
    except Exception as e:
        print_error(f"Database service integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print_test_header("Supabase Integration Test Suite")
    print_info("Testing Supabase integration for Jaaz AI Design Agent")
    print_info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Check environment
    print_info("Checking environment variables...")
    required_env_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]
    optional_env_vars = ["SUPABASE_SERVICE_ROLE_KEY", "USE_SUPABASE"]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
        else:
            print_success(f"{var} is set")
    
    for var in optional_env_vars:
        if os.getenv(var):
            print_success(f"{var} is set")
        else:
            print_info(f"{var} is not set (optional)")
    
    if missing_vars:
        print_error(f"Missing required environment variables: {missing_vars}")
        print_info("Please set these in your .env file or environment")
        return False
    
    # Run tests
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Direct Supabase Service
    if await test_supabase_direct():
        tests_passed += 1
    
    # Test 2: Database Service Integration
    if await test_db_service_integration():
        tests_passed += 1
    
    # Final Results
    print_test_header("Test Results Summary")
    print_info(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print_success("🎉 All tests passed! Your Supabase integration is working correctly.")
        print_info("You can now:")
        print_info("  1. Set USE_SUPABASE=true in your .env file")
        print_info("  2. Start your FastAPI server: uvicorn main:app --reload")
        print_info("  3. Test your API endpoints")
        print_info("  4. Deploy to production with Supabase configuration")
        return True
    else:
        print_error("❌ Some tests failed. Please check the errors above and fix them.")
        print_info("Common issues:")
        print_info("  1. Incorrect Supabase URL or API keys")
        print_info("  2. Database schema not created (run the SQL from the migration guide)")
        print_info("  3. Network connectivity issues")
        print_info("  4. Row Level Security policies blocking operations")
        return False

if __name__ == "__main__":
    asyncio.run(main())