import { useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '');

function App() {
  const [balance, setBalance] = useState(0);
  const [payouts, setPayouts] = useState([]);
  const [amount, setAmount] = useState('');
  const [bankAccountId, setBankAccountId] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchBalance = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/balance/`);
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      setBalance(data.balance_paise);
    } catch (e) {
      console.error("Balance fetch failed:", e);
      setError(`Failed to fetch balance: ${e.message}`);
    }
  };

  const fetchPayouts = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/payouts/`);
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      setPayouts(data);
    } catch (e) {
      console.error("Payouts fetch failed:", e);
      setError(`Failed to fetch payouts: ${e.message}`);
    }
  };

  useEffect(() => {
    fetchBalance();
    fetchPayouts();
    
    // Auto-refresh history every 10 seconds to show state transitions
    const interval = setInterval(fetchPayouts, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRequestPayout = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const idempotencyKey = crypto.randomUUID();

    try {
      const res = await fetch(`${API_BASE_URL}/payouts/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify({
          amount_paise: parseInt(amount),
          bank_account_id: bankAccountId,
        }),
      });

      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.error || 'Failed to request payout');
      }

      setAmount('');
      setBankAccountId('');
      fetchBalance();
      fetchPayouts();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusClass = (status) => {
    switch (status.toLowerCase()) {
      case 'completed': return 'status-completed';
      case 'pending': return 'status-pending';
      case 'processing': return 'status-processing';
      case 'failed': return 'status-failed';
      default: return '';
    }
  };

  return (
    <div className="app-container">
      <header>
        <div className="logo">
          <h1>Playto Pay</h1>
        </div>
        <div className="balance-card glass">
          <h2>Available Funds</h2>
          <div className="amount">₹ {(balance / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
          <span className="paise">{balance.toLocaleString()} paise available</span>
        </div>
      </header>

      <div className="dashboard-grid">
        <section className="request-payout glass">
          <h3>Request New Payout</h3>
          {error && <div className="error-toast">⚠️ {error}</div>}
          <form onSubmit={handleRequestPayout}>
            <div className="form-group">
              <label>Amount (in paise)</label>
              <input 
                type="number" 
                value={amount} 
                onChange={(e) => setAmount(e.target.value)} 
                min="1"
                required 
                placeholder="e.g. 5000"
              />
            </div>
            <div className="form-group">
              <label>Bank Account Identifier</label>
              <input 
                type="text" 
                value={bankAccountId} 
                onChange={(e) => setBankAccountId(e.target.value)} 
                required 
                placeholder="e.g. axis_bank_9921"
              />
            </div>
            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? 'Processing...' : 'Authorize Withdrawal'}
            </button>
          </form>
        </section>

        <section className="payout-history glass">
          <h3>Payout History</h3>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Amount</th>
                  <th>Destination</th>
                  <th>Status</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {payouts.map(p => (
                  <tr key={p.id} className="payout-row">
                    <td style={{ opacity: 0.5 }}>#{p.id}</td>
                    <td style={{ fontWeight: 600 }}>₹ {(p.amount_paise / 100).toFixed(2)}</td>
                    <td>{p.bank_account_id}</td>
                    <td>
                      <span className={`status-badge ${getStatusClass(p.status)}`}>
                        {p.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {new Date(p.created_at).toLocaleDateString()}
                      <br/>
                      {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                  </tr>
                ))}
                {payouts.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      No payout records found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;
