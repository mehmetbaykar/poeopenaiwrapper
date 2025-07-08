# POE OpenAI Wrapper

A local OpenAI-compatible API server wrapping the [POE.com](https://poe.com) API, allowing you to seamlessly integrate POE’s AI models with your IDEs (like Xcode or Cursor) through a familiar OpenAI API interface.

## What This Wrapper Does

* **Wraps POE API**: Translates OpenAI-compatible requests to POE-compatible calls.
* **OpenAI Compatible**: Integrates with any app expecting the OpenAI API format.
* **Local & Public Access**: Provides both localhost and secure public access via Cloudflare Tunnel.
* **File Support**: Manages file uploads and multimodal conversations.
* **Zero Configuration Tunneling**: No accounts or API keys needed for public access.
* **Free & Anonymous**: Cloudflare tunnel works without any registration or personal data.

## Required API Keys

1. **POE API Key**: Obtain from [https://poe.com/api\_key](https://poe.com/api_key)

> **Note**: No Cloudflare account or API key needed! The tunnel works automatically.

## Quick Setup

Run the following command:

```bash
./setup.sh
```

This setup script performs the following:

* Prompts for your POE API key.
* Generates a local API key automatically.
* Launches Docker services.
* Creates a secure Cloudflare tunnel for public access.
* Displays configuration details upon completion.

## IDE Configuration

### Xcode Configuration

* **Host URL**: `http://localhost:8000`
* **API Token**: Your auto-generated `LOCAL_API_KEY`
* **Header**: `x-api-key`

### Cursor IDE Configuration

* **Host URL**: Your Cloudflare tunnel URL (e.g., `https://your-subdomain.trycloudflare.com`)
* **API Token**: Your auto-generated `LOCAL_API_KEY`

> **Why Cloudflare Tunnel?**
>
> Cursor IDE doesn't support private hosts. It requires public access URLs. Cloudflare provides a secure, free tunnel from your local environment to the public internet without requiring any account or configuration.

## Available API Endpoints

* `GET /v1/models` – List available models
* `POST /v1/chat/completions` – Chat completions
* `POST /v1/completions` – Text completions
* `POST /v1/moderations` – Moderation tasks
* `/v1/files` – Manage file uploads

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

After setup completion, you can access:

* **Local API**: [`http://localhost:8000/v1`](http://localhost:8000/v1)
* **Public API**: Your Cloudflare tunnel URL (e.g., `https://your-subdomain.trycloudflare.com/v1`)
* **API Documentation**: [`http://localhost:8000/docs`](http://localhost:8000/docs)


**Important**: The tunnel URL changes each time you restart the container. This is a security feature that provides additional anonymity.

## Prerequisites

* Python **3.12+**
* Docker & Docker Compose
* Active internet connection

## Disclaimer

`This project is not affiliated with, endorsed by, or sponsored by Poe.com or OpenAI. It is intended for educational and personal use. Users are responsible for complying with the Terms of Service of Poe.com and any other services they connect to via this wrapper. Use at your own discretion.`

---
