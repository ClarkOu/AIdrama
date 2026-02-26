from __future__ import annotations
import asyncio
import subprocess
import logging
import os
import tempfile
from pathlib import Path

import httpx

from backend.core.config import settings
from backend.core.events import event_bus, COMPOSE_DONE

logger = logging.getLogger(__name__)


class ComposeAgent:
    """
    Compose Agent：使用 FFmpeg 本地拼接所有 Segment 视频，输出整集 MP4。
    零 API 调用，纯本地处理。
    """

    OUTPUT_DIR = Path(settings.ASSETS_DIR) / "output"

    async def compose(self, payload: dict):
        """
        payload: {
            ep_id: str,
            project_title: str,
            ep_number: int,
            segments: [{seg_id, order, final_video_url}]   # 已按 order 排序
        }
        """
        ep_id = payload["ep_id"]
        segments = sorted(payload["segments"], key=lambda s: s["order"])
        video_urls = [s["final_video_url"] for s in segments if s.get("final_video_url")]

        if not video_urls:
            raise ValueError(f"[ComposeAgent] ep_id={ep_id} 没有可合成的视频片段")

        logger.info(f"[ComposeAgent] 开始合成: ep_id={ep_id}, 片段数={len(video_urls)}")

        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_filename = f"{payload.get('project_title', 'episode')}_{payload.get('ep_number', 0):02d}.mp4"
        output_path = str(self.OUTPUT_DIR / output_filename)

        # 下载所有 HTTP 视频到临时文件
        local_paths = await self._download_videos(video_urls)
        try:
            # 在线程池中执行 FFmpeg（阻塞操作）
            await asyncio.get_event_loop().run_in_executor(
                None, self._run_ffmpeg, local_paths, output_path
            )
        finally:
            # 清理临时下载文件
            for p in local_paths:
                if p.startswith(tempfile.gettempdir()):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

        logger.info(f"[ComposeAgent] 合成完成: {output_path}")
        await event_bus.publish(COMPOSE_DONE, {
            "ep_id": ep_id,
            "output_path": output_path,
        })
        return output_path

    async def _download_videos(self, urls: list[str]) -> list[str]:
        """将 HTTP URL 下载为本地临时文件，本地路径原样返回"""
        local_paths = []
        async with httpx.AsyncClient(timeout=120) as client:
            for i, url in enumerate(urls):
                if url.startswith("http://") or url.startswith("https://"):
                    resp = await client.get(url)
                    resp.raise_for_status()
                    suffix = ".mp4"
                    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                    tmp.write(resp.content)
                    tmp.close()
                    logger.info(f"[ComposeAgent] 下载视频 {i+1}/{len(urls)}: {url} -> {tmp.name}")
                    local_paths.append(tmp.name)
                else:
                    # 已是本地路径
                    local_paths.append(url)
        return local_paths

    def _run_ffmpeg(self, video_urls: list[str], output_path: str):
        """
        构建 FFmpeg concat 命令并执行。
        使用 concat demuxer（稳定，支持不同编码格式）。
        """
        # 写 concat list 文件
        list_path = output_path.replace(".mp4", "_concat_list.txt")
        with open(list_path, "w") as f:
            for url in video_urls:
                # 本地路径：直接使用；远程 URL：需先下载（此处假设已是本地路径）
                escaped = url.replace("'", r"\'")
                f.write(f"file '{escaped}'\n")

        cmd = [
            "ffmpeg",
            "-y",                  # 覆盖输出
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info(f"[ComposeAgent] FFmpeg 命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 失败:\n{result.stderr}")

        # 清理临时文件
        try:
            os.remove(list_path)
        except OSError:
            pass
