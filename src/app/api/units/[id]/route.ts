import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { unit_number, bedrooms, bathrooms, sqft, rent_amount, section8, status, notes } = body;

  const db = getDb();
  db.prepare(
    'UPDATE units SET unit_number=?, bedrooms=?, bathrooms=?, sqft=?, rent_amount=?, section8=?, status=?, notes=? WHERE id=?'
  ).run(unit_number, bedrooms, bathrooms, sqft, rent_amount, section8 ? 1 : 0, status, notes, params.id);

  logActivity('unit', `Updated unit ${unit_number}`);
  return NextResponse.json({ success: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const unit = db.prepare('SELECT unit_number FROM units WHERE id = ?').get(params.id) as any;
  db.prepare('DELETE FROM units WHERE id = ?').run(params.id);

  logActivity('unit', `Deleted unit ${unit?.unit_number}`);
  return NextResponse.json({ success: true });
}
