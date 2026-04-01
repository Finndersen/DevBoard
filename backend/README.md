# DevBoard Backend

FastAPI backend for the DevBoard developer command centre application.

## Development

Install dependencies:
```bash
make install
```

Run the application:
```bash
make start
```

Update lock file for newly added/updated dependencies:
```bash
make lock
```

## Code Quality

Fix formatting/lint issues and run type checking:
```bash
make lint          # auto-fix formatting and lint issues with ruff
make typecheck     # type-check with pyright (slow — run separately)
make validate      # run lint + typecheck together
```

## Database

Run migrations:
```bash
make migrate
```

Generate new migration:
```bash
make migrate-auto
```

## Testing

Run tests:
```bash
make test
```

## Available Commands

Run `make help` to see all available commands.