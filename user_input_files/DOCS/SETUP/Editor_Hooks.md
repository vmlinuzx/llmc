# Editor Hooks for RAG Sync

These integrations trigger `python -m tools.rag.cli sync --stdin` whenever you save supported files. They assume:

- You have a virtualenv with the dependencies from `tools/rag/requirements.txt` (export `RAG_VENV=/path/to/venv`).
- The helper script `scripts/rag_sync.sh` is executable and lives in the repo root (added in this change).

## LazyVim / Neovim

Create `~/.config/nvim/lua/plugins/rag.lua` (or add to an existing LazyVim custom module):

```lua
return {
  {
    "nvim-lua/plenary.nvim",
    optional = true,
    config = function()
      local Job = require("plenary.job")
      local util = require("lazyvim.util")
      local augroup = vim.api.nvim_create_augroup("RagSync", { clear = true })
      local patterns = { "*.py", "*.ts", "*.tsx", "*.js", "*.go", "*.java" }

      vim.api.nvim_create_autocmd("BufWritePost", {
        group = augroup,
        pattern = patterns,
        callback = function(event)
          local root = util.get_root(event.buf)
          if root == "" then
            return
          end
          Job:new({
            command = root .. "/scripts/rag_sync.sh",
            args = { event.match },
            cwd = root,
            detach = true,
            on_exit = function(_, code)
              if code ~= 0 then
                vim.schedule(function()
                  vim.notify("RAG sync failed (" .. code .. ")", vim.log.levels.WARN)
                end)
              end
            end,
          }):start()
        end,
      })
    end,
  },
}
```

Notes:
- LazyVim already bundles `plenary.nvim` and `lazyvim.util`.
- Set `vim.g.rag_sync_enabled = false` in your config if you want to toggle the autocmd.

## VS Code

Add the following to `.vscode/tasks.json` in your workspace:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "RAG: Sync current file",
      "type": "shell",
      "command": "${workspaceFolder}/scripts/rag_sync.sh",
      "args": ["${file}"],
      "problemMatcher": [],
      "presentation": {
        "reveal": "never",
        "panel": "dedicated"
      },
      "runOptions": {
        "runOn": "fileSave"
      },
      "isBackground": true
    }
  ]
}
```

Tips:
- Set `RAG_VENV` in your shell or VS Code environment to point to the virtualenv so `scripts/rag_sync.sh` can locate Python dependencies.
- The task is idempotent; if multiple saves happen quickly, `rag_sync` de-duplicates via SQLite transactions.
- To disable temporarily, change `runOn` to `"manual"` or comment out the task.

These hooks are optional but keep the `.rag/index.db` warm for instantaneous lookups and drastically reduce remote token spend.
