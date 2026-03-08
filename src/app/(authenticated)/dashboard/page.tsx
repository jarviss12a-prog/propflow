'use client';

import { useEffect, useState } from 'react';
import { Building2, Home, Users, DollarSign, AlertTriangle, Calendar, Activity } from 'lucide-react';

interface DashboardData {
  totalProperties: number;
  totalUnits: number;
  occupiedUnits: number;
  vacantUnits: number;
  monthlyRevenue: number;
  outstandingPayments: number;
  upcomingLeaseExpirations: any[];
  recentActivity: any[];
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/dashboard')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-gray-400">Loading dashboard...</div>;
  }

  if (!data) return null;

  const stats = [
    { label: 'Total Properties', value: data.totalProperties, icon: Building2, color: 'text-blue-400' },
    { label: 'Total Units', value: data.totalUnits, icon: Home, color: 'text-purple-400' },
    { label: 'Occupied Units', value: data.occupiedUnits, icon: Users, color: 'text-green-400' },
    { label: 'Vacant Units', value: data.vacantUnits, icon: Home, color: 'text-yellow-400' },
    { label: 'Monthly Revenue', value: `$${data.monthlyRevenue.toLocaleString()}`, icon: DollarSign, color: 'text-[#C6963A]' },
    { label: 'Outstanding Payments', value: data.outstandingPayments, icon: AlertTriangle, color: 'text-red-400' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Overview of your properties</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="card flex items-center gap-4">
            <div className={`p-3 rounded-lg bg-[#111] ${stat.color}`}>
              <stat.icon size={22} />
            </div>
            <div>
              <p className="text-gray-500 text-xs">{stat.label}</p>
              <p className="text-xl font-bold">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Upcoming Lease Expirations */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Calendar size={18} className="text-[#C6963A]" />
            <h2 className="font-semibold">Upcoming Lease Expirations (90 days)</h2>
          </div>
          {data.upcomingLeaseExpirations.length === 0 ? (
            <p className="text-gray-500 text-sm">No upcoming expirations</p>
          ) : (
            <div className="space-y-2">
              {data.upcomingLeaseExpirations.map((item: any, i: number) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-[#2a2a2a] last:border-0">
                  <div>
                    <p className="text-sm font-medium">{item.name}</p>
                    <p className="text-xs text-gray-500">{item.address} - Unit {item.unit_number}</p>
                  </div>
                  <span className="badge-yellow">{item.lease_end}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={18} className="text-[#C6963A]" />
            <h2 className="font-semibold">Recent Activity</h2>
          </div>
          {data.recentActivity.length === 0 ? (
            <p className="text-gray-500 text-sm">No recent activity</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {data.recentActivity.map((item: any) => (
                <div key={item.id} className="flex justify-between items-start py-2 border-b border-[#2a2a2a] last:border-0">
                  <div>
                    <span className="badge-blue mr-2">{item.type}</span>
                    <span className="text-sm">{item.message}</span>
                  </div>
                  <span className="text-xs text-gray-500 whitespace-nowrap ml-2">
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
