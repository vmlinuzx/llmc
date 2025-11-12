/** @jest-environment node */

import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import JSZip from 'jszip';

import { createBundle } from '@/lib/generateBundle';
import { resetTemplateRegistryCache } from '@/lib/registry';

const unzipBuffer = async (buffer: Buffer, destination: string) => {
  const zip = await JSZip.loadAsync(buffer);
  await Promise.all(
    Object.entries(zip.files).map(async ([name, entry]) => {
      const resolved = path.join(destination, name);
      if (entry.dir) {
        await fs.mkdir(resolved, { recursive: true });
        return;
      }
      await fs.mkdir(path.dirname(resolved), { recursive: true });
      const contents = await entry.async('nodebuffer');
      await fs.writeFile(resolved, contents);
    })
  );
};

describe('bundle integration', () => {
  beforeEach(() => {
    resetTemplateRegistryCache();
  });

  it('creates a bundle that unpacks with all artifacts', async () => {
    const result = await createBundle({
      projectName: 'Integration Kit',
      profile: 'code',
      tools: ['desktop-commander'],
      artifacts: ['contracts', 'agents', 'envs']
    });

    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'template-builder-'));
    await unzipBuffer(result.buffer, tmpDir);

    const readme = await fs.readFile(path.join(tmpDir, 'README.md'), 'utf8');
    expect(readme).toContain('Integration Kit');

    const agentManifest = JSON.parse(
      await fs.readFile(
        path.join(tmpDir, 'agents', 'desktop-commander.json'),
        'utf8'
      )
    );
    expect(agentManifest.entryPoint).toBe('agents/desktop-commander.mjs');

    const envFile = await fs.readFile(path.join(tmpDir, 'envs', '.env.llmc'), 'utf8');
    expect(envFile).toContain('OLLAMA_PROFILE=code');

    const codexConfig = await fs.readFile(
      path.join(tmpDir, '.codex', 'config.toml'),
      'utf8'
    );
    expect(codexConfig).toContain('model = "qwen2.5:14b-instruct-q4_K_M"');

    const toolsManifest = JSON.parse(
      await fs.readFile(path.join(tmpDir, '.codex', 'tools.json'), 'utf8')
    );
    expect(toolsManifest.mcp_servers).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: 'desktop-commander' })])
    );
  });
});
