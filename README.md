# POE OpenAI Wrapper

A local OpenAI-compatible API server wrapping the [POE.com](https://poe.com) API, allowing you to seamlessly integrate POE’s AI models with your IDEs (like Xcode or Cursor) through a familiar OpenAI API interface.

## What This Wrapper Does

* **Wraps POE API**: Translates OpenAI-compatible requests to POE-compatible calls.
* **OpenAI Compatible**: Integrates with any app expecting the OpenAI API format.
* **Local & Public Access**: Provides both localhost and secure public access via Cloudflare Tunnel.
* **File Support**: Manages file uploads and multimodal conversations.
* **Zero Configuration Tunneling**: Random URLs work without any account.
* **Custom Domain Support**: Use your own domain for permanent URLs.

## Required API Keys

1. **POE API Key**: Obtain from [https://poe.com/api\_key](https://poe.com/api_key)
2. **Cloudflare Tunnel Token** (Optional): Only needed if you want a custom domain instead of random URLs

## Quick Setup

Just run:

```bash
./setup.sh
```

The script handles everything automatically:

1. **Validates environment** - Checks for Python, Docker, and Docker Compose
2. **Collects credentials** - Prompts for POE API key if needed
3. **Generates secure API key** - Creates a strong LOCAL_API_KEY automatically
4. **Optional custom domain** - Asks if you want to use your own domain
5. **Starts services** - Launches everything with the right configuration
6. **Shows your URLs** - Displays both local and public endpoints

## Tunneling Options

### Option 1: Random URL (Default)
- **URL**: `https://random-name.trycloudflare.com`
- **Cost**: FREE
- **Requirements**: None
- **Note**: URL changes on each restart

### Option 2: Custom Domain
- **URL**: `https://poeapiwrapper.example.com` (your subdomain)
- **Cost**: FREE (subdomains don't cost extra)
- **Requirements**: Cloudflare account + domain
- **Benefit**: Permanent URL that never changes

## Custom Domain Setup

If you choose custom domain during `./setup.sh`, follow these steps:

1. **Create Cloudflare Tunnel**
   - Go to [https://one.dash.cloudflare.com/](https://one.dash.cloudflare.com/)
   - Navigate to **Networks** → **Tunnels** → **Create a tunnel**
   - Select **Cloudflared** → Name your tunnel → **Save tunnel**

2. **Configure Public Hostname**
   - Click **Configure** → **Public Hostname**
   - **Subdomain**: Enter desired name (e.g., `poeapiwrapper`)
   - **Domain**: Select your domain
   - **Service**: HTTP → `poe-wrapper:8000`
   - Click **Save**

3. **Get Token**
   - Go back to tunnel overview
   - Find the Docker run command
   - Copy the token (long string after `--token`)

4. **Use in Setup**
   - When prompted, enter full subdomain (e.g., `poeapiwrapper.example.com`)
   - Paste the token

## IDE Configuration

### Xcode Configuration

* **Host URL**: `http://localhost:8000`
* **API Token**: Your auto-generated `LOCAL_API_KEY`
* **Header**: `x-api-key`

### Cursor IDE Configuration

* **Host URL**: Your Cloudflare tunnel URL
  - Random: `https://random-name.trycloudflare.com`
  - Custom: `https://poeapiwrapper.example.com`
* **API Token**: Your auto-generated `LOCAL_API_KEY`

## Available API Endpoints

### Core Endpoints
* `GET /v1/models` – List available models
* `POST /v1/chat/completions` – Chat completions with streaming, tools, and attachments
* `POST /v1/completions` – Legacy text completions
* `POST /v1/embeddings` – Generate embeddings (simulated)
* `POST /v1/moderations` – Content moderation

### Image Generation
* `POST /v1/images/generations` – Generate images from text
* `POST /v1/images/edits` – Edit images with prompts
* `POST /v1/images/variations` – Create image variations

### File Management
* `GET /v1/files` – List uploaded files
* `POST /v1/files/upload` – Upload files
* `GET /v1/files/{file_id}` – Get file details
* `DELETE /v1/files/{file_id}` – Delete a file

### Assistants API (Beta)
* `/v1/assistants` – Manage assistants
* `/v1/threads` – Manage conversation threads
* `/v1/threads/{thread_id}/messages` – Thread messages
* `/v1/threads/{thread_id}/runs` – Execute assistant runs

## Important: Real vs Simulated Features

### 🟢 Real Features (Native Poe Support)
- Chat completions with streaming
- Temperature control  
- Stop sequences
- File/image uploads (including base64)
- Image generation (DALL-E-3, Stable Diffusion)
- Function calling (native for GPT, Claude, Llama, DeepSeek, Grok, Perplexity, Qwen models; XML fallback for others)

### 🟡 Simulated Features (Workarounds)
- **max_tokens**: Via system prompts
- **response_format**: JSON mode via prompts
- **Image editing**: Creates new images instead

### 🔴 Fake Features (Not Real)
- **Embeddings**: LLM-generated vectors (won't work for RAG/similarity)
- **Moderations**: LLM analysis (not a safety system)
- **Token counting**: Word-based estimates
- **Assistants API**: In-memory only (data lost on restart)

### ❌ Ignored Parameters
`n`, `presence_penalty`, `frequency_penalty`, `top_p`, `seed`, `logit_bias`

## Model Support

All Poe models are available with OpenAI-compatible names:

**Image-Capable Models:**
- `gpt-4o`, `gpt-image-1` → Can generate and analyze images

## Useful Docker Commands

```bash
# Start Docker services
cd docker && docker-compose up --build -d  

# View service logs  
cd docker && docker-compose logs -f poe-wrapper

# Restart Docker services
cd docker && docker-compose restart

# Stop Docker services
cd docker && docker-compose down

# Retrieve Cloudflare tunnel URL
python scripts/get_cloudflare_url.py
```

## Access URLs

After setup completion:

* **Local API**: `http://localhost:8000/v1`
* **Public API**: 
  - Random: `https://random-name.trycloudflare.com/v1` (changes on restart)
  - Custom: `https://poeapiwrapper.example.com/v1` (permanent)
* **API Documentation**: `http://localhost:8000/docs`

## Prerequisites

* Python **3.12+**
* Docker & Docker Compose
* Active internet connection

## Quick Start for Developers

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-local-api-key",
    base_url="http://localhost:8000/v1"
)

# Basic chat
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)

# With image
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]
    }]
)

# Function calling
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's the weather?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather info",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"]
            }
        }
    }]
)
```

## Troubleshooting

### Common Issues

1. **URL changes on restart** (Random URLs)
   - This is normal behavior for free tunnels
   - Use `python scripts/get_cloudflare_url.py` to get the new URL
   - Consider using a custom domain for permanent URLs

2. **Authentication errors**
   - Verify your POE_API_KEY is correct
   - Check LOCAL_API_KEY in requests
   - Ensure x-api-key header is set

3. **Model not found**
   - Run `GET /v1/models` to see available models
   - Use exact model names from the list

4. **Image generation issues**
   - Ensure you're using image models (dall-e-3, stable-diffusion-xl, etc.)
   - Check response format parameter (url or b64_json)

### Logs
```bash
# View application logs
cd docker && docker-compose logs -f poe-wrapper

# Check specific log files
tail -f logs/app.log
tail -f logs/startup.log
```

## Contributing

Pull requests are welcome! Please ensure:
- Code follows existing patterns
- New features include documentation
- Tests pass (when available)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

`This project is not affiliated with, endorsed by, or sponsored by Poe.com or OpenAI. It is intended for educational and personal use. Users are responsible for complying with the Terms of Service of Poe.com and any other services they connect to via this wrapper. Use at your own discretion.`

---
