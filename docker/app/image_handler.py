"""
Image generation handler for Poe API integration.
"""
# pylint: disable=duplicate-code

import base64
import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from .config import AVAILABLE_MODELS
from .exceptions import PoeAPIError
from .models import ChatMessage
from .poe_client import PoeClient

logger = logging.getLogger(__name__)

# Image generation models available on Poe
IMAGE_GENERATION_MODELS = {
    "dall-e-2": "DALL-E-3",
    "dall-e-3": "DALL-E-3",
    "stable-diffusion": "StableDiffusionXL",
    "stable-diffusion-xl": "StableDiffusionXL",
    "playground-v2": "Playground-v2",
    "stable-diffusion-3": "StableDiffusion3",
}


class ImageGenerationHandler:
    """Handles image generation requests."""

    def __init__(self):
        self.poe_client = PoeClient()

    def get_image_model(self, requested_model: Optional[str]) -> str:
        """Map OpenAI model names to Poe image model names."""
        if not requested_model:
            return "DALL-E-3"  # Default
        # Check if it's already a Poe model name
        if requested_model in AVAILABLE_MODELS:
            return requested_model
        # Map from OpenAI names
        return IMAGE_GENERATION_MODELS.get(requested_model.lower(), "DALL-E-3")

    async def generate_images(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,unused-argument
        self,
        prompt: str,
        model: Optional[str] = None,
        n: int = 1,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        style: Optional[str] = None,
        response_format: str = "url",
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate images using Poe's image generation models."""
        poe_model = self.get_image_model(model)
        # Validate model is available
        if poe_model not in AVAILABLE_MODELS:
            available_image_models = [
                m for m in AVAILABLE_MODELS
                if "DALL" in m or "Stable" in m or "Playground" in m
            ]
            raise PoeAPIError(
                f"Model '{poe_model}' not available. Available image models: "
                f"{available_image_models}",
                404
            )
        # Build enhanced prompt with quality/style modifiers
        enhanced_prompt = self._enhance_prompt(prompt, quality, style, size)
        # For multiple images, make multiple requests
        # Poe doesn't support batch generation in a single request
        images_data = []
        for i in range(n):
            try:
                # Create messages for Poe
                messages = [
                    ChatMessage(
                        role="user",
                        content=enhanced_prompt,
                        name=None,
                        tool_calls=None,
                        tool_call_id=None,
                    )
                ]
                poe_messages = await PoeClient.convert_to_poe_messages(messages)
                # Get response from Poe
                complete_text, _ = await self.poe_client.get_complete_response(
                    poe_messages, poe_model
                )
                # Extract image URL from response
                image_url = await self._extract_image_url(complete_text)
                if image_url:
                    if response_format == "b64_json":
                        # Download and convert to base64
                        b64_data = await self._download_and_encode_image(image_url)
                        images_data.append({"b64_json": b64_data})
                    else:
                        images_data.append({"url": image_url})
                else:
                    logger.warning("No image URL found in response for image %d", i+1)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error generating image %d: %s", i+1, e)
                if i == 0:
                    # If first image fails, raise the error
                    raise
                # Otherwise, continue with other images
        if not images_data:
            raise PoeAPIError("Failed to generate any images", 500)
        # Return OpenAI-compatible response
        return {
            "created": int(time.time()),
            "data": images_data
        }

    def _enhance_prompt(
        self,
        prompt: str,
        quality: Optional[str],
        style: Optional[str],
        size: Optional[str]
    ) -> str:
        """Enhance prompt with quality and style modifiers."""
        enhanced = prompt
        # Add quality modifiers
        if quality == "hd":
            enhanced = f"{enhanced}, high quality, detailed, 4k resolution"
        # Add style modifiers
        if style == "vivid":
            enhanced = f"{enhanced}, vivid colors, dynamic, vibrant"
        elif style == "natural":
            enhanced = f"{enhanced}, natural lighting, realistic, photographic"
        # Add size hints (though Poe models determine their own sizes)
        if size:
            if "1792" in size or "1024" in size:
                enhanced = f"{enhanced}, high resolution"
            elif "512" in size:
                enhanced = f"{enhanced}, medium resolution"
        return enhanced

    async def _extract_image_url(self, response_text: str) -> Optional[str]:
        """Extract image URL from Poe's response."""
        if not response_text:
            return None
        # Look for markdown image syntax
        import re  # pylint: disable=import-outside-toplevel
        # Pattern for markdown images: ![...](url)
        img_pattern = r'!\[.*?\]\((https?://[^\)]+)\)'
        matches = re.findall(img_pattern, response_text)
        if matches:
            return matches[0]
        # Look for plain URLs that might be images
        url_pattern = r'(https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp))'
        url_matches = re.findall(url_pattern, response_text, re.IGNORECASE)
        if url_matches:
            return url_matches[0]

        # Look for any poe.com image URLs
        poe_pattern = r'(https?://[^\s]*poe\.com[^\s]+)'
        poe_matches = re.findall(poe_pattern, response_text)
        for url in poe_matches:
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                return url
        return None

    async def _download_and_encode_image(self, image_url: str) -> str:
        """Download image and encode to base64."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise PoeAPIError(
                            f"Failed to download image: HTTP {response.status}",
                            response.status
                        )
                    image_data = await response.read()
                    return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error("Error downloading image from %s: %s", image_url, e)
            raise PoeAPIError(f"Failed to download image: {e}", 500) from e

    async def edit_image(  # pylint: disable=too-many-arguments,too-many-positional-arguments,unused-argument
        self,
        image: str,
        prompt: str,
        mask: Optional[str] = None,
        model: Optional[str] = None,
        n: int = 1,
        size: Optional[str] = None,
        response_format: str = "url",
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Edit an image (currently uses generation with instructions)."""
        # Since Poe doesn't have direct image editing, we'll use generation
        # with instructions that reference the original image
        edit_prompt = f"Edit this image according to these instructions: {prompt}"
        if mask:
            edit_prompt += " (Note: A mask was provided indicating areas to edit)"
        # For now, generate new images based on the edit prompt
        # In future, we could upload the original image as an attachment
        return await self.generate_images(
            prompt=edit_prompt,
            model=model,
            n=n,
            size=size,
            response_format=response_format,
            user=user,
        )

    async def create_image_variation(  # pylint: disable=too-many-arguments,too-many-positional-arguments,unused-argument
        self,
        image: str,
        model: Optional[str] = None,
        n: int = 1,
        size: Optional[str] = None,
        response_format: str = "url",
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create variations of an image."""
        # Use a prompt that asks for variations
        variation_prompt = (
            "Create a variation of this image, maintaining the same style and subject "
            "but with creative differences"
        )
        return await self.generate_images(
            prompt=variation_prompt,
            model=model,
            n=n,
            size=size,
            response_format=response_format,
            user=user,
        )
