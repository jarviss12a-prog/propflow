import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const month = req.nextUrl.searchParams.get('month');
  const propertyId = req.nextUrl.searchParams.get('property_id');
  const status = req.nextUrl.searchParams.get('status');

  const db = getDb();

  let query = `
    SELECT pay.*, t.name as tenant_name, t.rent_amount as expected_rent,
      u.unit_number, p.address as property_address, p.name as property_name, p.id as property_id
    FROM payments pay
    JOIN tenants t ON pay.tenant_id = t.id
    LEFT JOIN units u ON t.unit_id = u.id
    LEFT JOIN properties p ON u.property_id = p.id
    WHERE 1=1
  `;
  const params: any[] = [];

  if (month) {
    query += " AND strftime('%Y-%m', pay.date) = ?";
    params.push(month);
  }
  if (propertyId) {
    query += ' AND p.id = ?';
    params.push(propertyId);
  }
  if (status) {
    query += ' AND pay.status = ?';
    params.push(status);
  }

  query += ' ORDER BY pay.date DESC';

  const payments = db.prepare(query).all(...params);
  return NextResponse.json(payments);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { tenant_id, amount, date, due_date, method, status, notes } = body;

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO payments (tenant_id, amount, date, due_date, method, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)'
  ).run(tenant_id, amount, date, due_date || null, method || '', status || 'paid', notes || '');

  const tenant = db.prepare('SELECT name FROM tenants WHERE id = ?').get(tenant_id) as any;
  logActivity('payment', `Recorded payment of $${amount} from ${tenant?.name}`);

  return NextResponse.json({ id: result.lastInsertRowid }, { status: 201 });
}
