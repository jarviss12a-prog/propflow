'use client';

import { useEffect, useState, useRef } from 'react';
import { ShieldCheck, Printer } from 'lucide-react';

interface S8Tenant {
  id: number;
  name: string;
  unit_number: string;
  property_address: string;
  property_name: string;
  rent_amount: number;
  unit_rent: number;
  section8_voucher: string;
  section8_case_number: string;
  lease_start: string;
  lease_end: string;
}

export default function Section8Page() {
  const [tenants, setTenants] = useState<S8Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [proposedRents, setProposedRents] = useState<Record<number, number>>({});
  const [printTenant, setPrintTenant] = useState<S8Tenant | null>(null);
  const printRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/api/section8').then(r => r.json()).then(d => { setTenants(d); setLoading(false); });
  }, []);

  const handlePrint = (tenant: S8Tenant) => {
    setPrintTenant(tenant);
    setTimeout(() => {
      const printContent = printRef.current?.innerHTML;
      if (!printContent) return;
      const win = window.open('', '_blank');
      if (!win) return;
      win.document.write(`
        <html><head><title>Section 8 Rent Increase Form</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; color: #000; line-height: 1.6; }
          h1 { font-size: 22px; text-align: center; margin-bottom: 30px; }
          .field { margin: 12px 0; }
          .field label { font-weight: bold; }
          .signature-line { margin-top: 50px; display: flex; justify-content: space-between; }
          .sig { border-top: 1px solid #000; width: 200px; text-align: center; padding-top: 5px; }
        </style>
        </head><body>${printContent}</body></html>
      `);
      win.document.close();
      win.print();
    }, 100);
  };

  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Section 8 Rent Increase Tool</h1>
        <p className="text-gray-500 text-sm mt-1">Manage Section 8 rent adjustments</p>
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : tenants.length === 0 ? (
        <div className="card text-center py-12">
          <ShieldCheck size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No Section 8 tenants found. Add tenants with Section 8 status first.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {tenants.map((t) => (
            <div key={t.id} className="card">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">{t.name}</h3>
                  <p className="text-sm text-gray-400">{t.property_name} - Unit {t.unit_number}</p>
                  <p className="text-xs text-gray-500">{t.property_address}</p>
                  <div className="flex gap-4 mt-2 text-sm">
                    <span>Current Rent: <span className="text-[#C6963A] font-medium">${t.rent_amount.toLocaleString()}</span></span>
                    {t.section8_voucher && <span className="text-gray-400">Voucher: {t.section8_voucher}</span>}
                    {t.section8_case_number && <span className="text-gray-400">Case: {t.section8_case_number}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div>
                    <label className="label">Proposed Rent</label>
                    <input
                      type="number"
                      step="0.01"
                      className="input w-32"
                      value={proposedRents[t.id] || ''}
                      onChange={e => setProposedRents({ ...proposedRents, [t.id]: Number(e.target.value) })}
                      placeholder="New rent"
                    />
                  </div>
                  <button
                    onClick={() => handlePrint(t)}
                    disabled={!proposedRents[t.id]}
                    className="btn-primary flex items-center gap-2 mt-5 disabled:opacity-30"
                  >
                    <Printer size={16} /> Print Form
                  </button>
                </div>
              </div>

              {proposedRents[t.id] && proposedRents[t.id] > t.rent_amount && (
                <div className="mt-3 pt-3 border-t border-[#2a2a2a] text-sm">
                  <span className="text-green-400">
                    Increase: ${(proposedRents[t.id] - t.rent_amount).toFixed(2)}/mo
                    ({((proposedRents[t.id] - t.rent_amount) / t.rent_amount * 100).toFixed(1)}%)
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Hidden print template */}
      <div className="hidden">
        <div ref={printRef}>
          {printTenant && (
            <div>
              <h1>NOTICE OF RENT INCREASE</h1>
              <h2 style={{ textAlign: 'center', fontSize: '16px', color: '#666' }}>Section 8 Housing Choice Voucher Program</h2>

              <div className="field"><label>Date:</label> {today}</div>
              <div className="field"><label>Tenant Name:</label> {printTenant.name}</div>
              <div className="field"><label>Property:</label> {printTenant.property_address}</div>
              <div className="field"><label>Unit:</label> {printTenant.unit_number}</div>
              {printTenant.section8_voucher && <div className="field"><label>Voucher Number:</label> {printTenant.section8_voucher}</div>}
              {printTenant.section8_case_number && <div className="field"><label>Case Number:</label> {printTenant.section8_case_number}</div>}

              <hr style={{ margin: '20px 0' }} />

              <div className="field"><label>Current Monthly Rent:</label> ${printTenant.rent_amount.toLocaleString()}</div>
              <div className="field"><label>Proposed New Monthly Rent:</label> ${(proposedRents[printTenant.id] || 0).toLocaleString()}</div>
              <div className="field"><label>Monthly Increase:</label> ${((proposedRents[printTenant.id] || 0) - printTenant.rent_amount).toFixed(2)}</div>

              <hr style={{ margin: '20px 0' }} />

              <p>This notice serves as a formal request to adjust the contract rent for the above-referenced unit under the Section 8 Housing Choice Voucher Program. The proposed rent increase is effective 60 days from the date of this notice, subject to approval by the local Housing Authority.</p>

              <p style={{ marginTop: '15px' }}>The landlord certifies that the proposed rent is reasonable and comparable to similar unassisted units in the area.</p>

              <div className="signature-line">
                <div className="sig">Landlord Signature</div>
                <div className="sig">Date</div>
              </div>

              <div className="signature-line" style={{ marginTop: '30px' }}>
                <div className="sig">Tenant Signature</div>
                <div className="sig">Date</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
