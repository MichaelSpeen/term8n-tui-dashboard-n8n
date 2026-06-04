# term8n

A terminal UI dashboard for monitoring [n8n](https://n8n.io) workflow executions in real time. Built with [Textual](https://github.com/Textualize/textual).

Works with any standard n8n installation — no plugins or custom nodes required.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Textual](https://img.shields.io/badge/textual-0.80%2B-purple)

## Features

- **Live execution table** — running, waiting, and finished executions auto-refresh every few seconds; running jobs always appear at the top
- **Workflow sidebar** — filter the execution table by workflow with per-workflow execution counts
- **Stats bar** — at-a-glance totals (running, errors, today's count, average duration) with a sparkline of recent durations
- **Node timeline** — select any execution to see a proportional bar-chart timeline of every node that ran, colour-coded by success / error / zero-time
- **Live node progress** — when a running execution is selected, the timeline updates in real time via WebSocket push events; the active node is highlighted and completed nodes appear with their timings as they finish (requires `N8N_EMAIL` + `N8N_PASSWORD`)
- **Node detail modal** — click or press Enter on a timeline node to inspect its full JSON output with syntax highlighting
- **Canvas diagram** — press `w` to open a full-screen ASCII diagram of the selected workflow's node layout, with colour-coded node types and arrows including backward/loop connections
- **Flow diagram** — press `t` to open a compact top-down topological flow view of the same workflow; depth is computed via longest-path so parallel branches are laid out correctly
- **System stats bar** — live CPU, RAM, disk free space, API key status, and WebSocket credentials status in the footer

## Installation

```bash
git clone https://github.com/MichaelSpeen/term8n-tui-dashboard-n8n.git
cd term8n-tui-dashboard-n8n
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_api_key_here
N8N_POLL_INTERVAL=3.0
N8N_MAX_EXECUTIONS=50

# Optional — enables real-time node progress via WebSocket push events
N8N_EMAIL=your@email.com
N8N_PASSWORD=your_password
```

Create an API key at: **n8n Settings → n8n API → Create API key**

### Real-time node progress

By default term8n polls the REST API on an interval. Because n8n only persists execution data after a workflow completes, the node timeline for a running execution shows the workflow's node structure as a plan.

When `N8N_EMAIL` and `N8N_PASSWORD` are set, term8n additionally:

1. Logs in to obtain a session cookie
2. Connects to n8n's WebSocket push endpoint (`/rest/push`)
3. Receives `nodeExecuteBefore` / `nodeExecuteAfter` events in real time

The timeline then updates node-by-node as each one starts and finishes, with live timing bars and the active node name shown in the header. The footer shows **credentials OK** (green) once the WebSocket is live, or **credentials ERROR** (red) if login fails.

## Usage

```bash
term8n
```

### Key bindings

| Key | Action |
|-----|--------|
| `r` | Force refresh |
| `w` | Open canvas diagram for selected workflow |
| `t` | Open top-down flow diagram for selected workflow |
| `↑ / ↓` | Navigate executions / nodes |
| `Enter` | Open node detail modal |
| `Escape` | Close modal / clear selection |
| `q` | Quit |

## Planned features

The following interactions are common in the n8n web UI and are candidates for future implementation in term8n. All are supported by n8n's public REST API.

### Execution management
- **Manual trigger** — run a workflow on demand (`POST /api/v1/workflows/{id}/run`)
- **Retry failed execution** — re-run a specific failed execution
- **Delete execution** — remove one or all executions for a workflow

### Workflow control
- **Toggle active / inactive** — enable or disable a workflow without leaving the terminal
- **Bulk activate / deactivate** — toggle multiple workflows at once
- **Search / filter by name or tag**

### Monitoring
- **Error-only view** — filter the execution table to failures only
- **Execution statistics** — success rate, average duration, trend over time

### Credentials & settings
- **Credential health check** — test whether stored credentials are still valid
- **Global variables viewer** — read n8n instance variables
- **Worker / queue status** — concurrency and queue depth for scaled deployments

## Requirements

- Python 3.10+
- n8n instance with REST API enabled (any version with `/api/v1` support)
