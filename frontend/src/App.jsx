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
      console.log(`Fetching balance from: ${API_BASE_URL}/balance/`);
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
      console.log(`Fetching payouts from: ${API_BASE_URL}/payouts/`);
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

  return (
    <div className="container">
      <header>
        <h1>Playto Pay Engine</h1>
        <div className="balance-card">
          <h2>Available Balance</h2>
          <p>₹ {(balance / 100).toFixed(2)}</p>
          <small>{balance} paise</small>
        </div>
      </header>

      <main>
        <section className="request-section">
          <h3>Request Payout</h3>
          {error && <div className="error">{error}</div>}
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
              <label>Bank Account ID</label>
              <input 
                type="text" 
                value={bankAccountId} 
                onChange={(e) => setBankAccountId(e.target.value)} 
                required 
                placeholder="e.g. bank_xyz123"
              />
            </div>
            <button type="submit" disabled={loading}>
              {loading ? 'Processing...' : 'Withdraw Funds'}
            </button>
          </form>
        </section>

        <section className="history-section">
          <h3>Payout History</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Amount (₹)</th>
                <th>Bank Account</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {payouts.map(p => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{(p.amount_paise / 100).toFixed(2)}</td>
                  <td>{p.bank_account_id}</td>
                  <td><span className={`status ${p.status.toLowerCase()}`}>{p.status}</span></td>
                  <td>{new Date(p.created_at).toLocaleString()}</td>
                </tr>
              ))}
              {payouts.length === 0 && (
                <tr>
                  <td colSpan="5">No payouts requested yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

export default App;
