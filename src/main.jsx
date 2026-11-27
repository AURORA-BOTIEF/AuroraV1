// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
// Amplify configuration is now handled in src/amplify.js
import './amplify.js';
import App from './App.jsx';
import './index.css';

// Add global error handler to suppress browser extension errors
// that don't affect the application functionality
window.addEventListener('error', (event) => {
  if (event.message && event.message.includes('message channel closed')) {
    console.warn('Suppressed browser extension error:', event.message);
    event.preventDefault();
    return false;
  }
});

// Also handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  if (event.reason && String(event.reason).includes('message channel closed')) {
    console.warn('Suppressed async browser extension error:', event.reason);
    event.preventDefault();
    return false;
  }
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);


