# Template Builder TUI

A Text-based User Interface (TUI) for the Template Builder that provides an interactive way to configure and generate LLMC bundles.

## Overview

The Template Builder TUI is an interactive command-line interface that allows users to:
- Start and manage the Template Builder server
- Configure bundles with profiles, tools, and artifacts
- Generate and download bundles
- View logs and monitor the system
- Open the web UI in a browser

## Quick Start

### Launch the TUI

You can launch the TUI in two ways:

**Option 1: Direct launch**
```bash
./scripts/template_builder_tui.sh
```

**Option 2: Via claude_wrap.sh**
```bash
./scripts/claude_wrap.sh --template
```

## Features

### 1. Server Management
- Automatic detection of running Template Builder server
- One-click server startup with dependency checking
- Background process management with automatic cleanup
- Log monitoring and viewing

### 2. Bundle Configuration
The TUI provides an interactive configuration flow:

**Project Basics**
- Enter project name
- Select model profile (Code, Research, etc.)

**Orchestration Tools**
- Select from available tools (Codex, RAG, etc.)
- Support for multiple selections
- Visual indicators for default selections

**Bundle Contents**
- Choose artifacts (Contracts, Agents, etc.)
- Customizable bundle composition

### 3. Bundle Generation
- Real-time status updates
- Automatic download to current directory
- Confirmation before generation
- Error handling with helpful messages

### 4. Browser Integration
- Open Template Builder in default web browser
- Direct link to `http://localhost:3000`

### 5. Visual Interface
- Color-coded status indicators
- Clear menu navigation
- Progress indicators
- User-friendly error messages

## Menu Options

When you launch the TUI, you'll see the main menu:

```
╔══════════════════════════════════════════════════════════════╗
║                  Template Builder TUI                        ║
║               LLMC Bundle Generator                          ║
╚══════════════════════════════════════════════════════════════╝

Status: Template Builder is running/not running

What would you like to do?

  1) Start Template Builder
  2) Configure and Generate Bundle
  3) Open in Browser
  4) View Logs
  5) Exit
```

### Option 1: Start Template Builder
- Checks if server is already running
- Installs dependencies if needed
- Starts the dev server on port 3000
- Waits for server to be ready (max 30 seconds)
- Provides feedback on startup status

### Option 2: Configure and Generate Bundle
Interactive wizard with the following steps:

1. **Project Name**
   - Enter a name for your project
   - Default: `my-template`

2. **Model Profile**
   - Browse available profiles
   - Each profile shows description
   - Select by number

3. **Orchestration Tools**
   - Choose tools to include
   - Multiple selection support
   - Default selections marked with `[default]`

4. **Bundle Contents**
   - Select artifacts to include
   - Multiple selection support
   - Default selections marked with `[default]`

5. **Summary & Confirmation**
   - Review configuration
   - Confirm or cancel generation
   - Shows selected options

### Option 3: Open in Browser
- Launches default browser
- Opens `http://localhost:3000`
- Fallback: displays URL if browser cannot be opened

### Option 4: View Logs
- Shows last 50 lines of server log
- Real-time log monitoring capability
- Useful for debugging

### Option 5: Exit
- Clean shutdown
- Stops Template Builder if started by TUI
- Exits with status 0

## Configuration

### Environment Variables

- `TEMPLATE_BUILDER_PORT`: Port for Template Builder (default: 3000)
- `TEMPLATE_BUILDER_URL`: Full URL to Template Builder (default: http://localhost:3000)

### Dependencies

The TUI requires:
- `bash` (version 4.0+)
- `curl` (for API calls)
- `jq` (optional, for better JSON parsing)
- `node` (version 16+)
- `npm` (version 7+)

If `jq` is not installed, the TUI will fall back to basic text parsing.

## API Integration

The TUI interacts with the Template Builder via its REST API:

### GET /api/options
Retrieves available configuration options:
```json
{
  "tools": [...],
  "modelProfiles": [...],
  "artifacts": [...]
}
```

### POST /api/generate
Generates and downloads a bundle:
```json
{
  "projectName": "my-template",
  "profile": "code",
  "tools": ["codex", "rag"],
  "artifacts": ["contracts", "agents"]
}
```

## Troubleshooting

### Server Won't Start
1. Check if port 3000 is already in use:
   ```bash
   lsof -i :3000
   ```
2. Check node and npm are installed:
   ```bash
   node --version
   npm --version
   ```
3. Install dependencies:
   ```bash
   cd apps/template-builder
   npm install
   ```
4. View logs for errors (option 4 in TUI)

### API Connection Failed
1. Ensure Template Builder is running
2. Check the port in environment variable
3. Verify server logs for errors

### Bundle Generation Failed
1. Check server logs
2. Verify all required fields in configuration
3. Ensure sufficient disk space
4. Try regenerating with different configuration

### Permission Errors
1. Ensure script is executable:
   ```bash
   chmod +x scripts/template_builder_tui.sh
   ```
2. Check file permissions in template-builder directory

## Advanced Usage

### Custom Port
```bash
TEMPLATE_BUILDER_PORT=3001 ./scripts/template_builder_tui.sh
```

### Non-Interactive Mode
The TUI is designed for interactive use. For automation, consider using the Template Builder API directly:

```bash
# Start server
cd apps/template-builder
npm run dev &
SERVER_PID=$!

# Wait for server
sleep 5

# Generate bundle
curl -X POST http://localhost:3000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"projectName":"test","profile":"code","tools":["codex"],"artifacts":["contracts"]}' \
  -o test-bundle.zip

# Stop server
kill $SERVER_PID
```

## Integration with claude_wrap.sh

The TUI is fully integrated with the main `claude_wrap.sh` script:

```bash
# Launch TUI via claude_wrap
./scripts/claude_wrap.sh --template

# This is equivalent to direct launch
./scripts/template_builder_tui.sh
```

The integration allows you to:
- Access TUI from the same script as other LLM backends
- Use consistent environment and configuration
- Combine with other features (RAG, routing, etc.)

## Future Enhancements

Planned features for future versions:
- [ ] Server status monitoring with periodic updates
- [ ] Multiple project management
- [ ] Template customization wizard
- [ ] Bundle preview without generation
- [ ] Export/import configurations
- [ ] Color theme customization
- [ ] Keyboard shortcuts for navigation
- [ ] Progress bar for bundle generation
- [ ] Telemetry and usage statistics
- [ ] Plugin system for custom tools

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review server logs (TUI option 4)
3. Check Template Builder documentation
4. Create an issue in the repository

## License

Part of the LLMC project. See main repository for license information.