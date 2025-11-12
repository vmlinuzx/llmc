import { NextResponse } from 'next/server';

import { createBundle, type BundleConfig } from '@/lib/generateBundle';
import { loadTemplateRegistry } from '@/lib/registry';

export async function POST(request: Request): Promise<Response> {
  let payload: Partial<BundleConfig>;

  try {
    payload = (await request.json()) as Partial<BundleConfig>;
  } catch (error) {
    return NextResponse.json(
      { message: 'Invalid JSON payload.' },
      { status: 400 }
    );
  }

  const tools = Array.isArray(payload.tools)
    ? (Array.from(new Set(payload.tools)) as BundleConfig['tools'])
    : [];
  const artifacts = Array.isArray(payload.artifacts)
    ? (Array.from(new Set(payload.artifacts)) as BundleConfig['artifacts'])
    : [];

  try {
    const registry = await loadTemplateRegistry();
    const defaultArtifactIds = registry.artifacts
      .filter((artifact) => artifact.defaultSelected)
      .map((artifact) => artifact.id);
    const selectedArtifacts =
      artifacts.length > 0
        ? artifacts
        : defaultArtifactIds.length > 0
          ? defaultArtifactIds
          : registry.artifacts.map((artifact) => artifact.id);

    const defaultToolIds = registry.tools
      .filter((tool) => tool.defaultSelected)
      .map((tool) => tool.id);
    const selectedTools =
      tools.length > 0
        ? tools
        : defaultToolIds.length > 0
          ? defaultToolIds
          : registry.tools.map((tool) => tool.id);

    const fallbackProfile =
      registry.modelProfiles.find((profile) => profile.defaultSelected) ??
      registry.modelProfiles[0];

    const { buffer, filename } = await createBundle({
      projectName: payload.projectName ?? 'template-builder',
      profile: payload.profile ?? fallbackProfile?.id ?? 'code',
      tools: selectedTools,
      artifacts: selectedArtifacts
    });

    const headers = new Headers();
    headers.set('Content-Type', 'application/zip');
    headers.set('Content-Disposition', `attachment; filename="${filename}"`);
    headers.set('x-download-filename', filename);

    return new Response(buffer, {
      status: 200,
      headers
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'Failed to generate bundle.';
    return NextResponse.json({ message }, { status: 400 });
  }
}
