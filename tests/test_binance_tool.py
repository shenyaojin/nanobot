import os
import pytest
from unittest.mock import MagicMock, patch
from nanobot.agent.tools.binance import BinanceTool

@pytest.mark.asyncio
async def test_binance_tool_properties():
    tool = BinanceTool()
    assert tool.name == "binance"
    assert "Interact with Binance exchange" in tool.description
    assert "action" in tool.parameters["required"]

@pytest.mark.asyncio
async def test_binance_tool_missing_import():
    # Force ImportError for the tool's lazy load
    with patch.dict('sys.modules', {'coin_margined_fra.core.exchange': None}):
        tool = BinanceTool()
        result = await tool.execute(action="get_balances")
        assert "ImportError" in result or "not installed" in result

@pytest.mark.asyncio
async def test_binance_tool_missing_creds():
    # Ensure no BINANCE env vars exist
    with patch.dict(os.environ, {}, clear=True):
        tool = BinanceTool(sandbox_mode=True)
        # We need to mock the import since it's only available in oc_crypto env
        with patch('coin_margined_fra.core.exchange.Exchange', MagicMock()):
             result = await tool.execute(action="get_balances")
             assert "Binance API credentials not found" in result

@pytest.mark.asyncio
async def test_binance_tool_param_validation():
    tool = BinanceTool()
    
    # Missing required 'action'
    errors = tool.validate_params({})
    assert any("missing required action" in e for e in errors)
    
    # Valid action
    errors = tool.validate_params({"action": "get_balances"})
    assert not errors

    # Invalid action
    errors = tool.validate_params({"action": "invalid_action"})
    assert any("must be one of" in e for e in errors)

@pytest.mark.asyncio
async def test_binance_tool_execute_delegation():
    # Mock Exchange and its methods
    mock_exchange = MagicMock()
    mock_exchange.get_balances.return_value = MagicMock(
        spot=MagicMock(empty=True),
        inverse=MagicMock(empty=True)
    )

    with patch.dict(os.environ, {
        "BINANCE_TESTNET_API_KEY": "fake_key",
        "BINANCE_TESTNET_API_SECRET": "fake_secret"
    }):
        with patch('coin_margined_fra.core.exchange.Exchange', return_value=mock_exchange):
            tool = BinanceTool(sandbox_mode=True)
            result = await tool.execute(action="get_balances")
            assert "No non-zero balances found" in result
            mock_exchange.get_balances.assert_called_once()
