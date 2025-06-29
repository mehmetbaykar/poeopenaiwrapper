"""
Script to retrieve the public ngrok URL.
"""

import sys

import requests

def get_ngrok_url() -> str | None:
    """Retrieves the current ngrok public URL from the ngrok API."""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        response.raise_for_status()

        data = response.json()
        tunnels = data.get("tunnels", [])

        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                public_url = tunnel.get("public_url")
                if public_url:
                    return public_url

        for tunnel in tunnels:
            if tunnel.get("proto") == "http":
                public_url = tunnel.get("public_url")
                if public_url:
                    return public_url.replace("http://", "https://")

        return None

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to ngrok: {e}", file=sys.stderr)
        return None
    except ValueError as e:
        print(f"Error parsing ngrok response: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        print(f"Ngrok URL: {ngrok_url}")
        print(f"API Base URL: {ngrok_url}/v1")
    else:
        print("Could not get ngrok URL. Make sure ngrok is running.")
        sys.exit(1)
