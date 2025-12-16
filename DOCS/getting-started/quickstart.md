# Quickstart: 5 Minutes to Search

This guide will get you from zero to your first semantic search in under 5 minutes.

## Prerequisites

Ensure you have installed LLMC.

```bash
llmc-cli --version
# Output: llmc-cli 0.1.0
```

If you haven't installed it yet, check the [Installation Guide](installation.md).

---

## Step 1: Add a Repository

First, tell LLMC which code you want to search. Navigate to your project's root directory and register it.

```bash
cd /path/to/your/project
llmc-cli repo add .
```

**Expected Output:**
```text
✓ Added repository: /path/to/your/project
  Name: project-name
  Type: python (detected)
```

## Step 2: Index Your Code

Now, generate the index. This process parses your code, splits it into chunks, and generates vector embeddings for semantic search.

```bash
llmc-cli index
```

**Expected Output:**
```text
Indexing project-name...
[====================] 100% Parsing files
[====================] 100% Generating embeddings
✓ Indexing complete. 142 files processed in 4.2s.
```

## Step 3: Search

You are ready to search. Unlike `grep`, you can use natural language queries.

```bash
llmc-cli search "how is the database configured?"
```

**Expected Output:**
```text
Found 3 relevant results:

1. src/config/database.py (Score: 0.89)
----------------------------------------
def get_db_connection():
    """Establishes connection using env vars."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER")
    )

2. src/main.py (Score: 0.72)
----------------------------------------
# Initialize database on startup
db = get_db_connection()
migrate(db)
```

---

## What's Next?

Now that you have the basics running:

*   **[Core Concepts](concepts.md):** Understand how LLMC "reads" your code.
*   **[CLI Reference](../user-guide/cli-reference.md):** Explore advanced commands.
*   **[Configuration](../user-guide/configuration.md):** Customize how LLMC indexes your files.