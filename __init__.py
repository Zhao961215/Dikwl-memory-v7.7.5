"""DIKW 闭环终极调度器 v7.7.5"""
import json, os, threading
from datetime import datetime
from typing import Any, Dict
try: from .dikw_core import DIKWCore
except ImportError: from dikw_core import DIKWCore
from agent.memory_provider import MemoryProvider

__version__ = "7.7.5"
__all__ = ["DIKWPlugin", "DIKWMemoryProvider"]

class DIKWPlugin(MemoryProvider):
    @property
    def name(self) -> str: return "dikw"
    @property
    def version(self) -> str: return "7.7.5"
    description = "DIKW 认知调度器 v7.7.5"

    def __init__(self, config=None, config_path=None):
        self.core = DIKWCore(config, config_path)

    def initialize(self, session_id: str, **kwargs) -> None: pass
    def is_available(self) -> bool: return self.core.is_available
    def get_tool_schemas(self) -> list: return self.core.get_tool_schemas()
    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str: return self.core.handle_tool_call(tool_name, args)
    def set_delegate(self, delegate): self.core.set_delegate(delegate)
    def set_callbacks(self, callbacks): self.core.set_callbacks(callbacks)

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'): raise AttributeError(name)
        target = self.core if hasattr(self, 'core') and self.core is not None else None
        return getattr(target, name) if target and hasattr(target, name) else super().__getattribute__(name)

    def system_prompt_block(self) -> str:
        snr = self.core.get_snr_status()
        status_emoji = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}.get(snr.get("status", ""), "⚪")
        return (
            f"\n🧠 DIKW v7.7.5 {status_emoji} 认知库:{snr.get('n_items', '?')}条\n"
            "⚠️ 成长铁律 (强制执行):\n"
            "1. 行动前回忆: 必须执行 memory_recall(query='当前任务') 寻找避坑经验\n"
            "2. 原则必沉淀: 产生方法/踩坑后必须执行 memory_learn(content='...')\n"
            "3. 认知必进化: 发现旧原则有误时必须执行 memory_evolve(old_id='...', new_content='...')\n"
        )

    def prefetch(self, query: str = "", *, session_id: str = "") -> str:
        res = self.core.memory_recall(query=query or "")
        if res.get("status") == "hit": return json.dumps(res.get("data"), ensure_ascii=False)[:2000]
        return ""

    def sync_turn(self, user_content="", assistant_content="", *, session_id="", messages=None) -> None:
        if not assistant_content or len(assistant_content.strip()) <= 10: return
        is_lesson = any(k in assistant_content for k in ["踩坑", "教训", "错误", "失败", "注意"])
        is_wisdom = any(k in assistant_content for k in ["原则", "铁律", "必须", "流程", "方法论"])
        if is_lesson or is_wisdom:
            source = "lesson" if is_lesson else "wisdom"
            t = threading.Thread(target=self.core.memory_learn, args=(assistant_content.strip(), source, session_id or "sync"), daemon=False)
            t.start()

    def on_session_start(self, session_id): return {"action": "session_start", "session_id": session_id}
    def on_session_end(self, session_id): return {"action": "save_last_moment", "session_id": session_id}

DIKWMemoryProvider = DIKWPlugin

def register(ctx):
    plugin_raw_cfg = ctx.config.get("plugins", {}).get("dikw", {})
    config = plugin_raw_cfg.get("config", plugin_raw_cfg) if isinstance(plugin_raw_cfg, dict) else {}
    provider = DIKWPlugin(config=config)
    ctx.register_memory_provider(provider)
