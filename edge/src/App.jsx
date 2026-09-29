import React, { useState, useEffect } from 'react';
import { StockView } from './components/StockView';
import { RecordMovement } from './components/RecordMovement';
import { MyAlerts } from './components/MyAlerts';
import { SyncStatus } from './components/SyncStatus';
import { db } from './db';

export function App() {
  const [activeTab, setActiveTab] = useState('stock');
  const [isSimulatedOffline, setIsSimulatedOffline] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    updatePendingBadge();
    const interval = setInterval(updatePendingBadge, 3000);
    return () => clearInterval(interval);
  }, []);

  async function updatePendingBadge() {
    try {
      const count = await db.pending_queue.where('status').equals('pending').count();
      setPendingCount(count);
    } catch (e) {
      // Ignore initial load race
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', color: '#f8fafc', paddingBottom: '70px', fontFamily: 'Inter, sans-serif' }}>
      {/* Top Navbar */}
      <header
        style={{
          background: '#1e293b',
          padding: '12px 16px',
          borderBottom: '1px solid #334155',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.2rem' }}>🏥</span>
          <div>
            <h1 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold', color: '#14b8a6' }}>
              HealthSupply Edge
            </h1>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PHC / Facility Node</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              padding: '4px 8px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 'bold',
              background: isSimulatedOffline ? '#7f1d1d' : '#064e3b',
              color: isSimulatedOffline ? '#fca5a5' : '#6ee7b7'
            }}
          >
            {isSimulatedOffline ? 'OFFLINE' : 'ONLINE'}
          </span>
          {pendingCount > 0 && (
            <span
              style={{
                padding: '4px 8px',
                borderRadius: '9999px',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                background: '#854d0e',
                color: '#fef08a'
              }}
            >
              {pendingCount} queued
            </span>
          )}
        </div>
      </header>

      {/* Screen Views (Only 4 screens — zero scope creep) */}
      <main style={{ marginTop: '8px' }}>
        {activeTab === 'stock' && <StockView />}
        {activeTab === 'movement' && <RecordMovement onTransactionRecorded={updatePendingBadge} />}
        {activeTab === 'alerts' && <MyAlerts />}
        {activeTab === 'sync' && (
          <SyncStatus
            isSimulatedOffline={isSimulatedOffline}
            onToggleSimulatedOffline={() => setIsSimulatedOffline(!isSimulatedOffline)}
          />
        )}
      </main>

      {/* Bottom Sticky Tab Navigation */}
      <nav
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#1e293b',
          borderTop: '1px solid #334155',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          height: '60px',
          zIndex: 50
        }}
      >
        {[
          { id: 'stock', label: 'Stock', icon: '📦' },
          { id: 'movement', label: 'Movement', icon: '⚡' },
          { id: 'alerts', label: 'Alerts', icon: '🔔' },
          { id: 'sync', label: 'Sync', icon: '🔄', badge: pendingCount }
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'none',
              border: 'none',
              color: activeTab === tab.id ? '#14b8a6' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: activeTab === tab.id ? 'bold' : 'normal',
              fontSize: '0.75rem',
              position: 'relative'
            }}
          >
            <span style={{ fontSize: '1.2rem', marginBottom: '2px' }}>{tab.icon}</span>
            <span>{tab.label}</span>
            {tab.badge > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: '6px',
                  right: '18%',
                  background: '#ef4444',
                  color: '#fff',
                  borderRadius: '50%',
                  width: '16px',
                  height: '16px',
                  fontSize: '0.65rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 'bold'
                }}
              >
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
}
export default App;
