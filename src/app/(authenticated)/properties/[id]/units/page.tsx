'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Plus, Pencil, Trash2, Home } from 'lucide-react';
import Modal from '@/components/Modal';

interface Unit {
  id: number;
  property_id: number;
  unit_number: string;
  bedrooms: number;
  bathrooms: number;
  sqft: number;
  rent_amount: number;
  section8: number;
  status: string;
  notes: string;
  tenant_name: string | null;
  tenant_id: number | null;
}

interface Property {
  id: number;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
}

const emptyForm = { unit_number: '', bedrooms: 0, bathrooms: 0, sqft: 0, rent_amount: 0, section8: false, status: 'vacant', notes: '' };

export default function UnitsPage() {
  const params = useParams();
  const propertyId = params.id as string;

  const [property, setProperty] = useState<Property | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);

  const load = () => {
    Promise.all([
      fetch(`/api/properties/${propertyId}`).then(r => r.json()),
      fetch(`/api/units?property_id=${propertyId}`).then(r => r.json()),
    ]).then(([p, u]) => {
      setProperty(p);
      setUnits(u);
      setLoading(false);
    });
  };

  useEffect(() => { load(); }, [propertyId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...form, property_id: Number(propertyId), section8: form.section8 ? 1 : 0 };
    if (editId) {
      await fetch(`/api/units/${editId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } else {
      await fetch('/api/units', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
    setShowModal(false);
    setEditId(null);
    setForm(emptyForm);
    load();
  };

  const handleEdit = (u: Unit) => {
    setForm({
      unit_number: u.unit_number,
      bedrooms: u.bedrooms,
      bathrooms: u.bathrooms,
      sqft: u.sqft,
      rent_amount: u.rent_amount,
      section8: Boolean(u.section8),
      status: u.status,
      notes: u.notes || '',
    });
    setEditId(u.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this unit?')) return;
    await fetch(`/api/units/${id}`, { method: 'DELETE' });
    load();
  };

  if (loading) return <div className="text-gray-400">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <Link href="/properties" className="text-gray-400 hover:text-white p-2 rounded-lg hover:bg-[#1a1a1a]">
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{property?.name}</h1>
          <p className="text-gray-500 text-sm">{property?.address}, {property?.city}, {property?.state} {property?.zip}</p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-gray-400 text-sm">{units.length} units</p>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowModal(true); }} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Add Unit
        </button>
      </div>

      {units.length === 0 ? (
        <div className="card text-center py-12">
          <Home size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No units yet. Add units to this property.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {units.map((u) => (
            <div key={u.id} className="card">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold">Unit {u.unit_number}</h3>
                  <p className="text-xs text-gray-500">{u.bedrooms} bed / {u.bathrooms} bath / {u.sqft} sqft</p>
                </div>
                <span className={u.status === 'occupied' ? 'badge-green' : 'badge-yellow'}>{u.status}</span>
              </div>

              <div className="space-y-1 text-sm mb-3">
                <p className="text-[#C6963A] font-medium">${u.rent_amount.toLocaleString()}/mo</p>
                {u.section8 ? <span className="badge-blue">Section 8</span> : null}
                {u.tenant_name && <p className="text-gray-400">Tenant: {u.tenant_name}</p>}
              </div>

              <div className="flex gap-2 pt-3 border-t border-[#2a2a2a]">
                <button onClick={() => handleEdit(u)} className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-[#2a2a2a]">
                  <Pencil size={14} />
                </button>
                <button onClick={() => handleDelete(u.id)} className="text-gray-400 hover:text-red-400 p-1.5 rounded hover:bg-[#2a2a2a]">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={showModal} onClose={() => { setShowModal(false); setEditId(null); }} title={editId ? 'Edit Unit' : 'Add Unit'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Unit Number</label>
            <input className="input" value={form.unit_number} onChange={e => setForm({ ...form, unit_number: e.target.value })} required placeholder="e.g., A, B, 101" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Bedrooms</label>
              <input type="number" className="input" value={form.bedrooms} onChange={e => setForm({ ...form, bedrooms: Number(e.target.value) })} />
            </div>
            <div>
              <label className="label">Bathrooms</label>
              <input type="number" step="0.5" className="input" value={form.bathrooms} onChange={e => setForm({ ...form, bathrooms: Number(e.target.value) })} />
            </div>
            <div>
              <label className="label">Sqft</label>
              <input type="number" className="input" value={form.sqft} onChange={e => setForm({ ...form, sqft: Number(e.target.value) })} />
            </div>
          </div>
          <div>
            <label className="label">Rent Amount</label>
            <input type="number" step="0.01" className="input" value={form.rent_amount} onChange={e => setForm({ ...form, rent_amount: Number(e.target.value) })} />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="section8" checked={form.section8} onChange={e => setForm({ ...form, section8: e.target.checked })} className="rounded bg-[#111] border-[#2a2a2a]" />
            <label htmlFor="section8" className="text-sm text-gray-400">Section 8</label>
          </div>
          {editId && (
            <div>
              <label className="label">Status</label>
              <select className="input" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
                <option value="vacant">Vacant</option>
                <option value="occupied">Occupied</option>
              </select>
            </div>
          )}
          <div>
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary">{editId ? 'Update' : 'Add'} Unit</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
