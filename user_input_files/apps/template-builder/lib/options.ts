export type ToolId = string;
export type ModelProfileId = string;
export type ArtifactId = string;

export type ToolOption = {
  id: ToolId;
  label: string;
  description: string;
  contract?: string;
  env?: string[];
  defaultSelected?: boolean;
};

export type ModelProfileOption = {
  id: ModelProfileId;
  label: string;
  description: string;
  model?: string;
  defaultSelected?: boolean;
};

export type ArtifactOption = {
  id: ArtifactId;
  label: string;
  description: string;
  defaultSelected?: boolean;
};

export const DEFAULT_TOOL_OPTIONS: ToolOption[] = [
  {
    id: 'desktop-commander',
    label: 'Desktop Commander',
    description:
      'Execute shell workflows and collect output for orchestration across the repo.',
    contract: [
      'Use for terminal commands, process management, and diff-style editing.',
      'Respect repo boundaries and prefer dry-run workflows before writing.',
      'Keep logs for reproducibility under /tmp/codex-work/desktop-commander/.'
    ].join('\n- '),
    env: ['DESKTOP_COMMANDER_TIMEOUT=600000'],
    defaultSelected: true
  },
  {
    id: 'fs-project',
    label: 'fs-Project MCP',
    description:
      'Read and write project files from within the LLMC workspace root.',
    contract: [
      'Scope file edits to the workspace root unless escalation is approved.',
      'Prefer apply_patch or streaming writes with explicit diff context.',
      'Leave files UTF-8 with LF endings; log large writes for auditing.'
    ].join('\n- '),
    defaultSelected: true
  },
  {
    id: 'windows-mcp',
    label: 'Windows MCP',
    description:
      'Bridge into host OS automations and desktop controls where available.',
    contract: [
      'Use sparingly for host-level interactions that lack direct CLI parity.',
      'Confirm destination paths when triggering explorer or shell actions.',
      'Avoid persisting credentials or personal data outside project scope.'
    ].join('\n- ')
  }
];

export const DEFAULT_MODEL_PROFILES: ModelProfileOption[] = [
  {
    id: 'code',
    label: 'Code · qwen2.5:14b-instruct-q4_K_M',
    description: 'Default profile prioritising safe, accurate code generation.',
    model: 'qwen2.5:14b-instruct-q4_K_M',
    defaultSelected: true
  },
  {
    id: 'uncensored',
    label: 'Uncensored · gpt-oss:20b',
    description: 'Minimal guardrails for creative rewrites and merchant copy.',
    model: 'gpt-oss:20b'
  },
  {
    id: 'fast',
    label: 'Fast · deepseek-coder:6.7b',
    description: 'Quick responses for iterative prompts and lightweight tasks.',
    model: 'deepseek-coder:6.7b'
  }
];

export const DEFAULT_ARTIFACT_OPTIONS: ArtifactOption[] = [
  {
    id: 'contracts',
    label: 'Contracts',
    description:
      'Baseline guardrails and execution contracts for LLMC orchestration.',
    defaultSelected: true
  },
  {
    id: 'agents',
    label: 'Agents',
    description: 'Agent manifests aligned with the selected orchestration tools.',
    defaultSelected: true
  },
  {
    id: 'envs',
    label: 'Environment',
    description: 'Environment variables and gateway configuration scaffold.',
    defaultSelected: true
  }
];
