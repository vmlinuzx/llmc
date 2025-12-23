# Quickstart: 5 Minutes to Search

This guide will get you from zero to your first semantic search in under 5 minutes.

## Prerequisites

Ensure you have installed LLMC.

```bash
llmc-cli --version
```

If you haven't installed it yet, check the [Installation Guide](installation.md).

---

## Step 1: Initialize and Configure

Navigate to your project's root directory and run the initialization wizard.

```bash
cd /path/to/your/project
llmc-cli init
llmc-cli config wizard
```

## Step 2: Register Repository

Start the RAG service and register your repository.

```bash
llmc-cli service start
llmc-cli repo register
```

## Step 3: Search

You are ready to search. Unlike `grep`, you can use natural language queries.

```bash
llmc-cli analytics search "how is the database configured?"
```

Or ask the AI assistant:

```bash
llmc-cli chat "how is the database configured?"
```

---

## What's Next?

Now that you have the basics running:

*   **[Core Concepts](concepts.md):** Understand how LLMC "reads" your code.
*   **[CLI Reference](../user-guide/cli-reference.md):** Explore advanced commands.
*   **[Configuration](../user-guide/configuration.md):** Customize how LLMC indexes your files.
