'use client';

import { useEffect, useState } from 'react';
import { CreditCard, Plus, Pencil, Trash2, Filter } from 'lucide-react';
import Modal from '@/components/Modal';

interface Payment {
  id: number;
  tenant_id: number;
  tenant_name: string;
  expected_rent: number;
  unit_number: string;
  property_address: string;
  property_name: string;
  property_id: number;
  amount: number;
  date: string;
  due_date: string;
  method: string;
  status: string;
  notes: string;
}

interface TenantOption { id: number; name: string; rent_amount: number; }
interface PropertyOption { id: number; name: string; }

const emptyForm = { tenant_id: '', amount: 0, date: new Date().toISOString().split('T')[0], due_date: '', method: 'check', status: 'paid', notes: '' };

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [properties, setProperties] = useState<PropertyOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);

  const now = new Date();
  const [filterMonth, setFilterMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`);
  const [filterProperty, setFilterProperty] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const load = () => {
    const params = new URLSearchParams();
    if (filterMonth) params.set('month', filterMonth);
    if (filterProperty) params.set('property_id', filterProperty);
    if (filterStatus) params.set('status', filterStatus);

    Promise.all([
      fetch(`/api/payments?${params}`).then(r => r.json()),
      fetch('/api/tenants').then(r => r.json()),
      fetch('/api/properties').then(r => r.json()),
    ]).then(([p, t, pr]) => {
      setPayments(p);
      setTenants(t.filter((te: any) => te.status === 'active'));
      setProperties(pr);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, [filterMonth, filterProperty, filterStatus]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...form, tenant_id: Number(form.tenant_id) };
    if (editId) {
      await fetch(`/api/payments/${editId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } else {
      await fetch('/api/payments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
    setShowModal(false);
    setEditId(null);
    setForm(emptyForm);
    load();
  };

  const handleEdit = (p: Payment) => {
    setForm({
      tenant_id: String(p.tenant_id), amount: p.amount, date: p.date,
      due_date: p.due_date || '', method: p.method || 'check', status: p.status, notes: p.notes || '',
    });
    setEditId(p.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this payment?')) return;
    await fetch(`/api/payments/${id}`, { method: 'DELETE' });
    load();
  };

  const isLate = (p: Payment) => {
    if (p.status === 'paid') return false;
    const day = new Date(p.date).getDate();
    return day > 5;
  };

  const totalPaid = payments.filter(p => p.status === 'paid').reduce((s, p) => s + p.amount, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Rent Tracker</h1>
          <p className="text-gray-500 text-sm mt-1">Total collected: <span className="text-[#C6963A]">${totalPaid.toLocaleString()}</span></p>
        </div>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowModal(true); }} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Record Payment
        </button>
      </div>

      {/* Filters */}
      <div className="card flex flex-wrap gap-3 items-center">
        <Filter size={16} className="text-gray-500" />
        <input type="month" className="input w-auto" value={filterMonth} onChange={e => setFilterMonth(e.target.value)} />
        <select className="input w-auto" value={filterProperty} onChange={e => setFilterProperty(e.target.value)}>
          <option value="">All Properties</option>
          {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select className="input w-auto" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">All Status</option>
          <option value="paid">Paid</option>
          <option value="pending">Pending</option>
          <option value="late">Late</option>
          <option value="partial">Partial</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : payments.length === 0 ? (
        <div className="card text-center py-12">
          <CreditCard size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No payments recorded for this period</p>
        </div>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead className="border-b border-[#2a2a2a]">
              <tr>
                <th className="table-header">Tenant</th>
                <th className="table-header">Property</th>
                <th className="table-header">Amount</th>
                <th className="table-header">Date</th>
                <th className="table-header">Method</th>
                <th className="table-header">Status</th>
                <th className="table-header">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2a2a2a]">
              {payments.map((p) => (
                <tr key={p.id} className={`hover:bg-[#111] ${isLate(p) ? 'bg-red-900/5' : ''}`}>
                  <td className="table-cell font-medium">{p.tenant_name}</td>
                  <td className="table-cell">
                    <p className="text-sm">{p.property_name}</p>
                    <p className="text-xs text-gray-500">Unit {p.unit_number}</p>
                  </td>
                  <td className="table-cell text-[#C6963A] font-medium">${p.amount.toLocaleString()}</td>
                  <td className="table-cell text-sm text-gray-400">{p.date}</td>
                  <td className="table-cell text-sm text-gray-400 capitalize">{p.method}</td>
                  <td className="table-cell">
                    <span className={
                      p.status === 'paid' ? 'badge-green' :
                      p.status === 'late' ? 'badge-red' :
                      p.status === 'partial' ? 'badge-yellow' : 'badge-gray'
                    }>
                      {p.status}
                    </span>
                  </td>
                  <td className="table-cell">
                    <div className="flex gap-1">
                      <button onClick={() => handleEdit(p)} className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-[#2a2a2a]">
                        <Pencil size={14} />
                      </button>
                      <button onClick={() => handleDelete(p.id)} className="text-gray-400 hover:text-red-400 p-1.5 rounded hover:bg-[#2a2a2a]">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal isOpen={showModal} onClose={() => { setShowModal(false); setEditId(null); }} title={editId ? 'Edit Payment' : 'Record Payment'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Tenant</label>
            <select className="input" value={form.tenant_id} onChange={e => {
              const tid = e.target.value;
              const tenant = tenants.find(t => t.id === Number(tid));
              setForm({ ...form, tenant_id: tid, amount: tenant?.rent_amount || form.amount });
            }} required>
              <option value="">Select tenant</option>
              {tenants.map(t => <option key={t.id} value={t.id}>{t.name} (${t.rent_amount}/mo)</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Amount</label>
              <input type="number" step="0.01" className="input" value={form.amount} onChange={e => setForm({ ...form, amount: Number(e.target.value) })} required />
            </div>
            <div>
              <label className="label">Date</label>
              <input type="date" className="input" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} required />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Method</label>
              <select className="input" value={form.method} onChange={e => setForm({ ...form, method: e.target.value })}>
                <option value="check">Check</option>
                <option value="cash">Cash</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="money_order">Money Order</option>
                <option value="venmo">Venmo</option>
                <option value="zelle">Zelle</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="label">Status</label>
              <select className="input" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
                <option value="paid">Paid</option>
                <option value="pending">Pending</option>
                <option value="late">Late</option>
                <option value="partial">Partial</option>
              </select>
            </div>
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary">{editId ? 'Update' : 'Record'} Payment</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
