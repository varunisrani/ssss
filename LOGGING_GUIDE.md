# 🗄️ Supabase Database Logging Guide

## 📋 Overview

Complete logging system has been implemented to track all database operations between the frontend and Supabase backend.

## 🎯 What Gets Logged

### 1. **Backend Database Operations** (Supabase Service)
- ✅ **Canvas Operations**: Create, Read, Update, Delete, List
- ✅ **Chat Session Operations**: Create, Read, Update, List
- ✅ **Chat Message Operations**: Create, Read, List
- ✅ **ComfyUI Workflow Operations**: Create, Read, Update, Delete, List
- ✅ **Health Checks & Statistics**

### 2. **Frontend API Requests** (React App)
- ✅ **Canvas API**: List, Create, Get, Save, Rename, Delete
- ✅ **Chat API**: Get session, Send messages, Cancel chat
- ✅ **Session API**: Create chat sessions

### 3. **Real-time Events** (WebSocket)
- ✅ **Connection Events**: Connect, disconnect, errors
- ✅ **Session Updates**: All real-time chat events
- ✅ **Image/Video Generation**: Tool call results
- ✅ **Message Updates**: Real-time message streams

## 🔍 Log Format Examples

### Backend Supabase Logs
```
🗄️  SUPABASE [14:23:45.123] CREATE
   📋 Table: canvases
   📊 canvas_id: test-canvas-123
   📊 name: My New Canvas
   📊 description: Test canvas
   ──────────────────────────────────────────────

🗄️  SUPABASE [14:23:45.456] CREATE CANVAS - ✅ SUCCESS
   📋 Result: {
     "id": "test-canvas-123",
     "name": "My New Canvas",
     "created_at": "2025-07-10T14:23:45.456Z"
   }
   ──────────────────────────────────────────────
```

### Frontend API Logs
```
🗄️ DATABASE [14:23:44.987] CREATE
📋 Table: canvases
📊 canvas_id: test-canvas-123
📊 name: My New Canvas
📊 messages_count: 2
📊 model: openai/gpt-4o
────────────────────────────────────────────────────────────

🌐 FRONTEND API [14:23:45.001] CREATE_CANVAS
📡 POST /api/canvas/create
📦 Request Body:
{
  "name": "My New Canvas",
  "canvas_id": "test-canvas-123",
  "messages": [...]
}
────────────────────────────────────────────────────────────

🌐 FRONTEND API [14:23:45.456] CREATE_CANVAS - ✅ SUCCESS (455ms)
📋 Response:
{
  "id": "test-canvas-123",
  "status": "success"
}
────────────────────────────────────────────────────────────
```

### WebSocket Real-time Logs
```
🗄️ DATABASE [14:23:46.123] REALTIME_EVENT
📋 Table: chat_sessions
📊 session_id: session-456
📊 event_type: ImageGenerated
📊 timestamp: 2025-07-10T14:23:46.123Z
📊 has_data: true
────────────────────────────────────────────────────────────

🗄️ DATABASE [14:23:46.124] IMAGE_GENERATED
📋 Table: chat_messages
📊 session_id: session-456
📊 image_url: https://example.com/image.jpg
📊 tool_name: generate_image_by_flux_kontext_pro
────────────────────────────────────────────────────────────
```

## 🚀 How to Monitor

### 1. **Backend Console**
Start your server and watch the console:
```bash
cd backend
export USE_SUPABASE=true
uvicorn main:app --reload
```

### 2. **Frontend Console**
Open browser DevTools → Console tab and use your app normally.

### 3. **Common Database Operations to Test**

#### Test Canvas Operations:
1. **Create Canvas**: Home page → "New Canvas"
2. **List Canvases**: Home page load
3. **Get Canvas**: Click on any canvas
4. **Save Canvas**: Make changes and save
5. **Delete Canvas**: Right-click → Delete

#### Test Chat Operations:
1. **Create Session**: Start a new chat
2. **Send Messages**: Type and send messages
3. **Get Messages**: Load chat history

#### Test Real-time:
1. **Image Generation**: Ask AI to generate an image
2. **Video Generation**: Ask AI to generate a video
3. **Tool Calls**: Use any AI tool

## 📊 Log Categories

### 🟢 Success Indicators
- ✅ **SUCCESS**: Operation completed successfully
- 📈 **Records**: Number of records returned
- 📋 **Result**: Actual data returned

### 🔴 Error Indicators
- ❌ **ERROR**: Operation failed
- ⚠️ **Error**: Error message details
- 🔌 **Disconnect**: Connection issues

### 🔵 Info Indicators
- 📋 **Table**: Database table involved
- 📊 **Details**: Operation parameters
- 🕐 **Timestamp**: When operation occurred
- ⏱️ **Duration**: How long it took (frontend only)

## 🎯 Benefits

1. **🐛 Debug Issues**: See exactly what database operations fail
2. **📈 Performance**: Monitor response times and data sizes
3. **🔄 Real-time**: Track WebSocket events and data flow
4. **🛡️ Security**: Monitor all data access patterns
5. **📊 Analytics**: Understand user behavior and usage patterns

## 🛠️ Customization

### Enable/Disable Logging
```typescript
// In frontend code, you can conditionally enable logging:
if (process.env.NODE_ENV === 'development') {
  ApiLogger.logDatabaseOperation('CREATE', 'canvases', data);
}
```

### Filter Logs
```javascript
// In browser console, filter logs:
// Show only database operations:
console.clear();
// Then look for logs starting with 🗄️ or 🌐
```

## 🎉 Result

Now you can see **every single database interaction** between your frontend and Supabase in real-time, making debugging and monitoring incredibly easy!