import JSZip from 'jszip';

import { createBundle } from '@/lib/generateBundle';
import { resetTemplateRegistryCache } from '@/lib/registry';

beforeEach(() => {
  resetTemplateRegistryCache();
});

describe('createBundle', () => {
  it('builds a bundle with the requested artifacts', async () => {
    const bundle = await createBundle({
      projectName: 'Test Kit',
      profile: 'code',
      tools: ['desktop-commander', 'fs-project'],
      artifacts: ['contracts', 'agents', 'envs']
    });

    expect(bundle.filename).toBe('test-kit-bundle.zip');

    const zip = await JSZip.loadAsync(bundle.buffer);
    const fileNames = Object.keys(zip.files);

    expect(fileNames).toEqual(
      expect.arrayContaining([
        'README.md',
        'manifest.json',
        'contracts/orchestration.md',
        'agents/desktop-commander.json',
        'agents/fs-project.json',
        'envs/.env.llmc'
      ])
    );

    const manifestRaw = await zip.file('manifest.json')?.async('string');
    expect(manifestRaw).toBeDefined();

    const manifest = JSON.parse(manifestRaw ?? '{}');
    expect(manifest.profile).toBe('code');
    expect(manifest.tools).toEqual(
      expect.arrayContaining(['desktop-commander', 'fs-project'])
    );

    const codexConfig = await zip.file('.codex/config.toml')?.async('string');
    expect(codexConfig).toBeDefined();
    expect(codexConfig).toContain('model = "qwen2.5:14b-instruct-q4_K_M"');

    const toolsJsonRaw = await zip.file('.codex/tools.json')?.async('string');
    expect(toolsJsonRaw).toBeDefined();

    const toolsManifest = JSON.parse(toolsJsonRaw ?? '{}');
    expect(toolsManifest.mcp_servers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: 'desktop-commander' }),
        expect.objectContaining({ id: 'fs-project' })
      ])
    );

    const ollamaEntry = toolsManifest.models.find(
      (model: { id?: string }) => model?.id === 'ollama'
    );
    expect(ollamaEntry?.default_profile).toBe('code');

    const contract = await zip.file('contracts/orchestration.md')?.async('string');
    expect(contract).toContain('## Tool Operating Guidelines');
    expect(contract).toContain('Desktop Commander');
  });

  it('throws when project name is missing', async () => {
    await expect(
      createBundle({
        projectName: '   ',
        profile: 'code',
        tools: ['desktop-commander'],
        artifacts: ['contracts']
      })
    ).rejects.toThrow('Project name is required.');
  });
});
