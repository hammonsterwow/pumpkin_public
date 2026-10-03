import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import AdminDashboard from './AdminDashboard';
import './index.css';
import './step3Bridge';

const isAdminPage = window.location.pathname === '/admin';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isAdminPage ? <AdminDashboard /> : <App />}
  </React.StrictMode>,
);
