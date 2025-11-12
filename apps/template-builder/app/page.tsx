'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';

import {
  DEFAULT_ARTIFACT_OPTIONS,
  DEFAULT_MODEL_PROFILES,
  DEFAULT_TOOL_OPTIONS,
  type ArtifactOption,
  type ModelProfileOption,
  type ToolOption
} from '@/lib/options';

const DEFAULT_TOOL_IDS = DEFAULT_TOOL_OPTIONS.filter(
  (tool) => tool.defaultSelected
).map((tool) => tool.id);

const DEFAULT_ARTIFACT_IDS = DEFAULT_ARTIFACT_OPTIONS.filter(
  (artifact) => artifact.defaultSelected
).map((artifact) => artifact.id);

const DEFAULT_PROFILE_ID =
  DEFAULT_MODEL_PROFILES.find((profile) => profile.defaultSelected)?.id ??
  DEFAULT_MODEL_PROFILES[0]?.id ??
  'code';

type Status =
  | { state: 'idle' }
  | { state: 'generating' }
  | { state: 'ready'; filename: string }
  | { state: 'error'; message: string };

export default function TemplateBuilderPage(): JSX.Element {
  const [projectName, setProjectName] = useState('template-builder-mvp');
  const [profile, setProfile] = useState<string>(DEFAULT_PROFILE_ID);
  const [toolOptions, setToolOptions] = useState<ToolOption[]>(
    DEFAULT_TOOL_OPTIONS
  );
  const [modelOptions, setModelOptions] = useState<ModelProfileOption[]>(
    DEFAULT_MODEL_PROFILES
  );
  const [artifactOptions, setArtifactOptions] = useState<ArtifactOption[]>(
    DEFAULT_ARTIFACT_OPTIONS
  );
  const [selectedTools, setSelectedTools] = useState<Set<string>>(
    () =>
      new Set(
        DEFAULT_TOOL_IDS.length
          ? DEFAULT_TOOL_IDS
          : DEFAULT_TOOL_OPTIONS.map((tool) => tool.id)
      )
  );
  const [selectedArtifacts, setSelectedArtifacts] = useState<Set<string>>(
    () =>
      new Set(
        DEFAULT_ARTIFACT_IDS.length
          ? DEFAULT_ARTIFACT_IDS
          : DEFAULT_ARTIFACT_OPTIONS.map((artifact) => artifact.id)
      )
  );
  const [status, setStatus] = useState<Status>({ state: 'idle' });

  const isGenerating = status.state === 'generating';

  const selectedProfile = useMemo(
    () => modelOptions.find((model) => model.id === profile),
    [modelOptions, profile]
  );

  useEffect(() => {
    let cancelled = false;
    const loadRegistry = async () => {
      try {
        const response = await fetch('/api/options');
        if (!response.ok) {
          throw new Error('Failed to load template registry.');
        }
        const data = (await response.json()) as {
          tools?: ToolOption[];
          modelProfiles?: ModelProfileOption[];
          artifacts?: ArtifactOption[];
        };
        if (cancelled) return;

        if (data.modelProfiles?.length) {
          setModelOptions(data.modelProfiles);
          setProfile((current) => {
            if (data.modelProfiles?.some((model) => model.id === current)) {
              return current;
            }
            const fallback =
              data.modelProfiles.find((model) => model.defaultSelected) ??
              data.modelProfiles[0];
            return fallback ? fallback.id : current;
          });
        }

        if (data.tools?.length) {
          setToolOptions(data.tools);
          setSelectedTools((prev) => {
            const allowed = new Set(data.tools.map((tool) => tool.id));
            const next = new Set(
              Array.from(prev).filter((id) => allowed.has(id))
            );
            if (next.size === 0) {
              data.tools
                .filter((tool) => tool.defaultSelected)
                .forEach((tool) => next.add(tool.id));
            }
            if (next.size === 0) {
              next.add(data.tools[0].id);
            }
            return next;
          });
        }

        if (data.artifacts?.length) {
          setArtifactOptions(data.artifacts);
          setSelectedArtifacts((prev) => {
            const allowed = new Set(data.artifacts.map((artifact) => artifact.id));
            const next = new Set(
              Array.from(prev).filter((id) => allowed.has(id))
            );
            if (next.size === 0) {
              data.artifacts
                .filter((artifact) => artifact.defaultSelected)
                .forEach((artifact) => next.add(artifact.id));
            }
            if (next.size === 0) {
              next.add(data.artifacts[0].id);
            }
            return next;
          });
        }
      } catch (error) {
        console.error('Failed to load template registry', error);
      }
    };

    void loadRegistry();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectName.trim()) {
      setStatus({ state: 'error', message: 'Project name is required.' });
      return;
    }

    setStatus({ state: 'generating' });
    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectName: projectName.trim(),
          profile,
          tools: Array.from(selectedTools),
          artifacts: Array.from(selectedArtifacts)
        })
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(
          errorPayload?.message ?? `Request failed: ${response.statusText}`
        );
      }

      const blob = await response.blob();
      const filename =
        response.headers.get('x-download-filename') ??
        `${projectName.trim()}-bundle.zip`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setStatus({ state: 'ready', filename });
    } catch (error) {
      console.error(error);
      setStatus({
        state: 'error',
        message:
          error instanceof Error
            ? error.message
            : 'Unexpected error generating bundle.'
      });
    }
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) {
        next.delete(toolId);
      } else {
        next.add(toolId);
      }
      return next;
    });
  };

  const toggleArtifact = (artifactId: string) => {
    setSelectedArtifacts((prev) => {
      const next = new Set(prev);
      if (next.has(artifactId)) {
        next.delete(artifactId);
      } else {
        next.add(artifactId);
      }
      return next;
    });
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Template Builder MVP</h1>
        <p className="text-base text-neutral-600">
          Configure orchestration profiles and export an LLMC-ready starter kit
          with one click. You fight for the user; we handle the scaffolding.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-10 rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm"
      >
        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-medium">Project Basics</h2>
          <label className="flex flex-col gap-2 text-sm">
            Project name
            <input
              className="rounded-md border border-neutral-300 px-3 py-2 text-base focus:border-black focus:outline-none"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="template-builder-mvp"
              required
            />
          </label>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Model profile</span>
            <div className="flex flex-col gap-3">
              {modelOptions.map((model) => (
                <label
                  key={model.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 text-sm transition-colors ${
                    profile === model.id
                      ? 'border-black bg-neutral-50'
                      : 'border-neutral-300 hover:border-neutral-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="modelProfile"
                    value={model.id}
                    checked={profile === model.id}
                    onChange={() => setProfile(model.id)}
                    className="mt-1"
                  />
                  <span>
                    <span className="block text-base font-medium">
                      {model.label}
                    </span>
                    <span className="block text-neutral-600">
                      {model.description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
            {selectedProfile && (
              <p className="text-xs text-neutral-500">
                Selected profile drives defaults across contracts, agent
                manifests, and environment configuration.
              </p>
            )}
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-medium">Orchestration Tools</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {toolOptions.map((tool) => (
              <label
                key={tool.id}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 text-sm transition-colors ${
                  selectedTools.has(tool.id)
                    ? 'border-black bg-neutral-50'
                    : 'border-neutral-300 hover:border-neutral-500'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedTools.has(tool.id)}
                  onChange={() => toggleTool(tool.id)}
                  className="mt-1"
                />
                <span>
                  <span className="block text-base font-medium">
                    {tool.label}
                  </span>
                  <span className="block text-neutral-600">
                    {tool.description}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-medium">Bundle Contents</h2>
          <div className="grid gap-3 md:grid-cols-3">
            {artifactOptions.map((artifact) => (
              <label
                key={artifact.id}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 text-sm transition-colors ${
                  selectedArtifacts.has(artifact.id)
                    ? 'border-black bg-neutral-50'
                    : 'border-neutral-300 hover:border-neutral-500'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedArtifacts.has(artifact.id)}
                  onChange={() => toggleArtifact(artifact.id)}
                  className="mt-1"
                />
                <span>
                  <span className="block text-base font-medium">
                    {artifact.label}
                  </span>
                  <span className="block text-neutral-600">
                    {artifact.description}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </section>

        <div className="flex flex-col gap-3">
          <button
            type="submit"
            disabled={isGenerating || selectedArtifacts.size === 0}
            className="inline-flex items-center justify-center rounded-md bg-black px-4 py-2 text-base font-medium text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isGenerating ? 'Generating...' : 'Generate LLMC Bundle'}
          </button>
          {status.state === 'ready' && (
            <p className="text-sm text-green-600">
              Bundle ready: {status.filename}
            </p>
          )}
          {status.state === 'error' && (
            <p className="text-sm text-red-600">{status.message}</p>
          )}
          {selectedArtifacts.size === 0 && (
            <p className="text-xs text-neutral-500">
              Select at least one artifact to generate.
            </p>
          )}
        </div>
      </form>
    </main>
  );
}
