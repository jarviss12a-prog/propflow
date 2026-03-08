import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const property = db.prepare('SELECT * FROM properties WHERE id = ?').get(params.id);
  if (!property) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  return NextResponse.json(property);
}

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { name, address, city, state, zip, type, tenant, notes } = body;

  const db = getDb();
  db.prepare(
    'UPDATE properties SET name=?, address=?, city=?, state=?, zip=?, type=?, tenant=?, notes=? WHERE id=?'
  ).run(name, address, city, state, zip, type, tenant || '', notes, params.id);

  logActivity('property', `Updated property: ${name}`);
  return NextResponse.json({ success: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const property = db.prepare('SELECT name FROM properties WHERE id = ?').get(params.id) as any;
  db.prepare('DELETE FROM properties WHERE id = ?').run(params.id);

  logActivity('property', `Deleted property: ${property?.name}`);
  return NextResponse.json({ success: true });
}
