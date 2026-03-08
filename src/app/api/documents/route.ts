import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb from '@/lib/db';
import { writeFile } from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const propertyId = req.nextUrl.searchParams.get('property_id');
  const tenantId = req.nextUrl.searchParams.get('tenant_id');

  const db = getDb();
  let docs;
  if (propertyId) {
    docs = db.prepare('SELECT * FROM documents WHERE property_id = ? ORDER BY created_at DESC').all(propertyId);
  } else if (tenantId) {
    docs = db.prepare('SELECT * FROM documents WHERE tenant_id = ? ORDER BY created_at DESC').all(tenantId);
  } else {
    docs = db.prepare('SELECT * FROM documents ORDER BY created_at DESC LIMIT 100').all();
  }
  return NextResponse.json(docs);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const formData = await req.formData();
  const file = formData.get('file') as File;
  const propertyId = formData.get('property_id') as string || null;
  const tenantId = formData.get('tenant_id') as string || null;
  const category = formData.get('category') as string || 'other';
  const notes = formData.get('notes') as string || '';

  const ext = path.extname(file.name);
  const filename = `${randomUUID()}${ext}`;
  const uploadDir = path.join(process.cwd(), 'public', 'uploads', 'documents');
  const buffer = Buffer.from(await file.arrayBuffer());
  await writeFile(path.join(uploadDir, filename), buffer);

  const db = getDb();
  db.prepare('INSERT INTO documents (property_id, tenant_id, filename, original_name, mime_type, size, category, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
    .run(propertyId, tenantId, filename, file.name, file.type, file.size, category, notes);

  return NextResponse.json({ success: true }, { status: 201 });
}
