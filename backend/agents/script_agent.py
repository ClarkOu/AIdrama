from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
import difflib

from backend.core.config import settings
from backend.core.events import event_bus, SCRIPT_SEGMENTS_READY, SCRIPT_STREAM_CHUNK, OUTLINES_READY, OUTLINE_STREAM_CHUNK

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个短剧编剧助手。根据以下信息，一次性生成本集完整脚本和分镜列表。

【项目信息】
剧名：{title}
风格：{tone}
视觉：{visual_style}

【角色库】
{characters_info}

【前情回顾（仅供情节连贯参考，严禁在本集内容中重复前集剧情）】
{prev_episodes_info}

【本集任务】
现在请为《{title}》第 {ep_number} 集写脚本。本集梗概如下：
{outline}
严禁内容与前集雷同，必须推进新的情节冲突。

【分镜规则】
1. 总分镜数 10-14 个（每段对应 10-12 秒视频）
2. 严格按 5 幕结构：
   - 第1幕（开场钩子）：2-3个，情绪压抑
   - 第2幕（冲突升级）：3-4个，持续压抑
   - 第3幕（转折爽点）：2-3个，急速反转
   - 第4幕（连锁反应）：2-3个，爽感持续
   - 第5幕（集尾钩子）：1-2个，悬念留白
3. characters[] 只能使用角色库中的 name，禁止使用代词
4. prompt 要求：
   - 纯叙述句，无任何结构标记（无括号、无标题、无分点）
   - 开头必须包含出场角色的 fixed_desc
   - 不超过 120 字
   - 结尾画面自然衔接下一段

【输出格式】
严格输出 JSON，不附加任何说明文字：
{{
  "script_text": "完整剧本原文...",
  "segments": [
    {{
      "id": 1,
      "act": 1,
      "scene_desc": "场景简述（中文，供人读）",
      "characters": ["角色名1"],
      "dialogue": "对白原文（无对白填null）",
      "prompt": "完整的视频生成提示词...",
      "duration": 6
    }}
  ]
}}

duration 根据场景内容自动判断（整数，单位秒）：
- 纯景别/过场/对话简短：4-5 秒
- 普通动作/多人对话：6-7 秒
- 高潮冲突/大场面/长台词动作：8-10 秒
- 极限范围：4~12 秒"""


class ScriptAgent:
    """
    Script Agent：
    1. generate()    — 根据 outline + 角色库 调用 LLM 生成剧本 + 分镜
    2. handle_edit() — 对比 diff，决定轻量/重量编辑
    """

    async def generate(self, payload: dict):
        """
        payload: {ep_id, ep_number, project_id, outline, title, tone, visual_style, characters:[{name, fixed_desc}]}
        """
        ep_id        = payload["ep_id"]
        ep_number    = payload.get("ep_number", "?")
        outline      = payload["outline"]
        title        = payload.get("title", "")
        tone         = payload.get("tone", "")
        visual_style = payload.get("visual_style", "")
        characters   = payload.get("characters", [])
        prev_episodes = payload.get("prev_episodes", [])

        characters_info = "\n".join(
            f"{c['name']}：{c['fixed_desc']}" for c in characters
        ) or "（未设置角色）"

        if prev_episodes:
            # 只传每集棒构摘要，不传剧本全文，避免 LLM 照抄前集
            prev_episodes_info = "\n".join(
                f"第{p['ep_number']}集：{p['outline']}"
                for p in prev_episodes
            )
        else:
            prev_episodes_info = "（本剧第一集，无前情）"

        def _esc(s: str) -> str:
            """转义值中的花括号，避免 .format() 把它们当占位符"""
            return str(s).replace("{", "{{").replace("}", "}}")

        prompt = SYSTEM_PROMPT.format(
            title=_esc(title),
            tone=_esc(tone),
            visual_style=_esc(visual_style),
            characters_info=_esc(characters_info),
            prev_episodes_info=_esc(prev_episodes_info),
            ep_number=ep_number,
            outline=_esc(outline),
        )

        logger.info(f"[ScriptAgent] 开始生成: ep_id={ep_id}")
        raw = await self._call_llm(prompt, ep_id=ep_id)
        result = self._parse_llm_output(raw)

        await event_bus.publish(SCRIPT_SEGMENTS_READY, {
            "ep_id": ep_id,
            "script_text": result["script_text"],
            "segments": result["segments"],
        })
        return result

    async def generate_outlines(self, payload: dict):
        """
        payload: {project_id, title, genre, tone, story_premise, total_episodes}
        调用 LLM 生成所有集的梗概，发布 OUTLINES_READY 事件
        """
        import re
        project_id     = payload["project_id"]
        title          = payload.get("title", "")
        genre          = payload.get("genre", "")
        tone           = payload.get("tone", "")
        story_premise  = payload.get("story_premise", "")
        total_episodes = int(payload.get("total_episodes", 6))

        prompt = (
            f"你是一个短剧编剧。请根据以下项目信息，为整部剧生成 {total_episodes} 集的分集大纲。\n\n"
            f"【项目信息】\n"
            f"剧名：{title}\n"
            f"类型：{genre}\n"
            f"基调：{tone}\n"
            f"故事主线：{story_premise}\n\n"
            f"要求：\n"
            f"1. 每集梗概 50-100 字，高度概括本集核心冲突和转折\n"
            f"2. 各集之间情节连贯，有明显情绪起伏\n"
            f"3. 严格按照 JSON 格式返回，不要包含任何额外文字\n\n"
            f'返回格式：{{"outlines": [{{"ep": 1, "outline": "第一集梗概内容"}}, {{"ep": 2, "outline": "第二集梗概内容"}}]}}'
        )

        raw = await self._call_llm(prompt, project_id=project_id)

        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            logger.error(f"[ScriptAgent] generate_outlines 返回非 JSON: {raw[:300]}")
            return

        try:
            data     = json.loads(m.group())
            outlines = data.get("outlines", [])
        except json.JSONDecodeError as e:
            logger.error(f"[ScriptAgent] generate_outlines JSON 解析失败: {e}\n原文: {raw[:300]}")
            return

        await event_bus.publish(OUTLINES_READY, {
            "project_id": project_id,
            "outlines":   outlines,
        })
        logger.info(f"[ScriptAgent] 大纲生成完成: project_id={project_id}, count={len(outlines)}")

    async def handle_edit(self, payload: dict):
        """
        payload: {ep_id, old_script_text, new_script_text, segments:[Segment], characters, title, tone, visual_style}
        脚本 diff 分析：判断影响范围，决定轻量/重量编辑。
        """
        old_text = payload["old_script_text"]
        new_text = payload["new_script_text"]
        segments = payload["segments"]

        diff = list(difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            lineterm=""
        ))

        changed_lines = [l for l in diff if l.startswith("+") or l.startswith("-")]
        structural_keywords = ["幕", "场景", "转折", "复仇", "决定", "离开", "赶走"]
        is_structural = any(kw in "".join(changed_lines) for kw in structural_keywords)

        if not is_structural:
            # 轻量编辑：只更新 dialogue，标记 prompt_dirty
            logger.info(f"[ScriptAgent] 轻量编辑：仅更新对白")
            return {"type": "light", "affected_acts": [], "dirty_only": True}
        else:
            # 重量编辑：识别变动幕，局部 re-gen
            changed_acts = self._detect_changed_acts(diff, segments)
            logger.info(f"[ScriptAgent] 重量编辑：重新生成第 {changed_acts} 幕")
            regen_payload = {**payload, "acts_to_regen": changed_acts}
            await self._partial_regen(regen_payload)
            return {"type": "heavy", "affected_acts": changed_acts}

    async def _partial_regen(self, payload: dict):
        """对变动幕局部重新调 LLM，未变动幕不触碰"""
        acts_to_regen = payload["acts_to_regen"]
        existing_segments = [s for s in payload["segments"] if s["act"] not in acts_to_regen]

        prompt = f"""以下是已有分镜（不需要修改）：
{json.dumps(existing_segments, ensure_ascii=False, indent=2)}

请只对第 {acts_to_regen} 幕重新生成分镜，约 {len(acts_to_regen)*3} 个 Segment。
新的剧本文本：
{payload['new_script_text']}

输出格式同原格式，严格 JSON，segments[] 只包含需要重生成的幕。"""

        raw = await self._call_llm(prompt)
        result = self._parse_llm_output(raw)

        await event_bus.publish(SCRIPT_SEGMENTS_READY, {
            "ep_id": payload["ep_id"],
            "script_text": payload["new_script_text"],
            "segments": result["segments"],
            "partial": True,
            "acts_regenned": acts_to_regen,
        })

    def _detect_changed_acts(self, diff: list[str], segments: list[dict]) -> list[int]:
        """从 diff 内容中推断哪些幕受到影响（简单启发式）"""
        changed_acts = set()
        for seg in segments:
            scene = seg.get("scene_desc", "") + seg.get("dialogue", "")
            for line in diff:
                if line.startswith("+") or line.startswith("-"):
                    if any(word in line for word in scene.split()[:3]):
                        changed_acts.add(seg["act"])
        return sorted(changed_acts) if changed_acts else [3]  # 默认重生第3幕

    def _parse_llm_output(self, raw: str) -> dict:
        """解析 LLM 返回的 JSON，容错处理"""
        raw = raw.strip()
        # 去掉可能的 markdown 代码块
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"[ScriptAgent] JSON 解析失败: {e}\n原始输出: {raw[:200]}")
            raise ValueError(f"LLM 输出非合法 JSON: {e}")

    async def _call_llm(self, prompt: str, ep_id: str = "", project_id: str = "") -> str:
        """统一 LLM 调用入口，支持 Anthropic / OpenAI"""
        provider = settings.LLM_PROVIDER
        model    = settings.LLM_MODEL

        if provider == "anthropic":
            return await self._call_anthropic(prompt, model)
        elif provider == "openai":
            return await self._call_openai(prompt, model, ep_id=ep_id, project_id=project_id)
        else:
            raise ValueError(f"不支持的 LLM_PROVIDER: {provider}")

    async def _call_anthropic(self, prompt: str, model: str) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = await client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    async def _call_openai(self, prompt: str, model: str, ep_id: str = "", project_id: str = "") -> str:
        from openai import AsyncOpenAI
        api_key  = settings.LLM_API_KEY or settings.OPENAI_API_KEY
        base_url = settings.LLM_BASE_URL
        client   = AsyncOpenAI(api_key=api_key, base_url=base_url)

        full_text = ""
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            if delta:
                full_text += delta
                if ep_id:
                    await event_bus.publish(SCRIPT_STREAM_CHUNK, {
                        "ep_id": ep_id,
                        "delta": delta,
                    })
                if project_id:
                    await event_bus.publish(OUTLINE_STREAM_CHUNK, {
                        "project_id": project_id,
                        "delta": delta,
                    })
        return full_text
