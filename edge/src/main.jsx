import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// Register Service Worker for offline PWA capabilities
if ('serviceWorker' in navigator && !window.location.host.startsWith('localhost')) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.log('SW registration notice:', err);
    });
  });
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
