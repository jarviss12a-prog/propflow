import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb, { logActivity } from '@/lib/db';

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const propertyId = req.nextUrl.searchParams.get('property_id');
  const db = getDb();

  let query = `
    SELECT e.*, p.address as property_address, p.name as property_name
    FROM expenses e
    JOIN properties p ON e.property_id = p.id
  `;
  const params: any[] = [];

  if (propertyId) {
    query += ' WHERE e.property_id = ?';
    params.push(propertyId);
  }

  query += ' ORDER BY e.date DESC';

  const expenses = db.prepare(query).all(...params);
  return NextResponse.json(expenses);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json();
  const { property_id, date, category, amount, vendor, description } = body;

  const db = getDb();
  const result = db.prepare(
    'INSERT INTO expenses (property_id, date, category, amount, vendor, description) VALUES (?, ?, ?, ?, ?, ?)'
  ).run(property_id, date, category, amount, vendor || '', description || '');

  logActivity('expense', `Recorded expense: $${amount} - ${category}`);
  return NextResponse.json({ id: result.lastInsertRowid }, { status: 201 });
}
