"""
Embeddings handler for Poe API integration.
Provides OpenAI-compatible embeddings endpoint using prompt engineering.
"""

import base64
import hashlib
import json
import logging
import random
import struct
from typing import Any, Dict, List, Optional, Union

from .config import AVAILABLE_MODELS
from .exceptions import PoeAPIError
from .models import ChatMessage
from .poe_client import PoeClient

logger = logging.getLogger(__name__)

# Models that can be used for generating embeddings
EMBEDDING_MODELS = {
    "text-embedding-ada-002": "Claude-3-Haiku",  # Fast model for embeddings
    "text-embedding-3-small": "Claude-3-Haiku",
    "text-embedding-3-large": "Claude-3.5-Sonnet",  # Better model for higher quality
}


class EmbeddingsHandler:
    """Handles embeddings generation using Poe models."""

    def __init__(self):
        self.poe_client = PoeClient()

    def get_embedding_model(self, requested_model: str) -> str:
        """Map OpenAI embedding model names to Poe model names."""
        # Check if it's already a Poe model name
        if requested_model in AVAILABLE_MODELS:
            return requested_model

        # Map from OpenAI names
        return EMBEDDING_MODELS.get(requested_model, "Claude-3-Haiku")

    async def create_embeddings(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,unused-argument
        self,
        input_data: Union[str, List[str]],
        model: str,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create embeddings for the given input."""

        # Log warning about fake embeddings
        logger.warning(
            "Embeddings endpoint is simulated using LLM-generated vectors. "
            "These are NOT real embeddings and should not be used for production similarity search."
        )

        # Normalize input to list
        if isinstance(input_data, str):
            inputs = [input_data]
        else:
            inputs = input_data

        poe_model = self.get_embedding_model(model)

        # Validate model
        if poe_model not in AVAILABLE_MODELS:
            raise PoeAPIError(
                f"Model '{poe_model}' not available. Available models: {list(AVAILABLE_MODELS)}",
                404,
                "model_not_found",
                "model"
            )

        embeddings_data = []

        for i, text in enumerate(inputs):
            try:
                # Generate embedding using prompt engineering
                embedding = await self._generate_embedding(text, poe_model, dimensions)

                if encoding_format == "base64":
                    # Convert to base64
                    # Pack floats as bytes
                    byte_data = struct.pack(f'{len(embedding)}f', *embedding)
                    b64_embedding = base64.b64encode(byte_data).decode('utf-8')

                    embeddings_data.append({
                        "object": "embedding",
                        "embedding": b64_embedding,
                        "index": i
                    })
                else:
                    embeddings_data.append({
                        "object": "embedding",
                        "embedding": embedding,
                        "index": i
                    })

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error generating embedding for text %d: %s", i, e)
                if i == 0:
                    raise
                # For subsequent embeddings, use a zero vector as fallback
                embedding = [0.0] * (dimensions or 1536)
                embeddings_data.append({
                    "object": "embedding",
                    "embedding": embedding,
                    "index": i
                })

        # Calculate token usage (approximate)
        total_tokens = sum(len(text.split()) * 1.3 for text in inputs)

        return {
            "object": "list",
            "data": embeddings_data,
            "model": model,
            "usage": {
                "prompt_tokens": int(total_tokens),
                "total_tokens": int(total_tokens)
            }
        }

    async def _generate_embedding(  # pylint: disable=too-many-locals
            self, text: str, model: str, dimensions: Optional[int]
    ) -> List[float]:
        """Generate a pseudo-embedding using the language model."""

        # Use dimensions if specified, otherwise use default
        embed_dims = dimensions or 1536

        # Create a deterministic hash of the text for consistency
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Create a prompt that asks for semantic analysis
        prompt = (
            f'Analyze the following text and provide a numerical representation:\n\n'
            f'Text: "{text[:500]}"{"..." if len(text) > 500 else ""}\n\n'
            f'Provide a JSON array of {min(embed_dims, 100)} floating-point numbers between '
            f'-1 and 1 that represents the semantic content of this text. The numbers should '
            f'capture different '
            f'aspects like sentiment, topic, complexity, etc.\n\n'
            f'Important: Respond with ONLY the JSON array, no other text. '
            f'Example format: [0.123, -0.456, 0.789, ...]'
        )

        messages = [
            ChatMessage(
                role="user",
                content=prompt,
                name=None,
                tool_calls=None,
                tool_call_id=None,
            )
        ]

        poe_messages = await PoeClient.convert_to_poe_messages(messages)

        try:
            # Get response from Poe
            response_text, _ = await self.poe_client.get_complete_response(
                poe_messages, model
            )

            # Try to parse the JSON array
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            embedding_values = json.loads(response_text.strip())

            if not isinstance(embedding_values, list):
                raise ValueError("Response is not a list")

            # Ensure we have the right number of dimensions
            if len(embedding_values) < embed_dims:
                # Pad with deterministic values based on hash
                random.seed(int(text_hash[:8], 16))
                while len(embedding_values) < embed_dims:
                    embedding_values.append(random.uniform(-0.1, 0.1))
            elif len(embedding_values) > embed_dims:
                embedding_values = embedding_values[:embed_dims]

            # Normalize values to be between -1 and 1
            embedding_values = [max(-1.0, min(1.0, float(v))) for v in embedding_values]

            return embedding_values

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse embedding response, using fallback: %s", e)

            # Fallback: Generate deterministic pseudo-embedding from text hash
            random.seed(int(text_hash[:8], 16))

            # Generate values that are somewhat based on text characteristics
            embedding = []
            for i in range(embed_dims):
                # Use different parts of the hash for different dimensions
                seed_part = int(text_hash[i % 64], 16)
                random.seed(seed_part + i)

                # Add some text-based features
                if i % 10 == 0:
                    # Sentiment-like feature
                    value = (
                        0.1 if any(word in text.lower()
                                   for word in ["good", "great", "excellent"])
                        else -0.1
                    )
                elif i % 10 == 1:
                    # Length feature
                    value = min(1.0, len(text) / 1000.0) - 0.5
                else:
                    # Random but deterministic
                    value = random.uniform(-0.5, 0.5)

                embedding.append(value)

            return embedding
