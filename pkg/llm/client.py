from __future__ import annotations

import asyncio
import threading
from typing import AsyncIterator, Tuple, cast

from google import genai

DEFAULT_MODEL = "gemini-2.5-pro"


class LLMClient:

    def __init__(self, gemini_api_key: str) -> None:
        self._client = genai.Client(api_key=gemini_api_key)

    async def generate(self, prompt: str, model: str = DEFAULT_MODEL) -> str:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt must be a non-empty string")

        return await asyncio.to_thread(self._generate_sync, prompt, model)

    async def stream_generate(self, prompt: str, model: str = DEFAULT_MODEL) -> AsyncIterator[str]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt must be a non-empty string")

        loop = asyncio.get_running_loop()
        queue: "asyncio.Queue[Tuple[str, object]]" = asyncio.Queue()

        def run_stream() -> None:
            try:
                with self._client.models.stream_generate_content(
                    model=model,
                    contents=prompt,
                ) as stream:
                    for chunk in stream:
                        text = getattr(chunk, "text", None)
                        if text:
                            loop.call_soon_threadsafe(queue.put_nowait, ("data", text))
            except Exception as exc:  # pragma: no cover - surface to caller
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        threading.Thread(target=run_stream, name="llm-stream", daemon=True).start()

        while True:
            kind, payload = await queue.get()
            if kind == "data":
                yield cast(str, payload)
            elif kind == "error":
                raise cast(Exception, payload)
            else:
                break

    def _generate_sync(self, prompt: str, model: str) -> str:
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini API returned no text content")
        return text
