"""DIKW 核心引擎 v7.7.5 (闭环终极版)"""
import json, os, math, re, sqlite3, time, inspect
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class DIKWCore:
    VERSION = "7.7.5"

    def __init__(self, config=None, config_path=None):
        self.config = self._load_config(config_path) if config_path else (config or self._default_config())
        self.holographic_delegate = None
        self._callbacks = {}
        self._enabled = True

    def _load_config(self, path):
        try:
            import yaml; 
            with open(path, 'r', encoding='utf-8') as f: return yaml.safe_load(f) or {}
        except Exception: return self._default_config()

    def _default_config(self):
        home = os.path.expanduser("~/.hermes")
        return {
            "workspace_dir": home, "vault_dir": os.path.join(home, "data", "knowledge", "vault"),
            "lesson_dir": os.path.join(home, "data", "knowledge", "vault", "踩坑记录"),
            "entities_dir": os.path.join(home, "data", "knowledge", "vault", "entities"),
            "cache_dir": os.path.join(home, "data", "cache"), "log_dir": os.path.join(home, "logs"),
            "cache_ttl": 86400, "snr": {"warning": 0.5, "critical": 0.3, "dim": 8192}
        }

    def set_delegate(self, d): self.holographic_delegate = d
    def set_callbacks(self, c): self._callbacks = c
    @property
    def is_available(self): return self._enabled

    def _call_engine(self, action, args):
        try:
            if self._callbacks.get("fact_store"): return self._callbacks["fact_store"](action, args)
            if self.holographic_delegate:
                payload = {**args, "action": action}
                return self.holographic_delegate._call_holographic_fact_store(payload)
        except Exception: pass
        return None

    def _extract_hrr_query(self, text):
        words = re.findall('[一-鿿]+|[a-zA-Z]+', text)
        return ' '.join(words[:15])

    def _persist_to_disk(self, dir_key, content, source, filename_fn, template_fn):
        d = self.config.get(dir_key, "")
        if not d: return None
        os.makedirs(d, exist_ok=True)
        fn, text = filename_fn(source, content), template_fn(source, content)
        fp = os.path.join(d, fn)
        try:
            with open(fp, 'w', encoding='utf-8') as f: f.write(text)
            return fp
        except Exception: return None

    def memory_learn(self, content, source="general", source_session="sys", metadata=None):
        if not content or not content.strip(): return {"error": "MISSING_PARAM"}
        metadata = metadata or {}
        cat = self._classify(content, source)
        hrr_q = self._extract_hrr_query(content)

        fact_id = None
        if cat in ("W", "L", "I"):
            fact_id = self._call_engine("add", {
                "content": content, "source": source, "source_session": source_session, 
                "metadata": {**metadata, "category": cat, "hrr_query": hrr_q}, "query": hrr_q
            })

        path = None
        if cat == "D":
            path = self._persist_to_disk("cache_dir", content, source, lambda s,c: f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{s}.md", lambda s,c: f"# {s} (cache)\n\n{c}")
        elif cat == "I":
            path = self._persist_to_disk("entities_dir", content, source, lambda s,c: f"{c[:30].replace('#','').strip()}.md", lambda s,c: f"# {c[:30]}\n\n{c}")
        elif cat == "W":
            path = self._persist_to_disk("vault_dir", content, source, lambda s,c: f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{s}.md", lambda s,c: f"# {s}\n\n{c}")
        elif cat == "L":
            path = self._persist_to_disk("lesson_dir", content, source, lambda s,c: f"{datetime.now().strftime('%Y-%m-%d')}-{c[:20]}.md", lambda s,c: f"# {c[:20]}\n\n## 教训\n{c}")

        return {"status": "learned", "fact_id": fact_id, "path": path, "category": cat, "storage": "brain+disk" if fact_id and path else "brain" if fact_id else "disk"}

    def _classify(self, c, s):
        if s == "lesson" or any(k in c for k in ["踩坑","教训","错误","失败","不要"]): return "L"
        if s == "data" or any(k in c for k in ["当前","今日","实时","API返回"]): return "D"
        if any(k in c for k in ["原则","规则","铁律","方法论","体系","框架","必须","禁止"]): return "W"
        return "I" if len(c) < 200 else "K"

    def memory_recall(self, query):
        if not query or not query.strip(): return {"status": "miss", "recommendation": "空查询不执行检索"}

        if any(p in query for p in ["刚才","之前","上一条"]):
            r = self._search_session(query)
            if r: return {"status": "hit", "source": "pronoun_path", "data": r}

        r = self._call_engine("search", {"query": query})
        # P0 修复: 必须校验结果实质内容，空字典短路导致文件兜底全部失效
        if r and isinstance(r, dict) and r.get("results"):
            return {"status": "hit", "source": "cognitive_matrix", "data": r}

        r = self._search_files([self.config.get("lesson_dir"), self.config.get("vault_dir"), self.config.get("entities_dir")], query)
        if r: return {"status": "hit", "source": "vault_fallback", "data": r}

        r = self._search_session(query)
        if r: return {"status": "hit", "source": "session_fallback", "data": r}

        r = self._search_cache(query)
        if r: return {"status": "hit", "source": "cache_fallback", "data": r}

        if self._callbacks.get("web_search"):
            try:
                r = self._callbacks["web_search"](query)
                if r: return {"status": "hit", "source": "web_search", "data": r}
            except Exception: pass

        return {
            "status": "miss", 
            "recommendation": "未命中认知，请遵循 FIRST 原则执行",
            "framework": {
                "F_focus": f"本质目标：{query}",
                "I_identify": "列出路径选最短(奥卡姆剃刀)",
                "R_run": "执行最小必要步骤(MVP)",
                "S_stop": "验证是否符合目标",
                "T_tune": "快速迭代，最多2次失败则求助"
            }
        }

    def _search_session(self, q):
        if self._callbacks.get("session_search"):
            try:
                r = self._callbacks["session_search"](q)
                if r: return r
            except Exception: pass
        return None

    def _search_files(self, dirs, q):
        if not q or not q.strip(): return None
        ql = q.lower()
        for d in dirs:
            if not d or not os.path.exists(d): continue
            for root, _, files in os.walk(d):
                for f in files:
                    if not f.endswith(".md") or f.startswith("_"): continue
                    try:
                        with open(os.path.join(root, f), 'r', encoding='utf-8') as fh:
                            if ql in fh.read().lower(): return f"文件 {f} 命中"
                    except Exception: continue
        return None

    def _search_cache(self, q):
        if not q or not q.strip(): return None
        d = self.config.get("cache_dir", "")
        if not d: return None
        ql = q.lower(); ttl = self.config.get("cache_ttl", 86400)
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            try:
                if time.time() - os.path.getmtime(fp) > ttl: continue
                with open(fp, 'r', encoding='utf-8') as fh:
                    if ql in fh.read().lower(): return f"缓存 {f} 命中"
            except Exception: continue
        return None

    def memory_evolve(self, old_fact_id, new_content, source_session="sys"):
        if not old_fact_id or not new_content: return {"error": "MISSING_PARAM"}
        fb_res = self._call_engine("feedback", {"fact_id": old_fact_id, "action": "unhelpful"})
        if fb_res is None:
            return {"error": "EVOLVE_ABORTED", "reason": "旧认知降权失败，拒绝无根进化"}
        learn_res = self.memory_learn(new_content, source="wisdom", source_session=source_session, metadata={"supersedes": old_fact_id})
        return {"status": "evolved", "deprecated_id": old_fact_id, "new_fact_id": learn_res.get("fact_id")}

    def memory_admin(self, action="snr", **kwargs):
        if action == "snr": return self.get_snr_status()
        if action == "migrate": return self.migrate_expired_to_vault(**kwargs)
        return {"error": "UNKNOWN_ADMIN_ACTION"}

    def get_snr_status(self):
        sc = self.config.get("snr", {}); dim = sc.get("dim", 8192); n = 0
        db = Path(self.config.get("workspace_dir", "~/.hermes")) / "memory_store.db"
        if db.exists():
            try:
                conn = sqlite3.connect(str(db)); n = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]; conn.close()
            except Exception: pass
        snr = math.sqrt(dim / n) if n > 0 else float('inf')
        st = "critical" if snr < 0.3 else "warning" if snr < 0.5 else "healthy"
        return {"n_items": n, "snr": round(snr, 4), "status": st}

    def migrate_expired_to_vault(self, days=30, trust_threshold=0.3):
        db = Path(self.config.get("workspace_dir", "~/.hermes")) / "memory_store.db"
        if not db.exists(): return {"error": "DB not found"}
        conn = sqlite3.connect(str(db)); cur = conn.cursor()
        cur.execute("DELETE FROM facts WHERE created_at < datetime('now', ?) AND trust_score < ?", (f"-{days} days", trust_threshold))
        deleted = cur.rowcount; conn.commit(); conn.close()
        return {"migrated": deleted}

    def get_tool_schemas(self):
        return [
            {"name": "memory_learn", "description": "学习: 沉淀原则/教训(W/L入脑)，实体/缓存(I/D降级)", "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "source": {"type": "string", "default": "general"}, "source_session": {"type": "string"}}, "required": ["content"]}},
            {"name": "memory_recall", "description": "回忆: 11步防漏检索(引擎优先,文件兜底,Miss返FIRST框架)", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "memory_evolve", "description": "进化: 纠正旧认知，升级方法论(旧认知降权失败则中止)", "parameters": {"type": "object", "properties": {"old_fact_id": {"type": "string"}, "new_content": {"type": "string"}, "source_session": {"type": "string"}}, "required": ["old_fact_id", "new_content"]}},
            {"name": "memory_admin", "description": "系统运维(snr/清理)", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["snr", "migrate"]}, "days": {"type": "integer", "default": 30}}}},
        ]

    def handle_tool_call(self, name, args):
        if args is None: args = {}
        fn = {"memory_learn": self.memory_learn, "memory_recall": self.memory_recall, "memory_evolve": self.memory_evolve, "memory_admin": self.memory_admin}.get(name)
        if not fn: return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            sig = inspect.signature(fn)
            for pname, param in sig.parameters.items():
                if param.name == 'self': continue
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD): continue
                if param.default == inspect.Parameter.empty and pname not in args:
                    return json.dumps({"error": "MISSING_PARAM", "detail": f"missing required: {pname}", "tool": name}, ensure_ascii=False)
        except Exception: pass

        try: return json.dumps(fn(**args), default=str, ensure_ascii=False)
        except Exception as e: return json.dumps({"error": str(e)}, ensure_ascii=False)
