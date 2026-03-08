import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import getDb from '@/lib/db';

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const db = getDb();

  const totalProperties = (db.prepare('SELECT COUNT(*) as count FROM properties').get() as any).count;
  const totalUnits = (db.prepare('SELECT COUNT(*) as count FROM units').get() as any).count;
  const occupiedUnits = (db.prepare("SELECT COUNT(*) as count FROM units WHERE status = 'occupied'").get() as any).count;
  const vacantUnits = totalUnits - occupiedUnits;
  const monthlyRevenue = (db.prepare("SELECT COALESCE(SUM(rent_amount), 0) as total FROM tenants WHERE status = 'active'").get() as any).total;

  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const monthStart = `${year}-${month}-01`;
  const dueDate = `${year}-${month}-05`;

  const activeTenants = (db.prepare("SELECT COUNT(*) as count FROM tenants WHERE status = 'active'").get() as any).count;
  const paidThisMonth = (db.prepare(
    "SELECT COUNT(DISTINCT tenant_id) as count FROM payments WHERE date >= ? AND status = 'paid'"
  ).get(monthStart) as any).count;
  const outstandingPayments = activeTenants - paidThisMonth;

  const ninetyDaysFromNow = new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  const today = now.toISOString().split('T')[0];
  const upcomingLeaseExpirations = db.prepare(
    "SELECT t.name, t.lease_end, u.unit_number, p.address FROM tenants t LEFT JOIN units u ON t.unit_id = u.id LEFT JOIN properties p ON u.property_id = p.id WHERE t.lease_end BETWEEN ? AND ? AND t.status = 'active' ORDER BY t.lease_end"
  ).all(today, ninetyDaysFromNow);

  const recentActivity = db.prepare(
    'SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 20'
  ).all();

  return NextResponse.json({
    totalProperties,
    totalUnits,
    occupiedUnits,
    vacantUnits,
    monthlyRevenue,
    outstandingPayments,
    upcomingLeaseExpirations,
    recentActivity,
  });
}
