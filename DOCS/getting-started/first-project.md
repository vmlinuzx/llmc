# Your First Project

Now that you have LLMC installed and understand the basics, let's walk through setting up your first project.

## Prerequisites

- [x] LLMC installed (`pip install llmc`)
- [x] A Git repository you want to chat with (or use our example repo)
- [x] An OpenAI API Key (or a local Ollama setup)

## 1. Initialize the Project

Navigate to the root directory of your project.

```bash
cd /path/to/your/project
llmc-cli init
```

This command will:
1.  Detect your project type (Python, TypeScript, Rust, etc.)
2.  Create a `.llmc` directory for local configuration.
3.  Create a `llmc.toml` configuration file.

## 2. Configure the Environment

You will be prompted to choose an embedding provider. For your first project, we recommend:

-   **OpenAI** (Easier setup, higher quality)
-   **Ollama** (Free, runs locally, requires `ollama` installed)

Follow the interactive prompts to set your API keys.

## 3. Register and Index Your Code

Once initialized, start the service and register your repository. The service will automatically index your codebase.

```bash
llmc-cli service start
llmc-cli repo register
```

You can monitor the indexing progress with:

```bash
llmc-cli monitor
```

*Note: For large repositories (100k+ lines), this might take a few minutes.*

## 4. Verify the Index

Let's make sure everything worked.

```bash
llmc-cli service status
```

You should see output indicating the number of files indexed and the status of your repository.

## 5. Ask a Question

Now for the fun part. Ask a question about your codebase.

```bash
llmc-cli chat "How does the authentication middleware work?"
```

LLMC will retrieve the relevant files and generate an answer based *only* on your code.

## Next Steps

- Explore the [User Guide](../user-guide/index.md) for advanced configuration.
- Learn about [Enrichment](../user-guide/enrichment/index.md) to improve search quality.
