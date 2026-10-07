---
name: "source-command-stack-up"
description: "Start the full dev stack (backend + frontend + database)"
---

# source-command-stack-up

Use this skill when the user asks to run the migrated source command `stack-up`.

## Command Template

Bring up the local development environment:

```bash
docker compose -f infra-dev/docker-compose.yaml up -d
echo "⏳ Waiting for services to be ready..."
sleep 5
echo "✅ Stack started"
echo "   Backend:  http://localhost:3000"
echo "   Frontend: "
```

Then verify health:

```bash
curl -s http://localhost:3000/health | jq .
```

To stop: `docker compose -f infra-dev/docker-compose.yaml down`

To see logs: `docker compose -f infra-dev/docker-compose.yaml logs -f [service]`
