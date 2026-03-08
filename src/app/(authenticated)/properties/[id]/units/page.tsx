'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Plus, Pencil, Trash2, Home, Camera, Upload, X, FileText, Image as ImageIcon } from 'lucide-react';
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
  section8_hap: number;
  section8_tenant_share: number;
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

interface Photo {
  id: number;
  unit_id: number;
  filename: string;
  original_name: string;
  caption: string;
  created_at: string;
}

interface Document {
  id: number;
  property_id: number;
  tenant_id: number | null;
  filename: string;
  original_name: string;
  category: string;
  notes: string;
  created_at: string;
}

const emptyForm = { unit_number: '', bedrooms: 0, bathrooms: 0, sqft: 0, rent_amount: 0, section8: false, section8_hap: 0, section8_tenant_share: 0, status: 'vacant', notes: '' };

export default function UnitsPage() {
  const params = useParams();
  const propertyId = params.id as string;

  const [property, setProperty] = useState<Property | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);

  // Photos
  const [showPhotos, setShowPhotos] = useState<number | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const photoInput = useRef<HTMLInputElement>(null);

  // Documents
  const [showDocs, setShowDocs] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [docCategory, setDocCategory] = useState('lease');
  const [docNotes, setDocNotes] = useState('');
  const docInput = useRef<HTMLInputElement>(null);

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

  const loadPhotos = (unitId: number) => {
    fetch(`/api/photos?unit_id=${unitId}`).then(r => r.json()).then(setPhotos);
  };

  const loadDocs = () => {
    fetch(`/api/documents?property_id=${propertyId}`).then(r => r.json()).then(setDocuments);
  };

  useEffect(() => { load(); }, [propertyId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...form,
      property_id: Number(propertyId),
      section8: form.section8 ? 1 : 0,
      section8_hap: form.section8 ? form.section8_hap : 0,
      section8_tenant_share: form.section8 ? form.section8_tenant_share : 0,
    };
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
      section8_hap: u.section8_hap || 0,
      section8_tenant_share: u.section8_tenant_share || 0,
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

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length || !showPhotos) return;
    setUploadingPhoto(true);
    const formData = new FormData();
    for (const file of Array.from(e.target.files)) {
      formData.append('files', file);
    }
    formData.append('unit_id', String(showPhotos));
    await fetch('/api/photos', { method: 'POST', body: formData });
    loadPhotos(showPhotos);
    setUploadingPhoto(false);
    if (photoInput.current) photoInput.current.value = '';
  };

  const handleDeletePhoto = async (photoId: number) => {
    await fetch(`/api/photos/${photoId}`, { method: 'DELETE' });
    if (showPhotos) loadPhotos(showPhotos);
  };

  const handleDocUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    setUploadingDoc(true);
    const formData = new FormData();
    formData.append('file', e.target.files[0]);
    formData.append('property_id', propertyId);
    formData.append('category', docCategory);
    formData.append('notes', docNotes);
    await fetch('/api/documents', { method: 'POST', body: formData });
    loadDocs();
    setUploadingDoc(false);
    setDocNotes('');
    if (docInput.current) docInput.current.value = '';
  };

  const handleDeleteDoc = async (docId: number) => {
    await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
    loadDocs();
  };

  // When Section 8 is toggled, auto-calc
  const handleRentChange = (val: number) => {
    setForm(f => ({
      ...f,
      rent_amount: val,
      section8_hap: f.section8 ? val - f.section8_tenant_share : 0,
    }));
  };

  const handleHapChange = (val: number) => {
    setForm(f => ({
      ...f,
      section8_hap: val,
      section8_tenant_share: f.rent_amount - val,
    }));
  };

  const handleTenantShareChange = (val: number) => {
    setForm(f => ({
      ...f,
      section8_tenant_share: val,
      section8_hap: f.rent_amount - val,
    }));
  };

  if (loading) return <div className="text-gray-400">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <Link href="/properties" className="text-gray-400 hover:text-white p-2 rounded-lg hover:bg-[#1a1a1a]">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{property?.name}</h1>
          <p className="text-gray-500 text-sm">{property?.address}, {property?.city}, {property?.state} {property?.zip}</p>
        </div>
        <button onClick={() => { loadDocs(); setShowDocs(true); }} className="btn-secondary flex items-center gap-2">
          <FileText size={16} /> Documents
        </button>
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
                {u.section8 ? (
                  <div className="space-y-0.5">
                    <span className="badge-blue">Section 8</span>
                    <p className="text-xs text-gray-500">HAP: ${(u.section8_hap || 0).toLocaleString()} | Tenant: ${(u.section8_tenant_share || 0).toLocaleString()}</p>
                  </div>
                ) : null}
                {u.tenant_name && <p className="text-gray-400">Tenant: {u.tenant_name}</p>}
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-[#2a2a2a]">
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(u)} className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-[#2a2a2a]">
                    <Pencil size={14} />
                  </button>
                  <button onClick={() => handleDelete(u.id)} className="text-gray-400 hover:text-red-400 p-1.5 rounded hover:bg-[#2a2a2a]">
                    <Trash2 size={14} />
                  </button>
                </div>
                <button onClick={() => { setShowPhotos(u.id); loadPhotos(u.id); }} className="text-[#C6963A] hover:text-[#d4a54a] text-sm flex items-center gap-1">
                  <Camera size={14} /> Photos
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Unit Modal */}
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
            <label className="label">Total Rent Amount</label>
            <input type="number" step="0.01" className="input" value={form.rent_amount} onChange={e => handleRentChange(Number(e.target.value))} />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="section8" checked={form.section8} onChange={e => setForm({ ...form, section8: e.target.checked })} className="rounded bg-[#111] border-[#2a2a2a]" />
            <label htmlFor="section8" className="text-sm text-gray-400">Section 8</label>
          </div>
          {form.section8 && (
            <div className="grid grid-cols-2 gap-3 p-3 bg-[#111] rounded-lg border border-[#2a2a2a]">
              <div>
                <label className="label">Section 8 (HAP)</label>
                <input type="number" step="0.01" className="input" value={form.section8_hap} onChange={e => handleHapChange(Number(e.target.value))} placeholder="Housing Authority pays" />
              </div>
              <div>
                <label className="label">Tenant Share</label>
                <input type="number" step="0.01" className="input" value={form.section8_tenant_share} onChange={e => handleTenantShareChange(Number(e.target.value))} placeholder="Tenant pays" />
              </div>
              <p className="col-span-2 text-xs text-gray-500">Total: ${form.rent_amount} = HAP ${form.section8_hap} + Tenant ${form.section8_tenant_share}</p>
            </div>
          )}
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

      {/* Photos Modal */}
      <Modal isOpen={showPhotos !== null} onClose={() => setShowPhotos(null)} title={`Unit ${units.find(u => u.id === showPhotos)?.unit_number || ''} — Photos`}>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <input ref={photoInput} type="file" accept="image/*" multiple onChange={handlePhotoUpload} className="hidden" />
            <button onClick={() => photoInput.current?.click()} className="btn-primary flex items-center gap-2" disabled={uploadingPhoto}>
              <Upload size={16} /> {uploadingPhoto ? 'Uploading...' : 'Upload Photos'}
            </button>
          </div>
          {photos.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-8">No photos yet. Upload photos of this unit.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[400px] overflow-y-auto">
              {photos.map(p => (
                <div key={p.id} className="relative group">
                  <img src={`/uploads/photos/${p.filename}`} alt={p.original_name} className="w-full h-32 object-cover rounded-lg" />
                  <button onClick={() => handleDeletePhoto(p.id)} className="absolute top-1 right-1 bg-red-500/80 hover:bg-red-600 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <X size={12} />
                  </button>
                  <p className="text-xs text-gray-500 mt-1 truncate">{p.original_name}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>

      {/* Documents Modal */}
      <Modal isOpen={showDocs} onClose={() => setShowDocs(false)} title={`${property?.name} — Documents`}>
        <div className="space-y-4">
          <div className="p-3 bg-[#111] rounded-lg border border-[#2a2a2a] space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Category</label>
                <select className="input" value={docCategory} onChange={e => setDocCategory(e.target.value)}>
                  <option value="lease">Lease</option>
                  <option value="application">Application</option>
                  <option value="id">ID / Identification</option>
                  <option value="inspection">Inspection Report</option>
                  <option value="section8">Section 8 Documents</option>
                  <option value="notice">Notice</option>
                  <option value="receipt">Receipt</option>
                  <option value="photo">Photo</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="label">Notes</label>
                <input className="input" value={docNotes} onChange={e => setDocNotes(e.target.value)} placeholder="Optional description" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <input ref={docInput} type="file" onChange={handleDocUpload} className="hidden" />
              <button onClick={() => docInput.current?.click()} className="btn-primary flex items-center gap-2" disabled={uploadingDoc}>
                <Upload size={16} /> {uploadingDoc ? 'Uploading...' : 'Upload Document'}
              </button>
            </div>
          </div>

          {documents.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-6">No documents yet.</p>
          ) : (
            <div className="space-y-2 max-h-[350px] overflow-y-auto">
              {documents.map(d => (
                <div key={d.id} className="flex items-center justify-between p-3 bg-[#111] rounded-lg border border-[#2a2a2a] hover:border-[#C6963A]/30">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex-shrink-0">
                      {d.category === 'photo' || d.original_name.match(/\.(jpg|jpeg|png|gif|webp)$/i)
                        ? <ImageIcon size={18} className="text-[#C6963A]" />
                        : <FileText size={18} className="text-[#C6963A]" />
                      }
                    </div>
                    <div className="min-w-0">
                      <a href={`/uploads/documents/${d.filename}`} target="_blank" className="text-sm text-white hover:text-[#C6963A] truncate block">{d.original_name}</a>
                      <p className="text-xs text-gray-500">
                        <span className="capitalize">{d.category}</span>
                        {d.notes && ` — ${d.notes}`}
                        {' — '}{new Date(d.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <button onClick={() => handleDeleteDoc(d.id)} className="text-gray-500 hover:text-red-400 p-1 flex-shrink-0">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
