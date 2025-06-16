#!/usr/bin/env python
import requests
import json
import sys

def get_ngrok_url():
    """Get the current ngrok public URL"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        tunnels = data.get("tunnels", [])
        
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                url = tunnel.get("public_url")
                if url:
                    return url
        
        # Fallback to http if https not found
        for tunnel in tunnels:
            if tunnel.get("proto") == "http":
                url = tunnel.get("public_url")
                if url:
                    return url.replace("http://", "https://")
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to ngrok: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error parsing ngrok response: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    url = get_ngrok_url()
    if url:
        print(f"Ngrok URL: {url}")
        print(f"API Base URL: {url}/v1")
    else:
        print("Could not get ngrok URL. Make sure ngrok is running.")
        sys.exit(1)