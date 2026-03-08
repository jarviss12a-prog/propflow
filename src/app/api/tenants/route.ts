import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const tenants = db.prepare(`
    SELECT t.*, u.unit_number, p.address as property_address, p.name as property_name
    FROM tenants t
    LEFT JOIN units u ON t.unit_id = u.id
    LEFT JOIN properties p ON u.property_id = p.id
    ORDER BY t.created_at DESC
  `).all();

  return NextResponse.json(tenants);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { name, email, phone, unit_id, lease_start, lease_end, rent_amount, security_deposit, section8, section8_voucher, section8_case_number, status, notes } = body;

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO tenants (name, email, phone, unit_id, lease_start, lease_end, rent_amount, security_deposit, section8, section8_voucher, section8_case_number, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(name, email, phone, unit_id || null, lease_start, lease_end, rent_amount || 0, security_deposit || 0, section8 ? 1 : 0, section8_voucher || '', section8_case_number || '', status || 'active', notes || '');

  // Update unit status if assigned
  if (unit_id) {
    db.prepare("UPDATE units SET status = 'occupied' WHERE id = ?").run(unit_id);
  }

  logActivity('tenant', `Added tenant: ${name}`);
  return NextResponse.json({ id: result.lastInsertRowid }, { status: 201 });
}
