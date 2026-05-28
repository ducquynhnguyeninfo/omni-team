---
description: Start the full dev stack (backend + frontend + database)
---

Bring up the local development environment:

```bash
docker compose -f infra-dev/docker-compose.yaml up -d
echo "⏳ Waiting for services to be ready..."
sleep 5
echo "✅ Stack started"
echo "   Backend:  {{backend.dev_url}}"
echo "   Frontend: {{frontend.dev_url}}"
```

Then verify health:

```bash
curl -s {{backend.health_url}} | jq .
```

To stop: `docker compose -f infra-dev/docker-compose.yaml down`

To see logs: `docker compose -f infra-dev/docker-compose.yaml logs -f [service]`
