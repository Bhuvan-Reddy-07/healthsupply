import Dexie from 'dexie';

export const db = new Dexie('HealthSupplyEdgeDB');

db.version(1).stores({
  batches: 'id, item_id, batch_number, expiry_date, current_quantity, status',
  items: 'id, name, category, velocity_class, requires_cold_chain',
  pending_queue: 'crdt_tx_id, facility_id, item_id, tx_type, created_at, status',
  alerts: 'id, facility_id, alert_type, severity, created_at',
  settings: 'key, value'
});

// Seed default fallback facility ID if not set
export async function getFacilityId() {
  const setting = await db.settings.get('facility_id');
  return setting ? setting.value : 'FAC-A-001';
}

export async function setFacilityId(id) {
  await db.settings.put({ key: 'facility_id', value: id });
}
