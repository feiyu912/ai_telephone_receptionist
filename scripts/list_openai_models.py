"""List all OpenAI models and filter for realtime-related ones."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import AsyncOpenAI
from app.config import get_settings


async def main():
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    print("Fetching models from OpenAI...\n")
    models = await client.models.list()

    all_ids = sorted([m.id for m in models.data])
    print(f"Total models returned: {len(all_ids)}\n")

    realtime_ids = [m for m in all_ids if "realtime" in m.lower()]
    print(f"Models with 'realtime' in ID: {len(realtime_ids)}")
    for m in realtime_ids:
        print(f"  - {m}")

    print("\n" + "=" * 50)
    print("All model IDs (first 30):")
    for m in all_ids[:30]:
        print(f"  - {m}")


if __name__ == "__main__":
    asyncio.run(main())
