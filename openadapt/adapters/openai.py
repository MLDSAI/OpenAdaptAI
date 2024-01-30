"""Adapter for GPT4-V API."""

from pprint import pprint
import base64
import json
import mimetypes
import os
import requests
import sys


from openadapt import cache, config


def create_payload(
    prompt: str,
    system_prompt: str | None = None,
    base64_images: list[str] | None = None,
    model="gpt-4-vision-preview",
    detail="high",
    max_tokens=None,
):
    """Creates the payload for the API request."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        },
    ]

    base64_images = base64_images or []
    for base64_image in base64_images:
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {
                "url": base64_image,
                "detail": detail,
            }
        })

    if system_prompt:
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt,
                    }
                ],
            }
        ] + messages

    rval = {
        "model": model,
        "messages": messages,
    }
    if max_tokens:
        rval["max_tokens"] = max_tokens
    return rval


@cache.cache()
def get_completion(payload):
    """Sends a request to the OpenAI API and prints the response."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.OPENAI_API_KEY}"
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
    )
    return response.json()
