import pytest
from backend.app.ingestion.nats_client import IngestionEventBus

def test_nats_fallback_guard_detects_reachable_server_with_unconnected_bus(monkeypatch):
    """
    CRITICAL ARCHITECTURAL SAFEGUARD:
    Guarantees that if NATS is reachable, the in-process fallback bus cannot quietly masquerade
    as the primary path.
    """
    bus = IngestionEventBus(nats_url="nats://localhost:4222")
    # Simulate that localhost:4222 is alive and reachable
    monkeypatch.setattr(bus, "is_nats_socket_listening", lambda url: True)
    bus.js = None # But Jetstream client is not connected

    with pytest.raises(RuntimeError) as exc_info:
        bus.assert_no_fallback_if_nats_reachable()

    assert "SAFETY VIOLATION" in str(exc_info.value)
    assert "Fallback is strictly prohibited" in str(exc_info.value)

def test_nats_fallback_allowed_when_truly_offline(monkeypatch):
    """When NATS port is genuinely closed/offline, assertion passes cleanly."""
    bus = IngestionEventBus(nats_url="nats://nonexistent:4222")
    monkeypatch.setattr(bus, "is_nats_socket_listening", lambda url: False)
    bus.js = None
    # Should not raise
    bus.assert_no_fallback_if_nats_reachable()
