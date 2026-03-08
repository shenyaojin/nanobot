import pytest
import numpy as np
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from nanobot.agent.memory import VectorStore, MemoryStore

def test_vector_store_basic_ops(tmp_path):
    """Test that VectorStore can add and search for vectors."""
    store = VectorStore(tmp_path)
    
    # Create some dummy vectors (3-dimensional for simplicity)
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0]
    vec3 = [0.9, 0.1, 0.0] # Similar to vec1
    
    store.add([vec1, vec2], ["I love cats", "I love dogs"])
    
    # Search for something similar to vec1
    results = store.search(vec3, top_k=1)
    
    assert len(results) == 1
    assert results[0][0] == "I love cats"
    assert results[0][1] > 0.8 # High similarity

def test_vector_store_persistence(tmp_path):
    """Test that data survives a reload."""
    store1 = VectorStore(tmp_path)
    store1.add([[0.1, 0.2]], ["Test snippet"])
    
    # Create a new store instance pointing to same path
    store2 = VectorStore(tmp_path)
    assert store2.metadata == ["Test snippet"]
    assert store2.vectors.shape == (1, 2)

@pytest.mark.asyncio
async def test_memory_store_rag_injection(tmp_path):
    """Test that MemoryStore.get_relevant_history works as expected."""
    mem = MemoryStore(tmp_path.parent) # tmp_path is the memory dir
    mem.memory_dir = tmp_path
    mem.vector_store = VectorStore(tmp_path)
    
    # Add a "memory"
    mem.vector_store.add([[1.0, 0.0]], ["DeepSeek is a great model"])
    
    # Mock provider
    mock_provider = MagicMock()
    mock_provider.embed = AsyncMock(return_value=[[0.95, 0.05]])
    
    context = await mem.get_relevant_history(mock_provider, "Tell me about DeepSeek")
    
    assert "Relevant Past Context" in context
    assert "DeepSeek is a great model" in context

@pytest.mark.asyncio
async def test_memory_consolidation_indexing(tmp_path):
    """Test that consolidation actually triggers vector indexing."""
    mem = MemoryStore(tmp_path.parent)
    mem.memory_dir = tmp_path
    mem.vector_store = VectorStore(tmp_path)
    
    # Mock session and provider
    session = MagicMock()
    session.messages = [{"role": "user", "content": "hello"}]
    session.last_consolidated = 0
    
    mock_provider = MagicMock()
    # Mock the LLM tool call response
    mock_response = MagicMock()
    mock_response.has_tool_calls = True
    mock_response.tool_calls = [
        MagicMock(arguments={
            "history_entry": "Summary",
            "memory_update": "Facts",
            "important_snippets": ["Bitcoin is digital gold"]
        })
    ]
    mock_provider.chat = AsyncMock(return_value=mock_response)
    mock_provider.embed = AsyncMock(return_value=[[0.5, 0.5]])
    
    await mem.consolidate(session, mock_provider, "test-model", archive_all=True)
    
    # Verify snippet was indexed
    assert "Bitcoin is digital gold" in mem.vector_store.metadata
