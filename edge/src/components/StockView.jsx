import React, { useState, useEffect } from 'react';
import { db } from '../db';

export function StockView() {
  const [batches, setBatches] = useState([]);
  const [search, setSearch] = useState('');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [decodedBarcode, setDecodedBarcode] = useState(null);

  useEffect(() => {
    loadBatches();
  }, []);

  async function loadBatches() {
    let list = await db.batches.toArray();
    if (list.length === 0) {
      // Seed default sample data into Dexie for immediate offline usability
      const sampleBatches = [
        { id: 'B-01', item_id: 'MED-HV-001', batch_number: 'B-2231', current_quantity: 450, expiry_date: '2026-12-31', status: 'active', name: 'Paracetamol 500mg' },
        { id: 'B-02', item_id: 'MED-HV-006', batch_number: 'B-4089', current_quantity: 120, expiry_date: '2026-08-15', status: 'active', name: 'Amoxicillin 500mg' },
        { id: 'B-03', item_id: 'MED-HV-004', batch_number: 'B-9912', current_quantity: 85, expiry_date: '2026-11-20', status: 'active', name: 'ORS Sachets 20.5g' },
        { id: 'B-04', item_id: 'MED-CC-001', batch_number: 'B-1102', current_quantity: 40, expiry_date: '2026-06-30', status: 'active', name: 'Oxytocin 10 IU (2-8°C)' },
      ];
      await db.batches.bulkPut(sampleBatches);
      list = sampleBatches;
    }
    setBatches(list);
  }

  // GS1 DataMatrix Decoder
  // Format: (01)GTIN(17)YYMMDD(10)BATCH or raw 01089012345678901726123110B-2231
  function decodeGS1DataMatrix(raw) {
    let clean = raw.trim();
    let gtin = null;
    let expiry = null;
    let batch = null;

    if (clean.includes('(01)')) {
      const gtinMatch = clean.match(/\(01\)(\d{14})/);
      const expMatch = clean.match(/\(17\)(\d{6})/);
      const batchMatch = clean.match(/\(10\)([^\(\)]+)/);
      if (gtinMatch) gtin = gtinMatch[1];
      if (expMatch) {
        const y = '20' + expMatch[1].substring(0, 2);
        const m = expMatch[1].substring(2, 4);
        const d = expMatch[1].substring(4, 6);
        expiry = `${y}-${m}-${d}`;
      }
      if (batchMatch) batch = batchMatch[1];
    } else {
      // Continuous string
      const match = clean.match(/01(\d{14})17(\d{6})10([A-Za-z0-9\-]+)/);
      if (match) {
        gtin = match[1];
        const y = '20' + match[2].substring(0, 2);
        const m = match[2].substring(2, 4);
        const d = match[2].substring(4, 6);
        expiry = `${y}-${m}-${d}`;
        batch = match[3];
      }
    }

    if (gtin || batch) {
      return { gtin, expiry, batch };
    }
    return null;
  }

  function handleBarcodeScan(e) {
    e.preventDefault();
    const result = decodeGS1DataMatrix(barcodeInput);
    setDecodedBarcode(result);
    if (result && result.batch) {
      setSearch(result.batch);
    }
  }

  const filtered = batches.filter(
    (b) =>
      b.batch_number.toLowerCase().includes(search.toLowerCase()) ||
      (b.name && b.name.toLowerCase().includes(search.toLowerCase())) ||
      b.item_id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ padding: '16px', maxWidth: '640px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#14b8a6', marginBottom: '12px' }}>
        📦 Facility Stock View
      </h2>

      {/* Barcode Scanner Box */}
      <div style={{ background: '#1e293b', padding: '12px', borderRadius: '8px', marginBottom: '16px' }}>
        <form onSubmit={handleBarcodeScan} style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            placeholder="Scan GS1 DataMatrix (e.g. (01)08901234567890(17)261231(10)B-2231)"
            value={barcodeInput}
            onChange={(e) => setBarcodeInput(e.target.value)}
            style={{ flex: 1, padding: '8px 12px', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', borderRadius: '6px' }}
          />
          <button
            type="submit"
            style={{ padding: '8px 16px', background: '#0d9488', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            Decode
          </button>
        </form>

        {decodedBarcode && (
          <div style={{ marginTop: '8px', padding: '8px', background: '#0f172a', borderRadius: '6px', fontSize: '0.85rem' }}>
            <span style={{ color: '#2dd4bf', fontWeight: 'bold' }}>GS1 Decoded:</span>{' '}
            Batch: <strong>{decodedBarcode.batch || 'N/A'}</strong> | Expiry: <strong>{decodedBarcode.expiry || 'N/A'}</strong> | GTIN: <strong>{decodedBarcode.gtin || 'N/A'}</strong>
          </div>
        )}
      </div>

      {/* Search Input */}
      <input
        type="text"
        placeholder="Filter by drug name or batch..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', borderRadius: '8px', marginBottom: '12px' }}
      />

      {/* Batches Table / Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {filtered.map((b) => (
          <div
            key={b.id}
            style={{
              background: '#1e293b',
              padding: '12px',
              borderRadius: '8px',
              borderLeft: b.current_quantity === 0 ? '4px solid #ef4444' : '4px solid #10b981',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              <div style={{ fontWeight: 'bold', fontSize: '1rem', color: '#f1f5f9' }}>{b.name || b.item_id}</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                Batch: <span style={{ color: '#e2e8f0' }}>{b.batch_number}</span> | Expires:{' '}
                <span style={{ color: '#fbbf24' }}>{b.expiry_date}</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: b.current_quantity === 0 ? '#f87171' : '#34d399' }}>
                {b.current_quantity}
              </div>
              <div style={{ fontSize: '0.75rem', color: b.current_quantity === 0 ? '#ef4444' : '#64748b' }}>
                {b.current_quantity === 0 ? 'STOCKOUT' : 'On-Hand'}
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', color: '#64748b', padding: '24px' }}>No matching batches found in offline store.</div>
        )}
      </div>
    </div>
  );
}
