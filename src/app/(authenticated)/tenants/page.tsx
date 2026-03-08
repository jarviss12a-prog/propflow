'use client';

import { useEffect, useState } from 'react';
import { Users, Plus, Pencil, Trash2, Search } from 'lucide-react';
import Modal from '@/components/Modal';

interface Tenant {
  id: number;
  name: string;
  email: string;
  phone: string;
  unit_id: number | null;
  unit_number: string;
  property_address: string;
  property_name: string;
  lease_start: string;
  lease_end: string;
  rent_amount: number;
  security_deposit: number;
  section8: number;
  section8_voucher: string;
  section8_case_number: string;
  status: string;
  notes: string;
}

interface UnitOption {
  id: number;
  unit_number: string;
  property_name: string;
  property_address: string;
  status: string;
}

const emptyForm = {
  name: '', email: '', phone: '', unit_id: '' as string,
  lease_start: '', lease_end: '', rent_amount: 0, security_deposit: 0,
  section8: false, section8_voucher: '', section8_case_number: '', status: 'active', notes: ''
};

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [units, setUnits] = useState<UnitOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [search, setSearch] = useState('');

  const load = () => {
    Promise.all([
      fetch('/api/tenants').then(r => r.json()),
      fetch('/api/units').then(r => r.json()),
    ]).then(([t, u]) => {
      setTenants(t);
      setUnits(u);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...form, unit_id: form.unit_id ? Number(form.unit_id) : null, section8: form.section8 ? 1 : 0 };
    if (editId) {
      await fetch(`/api/tenants/${editId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } else {
      await fetch('/api/tenants', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
    setShowModal(false);
    setEditId(null);
    setForm(emptyForm);
    load();
  };

  const handleEdit = (t: Tenant) => {
    setForm({
      name: t.name, email: t.email || '', phone: t.phone || '',
      unit_id: t.unit_id ? String(t.unit_id) : '',
      lease_start: t.lease_start || '', lease_end: t.lease_end || '',
      rent_amount: t.rent_amount, security_deposit: t.security_deposit,
      section8: Boolean(t.section8), section8_voucher: t.section8_voucher || '',
      section8_case_number: t.section8_case_number || '', status: t.status, notes: t.notes || '',
    });
    setEditId(t.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this tenant?')) return;
    await fetch(`/api/tenants/${id}`, { method: 'DELETE' });
    load();
  };

  const filtered = tenants.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    (t.property_address || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tenants</h1>
          <p className="text-gray-500 text-sm mt-1">{tenants.length} tenants</p>
        </div>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowModal(true); }} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Add Tenant
        </button>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input className="input pl-9" placeholder="Search tenants..." value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <Users size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">{search ? 'No tenants match your search' : 'No tenants yet'}</p>
        </div>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead className="border-b border-[#2a2a2a]">
              <tr>
                <th className="table-header">Name</th>
                <th className="table-header">Property / Unit</th>
                <th className="table-header">Rent</th>
                <th className="table-header">Lease End</th>
                <th className="table-header">Status</th>
                <th className="table-header">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2a2a2a]">
              {filtered.map((t) => (
                <tr key={t.id} className="hover:bg-[#111]">
                  <td className="table-cell">
                    <div>
                      <p className="font-medium">{t.name}</p>
                      <p className="text-xs text-gray-500">{t.phone} {t.email && `| ${t.email}`}</p>
                    </div>
                  </td>
                  <td className="table-cell">
                    <p className="text-sm">{t.property_name || '-'}</p>
                    <p className="text-xs text-gray-500">{t.unit_number ? `Unit ${t.unit_number}` : 'No unit assigned'}</p>
                  </td>
                  <td className="table-cell">
                    <span className="text-[#C6963A] font-medium">${t.rent_amount.toLocaleString()}</span>
                    {t.section8 ? <span className="badge-blue ml-2">S8</span> : null}
                  </td>
                  <td className="table-cell text-sm text-gray-400">{t.lease_end || '-'}</td>
                  <td className="table-cell">
                    <span className={t.status === 'active' ? 'badge-green' : t.status === 'evicted' ? 'badge-red' : 'badge-gray'}>
                      {t.status}
                    </span>
                  </td>
                  <td className="table-cell">
                    <div className="flex gap-1">
                      <button onClick={() => handleEdit(t)} className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-[#2a2a2a]">
                        <Pencil size={14} />
                      </button>
                      <button onClick={() => handleDelete(t.id)} className="text-gray-400 hover:text-red-400 p-1.5 rounded hover:bg-[#2a2a2a]">
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

      <Modal isOpen={showModal} onClose={() => { setShowModal(false); setEditId(null); }} title={editId ? 'Edit Tenant' : 'Add Tenant'} size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="label">Full Name</label>
              <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <label className="label">Phone</label>
              <input className="input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
          </div>

          <div>
            <label className="label">Assign to Unit</label>
            <select className="input" value={form.unit_id} onChange={e => setForm({ ...form, unit_id: e.target.value })}>
              <option value="">No unit assigned</option>
              {units.filter(u => u.status === 'vacant' || (editId && u.id === Number(form.unit_id))).map(u => (
                <option key={u.id} value={u.id}>{u.property_name} - Unit {u.unit_number}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Lease Start</label>
              <input type="date" className="input" value={form.lease_start} onChange={e => setForm({ ...form, lease_start: e.target.value })} />
            </div>
            <div>
              <label className="label">Lease End</label>
              <input type="date" className="input" value={form.lease_end} onChange={e => setForm({ ...form, lease_end: e.target.value })} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Monthly Rent</label>
              <input type="number" step="0.01" className="input" value={form.rent_amount} onChange={e => setForm({ ...form, rent_amount: Number(e.target.value) })} />
            </div>
            <div>
              <label className="label">Security Deposit</label>
              <input type="number" step="0.01" className="input" value={form.security_deposit} onChange={e => setForm({ ...form, security_deposit: Number(e.target.value) })} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" id="s8" checked={form.section8} onChange={e => setForm({ ...form, section8: e.target.checked })} className="rounded bg-[#111] border-[#2a2a2a]" />
            <label htmlFor="s8" className="text-sm text-gray-400">Section 8 Tenant</label>
          </div>

          {form.section8 && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Voucher Number</label>
                <input className="input" value={form.section8_voucher} onChange={e => setForm({ ...form, section8_voucher: e.target.value })} />
              </div>
              <div>
                <label className="label">Case Number</label>
                <input className="input" value={form.section8_case_number} onChange={e => setForm({ ...form, section8_case_number: e.target.value })} />
              </div>
            </div>
          )}

          <div>
            <label className="label">Status</label>
            <select className="input" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="evicted">Evicted</option>
            </select>
          </div>

          <div>
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>

          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary">{editId ? 'Update' : 'Add'} Tenant</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
