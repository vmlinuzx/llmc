import './globals.css';
import type { Metadata } from 'next';
import { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Template Builder',
  description:
    'Spin up LLMC-ready orchestration bundles with configurable tooling.'
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps): JSX.Element {
  return (
    <html lang="en">
      <body className="bg-neutral-100 text-neutral-900">{children}</body>
    </html>
  );
}
