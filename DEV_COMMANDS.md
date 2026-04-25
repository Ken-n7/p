# EFP Supply Chain — Dev Command Reference

## Start / Stop

```bash
# Start all services (app + MySQL + phpMyAdmin)
docker compose up

# Start in background
docker compose up -d

# Stop all services
docker compose down

# Stop and wipe volumes (destroys database data)
docker compose down -v

# Rebuild image (after Dockerfile or requirements changes)
docker compose up --build
```

---

## URLs

| Service | URL |
|---|---|
| App | http://localhost:8000 |
| phpMyAdmin | http://localhost:8080 |
| Admin panel | http://localhost:8000/admin |

---

## Django Management

```bash
# Run migrations
docker exec supply-chain-match-web-1 python manage.py migrate

# Create new migrations after model changes
docker exec supply-chain-match-web-1 python manage.py makemigrations inventory

# Create superuser
docker exec -it supply-chain-match-web-1 python manage.py createsuperuser

# System check (catches config errors)
docker exec supply-chain-match-web-1 python manage.py check

# Open Django shell
docker exec -it supply-chain-match-web-1 python manage.py shell
```

---

## Seed & Reset Data

```bash
# Seed database with sample products, movements, users, reconciliation records
docker exec supply-chain-match-web-1 python manage.py seed_data

# Seed users (demo credentials after seeding):
#   warehouse_staff / efp2025
#   sales_rep       / efp2025
#   accountant      / efp2025
#   admin_user      / efp2025
```

```bash
# Clear ALL data (products, movements, reconciliation, audit log, non-superusers)
# and start fresh — then re-seed
docker exec supply-chain-match-web-1 python manage.py shell -c "
from inventory.models import Product, InventoryMovement, RetailerSales, AuditLog
from django.contrib.auth.models import User
AuditLog.objects.all().delete()
RetailerSales.objects.all().delete()
InventoryMovement.objects.all().delete()
Product.objects.all().delete()
User.objects.filter(is_superuser=False).delete()
print('Cleared.')
"

# Then re-seed:
docker exec supply-chain-match-web-1 python manage.py seed_data
```

```bash
# Clear only audit log
docker exec supply-chain-match-web-1 python manage.py shell -c "
from inventory.models import AuditLog; AuditLog.objects.all().delete(); print('Audit log cleared.')
"

# Clear only reconciliation records
docker exec supply-chain-match-web-1 python manage.py shell -c "
from inventory.models import RetailerSales; RetailerSales.objects.all().delete(); print('Reconciliation cleared.')
"

# Clear only movements
docker exec supply-chain-match-web-1 python manage.py shell -c "
from inventory.models import InventoryMovement; InventoryMovement.objects.all().delete(); print('Movements cleared.')
"
```

---

## Completely Fresh Start

```bash
# Nuclear option — destroys DB volume and rebuilds from scratch
docker compose down -v
docker compose up -d
docker exec supply-chain-match-web-1 python manage.py migrate
docker exec -it supply-chain-match-web-1 python manage.py createsuperuser
docker exec supply-chain-match-web-1 python manage.py seed_data
```

---

## Logs & Debugging

```bash
# View live app logs
docker compose logs -f web

# View all service logs
docker compose logs -f

# Check running containers
docker ps

# Get a shell inside the container
docker exec -it supply-chain-match-web-1 bash
```

---

## Database (MySQL via phpMyAdmin)

- URL: http://localhost:8080
- Server: `db`
- Username: `root`
- Password: check `docker-compose.yml` → `MYSQL_ROOT_PASSWORD`

---

## Migrations Quick Reference

```bash
# Full workflow after a model change:
docker exec supply-chain-match-web-1 python manage.py makemigrations inventory
docker exec supply-chain-match-web-1 python manage.py migrate

# Show migration status
docker exec supply-chain-match-web-1 python manage.py showmigrations inventory

# Roll back last migration
docker exec supply-chain-match-web-1 python manage.py migrate inventory <previous_migration_name>
```

---

## Git Branches

| Branch | Purpose |
|---|---|
| `main` | Stable demo — delivered to client (2k budget) |
| `enhanced` | Enhanced version with modern UI, Chart.js, CSV export, user deactivate/delete — for upsell |
