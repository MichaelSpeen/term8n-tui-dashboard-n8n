import asyncio
from term8n.config import Config
from term8n.api import N8NClient


async def main():
    cfg = Config.from_env()
    client = N8NClient(cfg)
    print(f"Connecting to: {cfg.base_url}")

    ok = await client.check_connection()
    print(f"Health check: {'OK' if ok else 'FAILED'}")

    if ok:
        wfs = await client.get_workflows()
        print(f"\nWorkflows ({len(wfs)} total):")
        for w in wfs[:8]:
            print(f"  {'●' if w.active else ' '} [{w.id}] {w.name}")

        execs = await client.get_executions(limit=5)
        print(f"\nRecent executions ({len(execs)}):")
        for e in execs:
            print(f"  {e.status:10}  {e.workflow_name[:40]}")
    else:
        print("Cannot reach n8n — check N8N_BASE_URL and that n8n is running")

    await client.aclose()


asyncio.run(main())
