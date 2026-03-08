'use client';

import { useEffect, useState } from 'react';
import { Contact, Plus, Pencil, Trash2, Search, Phone, Mail } from 'lucide-react';
import Modal from '@/components/Modal';

interface ContactItem {
  id: number;
  name: string;
  company: string;
  phone: string;
  email: string;
  category: string;
  notes: string;
}

const contactCategories = ['Plumber', 'Electrician', 'HVAC', 'Handyman', 'Attorney', 'Accountant', 'Insurance', 'Property Manager', 'Contractor', 'Locksmith', 'Pest Control', 'Appliance Repair', 'Inspector', 'Other'];
const emptyForm = { name: '', company: '', phone: '', email: '', category: 'Plumber', notes: '' };

export default function ContactsPage() {
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [search, setSearch] = useState('');

  const load = () => {
    fetch('/api/contacts').then(r => r.json()).then(d => { setContacts(d); setLoading(false); });
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editId) {
      await fetch(`/api/contacts/${editId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
    } else {
      await fetch('/api/contacts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
    }
    setShowModal(false);
    setEditId(null);
    setForm(emptyForm);
    load();
  };

  const handleEdit = (c: ContactItem) => {
    setForm({ name: c.name, company: c.company || '', phone: c.phone || '', email: c.email || '', category: c.category, notes: c.notes || '' });
    setEditId(c.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this contact?')) return;
    await fetch(`/api/contacts/${id}`, { method: 'DELETE' });
    load();
  };

  const filtered = contacts.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.category.toLowerCase().includes(search.toLowerCase()) ||
    (c.company || '').toLowerCase().includes(search.toLowerCase())
  );

  // Group by category
  const grouped = filtered.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = [];
    acc[c.category].push(c);
    return acc;
  }, {} as Record<string, ContactItem[]>);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Contacts</h1>
          <p className="text-gray-500 text-sm mt-1">{contacts.length} contacts</p>
        </div>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowModal(true); }} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Add Contact
        </button>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input className="input pl-9" placeholder="Search contacts..." value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="card text-center py-12">
          <Contact size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">{search ? 'No contacts match your search' : 'No contacts yet'}</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, items]) => (
            <div key={category}>
              <h3 className="text-sm font-medium text-gray-500 mb-2 uppercase tracking-wider">{category}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {items.map((c) => (
                  <div key={c.id} className="card">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="font-medium">{c.name}</h4>
                        {c.company && <p className="text-xs text-gray-500">{c.company}</p>}
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => handleEdit(c)} className="text-gray-400 hover:text-white p-1 rounded hover:bg-[#2a2a2a]">
                          <Pencil size={12} />
                        </button>
                        <button onClick={() => handleDelete(c.id)} className="text-gray-400 hover:text-red-400 p-1 rounded hover:bg-[#2a2a2a]">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                    <div className="space-y-1 text-sm text-gray-400">
                      {c.phone && <p className="flex items-center gap-2"><Phone size={12} /> {c.phone}</p>}
                      {c.email && <p className="flex items-center gap-2"><Mail size={12} /> {c.email}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={showModal} onClose={() => { setShowModal(false); setEditId(null); }} title={editId ? 'Edit Contact' : 'Add Contact'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <label className="label">Company</label>
            <input className="input" value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Phone</label>
              <input className="input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Category</label>
            <select className="input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
              {contactCategories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary">{editId ? 'Update' : 'Add'} Contact</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
