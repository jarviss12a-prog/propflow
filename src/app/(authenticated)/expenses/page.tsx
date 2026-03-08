'use client';

import { useEffect, useState } from 'react';
import { Receipt, Plus, Pencil, Trash2 } from 'lucide-react';
import Modal from '@/components/Modal';

interface Expense {
  id: number;
  property_id: number;
  property_name: string;
  property_address: string;
  date: string;
  category: string;
  amount: number;
  vendor: string;
  description: string;
}

interface PropertyOption { id: number; name: string; }

const categories = ['Maintenance', 'Repair', 'Insurance', 'Taxes', 'Utilities', 'Legal', 'Management', 'Landscaping', 'Cleaning', 'Appliance', 'Other'];
const emptyForm = { property_id: '', date: new Date().toISOString().split('T')[0], category: 'Maintenance', amount: 0, vendor: '', description: '' };

export default function ExpensesPage() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [properties, setProperties] = useState<PropertyOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [filterProperty, setFilterProperty] = useState('');

  const load = () => {
    const params = filterProperty ? `?property_id=${filterProperty}` : '';
    Promise.all([
      fetch(`/api/expenses${params}`).then(r => r.json()),
      fetch('/api/properties').then(r => r.json()),
    ]).then(([e, p]) => {
      setExpenses(e);
      setProperties(p);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, [filterProperty]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...form, property_id: Number(form.property_id) };
    if (editId) {
      await fetch(`/api/expenses/${editId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } else {
      await fetch('/api/expenses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
    setShowModal(false);
    setEditId(null);
    setForm(emptyForm);
    load();
  };

  const handleEdit = (exp: Expense) => {
    setForm({
      property_id: String(exp.property_id), date: exp.date, category: exp.category,
      amount: exp.amount, vendor: exp.vendor || '', description: exp.description || '',
    });
    setEditId(exp.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this expense?')) return;
    await fetch(`/api/expenses/${id}`, { method: 'DELETE' });
    load();
  };

  const totalExpenses = expenses.reduce((s, e) => s + e.amount, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Expenses</h1>
          <p className="text-gray-500 text-sm mt-1">Total: <span className="text-red-400">${totalExpenses.toLocaleString()}</span></p>
        </div>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowModal(true); }} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Add Expense
        </button>
      </div>

      <div className="flex gap-3">
        <select className="input w-auto" value={filterProperty} onChange={e => setFilterProperty(e.target.value)}>
          <option value="">All Properties</option>
          {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : expenses.length === 0 ? (
        <div className="card text-center py-12">
          <Receipt size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No expenses recorded</p>
        </div>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead className="border-b border-[#2a2a2a]">
              <tr>
                <th className="table-header">Date</th>
                <th className="table-header">Property</th>
                <th className="table-header">Category</th>
                <th className="table-header">Vendor</th>
                <th className="table-header">Amount</th>
                <th className="table-header">Description</th>
                <th className="table-header">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2a2a2a]">
              {expenses.map((exp) => (
                <tr key={exp.id} className="hover:bg-[#111]">
                  <td className="table-cell text-sm text-gray-400">{exp.date}</td>
                  <td className="table-cell text-sm">{exp.property_name}</td>
                  <td className="table-cell"><span className="badge-blue">{exp.category}</span></td>
                  <td className="table-cell text-sm text-gray-400">{exp.vendor || '-'}</td>
                  <td className="table-cell text-red-400 font-medium">${exp.amount.toLocaleString()}</td>
                  <td className="table-cell text-sm text-gray-400 max-w-xs truncate">{exp.description || '-'}</td>
                  <td className="table-cell">
                    <div className="flex gap-1">
                      <button onClick={() => handleEdit(exp)} className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-[#2a2a2a]">
                        <Pencil size={14} />
                      </button>
                      <button onClick={() => handleDelete(exp.id)} className="text-gray-400 hover:text-red-400 p-1.5 rounded hover:bg-[#2a2a2a]">
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

      <Modal isOpen={showModal} onClose={() => { setShowModal(false); setEditId(null); }} title={editId ? 'Edit Expense' : 'Add Expense'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Property</label>
            <select className="input" value={form.property_id} onChange={e => setForm({ ...form, property_id: e.target.value })} required>
              <option value="">Select property</option>
              {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Date</label>
              <input type="date" className="input" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} required />
            </div>
            <div>
              <label className="label">Category</label>
              <select className="input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Amount</label>
              <input type="number" step="0.01" className="input" value={form.amount} onChange={e => setForm({ ...form, amount: Number(e.target.value) })} required />
            </div>
            <div>
              <label className="label">Vendor</label>
              <input className="input" value={form.vendor} onChange={e => setForm({ ...form, vendor: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input" rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary">{editId ? 'Update' : 'Add'} Expense</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
