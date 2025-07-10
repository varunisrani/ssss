# Jaaz AI Design Agent - Backend

This is the backend API server for the Jaaz AI Design Agent, built with FastAPI and Python.

## 🚀 Features

- **AI Image Generation & Editing** - Multiple AI models including Flux Kontext Pro
- **SVG Processing** - Convert images to SVG with text removal
- **Canvas Management** - Design canvas with real-time collaboration
- **WebSocket Support** - Real-time updates and communication
- **Tool System** - Extensible AI tool architecture

## 📁 Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── models/                 # Data models
├── routers/               # API endpoints
├── services/              # Business logic
├── tools/                 # AI model tools
├── utils/                 # Utilities
├── asset/                 # Configuration templates
└── user_data/             # User data and database
```

## 🛠 Setup & Installation

### Local Development

1. **Clone and navigate:**
```bash
cd backend
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. **Run the server:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

```bash
# Build and run with Docker
docker-compose up --build

# Or with plain Docker
docker build -t jaaz-backend .
docker run -p 8000:8000 jaaz-backend
```

## 🌐 Deployment Options

### 1. Render
- Connect your GitHub repository
- Use `render.yaml` configuration
- Set environment variables in Render dashboard

### 2. Railway
- Connect GitHub repository
- Railway will auto-detect Python and use `railway.json`
- Add environment variables in Railway dashboard

### 3. Fly.io
```bash
fly launch
fly deploy
```

### 4. Vercel (Serverless)
```bash
vercel --prod
```

## 🔧 Environment Variables

Required environment variables:

```env
# API Keys
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
REPLICATE_API_TOKEN=your_replicate_token
WRAKED_API_KEY=your_wraked_api_key
VOLCES_API_KEY=your_volces_api_key

# Database
DATABASE_URL=sqlite:///./user_data/localmanus.db

# Server
PORT=8000
HOST=0.0.0.0
```

## 📚 API Documentation

Once running, visit:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **ReDoc**: http://localhost:8000/redoc

## 🤖 Available AI Models

### Image Generation
- GPT Image 1 (OpenAI/Wraked)
- Imagen 4 (Wraked/Replicate)
- Flux Kontext Pro/Max (Wraked/Replicate)
- Recraft v3 (Wraked/Replicate)
- Ideogram V3 Turbo (Replicate)
- Seedream 3 (Replicate)

### Image Editing
- **Flux Kontext Dev** - Fast image editing
- **Flux Kontext Pro** - Professional image editing ✨ (NEW!)

### Video Generation
- Seedance v1 (Wraked/Volces)

## 🔌 WebSocket Endpoints

- `/ws` - Main WebSocket connection for real-time updates

## 📄 License

MIT License - see LICENSE file for details.

---

Built with ❤️ using FastAPI, Python, and cutting-edge AI models.