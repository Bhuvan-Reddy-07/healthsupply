import React, { useState, useEffect } from 'react';
import { db, getFacilityId } from '../db';

export function MyAlerts() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    loadAlerts();
  }, []);

  async function loadAlerts() {
    let list = await db.alerts.toArray();
    if (list.length === 0) {
      // Seed default sample alerts for offline display
      const facilityId = await getFacilityId();
      const defaultAlerts = [
        {
          id: 'ALT-01',
          facility_id: facilityId,
          alert_type: 'stockout_warning',
          severity: 'red',
          message: 'Critical Stockout Warning: Amoxicillin 500mg has < 2 days cover remaining.',
          created_at: new Date(Date.now() - 3600000).toISOString()
        },
        {
          id: 'ALT-02',
          facility_id: facilityId,
          alert_type: 'cold_chain_breach',
          severity: 'amber',
          message: 'Cold Chain Alert: Refrigerator A registered 8.4°C for 25 minutes.',
          created_at: new Date(Date.now() - 7200000).toISOString()
        },
        {
          id: 'ALT-03',
          facility_id: facilityId,
          alert_type: 'expiry_risk',
          severity: 'amber',
          message: 'Batch B-1102 (Oxytocin) expires in 45 days. Redistribution proposal pending.',
          created_at: new Date(Date.now() - 86400000).toISOString()
        }
      ];
      await db.alerts.bulkPut(defaultAlerts);
      list = defaultAlerts;
    }
    setAlerts(list);
  }

  function getSeverityColor(sev) {
    if (sev === 'red' || sev === 'black') return '#ef4444';
    if (sev === 'amber') return '#f59e0b';
    return '#3b82f6';
  }

  return (
    <div style={{ padding: '16px', maxWidth: '640px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#14b8a6', marginBottom: '12px' }}>
        🔔 My Facility Alerts (Read-Only)
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {alerts.map((alt) => (
          <div
            key={alt.id}
            style={{
              background: '#1e293b',
              padding: '14px',
              borderRadius: '8px',
              borderLeft: `4px solid ${getSeverityColor(alt.severity)}`
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  color: getSeverityColor(alt.severity)
                }}
              >
                {alt.severity} • {alt.alert_type.replace('_', ' ')}
              </span>
              <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                {new Date(alt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#f1f5f9', lineHeight: 1.4 }}>
              {alt.message}
            </p>
          </div>
        ))}
        {alerts.length === 0 && (
          <div style={{ textAlign: 'center', color: '#64748b', padding: '32px' }}>No active alerts for this facility.</div>
        )}
      </div>
    </div>
  );
}
