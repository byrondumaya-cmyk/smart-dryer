// src/app/layout.js — Root Layout
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';

export const metadata = {
  title: 'Smart Dryer — Control Dashboard',
  description: 'Raspberry Pi Smart Drying Rack monitoring and control dashboard',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
