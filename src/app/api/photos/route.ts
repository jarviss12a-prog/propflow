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

  const unitId = req.nextUrl.searchParams.get('unit_id');
  if (!unitId) return NextResponse.json([]);

  const db = getDb();
  const photos = db.prepare('SELECT * FROM photos WHERE unit_id = ? ORDER BY created_at DESC').all(unitId);
  return NextResponse.json(photos);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const formData = await req.formData();
  const unitId = formData.get('unit_id') as string;
  const files = formData.getAll('files') as File[];

  const db = getDb();
  const uploadDir = path.join(process.cwd(), 'public', 'uploads', 'photos');

  for (const file of files) {
    const ext = path.extname(file.name);
    const filename = `${randomUUID()}${ext}`;
    const buffer = Buffer.from(await file.arrayBuffer());
    await writeFile(path.join(uploadDir, filename), buffer);

    db.prepare('INSERT INTO photos (unit_id, filename, original_name, mime_type, size) VALUES (?, ?, ?, ?, ?)')
      .run(unitId, filename, file.name, file.type, file.size);
  }

  return NextResponse.json({ success: true }, { status: 201 });
}
