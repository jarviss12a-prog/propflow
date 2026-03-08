import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb from '@/lib/db';
import { unlink } from 'fs/promises';
import path from 'path';

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const doc = db.prepare('SELECT filename FROM documents WHERE id = ?').get(params.id) as any;
  if (doc) {
    try { await unlink(path.join(process.cwd(), 'public', 'uploads', 'documents', doc.filename)); } catch {}
    db.prepare('DELETE FROM documents WHERE id = ?').run(params.id);
  }
  return NextResponse.json({ success: true });
}
