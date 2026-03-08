'use client';

import { useEffect, useState } from 'react';
import { Building2, Plus, Pencil, Trash2, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import Modal from '@/components/Modal';

interface Property {
  id: number;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  type: string;
  notes: string;
  unit_count: number;
  occupied_count: number;
}

const emptyForm = { name: '', address: '', city: '', state: '', zip: '', type: 'residential', tenant: '', notes: '' };

export default function PropertiesPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);

  const load = () => {
    fetch('/api/properties').then(r => r.json()).then(d => { setProperties(d); setLoading(false); });
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const method = editId ? 'PUT' : 'POST';
    const url = editId ? `/api/properties/${editId}` : '/api/properties';
    await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
    setShowModal(false);
    setEditId(null);
    setForm(emptyForm);
    load();
  };

  const handleEdit = (p: Property) => {
    setForm({ name: p.name, address: p.address, city: p.city, state: p.state, zip: p.zip, type: p.type, tenant: (p as any).tenant || '', notes: p.notes || '' });
    setEditId(p.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this property and all its units?')) return;
    await fetch(`/api/properties/${id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Properties</h1>
          <p className="text-gray-500 text-sm mt-1">{properties.length} properties</p>
        </div>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowModal(true); }} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Add Property
        </button>
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : properties.length === 0 ? (
        <div className="card text-center py-12">
          <Building2 size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No properties yet. Add your first property to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {properties.map((p) => (
            <div key={p.id} className="card hover:border-[#C6963A]/30 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-lg">{p.name}</h3>
                  <p className="text-sm text-gray-400">{p.address}</p>
                  <p className="text-xs text-gray-500">{p.city}, {p.state} {p.zip}</p>
                </div>
                <span className="badge-blue">{p.type}</span>
              </div>

              <div className="flex gap-4 text-sm text-gray-400 mb-4">
                <span>{p.unit_count} units</span>
                <span className="text-green-400">{p.occupied_count} occupied</span>
                <span className="text-yellow-400">{p.unit_count - p.occupied_count} vacant</span>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-[#2a2a2a]">
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(p)} className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-[#2a2a2a]">
                    <Pencil size={14} />
                  </button>
                  <button onClick={() => handleDelete(p.id)} className="text-gray-400 hover:text-red-400 p-1.5 rounded hover:bg-[#2a2a2a]">
                    <Trash2 size={14} />
                  </button>
                </div>
                <Link href={`/properties/${p.id}/units`} className="text-[#C6963A] hover:text-[#d4a54a] text-sm flex items-center gap-1">
                  View Units <ChevronRight size={14} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={showModal} onClose={() => { setShowModal(false); setEditId(null); }} title={editId ? 'Edit Property' : 'Add Property'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Property Name</label>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required placeholder="e.g., Oak Street Duplex" />
          </div>
          <div>
            <label className="label">Address</label>
            <input className="input" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} required placeholder="Street address" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">City</label>
              <input className="input" value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} required />
            </div>
            <div>
              <label className="label">State</label>
              <input className="input" value={form.state} onChange={e => setForm({ ...form, state: e.target.value })} required />
            </div>
            <div>
              <label className="label">ZIP</label>
              <input className="input" value={form.zip} onChange={e => setForm({ ...form, zip: e.target.value })} required />
            </div>
          </div>
          <div>
            <label className="label">Type</label>
            <select className="input" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
              <option value="residential">Residential</option>
              <option value="commercial">Commercial</option>
              <option value="mixed">Mixed Use</option>
            </select>
          </div>
          <div>
            <label className="label">Tenant</label>
            <input className="input" value={form.tenant} onChange={e => setForm({ ...form, tenant: e.target.value })} placeholder="Tenant name" />
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea className="input" rows={3} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary">{editId ? 'Update' : 'Add'} Property</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
