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
- **Node detail modal** — click or press Enter on a timeline node to inspect its full JSON output with syntax highlighting
- **Workflow diagram** — press `w` to open a full-screen ASCII diagram of the selected workflow's node layout, with colour-coded node types and arrows (including backward/loop connections)
- **System stats bar** — live CPU and RAM usage shown in the footer

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
```

Create an API key at: **n8n Settings → n8n API → Create API key**

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
- **Live node progress** — watch a running execution update node by node
- **Execution statistics** — success rate, average duration, trend over time

### Credentials & settings
- **Credential health check** — test whether stored credentials are still valid
- **Global variables viewer** — read n8n instance variables
- **Worker / queue status** — concurrency and queue depth for scaled deployments

## Requirements

- Python 3.10+
- n8n instance with REST API enabled (any version with `/api/v1` support)
