import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { name, company, phone, email, category, notes } = body;

  const db = getDb();
  db.prepare(
    'UPDATE contacts SET name=?, company=?, phone=?, email=?, category=?, notes=? WHERE id=?'
  ).run(name, company, phone, email, category, notes, params.id);

  logActivity('contact', `Updated contact: ${name}`);
  return NextResponse.json({ success: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const contact = db.prepare('SELECT name FROM contacts WHERE id = ?').get(params.id) as any;
  db.prepare('DELETE FROM contacts WHERE id = ?').run(params.id);
  logActivity('contact', `Deleted contact: ${contact?.name}`);
  return NextResponse.json({ success: true });
}
