from __future__ import annotations
import httpx
import aiofiles
import os
import uuid
import logging
from pathlib import Path
from backend.core.config import settings
from backend.core.events import event_bus, CHARACTER_IMAGE_DONE

logger = logging.getLogger(__name__)

CHARS_DIR = Path(settings.ASSETS_DIR) / "chars"
CHARS_DIR.mkdir(parents=True, exist_ok=True)


class ImageAgent:
    """
    Image Agent：负责角色图片的生成与管理。
    支持三种方式：
      - text_to_image (t2i)：文生图
      - image_to_image (i2i)：图生图
      - upload：本地上传（直接由 API 层处理，此处存档）
    """

    BASE_URL = settings.SEEDREAM_BASE_URL
    API_KEY  = settings.SEEDREAM_API_KEY

    async def handle(self, payload: dict):
        mode = payload.get("mode")
        if mode == "t2i":
            await self.text_to_image(payload)
        elif mode == "i2i":
            await self.image_to_image(payload)
        else:
            logger.warning(f"[ImageAgent] 未知 mode: {mode}")

    # ── 文生图 ──────────────────────────────────────────────────
    async def text_to_image(self, payload: dict) -> dict:
        """
        payload: {char_id, char_name, prompt, project_id}
        """
        char_id = payload["char_id"]
        prompt  = payload["prompt"]

        logger.info(f"[ImageAgent] t2i 开始: char_id={char_id}")

        image_url = await self._call_seedream_t2i(prompt)
        local_path = await self._download_image(image_url, char_id, "t2i")

        result = {
            "char_id": char_id,
            "char_name": payload.get("char_name", ""),
            "project_id": payload.get("project_id", ""),
            "url": local_path,
            "source": "ai_t2i",
            "gen_prompt": prompt,
            "is_primary": True,
        }
        await event_bus.publish(CHARACTER_IMAGE_DONE, result)
        return result

    # ── 图生图 ──────────────────────────────────────────────────
    async def image_to_image(self, payload: dict) -> dict:
        """
        payload: {char_id, char_name, ref_image_path, prompt, project_id}
        """
        char_id        = payload["char_id"]
        ref_image_path = payload["ref_image_path"]
        prompt         = payload.get("prompt", "")

        logger.info(f"[ImageAgent] i2i 开始: char_id={char_id}")

        image_url = await self._call_seedream_i2i(ref_image_path, prompt)
        local_path = await self._download_image(image_url, char_id, "i2i")

        result = {
            "char_id": char_id,
            "char_name": payload.get("char_name", ""),
            "project_id": payload.get("project_id", ""),
            "url": local_path,
            "source": "ai_i2i",
            "gen_prompt": prompt,
            "is_primary": False,
        }
        await event_bus.publish(CHARACTER_IMAGE_DONE, result)
        return result

    # ── Seedream API 调用 ────────────────────────────────────────
    async def _call_seedream_t2i(self, prompt: str) -> str:
        """调用 Seedream 文生图，返回图片 URL"""
        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "seedream-3-0",
            "prompt": prompt,
            "size": "1024x1024",
            "response_format": "url",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/images/generations",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["url"]

    async def _call_seedream_i2i(self, ref_image_path: str, prompt: str) -> str:
        """调用 Seedream 图生图，返回图片 URL"""
        import base64
        # 支持本地路径和 HTTP URL 两种 ref_image_path
        if ref_image_path.startswith("http://") or ref_image_path.startswith("https://"):
            async with httpx.AsyncClient(timeout=60) as client:
                dl = await client.get(ref_image_path)
                dl.raise_for_status()
                img_b64 = base64.b64encode(dl.content).decode()
        else:
            with open(ref_image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "seedream-3-0",
            "prompt": prompt,
            "image": img_b64,
            "size": "1024x1024",
            "response_format": "url",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/images/edits",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["url"]

    # ── 图片下载 ─────────────────────────────────────────────────
    async def _download_image(self, url: str, char_id: str, suffix: str) -> str:
        filename = f"{char_id}_{suffix}_{uuid.uuid4().hex[:8]}.jpg"
        local_path = str(CHARS_DIR / filename)

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        async with aiofiles.open(local_path, "wb") as f:
            await f.write(resp.content)

        http_url = f"{settings.BACKEND_URL}/assets/chars/{filename}"
        logger.info(f"[ImageAgent] 图片已保存: {local_path} -> {http_url}")
        return http_url
