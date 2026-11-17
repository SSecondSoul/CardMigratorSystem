from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use the application init-db command with an explicit bound connection")
context.configure(connection=connection)
with context.begin_transaction():
    context.run_migrations()
