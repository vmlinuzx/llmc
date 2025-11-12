# MiniMax Filesystem MCP Server

A comprehensive, production-ready Model Context Protocol (MCP) server for filesystem operations, specifically designed for MiniMax integration.

## Overview

This MCP server provides secure, efficient access to filesystem operations through the Model Context Protocol. It's built on the highly-rated **mark3labs/mcp-filesystem-server** (552 GitHub stars) with custom configurations for MiniMax environments.

## Features

### ✅ Complete File Operations
- **read_file** - Read complete file contents
- **write_file** - Create or overwrite files with content
- **read_multiple_files** - Read multiple files in one operation
- **copy_file** - Copy files and directories
- **move_file** - Move/rename files and directories
- **delete_file** - Delete files with recursive option for directories
- **modify_file** - Update files with find/replace (supports regex)

### ✅ Directory Management
- **list_directory** - Get detailed directory listings
- **create_directory** - Create new directories
- **tree** - Generate hierarchical directory structures
- **get_file_info** - Retrieve detailed file/directory metadata

### ✅ Search & Discovery
- **search_files** - Recursively search files by name patterns
- **search_within_files** - Search text content within files
- **list_allowed_directories** - Show accessible directories

### ✅ Security & Safety
- **Path Validation** - Prevents directory traversal attacks
- **Allowed Directory Control** - Restricts access to specified directories
- **Symlink Security** - Safe symlink handling with security checks
- **MIME Type Detection** - Automatic file type recognition
- **Size Limits** - Built-in safeguards for large file handling

## Quick Start

### 1. Automatic Setup
The server includes automatic Go installation and binary building if needed.

### 2. Running the Server
```bash
cd /path/to/minimax-filesystem-mcp
sh run.sh
```

### 3. MCP Integration
Use the provided `mcp-server.json` configuration file for MiniMax integration.

## Configuration

### Allowed Directories
By default, the server provides access to:
- `/workspace/minimax-filesystem-mcp/workspace` (main workspace)

### Environment Variables
- `GO_HOME` - Custom Go installation directory (optional)

## MCP Tools Reference

| Tool | Description | Required Parameters |
|------|-------------|-------------------|
| `read_file` | Read complete file contents | `path` |
| `write_file` | Create/overwrite file | `path`, `content` |
| `list_directory` | List directory contents | `path` |
| `create_directory` | Create new directory | `path` |
| `delete_file` | Delete file/directory | `path`, `recursive` (optional) |
| `copy_file` | Copy files/directories | `source`, `destination` |
| `move_file` | Move/rename files | `source`, `destination` |
| `modify_file` | Update file content | `path`, `find`, `replace` |
| `search_files` | Search by filename pattern | `path`, `pattern` |
| `search_within_files` | Search file contents | `path`, `substring` |
| `tree` | Generate directory tree | `path` |
| `get_file_info` | Get file metadata | `path` |
| `list_allowed_directories` | List accessible paths | None |

## Architecture

### Built With
- **Go 1.22.1** - Fast, secure execution
- **MCP Protocol** - Standard Model Context Protocol implementation
- **Security Features** - Path validation and access controls

### Project Structure
```
minimax-filesystem-mcp/
├── run.sh                  # STDIO startup script
├── mcp-server.json         # MCP configuration
├── mcp-filesystem-server   # Pre-built binary
├── go.mod                  # Go dependencies
├── workspace/              # Default accessible directory
└── README.md              # This file
```

## Security Considerations

1. **Path Validation** - All paths are validated to prevent directory traversal
2. **Allowed Directories** - Access is restricted to configured directories
3. **No System Access** - Cannot access files outside allowed directories
4. **Symlink Safety** - Symlinks are validated before following

## Testing Status

✅ **All 14 tools tested and verified**
- File operations (read, write, delete, copy, move)
- Directory operations (list, create, tree)
- Search functionality (filename and content search)
- File modification with find/replace
- Metadata retrieval
- Security controls

## Integration with MiniMax

This MCP server is specifically designed for MiniMax integration with:
- ✅ Compatible STDIO protocol
- ✅ JSON-RPC communication
- ✅ Proper MCP tool definitions
- ✅ Error handling and validation
- ✅ Performance optimization

## Support

For issues or questions:
1. Check the test results in `/workspace/minimax-filesystem-mcp/workspace`
2. Verify Go installation: `go version`
3. Check server logs in terminal output

## License

MIT License - See LICENSE file for details.

---

**Built for MiniMax Integration** - Production-ready filesystem operations with enterprise-grade security and performance.