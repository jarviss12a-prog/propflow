'use client';

import { useEffect, useState } from 'react';
import { FileText, Printer } from 'lucide-react';

interface TenantOption {
  id: number;
  name: string;
  email: string;
  phone: string;
  unit_number: string;
  property_address: string;
  property_name: string;
  rent_amount: number;
  security_deposit: number;
  lease_start: string;
  lease_end: string;
  status: string;
}

export default function DocumentsPage() {
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [selectedTenant, setSelectedTenant] = useState('');

  useEffect(() => {
    fetch('/api/tenants').then(r => r.json()).then(setTenants);
  }, []);

  const tenant = tenants.find(t => t.id === Number(selectedTenant));

  const generateLease = () => {
    if (!tenant) return;
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(`
      <html><head><title>Residential Lease Agreement</title>
      <style>
        body { font-family: Georgia, serif; padding: 50px; color: #000; line-height: 1.8; max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; font-size: 24px; margin-bottom: 5px; }
        h2 { text-align: center; font-size: 14px; color: #666; margin-top: 0; }
        .section { margin: 25px 0; }
        .section-title { font-weight: bold; font-size: 14px; text-transform: uppercase; border-bottom: 1px solid #ccc; padding-bottom: 3px; margin-bottom: 10px; }
        p { margin: 8px 0; font-size: 13px; }
        .sig { display: flex; justify-content: space-between; margin-top: 60px; }
        .sig-line { border-top: 1px solid #000; width: 250px; text-align: center; padding-top: 5px; font-size: 12px; }
        .blank { border-bottom: 1px solid #000; min-width: 150px; display: inline-block; }
      </style></head><body>
        <h1>RESIDENTIAL LEASE AGREEMENT</h1>
        <h2>State of Illinois</h2>

        <div class="section">
          <div class="section-title">1. Parties</div>
          <p>This Lease Agreement is entered into between the <strong>Landlord</strong> (hereinafter "Landlord") and <strong>${tenant.name}</strong> (hereinafter "Tenant").</p>
        </div>

        <div class="section">
          <div class="section-title">2. Property</div>
          <p>The Landlord hereby leases to the Tenant the residential property located at:</p>
          <p><strong>${tenant.property_address}${tenant.unit_number ? ', Unit ' + tenant.unit_number : ''}</strong></p>
        </div>

        <div class="section">
          <div class="section-title">3. Term</div>
          <p>The lease term begins on <strong>${tenant.lease_start || '___________'}</strong> and ends on <strong>${tenant.lease_end || '___________'}</strong>.</p>
        </div>

        <div class="section">
          <div class="section-title">4. Rent</div>
          <p>Monthly rent: <strong>$${tenant.rent_amount.toLocaleString()}</strong>, due on the 1st of each month.</p>
          <p>Late fee of $50.00 applies after the 5th day of each month.</p>
          <p>Rent shall be paid by check, money order, or electronic transfer.</p>
        </div>

        <div class="section">
          <div class="section-title">5. Security Deposit</div>
          <p>Security deposit: <strong>$${tenant.security_deposit.toLocaleString()}</strong></p>
          <p>The deposit will be returned within 30 days of lease termination, less any deductions for damages or unpaid rent.</p>
        </div>

        <div class="section">
          <div class="section-title">6. Utilities</div>
          <p>Tenant is responsible for all utilities unless otherwise specified in writing.</p>
        </div>

        <div class="section">
          <div class="section-title">7. Maintenance</div>
          <p>Tenant shall maintain the premises in good condition and promptly report any needed repairs to the Landlord.</p>
        </div>

        <div class="section">
          <div class="section-title">8. Rules and Regulations</div>
          <p>No illegal activities. No alterations without written consent. No pets unless approved in writing. Quiet hours: 10 PM - 8 AM.</p>
        </div>

        <div class="section">
          <div class="section-title">9. Termination</div>
          <p>Either party may terminate with 30 days written notice. Early termination by tenant may result in forfeiture of security deposit.</p>
        </div>

        <div class="sig">
          <div class="sig-line">Landlord Signature / Date</div>
          <div class="sig-line">Tenant Signature / Date</div>
        </div>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  const generateApplication = () => {
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(`
      <html><head><title>Rental Application</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 40px; color: #000; line-height: 1.6; max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; font-size: 22px; }
        .section { margin: 20px 0; }
        .section-title { font-weight: bold; font-size: 14px; background: #f0f0f0; padding: 5px 10px; margin-bottom: 10px; }
        .field { display: flex; margin: 8px 0; font-size: 13px; }
        .field label { width: 200px; font-weight: bold; }
        .field .line { flex: 1; border-bottom: 1px solid #999; }
        .disclaimer { font-size: 11px; color: #666; margin-top: 30px; }
        .sig { display: flex; justify-content: space-between; margin-top: 40px; }
        .sig-line { border-top: 1px solid #000; width: 250px; text-align: center; padding-top: 5px; font-size: 12px; }
      </style></head><body>
        <h1>RENTAL APPLICATION</h1>

        <div class="section">
          <div class="section-title">PERSONAL INFORMATION</div>
          <div class="field"><label>Full Legal Name:</label><span class="line"></span></div>
          <div class="field"><label>Date of Birth:</label><span class="line"></span></div>
          <div class="field"><label>SSN (last 4):</label><span class="line"></span></div>
          <div class="field"><label>Phone:</label><span class="line"></span></div>
          <div class="field"><label>Email:</label><span class="line"></span></div>
          <div class="field"><label>Driver's License #:</label><span class="line"></span></div>
        </div>

        <div class="section">
          <div class="section-title">CURRENT ADDRESS</div>
          <div class="field"><label>Address:</label><span class="line"></span></div>
          <div class="field"><label>City/State/Zip:</label><span class="line"></span></div>
          <div class="field"><label>Landlord Name:</label><span class="line"></span></div>
          <div class="field"><label>Landlord Phone:</label><span class="line"></span></div>
          <div class="field"><label>Monthly Rent:</label><span class="line"></span></div>
          <div class="field"><label>Reason for Leaving:</label><span class="line"></span></div>
        </div>

        <div class="section">
          <div class="section-title">EMPLOYMENT</div>
          <div class="field"><label>Employer:</label><span class="line"></span></div>
          <div class="field"><label>Position:</label><span class="line"></span></div>
          <div class="field"><label>Monthly Income:</label><span class="line"></span></div>
          <div class="field"><label>Employer Phone:</label><span class="line"></span></div>
          <div class="field"><label>Length of Employment:</label><span class="line"></span></div>
        </div>

        <div class="section">
          <div class="section-title">ADDITIONAL INFORMATION</div>
          <div class="field"><label># of Occupants:</label><span class="line"></span></div>
          <div class="field"><label>Pets (type/breed):</label><span class="line"></span></div>
          <div class="field"><label>Vehicles (make/plate):</label><span class="line"></span></div>
          <div class="field"><label>Have you been evicted?</label><span class="line"></span></div>
          <div class="field"><label>Felony convictions?</label><span class="line"></span></div>
        </div>

        <div class="section">
          <div class="section-title">EMERGENCY CONTACT</div>
          <div class="field"><label>Name:</label><span class="line"></span></div>
          <div class="field"><label>Phone:</label><span class="line"></span></div>
          <div class="field"><label>Relationship:</label><span class="line"></span></div>
        </div>

        <div class="section">
          <div class="section-title">REFERENCES</div>
          <div class="field"><label>Reference 1 (Name/Phone):</label><span class="line"></span></div>
          <div class="field"><label>Reference 2 (Name/Phone):</label><span class="line"></span></div>
        </div>

        <p class="disclaimer">I hereby authorize the landlord to verify the information provided and to obtain credit reports, background checks, and employment verification. I certify that all information is true and complete. False information may result in denial of application or termination of any resulting lease.</p>

        <div class="sig">
          <div class="sig-line">Applicant Signature / Date</div>
          <div class="sig-line">Application Fee: $________</div>
        </div>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Documents</h1>
        <p className="text-gray-500 text-sm mt-1">Generate and print lease documents</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Lease Agreement */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 rounded-lg bg-[#111] text-[#C6963A]">
              <FileText size={24} />
            </div>
            <div>
              <h3 className="font-semibold text-lg">Lease Agreement</h3>
              <p className="text-sm text-gray-500">Generate a residential lease for a tenant</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="label">Select Tenant</label>
              <select className="input" value={selectedTenant} onChange={e => setSelectedTenant(e.target.value)}>
                <option value="">Choose a tenant</option>
                {tenants.filter(t => t.status === 'active').map(t => (
                  <option key={t.id} value={t.id}>{t.name} - {t.property_name} Unit {t.unit_number}</option>
                ))}
              </select>
            </div>

            {tenant && (
              <div className="bg-[#111] rounded-lg p-3 text-sm space-y-1">
                <p>Tenant: <span className="text-white">{tenant.name}</span></p>
                <p>Property: <span className="text-white">{tenant.property_address}</span></p>
                <p>Rent: <span className="text-[#C6963A]">${tenant.rent_amount}/mo</span></p>
                <p>Lease: <span className="text-white">{tenant.lease_start || 'N/A'} to {tenant.lease_end || 'N/A'}</span></p>
              </div>
            )}

            <button
              onClick={generateLease}
              disabled={!tenant}
              className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-30"
            >
              <Printer size={16} /> Generate Lease Agreement
            </button>
          </div>
        </div>

        {/* Rental Application */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 rounded-lg bg-[#111] text-[#C6963A]">
              <FileText size={24} />
            </div>
            <div>
              <h3 className="font-semibold text-lg">Rental Application</h3>
              <p className="text-sm text-gray-500">Blank rental application form</p>
            </div>
          </div>

          <p className="text-sm text-gray-400 mb-4">
            A standard rental application form with personal information, employment, references, and authorization for background/credit checks.
          </p>

          <button onClick={generateApplication} className="btn-primary w-full flex items-center justify-center gap-2">
            <Printer size={16} /> Print Rental Application
          </button>
        </div>
      </div>
    </div>
  );
}
