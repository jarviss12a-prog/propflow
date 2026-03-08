import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const propertyId = req.nextUrl.searchParams.get('property_id');
  const db = getDb();

  let units;
  if (propertyId) {
    units = db.prepare(`
      SELECT u.*, t.name as tenant_name, t.id as tenant_id
      FROM units u
      LEFT JOIN tenants t ON t.unit_id = u.id AND t.status = 'active'
      WHERE u.property_id = ?
      ORDER BY u.unit_number
    `).all(propertyId);
  } else {
    units = db.prepare(`
      SELECT u.*, p.address as property_address, p.name as property_name,
        t.name as tenant_name, t.id as tenant_id
      FROM units u
      LEFT JOIN properties p ON u.property_id = p.id
      LEFT JOIN tenants t ON t.unit_id = u.id AND t.status = 'active'
      ORDER BY p.name, u.unit_number
    `).all();
  }

  return NextResponse.json(units);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { property_id, unit_number, bedrooms, bathrooms, sqft, rent_amount, section8, section8_hap, section8_tenant_share, notes } = body;

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO units (property_id, unit_number, bedrooms, bathrooms, sqft, rent_amount, section8, section8_hap, section8_tenant_share, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(property_id, unit_number, bedrooms || 0, bathrooms || 0, sqft || 0, rent_amount || 0, section8 ? 1 : 0, section8_hap || 0, section8_tenant_share || 0, notes || '');

  logActivity('unit', `Added unit ${unit_number} to property #${property_id}`);
  return NextResponse.json({ id: result.lastInsertRowid }, { status: 201 });
}
