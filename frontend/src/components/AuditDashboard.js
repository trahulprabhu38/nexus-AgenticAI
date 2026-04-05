import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, Legend } from 'recharts';
import { getApiBase } from '../config';
import './AuditDashboard.css';

const API_BASE = getApiBase();

function AuditDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${API_BASE}/audit/metrics`);
        const data = await res.json();
        setMetrics(data);
      } catch (err) {
        console.warn('Could not load audit metrics:', err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchMetrics();
  }, []);

  if (loading) {
    return <div className="dashboard-shell">Loading audit dashboard...</div>;
  }

  if (!metrics) {
    return <div className="dashboard-shell">Audit dashboard is unavailable.</div>;
  }

  const agentData = Object.entries(metrics.agent_success_rate || {}).map(([name, success]) => ({ name, success }));
  const latencyData = (metrics.recent_events || []).slice(0, 12).reverse().map((event, index) => ({
    name: `Req ${metrics.recent_events.length - index}`,
    latency: event.duration,
    passed: event.audit_passed ? 1 : 0,
  }));

  return (
    <div className="dashboard-shell">
      <div className="dashboard-header">
        <div>
          <h1>Admin Audit Dashboard</h1>
          <p>Review agent reliability, latency, accuracy, and user feedback in one place.</p>
        </div>
        <button className="dashboard-back-btn" onClick={() => navigate('/chatbot')}>Return to Chat</button>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Total Requests</h3>
          <p>{metrics.total_requests}</p>
        </div>
        <div className="dashboard-card">
          <h3>Average Latency (s)</h3>
          <p>{metrics.average_latency}</p>
        </div>
        <div className="dashboard-card">
          <h3>Audit Pass Rate</h3>
          <p>{metrics.audit_pass_rate}%</p>
        </div>
      </div>

      <div className="dashboard-chart-panel">
        <div className="dashboard-chart-card">
          <h4>Agent Success Rate</h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={agentData} margin={{ top: 16, right: 16, left: 0, bottom: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="success" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="dashboard-chart-card">
          <h4>Recent Request Latency</h4>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={latencyData} margin={{ top: 16, right: 16, left: 0, bottom: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="latency" stroke="#0ea5e9" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="dashboard-feedback-panel">
        <div>
          <h4>Recent Feedback</h4>
          {(metrics.feedbacks || []).length === 0 ? (
            <p>No user feedback submitted yet.</p>
          ) : (
            <div className="feedback-list">
              {metrics.feedbacks.map((item, idx) => (
                <div key={idx} className="feedback-row">
                  <div><strong>{item.email}</strong> · <span>{new Date(item.timestamp).toLocaleString()}</span></div>
                  <div>{item.feedback}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AuditDashboard;
