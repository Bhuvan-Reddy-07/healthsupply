from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple

# Grace period: events must be within 7 days
MAX_GRACE_PERIOD_DAYS = 7

# Source reliability weights
SOURCE_RELIABILITY_WEIGHTS = {
    "edge_pwa": 1.00,
    "sensor": 0.95,
    "batch_sync": 0.90,
    "sms_fallback": 0.75,
    "manual_override": 0.70,
    "simulator": 1.00,
}

def evaluate_freshness(event_timestamp: datetime, reference_time: datetime = None) -> Tuple[float, bool]:
    """
    Evaluates freshness of an event against a 7-day grace period.
    Returns (freshness_score, is_within_grace).
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    
    # Ensure UTC timezone awareness
    if event_timestamp.tzinfo is None:
        event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    delta = reference_time - event_timestamp
    age_seconds = delta.total_seconds()

    # Reject future events beyond 1 hour clock skew
    if age_seconds < -3600:
        return 0.0, False

    age_hours = max(0.0, age_seconds / 3600.0)

    if age_hours <= 1.0:
        score = 1.0
    elif age_hours <= 24.0:
        score = 0.95
    elif age_hours <= 72.0: # 3 days
        score = 0.85
    elif age_hours <= (MAX_GRACE_PERIOD_DAYS * 24.0): # 7 days
        score = 0.70
    else:
        # Out of 7-day grace period
        return 0.0, False

    return score, True

def evaluate_plausibility(subject: str, payload: Dict[str, Any]) -> Tuple[float, bool, str]:
    """
    Evaluates physiological & physical plausibility of ingested payloads.
    Returns (plausibility_score, is_plausible, error_reason).
    """
    if subject == "stock.tx":
        qty = payload.get("quantity", 0)
        if qty is None or qty <= 0:
            return 0.0, False, "ERR_NEGATIVE_OR_ZERO_QTY"
        if qty > 5000:
            # Implausible single clinic transaction size
            return 0.4, True, "WARN_HIGH_DISPENSE_VOLUME"
        return 1.0, True, ""

    elif subject == "sensor.temp":
        temp = payload.get("temperature_c")
        if temp is None or temp < -50.0 or temp > 70.0:
            return 0.0, False, "ERR_TEMPERATURE_OUT_OF_PHYSICAL_RANGE"
        return 1.0, True, ""

    elif subject == "bed.state":
        total = payload.get("total_beds", 0)
        occupied = payload.get("occupied_beds", 0)
        if total < 0 or occupied < 0:
            return 0.0, False, "ERR_NEGATIVE_BED_COUNT"
        if occupied > (total * 1.5): # Surge capacity capped at 150%
            return 0.2, False, "ERR_IMPLAUSIBLE_BED_OVERCAPACITY"
        return 1.0, True, ""

    elif subject == "staff.attendance":
        docs = payload.get("doctors_present", 0)
        nurses = payload.get("nurses_present", 0)
        pharms = payload.get("pharmacists_present", 0)
        if docs < 0 or nurses < 0 or pharms < 0:
            return 0.0, False, "ERR_NEGATIVE_STAFF_COUNT"
        return 1.0, True, ""

    return 1.0, True, ""

def compute_data_quality_score(
    subject: str,
    source: str,
    event_timestamp: datetime,
    payload: Dict[str, Any],
    reference_time: datetime = None
) -> Tuple[float, float, bool, str]:
    """
    Composite Data-Quality Engine:
    Quality Score = 0.40 * Freshness + 0.30 * Source Reliability + 0.30 * Plausibility
    Returns (quality_score, source_reliability, is_valid, reason_code).
    """
    freshness, within_grace = evaluate_freshness(event_timestamp, reference_time)
    if not within_grace:
        return 0.0, SOURCE_RELIABILITY_WEIGHTS.get(source, 0.5), False, "ERR_TIMESTAMP_OUT_OF_GRACE"

    plausibility, is_plausible, err_reason = evaluate_plausibility(subject, payload)
    if not is_plausible:
        return 0.0, SOURCE_RELIABILITY_WEIGHTS.get(source, 0.5), False, err_reason

    reliability = SOURCE_RELIABILITY_WEIGHTS.get(source, 0.60)
    composite = (0.40 * freshness) + (0.30 * reliability) + (0.30 * plausibility)
    
    return round(composite, 3), reliability, True, ""
