import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb from '@/lib/db';

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();
  const tenants = db.prepare(`
    SELECT t.*, u.unit_number, u.rent_amount as unit_rent, p.address as property_address, p.name as property_name
    FROM tenants t
    JOIN units u ON t.unit_id = u.id
    JOIN properties p ON u.property_id = p.id
    WHERE t.section8 = 1 AND t.status = 'active'
    ORDER BY p.name, u.unit_number
  `).all();

  return NextResponse.json(tenants);
}
