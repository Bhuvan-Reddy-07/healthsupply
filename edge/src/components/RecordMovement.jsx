import React, { useState, useEffect } from 'react';
import { db } from '../db';
import { recordLocalTransaction } from '../crdt';

export function RecordMovement({ onTransactionRecorded }) {
  const [txType, setTxType] = useState('dispense'); // Tap 1
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState(''); // Tap 2
  const [quantity, setQuantity] = useState(10);
  const [successMsg, setSuccessMsg] = useState('');

  useEffect(() => {
    loadBatches();
  }, []);

  async function loadBatches() {
    const list = await db.batches.toArray();
    setBatches(list);
    if (list.length > 0) {
      setSelectedBatchId(list[0].id);
    }
  }

  async function handleSubmit(e) {
    if (e) e.preventDefault();
    if (!selectedBatchId) return;

    const batch = batches.find((b) => b.id === selectedBatchId);
    if (!batch) return;

    const tx = await recordLocalTransaction({
      itemId: batch.item_id,
      batchId: batch.id,
      txType,
      quantity: Number(quantity)
    });

    setSuccessMsg(`Recorded ${quantity} units ${txType} (CRDT ID: ${tx.crdt_tx_id.substring(0, 18)}...)`);
    setTimeout(() => setSuccessMsg(''), 4000);

    // Refresh local batches
    await loadBatches();
    if (onTransactionRecorded) onTransactionRecorded();
  }

  return (
    <div style={{ padding: '16px', maxWidth: '640px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#14b8a6', marginBottom: '12px' }}>
        ⚡ Record Movement (Max 3 Taps)
      </h2>

      {/* TAP 1: Select Type */}
      <div style={{ marginBottom: '16px' }}>
        <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>
          Tap 1: Movement Type
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
          {[
            { id: 'dispense', label: 'Dispense' },
            { id: 'receive', label: 'Receive' },
            { id: 'waste_expired', label: 'Waste' },
            { id: 'transfer_in', label: 'Transfer' }
          ].map((type) => (
            <button
              key={type.id}
              type="button"
              onClick={() => setTxType(type.id)}
              style={{
                padding: '10px 4px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '0.85rem',
                background: txType === type.id ? '#0d9488' : '#1e293b',
                color: txType === type.id ? '#ffffff' : '#94a3b8'
              }}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>

      {/* TAP 2: Select Item Batch & Quantity Preset */}
      <div style={{ marginBottom: '16px' }}>
        <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>
          Tap 2: Item & Batch
        </label>
        <select
          value={selectedBatchId}
          onChange={(e) => setSelectedBatchId(e.target.value)}
          style={{
            width: '100%',
            padding: '12px',
            background: '#1e293b',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '6px',
            marginBottom: '10px',
            fontSize: '0.95rem'
          }}
        >
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name || b.item_id} (Batch: {b.batch_number}, Stock: {b.current_quantity})
            </option>
          ))}
        </select>

        {/* Quick Quantity Presets */}
        <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>
          Quantity Preset:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px' }}>
          {[5, 10, 20, 50, 100].map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQuantity(q)}
              style={{
                padding: '8px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 'bold',
                background: quantity === q ? '#0369a1' : '#1e293b',
                color: quantity === q ? '#fff' : '#cbd5e1'
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* TAP 3: Submit Action */}
      <button
        type="button"
        onClick={handleSubmit}
        style={{
          width: '100%',
          padding: '14px',
          background: '#059669',
          color: '#ffffff',
          border: 'none',
          borderRadius: '8px',
          fontSize: '1.1rem',
          fontWeight: 'bold',
          cursor: 'pointer',
          marginTop: '8px',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.2)'
        }}
      >
        Tap 3: Confirm & Record Transaction
      </button>

      {successMsg && (
        <div
          style={{
            marginTop: '16px',
            padding: '12px',
            background: '#064e3b',
            color: '#34d399',
            borderRadius: '6px',
            fontSize: '0.9rem',
            textAlign: 'center',
            fontWeight: '500'
          }}
        >
          {successMsg}
        </div>
      )}
    </div>
  );
}
