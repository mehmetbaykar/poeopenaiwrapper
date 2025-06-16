# POE OpenAI Wrapper

A local OpenAI-compatible API server wrapping the [POE.com](https://poe.com) API, allowing you to seamlessly integrate POE’s AI models with your IDEs (like Xcode or Cursor) through a familiar OpenAI API interface.

## What This Wrapper Does

* **Wraps POE API**: Translates OpenAI-compatible requests to POE-compatible calls.
* **OpenAI Compatible**: Integrates with any app expecting the OpenAI API format.
* **Local & Public Access**: Provides both localhost and public access via Ngrok tunneling.
* **File Support**: Manages file uploads and multimodal conversations.

## Required API Keys

1. **POE API Key**: Obtain from [https://poe.com/api\_key](https://poe.com/api_key)
2. **Ngrok Auth Token**: Obtain from [https://dashboard.ngrok.com/api-keys](https://dashboard.ngrok.com/api-keys)

## Quick Setup

Run the following command:

```bash
./setup.sh
```

This setup script performs the following:

* Prompts for your POE API key and Ngrok token.
* Generates a local API key automatically.
* Launches Docker services.
* Creates an Ngrok tunnel for public access.
* Displays configuration details upon completion.

## IDE Configuration

### Xcode Configuration

* **Host URL**: `http://localhost:8000`
* **API Token**: Your auto-generated `LOCAL_API_KEY`
* **Header**: `x-api-key`

### Cursor IDE Configuration

* **Host URL**: Your Ngrok public URL (e.g., `https://abc123.ngrok.io`)
* **API Token**: Your auto-generated `LOCAL_API_KEY`

> **Why Ngrok?**
>
> Cursor IDE doesn't support private hosts. It requires public access URLs. Ngrok provides a secure tunnel from your local environment to the public internet, enabling seamless integration with Cursor or similar applications.

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

# Retrieve Ngrok URL
python scripts/get_ngrok_url.py
```

## Access URLs

After setup completion, you can access:

* **Local API**: [`http://localhost:8000/v1`](http://localhost:8000/v1)
* **Public API**: Your Ngrok URL (e.g., `https://your-ngrok-url.ngrok.io/v1`)
* **Ngrok Dashboard**: [`http://localhost:4040`](http://localhost:4040)
* **API Documentation**: [`http://localhost:8000/docs`](http://localhost:8000/docs)

## Prerequisites

* Python **3.12+**
* Docker & Docker Compose
* Active internet connection

---
