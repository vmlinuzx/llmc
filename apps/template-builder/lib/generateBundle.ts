import { promises as fs } from 'node:fs';
import path from 'node:path';

import JSZip from 'jszip';

import {
  DEFAULT_ARTIFACT_OPTIONS,
  DEFAULT_MODEL_PROFILES,
  type ArtifactOption,
  type ModelProfileOption,
  type ToolOption
} from './options';
import { loadTemplateRegistry } from './registry';

export type BundleConfig = {
  projectName: string;
  profile: string;
  tools: string[];
  artifacts: string[];
};

export type BundleResult = {
  filename: string;
  buffer: Buffer;
  manifest: BundleManifest;
};

export type BundleManifest = {
  projectName: string;
  profile: string;
  tools: string[];
  artifacts: string[];
  generatedAt: string;
};

const sanitizeName = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

type TemplateContext = {
  toolMap: Map<string, ToolOption>;
  profileMap: Map<string, ModelProfileOption>;
  artifacts: ArtifactOption[];
  envDefaults: string[];
};

const repoRoot =
  process.env.LLMC_PROJECT_ROOT || path.resolve(process.cwd(), '..', '..');

const defaultTemplateRoot = path.join(repoRoot, 'template');

let templateRootCache: string | null = null;

const getTemplateRoot = async (): Promise<string> => {
  if (templateRootCache) {
    return templateRootCache;
  }
  const resolved = process.env.LLMC_TEMPLATE_ROOT || defaultTemplateRoot;
  const stats = await fs.stat(resolved).catch(() => null);
  if (!stats?.isDirectory()) {
    throw new Error(`Template directory not found: ${resolved}`);
  }
  templateRootCache = resolved;
  return templateRootCache;
};

const toPosixPath = (value: string) => value.split(path.sep).join(path.posix.sep);

const addDirectoryToZip = async (
  zip: JSZip,
  sourceDir: string,
  relativeDir = ''
): Promise<void> => {
  const entries = await fs.readdir(sourceDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === '.DS_Store') continue;
    const absolute = path.join(sourceDir, entry.name);
    const zipPath = relativeDir
      ? path.join(relativeDir, entry.name)
      : entry.name;
    if (entry.isDirectory()) {
      await addDirectoryToZip(zip, absolute, zipPath);
    } else if (entry.isFile()) {
      const contents = await fs.readFile(absolute);
      zip.file(toPosixPath(zipPath), contents);
    }
  }
};

const readTemplateFile = async (
  templateRoot: string,
  relativePath: string
): Promise<string | null> => {
  const target = path.join(templateRoot, relativePath);
  try {
    return await fs.readFile(target, 'utf8');
  } catch {
    return null;
  }
};

const buildTemplateContext = async (): Promise<TemplateContext> => {
  const registry = await loadTemplateRegistry();
  return {
    toolMap: new Map(registry.tools.map((tool) => [tool.id, tool])),
    profileMap: new Map(registry.modelProfiles.map((profile) => [profile.id, profile])),
    artifacts: registry.artifacts,
    envDefaults: registry.envDefaults
  };
};

export async function validateConfig(config: BundleConfig): Promise<void> {
  const context = await buildTemplateContext();
  const artifactIds = new Set(context.artifacts.map((artifact) => artifact.id));

  if (!config.projectName.trim()) {
    throw new Error('Project name is required.');
  }
  if (!context.profileMap.has(config.profile)) {
    throw new Error(`Unknown model profile: ${config.profile}`);
  }
  config.tools.forEach((tool) => {
    if (!context.toolMap.has(tool)) {
      throw new Error(`Unknown tool: ${tool}`);
    }
  });
  config.artifacts.forEach((artifact) => {
    if (!artifactIds.has(artifact)) {
      throw new Error(`Unknown artifact: ${artifact}`);
    }
  });
}

type RenderContext = TemplateContext & {
  selectedTools: ToolOption[];
  selectedProfile: ModelProfileOption | undefined;
};

const renderContracts = (config: BundleConfig, context: RenderContext) => {
  return [
    '# LLMC Orchestration Contract',
    '',
    `**Project:** ${config.projectName}`,
    `**Profile:** ${context.selectedProfile?.label ?? config.profile}`,
    '',
    '## Execution Guarantees',
    '- Maintain safe defaults for shell access.',
    '- Respect workspace boundaries; escalate before using non-whitelisted tools.',
    '- Capture logs for every orchestrated step.',
    '',
    '## Toolchain',
    ...context.selectedTools.map((tool) => `- ${tool.label}`),
    '',
    '## Success Criteria',
    '- Bundle builds without manual patching.',
    '- Qwen responses stay under local context limits.',
    '- Smoke tests pass before delivery.',
    '',
    '## Tool Operating Guidelines',
    ...context.selectedTools.flatMap((tool) => {
      const header = `### ${tool.label}`;
      const body = tool.contract
        ? tool.contract
        : '- Follow standard LLMC guardrails for this tool.';
      return [header, body, ''];
    })
  ].join('\n');
};

const renderAgentManifest = (tool: ToolOption, profile: ModelProfileOption | undefined) => {
  return JSON.stringify(
    {
      name: tool.label,
      entryPoint: `agents/${tool.id}.mjs`,
      profile: profile?.id ?? 'code',
      description: `Auto-generated agent manifest for ${tool.label}.`
    },
    null,
    2
  );
};

const renderEnvFile = (
  config: BundleConfig,
  context: RenderContext
) => {
  const toolEnv = context.selectedTools
    .flatMap((tool) => tool.env ?? [])
    .filter(Boolean);

  const profileModel =
    context.selectedProfile?.model ??
    DEFAULT_MODEL_PROFILES.find((profile) => profile.id === config.profile)?.model;

  const lines = [
    `# Generated ${new Date().toISOString()}`,
    `PROJECT_NAME=${sanitizeName(config.projectName)}`,
    `LLM_DISABLED=false`,
    `NEXT_PUBLIC_LLM_DISABLED=false`,
    `OLLAMA_PROFILE=${config.profile}`,
    profileModel ? `OLLAMA_MODEL=${profileModel}` : null,
    `ENABLED_TOOLS=${config.tools.join(',')}`,
    '',
    '# Tool-specific defaults',
    ...toolEnv,
    '',
    '# Registry defaults',
    ...context.envDefaults
  ];
  const filtered = lines.filter((line): line is string => line !== null);
  const deduped: string[] = [];
  const seen = new Set<string>();
  let previousBlank = false;

  for (const line of filtered) {
    const isBlank = line.trim() === '';
    if (isBlank) {
      if (!previousBlank) {
        deduped.push('');
      }
      previousBlank = true;
      continue;
    }

    previousBlank = false;
    if (seen.has(line)) continue;
    seen.add(line);
    deduped.push(line);
  }

  return `${deduped.join('\n')}\n`;
};

const renderReadme = (config: BundleConfig, context: RenderContext) => {
  const toolSummary = context.selectedTools
    .map((tool) => `- ${tool.label}`)
    .join('\n');
  const envPreview = renderEnvFile(config, context)
    .trimEnd()
    .split('\n');

  return [
    '# Template Builder Bundle',
    '',
    `Generated for **${config.projectName}** using the ${
      context.selectedProfile?.label ?? config.profile
    } profile.`,
    '',
    '## Next Steps',
    '- Unzip into your LLMC workspace root.',
    '- Review contracts before distributing to agents.',
    '- Configure `.env.local` overrides as needed.',
    '',
    '## Included Tools',
    toolSummary || '- (none selected)',
    '',
    'Stay in the loop: fight for the user.',
    '',
    '## Environment Defaults',
    '```env',
    ...envPreview,
    '```'
  ].join('\n');
};

const renderToolsManifest = async (
  templateRoot: string,
  context: RenderContext
): Promise<string | null> => {
  const raw = await readTemplateFile(templateRoot, path.join('.codex', 'tools.json'));
  if (!raw) {
    return null;
  }

  try {
    type ToolManifest = {
      mcp_servers?: Array<Record<string, unknown>>;
      models?: Array<Record<string, unknown>>;
    };

    const parsed = JSON.parse(raw) as ToolManifest;
    const selectedToolIds = new Set(context.selectedTools.map((tool) => tool.id));

    const currentServers = Array.isArray(parsed.mcp_servers)
      ? parsed.mcp_servers.filter(
          (server) =>
            server &&
            typeof server === 'object' &&
            'id' in server &&
            typeof server.id === 'string' &&
            selectedToolIds.has(server.id)
        )
      : [];

    const existingIds = new Set(
      currentServers
        .map((server) =>
          server && typeof server === 'object' && 'id' in server
            ? (server.id as string)
            : null
        )
        .filter((id): id is string => Boolean(id))
    );

    context.selectedTools.forEach((tool) => {
      if (!existingIds.has(tool.id)) {
        currentServers.push({ id: tool.id });
      }
    });

    parsed.mcp_servers = currentServers;

    if (Array.isArray(parsed.models)) {
      const ollamaEntry = parsed.models.find(
        (model) => model && typeof model === 'object' && (model as { id?: string }).id === 'ollama'
      );
      if (ollamaEntry && typeof ollamaEntry === 'object') {
        if (context.selectedProfile) {
          (ollamaEntry as Record<string, unknown>).default_profile =
            context.selectedProfile.id;
        }
        const profiles =
          (ollamaEntry as Record<string, unknown>).profiles &&
          typeof (ollamaEntry as Record<string, unknown>).profiles === 'object'
            ? ((ollamaEntry as Record<string, unknown>).profiles as Record<string, string>)
            : {};

        for (const profile of context.profileMap.values()) {
          if (profile.model) {
            profiles[profile.id] = profile.model;
          }
        }

        (ollamaEntry as Record<string, unknown>).profiles = profiles;
      }
    }

    return `${JSON.stringify(parsed, null, 2)}\n`;
  } catch (error) {
    console.warn('Failed to generate customized tools manifest', error);
    return raw;
  }
};

const renderCodexConfig = async (
  templateRoot: string,
  context: RenderContext
): Promise<string | null> => {
  const raw = await readTemplateFile(templateRoot, path.join('.codex', 'config.toml'));
  const selectedModel = context.selectedProfile?.model;

  if (!raw || !selectedModel) {
    return raw;
  }

  const replacement = `model = "${selectedModel}"`;
  const lines = raw.split('\n');
  let replaced = false;

  const updated = lines.map((line) => {
    if (!replaced && line.trim().startsWith('model')) {
      replaced = true;
      return replacement;
    }
    return line;
  });

  if (!replaced) {
    if (updated.length === 0 || updated[updated.length - 1].trim() !== '') {
      updated.push('');
    }
    updated.push(replacement);
  }

  return `${updated.join('\n')}\n`;
};

export async function createBundle(config: BundleConfig): Promise<BundleResult> {
  await validateConfig(config);
  const projectName = config.projectName.trim();
  const context = await buildTemplateContext();
  const templateRoot = await getTemplateRoot();

  const uniqueTools = Array.from(new Set(config.tools));
  const uniqueArtifacts = Array.from(new Set(config.artifacts));
  const artifactIds = new Set(context.artifacts.map((artifact) => artifact.id));
  const selectedTools = uniqueTools
    .map((tool) => context.toolMap.get(tool))
    .filter((tool): tool is ToolOption => Boolean(tool));
  const selectedProfile = context.profileMap.get(config.profile);

  if (!selectedProfile) {
    throw new Error(`Unknown model profile: ${config.profile}`);
  }

  if (selectedTools.length !== uniqueTools.length) {
    const missing = uniqueTools.filter((tool) => !context.toolMap.has(tool));
    throw new Error(`Unknown tool(s): ${missing.join(', ')}`);
  }

  if (!artifactIds.size) {
    context.artifacts = DEFAULT_ARTIFACT_OPTIONS;
    DEFAULT_ARTIFACT_OPTIONS.forEach((artifact) =>
      artifactIds.add(artifact.id)
    );
  }

  const normalizedArtifacts = uniqueArtifacts.filter((artifact) =>
    artifactIds.has(artifact)
  );

  if (normalizedArtifacts.length !== uniqueArtifacts.length) {
    const missing = uniqueArtifacts.filter((artifact) => !artifactIds.has(artifact));
    throw new Error(`Unknown artifact(s): ${missing.join(', ')}`);
  }

  const normalizedConfig: BundleConfig = {
    ...config,
    projectName,
    tools: uniqueTools,
    artifacts: normalizedArtifacts
  };

  const renderContext: RenderContext = {
    ...context,
    selectedTools,
    selectedProfile
  };

  const zip = new JSZip();
  const slug = sanitizeName(normalizedConfig.projectName) || 'template-builder';
  const generatedAt = new Date().toISOString();

  await addDirectoryToZip(zip, templateRoot);

  const customizedTools = await renderToolsManifest(templateRoot, renderContext);
  if (customizedTools) {
    zip.file('.codex/tools.json', customizedTools);
  }

  const customizedConfig = await renderCodexConfig(templateRoot, renderContext);
  if (customizedConfig) {
    zip.file('.codex/config.toml', customizedConfig);
  }

  zip.file('README.md', renderReadme(normalizedConfig, renderContext));
  zip.file(
    'manifest.json',
    JSON.stringify(
      {
        projectName: normalizedConfig.projectName,
        profile: normalizedConfig.profile,
        tools: normalizedConfig.tools,
        artifacts: normalizedConfig.artifacts,
        generatedAt
      } satisfies BundleManifest,
      null,
      2
    )
  );

  if (normalizedArtifacts.includes('contracts')) {
    zip.file('contracts/orchestration.md', renderContracts(normalizedConfig, renderContext));
  }

  if (normalizedArtifacts.includes('agents')) {
    selectedTools.forEach((tool) => {
      zip.file(
        `agents/${tool.id}.json`,
        renderAgentManifest(tool, selectedProfile)
      );
    });
  }

  if (normalizedArtifacts.includes('envs')) {
    zip.file('envs/.env.llmc', renderEnvFile(normalizedConfig, renderContext));
  }

  const buffer = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });

  return {
    filename: `${slug}-bundle.zip`,
    buffer,
    manifest: {
      projectName: normalizedConfig.projectName,
      profile: normalizedConfig.profile,
      tools: normalizedConfig.tools,
      artifacts: normalizedConfig.artifacts,
      generatedAt
    }
  };
}
