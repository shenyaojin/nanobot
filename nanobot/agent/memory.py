"""Memory system for persistent agent memory."""

from __future__ import annotations

import json
import numpy as np
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from nanobot.utils.helpers import ensure_dir

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.session.manager import Session


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Full updated long-term memory as markdown. Include all existing "
                        "facts plus new ones. Return unchanged if nothing new.",
                    },
                    "important_snippets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Extract 1-3 key specific facts or details from the current conversation "
                        "for vector indexing. Keep each snippet under 200 chars.",
                    },
                },
                "required": ["history_entry", "memory_update", "important_snippets"],
            },
        },
    }
]


class VectorStore:
    """Lightweight vector storage using numpy and JSON."""

    def __init__(self, path: Path):
        self.vectors_file = path / "vectors.npy"
        self.meta_file = path / "metadata.json"
        self.vectors: np.ndarray = np.array([], dtype=np.float32)
        self.metadata: list[str] = []
        self._load()

    def _load(self):
        if self.vectors_file.exists():
            self.vectors = np.load(self.vectors_file).astype(np.float32)
        if self.meta_file.exists():
            with open(self.meta_file, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

    def _save(self):
        np.save(self.vectors_file, self.vectors)
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def add(self, vectors: list[list[float]], texts: list[str]):
        if not vectors:
            return
        new_vecs = np.array(vectors, dtype=np.float32)
        if self.vectors.size == 0:
            self.vectors = new_vecs
        else:
            self.vectors = np.vstack([self.vectors, new_vecs])
        self.metadata.extend(texts)
        self._save()

    def search(self, query_vec: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        if self.vectors.size == 0:
            return []
        
        q = np.array(query_vec, dtype=np.float32)
        # Cosine similarity
        norm_v = np.linalg.norm(self.vectors, axis=1)
        norm_q = np.linalg.norm(q)
        if norm_q == 0:
            return []
        
        sims = np.dot(self.vectors, q) / (norm_v * norm_q)
        top_indices = np.argsort(sims)[::-1][:top_k]
        
        return [(self.metadata[i], float(sims[i])) for i in top_indices if sims[i] > 0.3]


class MemoryStore:
    """Three-layer memory: MEMORY.md (facts) + HISTORY.md (log) + VectorStore (RAG)."""

    def __init__(self, workspace: Path):
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self.vector_store = VectorStore(self.memory_dir)

    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    async def get_relevant_history(self, provider: LLMProvider, query: str, top_k: int = 3) -> str:
        """Search vector store for relevant snippets to inject into prompt."""
        if not query or self.vector_store.vectors.size == 0:
            return ""
        
        try:
            vecs = await provider.embed([query])
            if not vecs:
                return ""
            
            hits = self.vector_store.search(vecs[0], top_k=top_k)
            if not hits:
                return ""
            
            snippets = "\n".join([f"- {text}" for text, score in hits])
            return f"\n## Relevant Past Context\n{snippets}\n"
        except Exception as e:
            logger.error("Vector search failed: {}", e)
            return ""

    async def consolidate(
        self,
        session: Session,
        provider: LLMProvider,
        model: str,
        *,
        archive_all: bool = False,
        memory_window: int = 50,
    ) -> bool:
        """Consolidate old messages into MEMORY.md + HISTORY.md via LLM tool call.

        Returns True on success (including no-op), False on failure.
        """
        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} messages", len(session.messages))
        else:
            keep_count = memory_window // 2
            if len(session.messages) <= keep_count:
                return True
            if len(session.messages) - session.last_consolidated <= 0:
                return True
            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return True
            logger.info("Memory consolidation: {} to consolidate, {} keep", len(old_messages), keep_count)

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")

        current_memory = self.read_long_term()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{chr(10).join(lines)}"""

        try:
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=model,
            )

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory, skipping")
                return False

            args = response.tool_calls[0].arguments
            # Some providers return arguments as a JSON string instead of dict
            if isinstance(args, str):
                args = json.loads(args)
            # Some providers return arguments as a list (handle edge case)
            if isinstance(args, list):
                if args and isinstance(args[0], dict):
                    args = args[0]
                else:
                    logger.warning("Memory consolidation: unexpected arguments as empty or non-dict list")
                    return False
            if not isinstance(args, dict):
                logger.warning("Memory consolidation: unexpected arguments type {}", type(args).__name__)
                return False

            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)
            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)
            
            if snippets := args.get("important_snippets"):
                if isinstance(snippets, list) and snippets:
                    logger.info("Vector indexing {} snippets", len(snippets))
                    vecs = await provider.embed(snippets)
                    if vecs:
                        self.vector_store.add(vecs, snippets)

            session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return False
