import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const tenant = db.prepare(`
    SELECT t.*, u.unit_number, p.address as property_address
    FROM tenants t
    LEFT JOIN units u ON t.unit_id = u.id
    LEFT JOIN properties p ON u.property_id = p.id
    WHERE t.id = ?
  `).get(params.id);

  if (!tenant) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  return NextResponse.json(tenant);
}

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { name, email, phone, unit_id, lease_start, lease_end, rent_amount, security_deposit, section8, section8_voucher, section8_case_number, status, notes } = body;

  const db = getDb();

  // Get old unit_id to update status
  const oldTenant = db.prepare('SELECT unit_id FROM tenants WHERE id = ?').get(params.id) as any;

  db.prepare(
    'UPDATE tenants SET name=?, email=?, phone=?, unit_id=?, lease_start=?, lease_end=?, rent_amount=?, security_deposit=?, section8=?, section8_voucher=?, section8_case_number=?, status=?, notes=? WHERE id=?'
  ).run(name, email, phone, unit_id || null, lease_start, lease_end, rent_amount, security_deposit, section8 ? 1 : 0, section8_voucher, section8_case_number, status, notes, params.id);

  // Update unit statuses
  if (oldTenant?.unit_id && oldTenant.unit_id !== unit_id) {
    db.prepare("UPDATE units SET status = 'vacant' WHERE id = ?").run(oldTenant.unit_id);
  }
  if (unit_id && status === 'active') {
    db.prepare("UPDATE units SET status = 'occupied' WHERE id = ?").run(unit_id);
  }
  if (unit_id && status !== 'active') {
    db.prepare("UPDATE units SET status = 'vacant' WHERE id = ?").run(unit_id);
  }

  logActivity('tenant', `Updated tenant: ${name}`);
  return NextResponse.json({ success: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const tenant = db.prepare('SELECT name, unit_id FROM tenants WHERE id = ?').get(params.id) as any;

  if (tenant?.unit_id) {
    db.prepare("UPDATE units SET status = 'vacant' WHERE id = ?").run(tenant.unit_id);
  }

  db.prepare('DELETE FROM tenants WHERE id = ?').run(params.id);
  logActivity('tenant', `Deleted tenant: ${tenant?.name}`);
  return NextResponse.json({ success: true });
}
