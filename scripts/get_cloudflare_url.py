#!/usr/bin/env python
"""Module for retrieving Cloudflare tunnel URLs from Docker container logs."""
import subprocess
import time
import re
import sys


def get_cloudflare_url(max_attempts=10, delay=2):
    """
    Get the Cloudflare tunnel URL by parsing docker logs.
    
    Args:
        max_attempts: Maximum number of attempts to find the URL
        delay: Delay between attempts in seconds
        
    Returns:
        str: The HTTPS tunnel URL or None if not found
    """
    for attempt in range(max_attempts):
        try:
            # Get logs from the cloudflared container
            result = subprocess.run(
                ["docker", "logs", "poe-cloudflared"],
                capture_output=True,
                text=True,
                check=False
            )

            # Look for the tunnel URL in the logs
            # Cloudflare logs URLs in format: https://[random-subdomain].trycloudflare.com
            pattern = r'https://[a-zA-Z0-9-]+\.trycloudflare\.com'
            matches = re.findall(pattern, result.stdout + result.stderr)

            if matches:
                # Return the most recent URL (last match)
                return matches[-1]

            if attempt < max_attempts - 1:
                time.sleep(delay)

        except subprocess.SubprocessError as e:
            print(f"Error checking cloudflare logs: {e}", file=sys.stderr)
            if attempt < max_attempts - 1:
                time.sleep(delay)

    return None


def main():
    """Main function to get and display the Cloudflare tunnel URL."""
    print("Getting Cloudflare tunnel URL...")

    url = get_cloudflare_url()

    if url:
        print("\n✅ Cloudflare tunnel established!")
        print(f"API Base URL: {url}/v1")
        print(f"\nYour public API endpoint: {url}/v1")
    else:
        print("\n❌ Could not get Cloudflare tunnel URL")
        print("Please check:")
        print("1. Docker containers are running: docker ps")
        print("2. Check cloudflared logs: docker logs poe-cloudflared")
        sys.exit(1)


if __name__ == "__main__":
    main()
