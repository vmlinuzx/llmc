import { NextResponse } from 'next/server';

import { loadTemplateRegistry } from '@/lib/registry';

export async function GET(): Promise<Response> {
  const registry = await loadTemplateRegistry();
  return NextResponse.json(registry);
}
