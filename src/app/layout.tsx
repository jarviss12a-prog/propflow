import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Providers from '@/components/Providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'PropFlow - Property Management',
  description: 'Property management CRM for landlords',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-[#0D0D0D] text-gray-100 antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
