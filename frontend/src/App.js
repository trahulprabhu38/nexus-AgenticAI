import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './components/Home';
import Login from './components/Login';
import Chatbot from './components/Chatbot';
import AuditDashboard from './components/AuditDashboard';
import RequireAdmin from './components/RequireAdmin';
import TableAgentPage from './components/TableAgent';
import ColumnPruningPage from './components/ColumnPruningPage';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/chatbot" element={<Chatbot />} />
          <Route path="/dashboard" element={<RequireAdmin><AuditDashboard /></RequireAdmin>} />
          <Route path="/table-agent" element={<TableAgentPage />} />
          <Route path="/column-pruning" element={<ColumnPruningPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
