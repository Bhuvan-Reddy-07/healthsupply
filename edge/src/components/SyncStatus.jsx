import React, { useState, useEffect } from 'react';
import { db, getFacilityId } from '../db';
import { syncPendingQueue } from '../crdt';

export function SyncStatus({ isSimulatedOffline, onToggleSimulatedOffline }) {
  const [queueDepth, setQueueDepth] = useState(0);
  const [lastSync, setLastSync] = useState('Never');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncLog, setSyncLog] = useState([]);
  const [facilityId, setFacilityIdState] = useState('');

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  async function loadStatus() {
    const depth = await db.pending_queue.where('status').equals('pending').count();
    setQueueDepth(depth);

    const setting = await db.settings.get('last_sync');
    if (setting) {
      setLastSync(new Date(setting.value).toLocaleTimeString());
    }

    const fac = await getFacilityId();
    setFacilityIdState(fac);
  }

  async function handleSyncNow() {
    if (isSimulatedOffline) {
      alert('Cannot sync while in Simulated Offline mode!');
      return;
    }
    setIsSyncing(true);
    const result = await syncPendingQueue();
    setIsSyncing(false);

    const logEntry = {
      timestamp: new Date().toLocaleTimeString(),
      status: result.status,
      synced: result.synced,
      deduplicated: result.deduplicated || 0,
      quarantined: result.quarantined || 0
    };
    setSyncLog((prev) => [logEntry, ...prev.slice(0, 4)]);
    await loadStatus();
  }

  return (
    <div style={{ padding: '16px', maxWidth: '640px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#14b8a6', marginBottom: '12px' }}>
        🔄 Sync & Offline Status
      </h2>

      {/* Connection & Network Status Card */}
      <div
        style={{
          background: '#1e293b',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '16px',
          borderLeft: isSimulatedOffline ? '4px solid #ef4444' : '4px solid #10b981'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Connection State</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: isSimulatedOffline ? '#f87171' : '#34d399' }}>
              {isSimulatedOffline ? '🔴 Offline (Simulated 2G/Cut)' : '🟢 Online (Synchronized)'}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
              Facility: <strong>{facilityId}</strong>
            </div>
          </div>
          <button
            type="button"
            onClick={onToggleSimulatedOffline}
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 'bold',
              background: isSimulatedOffline ? '#10b981' : '#b91c1c',
              color: '#ffffff',
              fontSize: '0.8rem'
            }}
          >
            {isSimulatedOffline ? 'Go Online' : 'Kill Network'}
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div style={{ background: '#1e293b', padding: '14px', borderRadius: '8px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Queue Depth</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: queueDepth > 0 ? '#fbbf24' : '#38bdf8' }}>
            {queueDepth}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Pending Local CRDT TXs</div>
        </div>

        <div style={{ background: '#1e293b', padding: '14px', borderRadius: '8px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Last Sync</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: '#f1f5f9', marginTop: '4px' }}>
            {lastSync}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>Auto-retry on reconnect</div>
        </div>
      </div>

      {/* Sync Button */}
      <button
        type="button"
        onClick={handleSyncNow}
        disabled={isSyncing || isSimulatedOffline}
        style={{
          width: '100%',
          padding: '14px',
          background: isSimulatedOffline ? '#475569' : '#0284c7',
          color: '#ffffff',
          border: 'none',
          borderRadius: '8px',
          fontSize: '1rem',
          fontWeight: 'bold',
          cursor: isSimulatedOffline ? 'not-allowed' : 'pointer',
          marginBottom: '16px'
        }}
      >
        {isSyncing ? 'Synchronizing Queue...' : 'Sync Now with Central Server'}
      </button>

      {/* Recent Sync Log */}
      {syncLog.length > 0 && (
        <div style={{ background: '#1e293b', padding: '12px', borderRadius: '8px' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#94a3b8', marginBottom: '8px' }}>
            Recent Sync History
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {syncLog.map((log, idx) => (
              <div key={idx} style={{ fontSize: '0.8rem', color: '#cbd5e1', display: 'flex', justifyContent: 'space-between' }}>
                <span>{log.timestamp}</span>
                <span style={{ color: log.status === 'success' ? '#34d399' : '#f87171' }}>
                  Synced: {log.synced} (Deduped: {log.deduplicated})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
