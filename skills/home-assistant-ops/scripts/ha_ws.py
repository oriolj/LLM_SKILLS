#!/usr/bin/env python3
# Minimal HA WebSocket client: each CLI arg is one JSON command, result printed as JSON.
# Needs HA_URL/HA_TOKEN in the env. Run without installing anything:
#   set -a; source .env; set +a; uv run --quiet --with websockets python scripts/ha_ws.py '{"type":"repairs/list_issues"}'
# Other useful commands: config/entity_registry/get|update, config_entries/get, repairs/list_issues.
import json, os, sys, asyncio, websockets
async def main():
    url = os.environ["HA_URL"].replace("http","ws")+"/api/websocket"
    async with websockets.connect(url, max_size=None) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type":"auth","access_token":os.environ["HA_TOKEN"]}))
        print(json.loads(await ws.recv())["type"], file=sys.stderr)
        i=1
        for t in sys.argv[1:]:
            i+=1; msg=json.loads(t); msg["id"]=i
            await ws.send(json.dumps(msg))
            r=json.loads(await ws.recv())
            print(json.dumps(r.get("result"), indent=1))
asyncio.run(main())
