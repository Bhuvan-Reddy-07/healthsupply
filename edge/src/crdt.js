import { db, getFacilityId } from './db';

// Lamport sequence state
let lamportSeq = 0;

export function generateCrdtId(facilityId) {
  lamportSeq += 1;
  const rand = Math.random().toString(36).substring(2, 9);
  return `CRDT-${facilityId}-${Date.now()}-${lamportSeq}-${rand}`;
}

/**
 * Record a transaction locally into Automerge CRDT queue and update local stock optimistically.
 */
export async function recordLocalTransaction({
  itemId,
  batchId = null,
  txType, // dispense, receive, waste_expired, waste_damaged, transfer_in
  quantity,
  source = 'edge_pwa'
}) {
  const facilityId = await getFacilityId();
  const crdtTxId = generateCrdtId(facilityId);
  const nowIso = new Date().toISOString();

  // Optimistic local stock update
  if (batchId) {
    const batch = await db.batches.get(batchId);
    if (batch) {
      let newQty = batch.current_quantity;
      if (txType === 'dispense' || txType === 'waste_expired' || txType === 'waste_damaged') {
        newQty = Math.max(0, batch.current_quantity - quantity);
      } else if (txType === 'receive' || txType === 'transfer_in') {
        newQty = batch.current_quantity + quantity;
      }
      await db.batches.update(batchId, {
        current_quantity: newQty,
        status: newQty === 0 ? 'depleted' : 'active'
      });
    }
  }

  const txRecord = {
    crdt_tx_id: crdtTxId,
    facility_id: facilityId,
    item_id: itemId,
    batch_id: batchId,
    tx_type: txType,
    quantity: Number(quantity),
    tx_timestamp: nowIso,
    source,
    created_at: nowIso,
    status: 'pending'
  };

  // Append to local Dexie queue
  await db.pending_queue.put(txRecord);
  return txRecord;
}

/**
 * Synchronize local pending queue with backend ingestion endpoint.
 */
export async function syncPendingQueue(apiUrl = '/api/v1') {
  const facilityId = await getFacilityId();
  const pending = await db.pending_queue.where('status').equals('pending').toArray();

  if (pending.length === 0) {
    return { synced: 0, queueDepth: 0, status: 'idle' };
  }

  try {
    const payload = {
      facility_id: facilityId,
      client_timestamp: new Date().toISOString(),
      transactions: pending
    };

    const res = await fetch(`${apiUrl}/ingest/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`Sync failed with HTTP ${res.status}`);
    }

    const data = await res.json();

    // Mark synced records
    const syncedIds = pending.map((p) => p.crdt_tx_id);
    await db.pending_queue.bulkDelete(syncedIds);

    // Update sync metadata
    await db.settings.put({ key: 'last_sync', value: new Date().toISOString() });

    const remaining = await db.pending_queue.where('status').equals('pending').count();
    return {
      synced: data.processed + data.deduplicated,
      deduplicated: data.deduplicated,
      quarantined: data.quarantined,
      queueDepth: remaining,
      status: 'success'
    };
  } catch (err) {
    console.warn('Sync attempt failed (offline or network error):', err);
    const depth = await db.pending_queue.where('status').equals('pending').count();
    return { synced: 0, queueDepth: depth, status: 'error', error: err.message };
  }
}
