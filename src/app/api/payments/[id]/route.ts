import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { tenant_id, amount, date, due_date, method, status, notes } = body;

  const db = getDb();
  db.prepare(
    'UPDATE payments SET tenant_id=?, amount=?, date=?, due_date=?, method=?, status=?, notes=? WHERE id=?'
  ).run(tenant_id, amount, date, due_date, method, status, notes, params.id);

  logActivity('payment', `Updated payment #${params.id}`);
  return NextResponse.json({ success: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  db.prepare('DELETE FROM payments WHERE id = ?').run(params.id);
  logActivity('payment', `Deleted payment #${params.id}`);
  return NextResponse.json({ success: true });
}
