import asyncio
import json
from typing import Dict, Any, Callable, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.database import SessionLocal
from backend.app.ingestion.pipeline import (
    ingest_stock_transaction,
    ingest_bed_state,
    ingest_staff_attendance,
    ingest_sensor_temperature
)

NATS_SUBJECTS = {
    "STOCK_TX": "stock.tx",
    "BED_STATE": "bed.state",
    "STAFF_ATTENDANCE": "staff.attendance",
    "SENSOR_TEMP": "sensor.temp",
}

class IngestionEventBus:
    """
    Unified Ingestion Event Bus.
    Supports live NATS JetStream when available, with in-process async routing fallback.
    """
    def __init__(self, nats_url: str = None):
        self.nats_url = nats_url or settings.NATS_URL
        self.nc = None
        self.js = None
        self._handlers = {
            NATS_SUBJECTS["STOCK_TX"]: ingest_stock_transaction,
            NATS_SUBJECTS["BED_STATE"]: ingest_bed_state,
            NATS_SUBJECTS["STAFF_ATTENDANCE"]: ingest_staff_attendance,
            NATS_SUBJECTS["SENSOR_TEMP"]: ingest_sensor_temperature,
        }

    async def connect(self) -> bool:
        """Attempts connection to live NATS server."""
        try:
            import nats
            self.nc = await nats.connect(self.nats_url, connect_timeout=2)
            self.js = self.nc.jetstream()
            logger.info(f"Connected to live NATS JetStream at {self.nats_url}")
            return True
        except Exception as e:
            logger.info(f"NATS live connection unavailable ({e}). Using in-process event bus.")
            self.nc = None
            self.js = None
            return False

    async def publish(self, subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publishes an event to a NATS subject.
        If live NATS is active, publishes via JetStream.
        Otherwise, routes immediately through the ingestion pipeline synchronously/async.
        """
        data_bytes = json.dumps(payload, default=str).encode("utf-8")

        if self.js is not None:
            try:
                ack = await self.js.publish(subject, data_bytes)
                logger.info(f"Published to NATS {subject} (seq: {ack.seq})")
                return {"status": "published_nats", "subject": subject, "seq": ack.seq}
            except Exception as e:
                logger.warning(f"NATS publish error: {e}. Falling back to pipeline.")

        # Local pipeline execution
        return self._dispatch_local(subject, payload)

    def _dispatch_local(self, subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches an event directly to the appropriate ingestion pipeline handler."""
        handler = self._handlers.get(subject)
        if not handler:
            raise ValueError(f"No registered handler for subject '{subject}'")

        db = SessionLocal()
        try:
            result, is_quarantined, status_msg = handler(db, payload)
            return {
                "status": "quarantined" if is_quarantined else "processed",
                "subject": subject,
                "reason_code": status_msg if is_quarantined else None,
                "result_id": getattr(result, "id", None) if result else None
            }
        finally:
            db.close()

    async def close(self):
        if self.nc:
            await self.nc.drain()
            self.nc = None

event_bus = IngestionEventBus()
