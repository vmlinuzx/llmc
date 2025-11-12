#!/usr/bin/env bash

# Template Builder TUI
# Interactive text-based user interface for the Template Builder

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_BUILDER_DIR="$ROOT_DIR/apps/template-builder"
TEMPLATE_BUILDER_PORT="${TEMPLATE_BUILDER_PORT:-3000}"
TEMPLATE_BUILDER_URL="http://localhost:$TEMPLATE_BUILDER_PORT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if jq is available for JSON parsing
if command -v jq > /dev/null 2>&1; then
    HAS_JQ=true
else
    HAS_JQ=false
    echo -e "${YELLOW}Warning: jq not found. Install jq for better JSON parsing.${NC}"
fi

# Check if template builder is running
is_template_builder_running() {
    curl -s -f "$TEMPLATE_BUILDER_URL/api/options" >/dev/null 2>&1
}

# Start template builder dev server
start_template_builder() {
    echo -e "${BLUE}Starting Template Builder dev server...${NC}"
    cd "$TEMPLATE_BUILDER_DIR"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing dependencies...${NC}"
        npm install
    fi

    # Start in background
    npm run dev > /tmp/template_builder.log 2>&1 &
    TEMPLATE_BUILDER_PID=$!

    echo -e "${BLUE}Waiting for server to be ready...${NC}"

    # Wait for server to be ready (max 30 seconds)
    for i in {1..30}; do
        if is_template_builder_running; then
            echo -e "${GREEN}✓ Template Builder is running on $TEMPLATE_BUILDER_URL${NC}"
            return 0
        fi
        sleep 1
        echo -n "."
    done

    echo -e "\n${RED}✗ Failed to start Template Builder${NC}"
    return 1
}

# Stop template builder
stop_template_builder() {
    if [ -n "${TEMPLATE_BUILDER_PID:-}" ]; then
        echo -e "${YELLOW}Stopping Template Builder...${NC}"
        kill $TEMPLATE_BUILDER_PID 2>/dev/null || true
        wait $TEMPLATE_BUILDER_PID 2>/dev/null || true
        echo -e "${GREEN}✓ Template Builder stopped${NC}"
    fi
}

# Trap to ensure cleanup on exit
cleanup() {
    stop_template_builder
}
trap cleanup EXIT INT TERM

# Fetch options from template builder
fetch_options() {
    if ! is_template_builder_running; then
        echo -e "${RED}Error: Template Builder is not running${NC}"
        return 1
    fi

    local response
    response=$(curl -s "$TEMPLATE_BUILDER_URL/api/options" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$response" ]; then
        echo -e "${RED}Failed to fetch options from Template Builder${NC}"
        return 1
    fi

    echo "$response"
}

# Display header
show_header() {
    clear
    echo -e "${MAGENTA}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                  Template Builder TUI                        ║"
    echo "║               LLMC Bundle Generator                          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Main menu
main_menu() {
    while true; do
        show_header

        # Check if server is running
        if is_template_builder_running; then
            echo -e "${GREEN}✓ Template Builder is running${NC}"
        else
            echo -e "${RED}✗ Template Builder is not running${NC}"
        fi
        echo ""

        echo "What would you like to do?"
        echo ""
        echo "  1) Start Template Builder"
        echo "  2) Configure and Generate Bundle"
        echo "  3) Open in Browser"
        echo "  4) View Logs"
        echo "  5) Exit"
        echo ""

        read -p "Select an option (1-5): " choice

        case $choice in
            1)
                if is_template_builder_running; then
                    echo -e "${YELLOW}Template Builder is already running${NC}"
                    read -p "Press Enter to continue..."
                else
                    start_template_builder
                    read -p "Press Enter to continue..."
                fi
                ;;
            2)
                configure_bundle
                ;;
            3)
                if is_template_builder_running; then
                    echo -e "${BLUE}Opening Template Builder in browser...${NC}"
                    if command -v xdg-open > /dev/null; then
                        xdg-open "$TEMPLATE_BUILDER_URL" 2>/dev/null || true
                    elif command -v open > /dev/null; then
                        open "$TEMPLATE_BUILDER_URL" 2>/dev/null || true
                    else
                        echo "Please open: $TEMPLATE_BUILDER_URL"
                    fi
                    read -p "Press Enter to continue..."
                else
                    echo -e "${RED}Template Builder is not running. Please start it first (option 1).${NC}"
                    read -p "Press Enter to continue..."
                fi
                ;;
            4)
                view_logs
                ;;
            5)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option. Please try again.${NC}"
                read -p "Press Enter to continue..."
                ;;
        esac
    done
}

# Configure and generate bundle
configure_bundle() {
    show_header

    if ! is_template_builder_running; then
        echo -e "${RED}Template Builder is not running. Please start it first.${NC}"
        read -p "Press Enter to continue..."
        return 1
    fi

    echo -e "${CYAN}Fetching available options...${NC}"
    local options_json
    options_json=$(fetch_options)

    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to fetch options${NC}"
        read -p "Press Enter to continue..."
        return 1
    fi

    echo ""
    echo "Configuration"
    echo "============="
    echo ""

    # Get project name
    read -p "Enter project name (default: my-template): " project_name
    project_name=${project_name:-my-template}

    # Get model profile
    echo ""
    echo "Select a model profile:"
    echo ""

    local profiles=()
    local profile_names=()
    local profile_descriptions=()

    if [ "$HAS_JQ" = true ]; then
        local idx=1
        # Parse model profiles
        while IFS= read -r profile_id; do
            profiles+=("$profile_id")
            profile_names+=("$(echo "$options_json" | jq -r ".modelProfiles[] | select(.id==\"$profile_id\") | .label")")
            profile_descriptions+=("$(echo "$options_json" | jq -r ".modelProfiles[] | select(.id==\"$profile_id\") | .description")")
            echo "  $idx) ${profile_names[$((idx-1))]} - ${profile_descriptions[$((idx-1))]}"
            ((idx++))
        done < <(echo "$options_json" | jq -r '.modelProfiles[].id')
    else
        # Fallback without jq
        echo "  1) code profile"
        echo "  2) research profile"
        profiles=("code" "research")
        profile_names=("Code" "Research")
        profile_descriptions=("Optimized for coding tasks" "Optimized for research tasks")
    fi

    echo ""
    read -p "Select profile (1-${#profiles[@]}, default: 1): " profile_choice
    profile_choice=${profile_choice:-1}

    if [ "$profile_choice" -ge 1 ] && [ "$profile_choice" -le ${#profiles[@]} ]; then
        profile="${profiles[$((profile_choice-1))]}"
    else
        profile="${profiles[0]}"
    fi

    # Get tools
    echo ""
    echo "Select orchestration tools (space-separated numbers, or 'all' for all):"
    echo ""

    local tools=()
    local tool_names=()
    local tool_descriptions=()
    local tool_defaults=()

    if [ "$HAS_JQ" = true ]; then
        local idx=1
        while IFS= read -r tool_id; do
            tools+=("$tool_id")
            tool_names+=("$(echo "$options_json" | jq -r ".tools[] | select(.id==\"$tool_id\") | .label")")
            tool_descriptions+=("$(echo "$options_json" | jq -r ".tools[] | select(.id==\"$tool_id\") | .description")")
            tool_defaults+=("$(echo "$options_json" | jq -r ".tools[] | select(.id==\"$tool_id\") | .defaultSelected")")
            local marker=""
            if [ "${tool_defaults[$((idx-1))]}" = "true" ]; then
                marker="${GREEN}[default]${NC}"
            fi
            echo "  $idx) ${tool_names[$((idx-1))]} - ${tool_descriptions[$((idx-1))]} $marker"
            ((idx++))
        done < <(echo "$options_json" | jq -r '.tools[].id')
    else
        # Fallback without jq
        echo "  1) codex - Codex orchestration"
        echo "  2) rag - RAG context system"
        tools=("codex" "rag")
        tool_names=("Codex" "RAG")
        tool_descriptions=("Codex orchestration" "RAG context system")
    fi

    echo ""
    read -p "Select tools (e.g., '1 2' or 'all', default: all): " tool_choice
    tool_choice=${tool_choice:-all}

    local selected_tools=()
    if [ "$tool_choice" = "all" ]; then
        selected_tools=("${tools[@]}")
    else
        for idx in $tool_choice; do
            if [ "$idx" -ge 1 ] && [ "$idx" -le ${#tools[@]} ]; then
                selected_tools+=("${tools[$((idx-1))]}")
            fi
        done
    fi

    if [ ${#selected_tools[@]} -eq 0 ]; then
        selected_tools=("${tools[@]}")
    fi

    # Get artifacts
    echo ""
    echo "Select bundle contents (space-separated numbers, or 'all' for all):"
    echo ""

    local artifacts=()
    local artifact_names=()
    local artifact_descriptions=()
    local artifact_defaults=()

    if [ "$HAS_JQ" = true ]; then
        local idx=1
        while IFS= read -r artifact_id; do
            artifacts+=("$artifact_id")
            artifact_names+=("$(echo "$options_json" | jq -r ".artifacts[] | select(.id==\"$artifact_id\") | .label")")
            artifact_descriptions+=("$(echo "$options_json" | jq -r ".artifacts[] | select(.id==\"$artifact_id\") | .description")")
            artifact_defaults+=("$(echo "$options_json" | jq -r ".artifacts[] | select(.id==\"$artifact_id\") | .defaultSelected")")
            local marker=""
            if [ "${artifact_defaults[$((idx-1))]}" = "true" ]; then
                marker="${GREEN}[default]${NC}"
            fi
            echo "  $idx) ${artifact_names[$((idx-1))]} - ${artifact_descriptions[$((idx-1))]} $marker"
            ((idx++))
        done < <(echo "$options_json" | jq -r '.artifacts[].id')
    else
        # Fallback without jq
        echo "  1) contracts - Contract definitions"
        echo "  2) agents - Agent manifests"
        artifacts=("contracts" "agents")
        artifact_names=("Contracts" "Agents")
        artifact_descriptions=("Contract definitions" "Agent manifests")
    fi

    echo ""
    read -p "Select artifacts (e.g., '1 2' or 'all', default: all): " artifact_choice
    artifact_choice=${artifact_choice:-all}

    local selected_artifacts=()
    if [ "$artifact_choice" = "all" ]; then
        selected_artifacts=("${artifacts[@]}")
    else
        for idx in $artifact_choice; do
            if [ "$idx" -ge 1 ] && [ "$idx" -le ${#artifacts[@]} ]; then
                selected_artifacts+=("${artifacts[$((idx-1))]}")
            fi
        done
    fi

    if [ ${#selected_artifacts[@]} -eq 0 ]; then
        selected_artifacts=("${artifacts[@]}")
    fi

    # Show summary
    echo ""
    echo -e "${CYAN}Configuration Summary:${NC}"
    echo "====================="
    echo "  Project: $project_name"
    echo "  Profile: $profile"
    echo "  Tools: ${selected_tools[*]}"
    echo "  Artifacts: ${selected_artifacts[*]}"
    echo ""

    read -p "Generate bundle? (Y/n): " confirm
    confirm=${confirm:-Y}

    if [[ $confirm =~ ^[Yy] ]] || [[ -z $confirm ]]; then
        generate_bundle "$project_name" "$profile" "${selected_tools[@]}" "${selected_artifacts[@]}"
    else
        echo "Cancelled."
        read -p "Press Enter to continue..."
    fi
}

# Generate bundle
generate_bundle() {
    local project_name="$1"
    shift
    local profile="$1"
    shift
    local tools=("$@")

    show_header
    echo -e "${CYAN}Generating bundle...${NC}"
    echo ""

    # Build tools array
    local tools_json="["
    for i in "${!tools[@]}"; do
        if [ $i -gt 0 ]; then
            tools_json+=","
        fi
        tools_json+="\"${tools[$i]}\""
    done
    tools_json+="]"

    # Build artifacts array (from remaining args or default)
    local artifacts_json="[\"contracts\", \"agents\"]"

    local payload
    payload=$(cat <<EOF
{
  "projectName": "$project_name",
  "profile": "$profile",
  "tools": $tools_json,
  "artifacts": $artifacts_json
}
EOF
)

    local output_file="${project_name}-bundle.zip"

    echo "Sending request to Template Builder..."
    echo ""
    echo "  Project: $project_name"
    echo "  Profile: $profile"
    echo "  Tools: ${tools[*]}"
    echo ""

    # Make the request
    local response_code
    response_code=$(curl -s -w "%{http_code}" -o "/tmp/bundle.zip" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$TEMPLATE_BUILDER_URL/api/generate" 2>/dev/null || echo "000")

    if [ "$response_code" = "200" ]; then
        if [ -f "/tmp/bundle.zip" ]; then
            mv "/tmp/bundle.zip" "$output_file"
            echo -e "${GREEN}✓ Bundle generated successfully: $output_file${NC}"
            echo ""
            echo "The bundle is ready to use. You can extract it with:"
            echo "  unzip $output_file"
            echo ""
            echo "This will create a project with:"
            echo "  - Next.js App Router setup"
            echo "  - Codex orchestration configuration"
            echo "  - RAG context system"
            echo "  - Template files and configs"
        else
            echo -e "${RED}✗ Bundle file not found${NC}"
        fi
    else
        echo -e "${RED}✗ Failed to generate bundle (HTTP $response_code)${NC}"
        echo ""
        echo "Check the logs (option 4 in main menu) for more details."
    fi

    read -p "Press Enter to continue..."
}

# View logs
view_logs() {
    show_header
    echo -e "${CYAN}Template Builder Logs${NC}"
    echo "==================="
    echo ""

    if [ -f "/tmp/template_builder.log" ]; then
        tail -n 50 /tmp/template_builder.log
    else
        echo "No logs available"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

# Check dependencies
check_dependencies() {
    local missing=()

    if ! command -v node > /dev/null; then
        missing+=("node")
    fi

    if ! command -v npm > /dev/null; then
        missing+=("npm")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${RED}Missing required dependencies:${NC}"
        for dep in "${missing[@]}"; do
            echo -e "  - $dep"
        done
        exit 1
    fi
}

# Main entry point
main() {
    check_dependencies

    # Check if already running
    if is_template_builder_running; then
        echo -e "${GREEN}Template Builder is already running at $TEMPLATE_BUILDER_URL${NC}"
    fi

    main_menu
}

main "$@"