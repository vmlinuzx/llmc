import { promises as fs } from 'node:fs';
import path from 'node:path';

import {
  DEFAULT_ARTIFACT_OPTIONS,
  DEFAULT_MODEL_PROFILES,
  DEFAULT_TOOL_OPTIONS,
  type ArtifactOption,
  type ModelProfileOption,
  type ToolOption
} from './options';

type ToolContractMap = Map<string, string>;

const repoRoot =
  process.env.LLMC_PROJECT_ROOT ||
  path.resolve(process.cwd(), '..', '..');

const scriptsRoot = path.join(repoRoot, 'scripts');
const docsRoot = repoRoot;

const stripMarkdown = (value: string) =>
  value.replace(/\*\*/g, '').replace(/`/g, '').trim();

const kebabCase = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

const safeReadFile = async (filePath: string): Promise<string | null> => {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch {
    return null;
  }
};

const parseModelProfiles = (source: string | null): ModelProfileOption[] => {
  if (!source) {
    return DEFAULT_MODEL_PROFILES;
  }
  const modelsMatch = source.match(/const\s+MODELS\s*=\s*{([\s\S]*?)};/);
  if (!modelsMatch) {
    return DEFAULT_MODEL_PROFILES;
  }
  const literal = modelsMatch[1]
    .replace(/\/\/.*$/gm, '')
    .trim();

  try {
    const parsed = Function(`"use strict"; return ({${literal}});`)() as Record<
      string,
      string
    >;
    const profiles: ModelProfileOption[] = Object.entries(parsed).map(
      ([id, model]) => {
        const fallback = DEFAULT_MODEL_PROFILES.find((p) => p.id === id);
        return {
          id,
          model,
          label: fallback?.label ?? `${id} · ${model}`,
          description:
            fallback?.description ??
            'Model profile discovered from llm_gateway configuration.',
          defaultSelected: fallback?.defaultSelected ?? id === 'code'
        };
      }
    );
    return profiles.length ? profiles : DEFAULT_MODEL_PROFILES;
  } catch {
    return DEFAULT_MODEL_PROFILES;
  }
};

const parseToolOptions = (source: string | null): ToolOption[] => {
  if (!source) {
    return DEFAULT_TOOL_OPTIONS;
  }

  const sectionMatch = source.match(
    /###\s+MCP Tools Required([\s\S]*?)(\n###\s+|\n##\s+|$)/
  );
  if (!sectionMatch) {
    return DEFAULT_TOOL_OPTIONS;
  }

  const lines = sectionMatch[1].split('\n');
  const extracted: ToolOption[] = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    const bulletMatch = line.match(
      /^(?:[-*]|\d+\.)\s+\*\*(.+?)\*\*\s*-\s*(.+)$/
    );
    if (!bulletMatch) continue;
    const [, label, description] = bulletMatch;
    const id = kebabCase(stripMarkdown(label));
    const fallback = DEFAULT_TOOL_OPTIONS.find((tool) => tool.id === id);
    extracted.push({
      id,
      label: stripMarkdown(label),
      description: stripMarkdown(description),
      contract: fallback?.contract,
      env: fallback?.env,
      defaultSelected: fallback?.defaultSelected ?? extracted.length === 0
    });
  }

  return extracted.length ? extracted : DEFAULT_TOOL_OPTIONS;
};

const parseToolContracts = (source: string | null): ToolContractMap => {
  if (!source) {
    return new Map();
  }

  const sectionMatch = source.match(
    /##\s+MCP Tools.*?\n([\s\S]*?)(\n##\s+|\n# |\s*$)/
  );
  if (!sectionMatch) {
    return new Map();
  }
  const section = sectionMatch[1];
  const lines = section.split('\n');
  const contracts = new Map<string, string>();
  let currentId: string | null = null;
  let buffer: string[] = [];

  const flush = () => {
    if (currentId && buffer.length) {
      contracts.set(currentId, buffer.join('\n').trim());
    }
    buffer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (buffer.length) buffer.push('');
      continue;
    }

    if (!line.startsWith('-') && !line.startsWith('•')) {
      flush();
      currentId = kebabCase(stripMarkdown(line.replace(/\(.*\)$/, '').trim()));
    } else if (currentId) {
      buffer.push(line.replace(/^[-•]\s*/, '- '));
    }
  }
  flush();
  return contracts;
};

const buildToolOptionsWithContracts = (
  base: ToolOption[],
  contracts: ToolContractMap
): ToolOption[] =>
  base.map((tool) => {
    const contract = contracts.get(tool.id);
    return {
      ...tool,
      contract: contract ?? tool.contract
    };
  });

const deriveEnvDefaults = (profiles: ModelProfileOption[]): string[] => {
  const defaultProfile =
    profiles.find((profile) => profile.defaultSelected) ?? profiles[0];
  const env: Array<string | null> = [
    '# Workspace defaults',
    'LLMC_EXEC_ROOT=${WORKSPACE_ROOT}',
    'LLMC_TARGET_REPO=${WORKSPACE_ROOT}',
    '',
    '# Logging controls',
    'CODEX_WRAP_ENABLE_LOGGING=1',
    'CODEX_LOG_FILE=${WORKSPACE_ROOT}/logs/codexlog.txt',
    '',
    '# Model insight',
    defaultProfile?.model
      ? `# Default Ollama model resolved to ${defaultProfile.model}`
      : '# Model resolution falls back to scripts/llm_gateway.js defaults'
  ];

  return env.filter((line): line is string => line !== null);
};

export type TemplateRegistry = {
  tools: ToolOption[];
  modelProfiles: ModelProfileOption[];
  artifacts: ArtifactOption[];
  envDefaults: string[];
};

let registryCache: TemplateRegistry | null = null;

export async function loadTemplateRegistry(): Promise<TemplateRegistry> {
  if (registryCache) {
    return registryCache;
  }

  const [llmGateway, agentsDoc, contractsDoc] = await Promise.all([
    safeReadFile(path.join(scriptsRoot, 'llm_gateway.js')),
    safeReadFile(path.join(docsRoot, 'AGENTS.md')),
    safeReadFile(path.join(docsRoot, 'CONTRACTS.md'))
  ]);

  const modelProfiles = parseModelProfiles(llmGateway);
  const toolContracts = parseToolContracts(contractsDoc);
  const toolOptions = buildToolOptionsWithContracts(
    parseToolOptions(agentsDoc),
    toolContracts
  );

  const artifacts = DEFAULT_ARTIFACT_OPTIONS;
  const envDefaults = deriveEnvDefaults(modelProfiles);

  registryCache = {
    tools: toolOptions,
    modelProfiles,
    artifacts,
    envDefaults
  };

  return registryCache;
}

export function resetTemplateRegistryCache(): void {
  registryCache = null;
}
