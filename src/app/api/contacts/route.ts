import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const contacts = db.prepare('SELECT * FROM contacts ORDER BY category, name').all();
  return NextResponse.json(contacts);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { name, company, phone, email, category, notes } = body;

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO contacts (name, company, phone, email, category, notes) VALUES (?, ?, ?, ?, ?, ?)'
  ).run(name, company || '', phone || '', email || '', category, notes || '');

  logActivity('contact', `Added contact: ${name} (${category})`);
  return NextResponse.json({ id: result.lastInsertRowid }, { status: 201 });
}
