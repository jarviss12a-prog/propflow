import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const properties = db.prepare(`
    SELECT p.*,
      (SELECT COUNT(*) FROM units WHERE property_id = p.id) as unit_count,
      (SELECT COUNT(*) FROM units WHERE property_id = p.id AND status = 'occupied') as occupied_count
    FROM properties p ORDER BY p.created_at DESC
  `).all();

  return NextResponse.json(properties);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { name, address, city, state, zip, type, notes } = body;

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO properties (name, address, city, state, zip, type, notes) VALUES (?, ?, ?, ?, ?, ?, ?)'
  ).run(name, address, city, state, zip, type || 'residential', notes || '');

  logActivity('property', `Added property: ${name} at ${address}`);
  return NextResponse.json({ id: result.lastInsertRowid }, { status: 201 });
}
