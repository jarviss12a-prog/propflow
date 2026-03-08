import AuthGuard from '@/components/AuthGuard';
import Sidebar from '@/components/Sidebar';

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 p-4 lg:p-8 lg:ml-0 overflow-x-hidden">
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </AuthGuard>
  );
}
