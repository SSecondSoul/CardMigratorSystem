"""Bounded, verified row transfer for backups/restores; never overwrite rows.

Callers own both transactions and the application transaction mutex. Files and
LangGraph checkpoints are managed by backup.py, not by this relational copier.
"""
from dataclasses import replace
from hashlib import sha256
import json
from types import SimpleNamespace

from sqlalchemy import JSON, MetaData, inspect, select, text

from .database import HEAD, _upgrade, engine_for


MAX_TRANSFER_BYTES = 256 * 1024 * 1024
MAX_TRANSFER_ROWS = 1_000_000
SQL_NULL_JSON = object()


def _snapshot(project):
    path = project / 'docs/deployment/mysql_handoff_v2/schema_multi_user.json'
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    if snapshot['schema_basis'] != HEAD or snapshot['table_count'] != 34:
        raise ValueError('portable_database_schema_not_reviewed')
    return {table['name']: table for table in snapshot['tables']}


def _reflect(connection, expected):
    if set(inspect(connection).get_table_names()) != set(expected):
        raise ValueError('portable_database_table_inventory_mismatch')
    if connection.dialect.name == 'mysql':
        # Do not assume all tables still use InnoDB merely because init-db once
        # passed; otherwise a "rollback" might leave partially imported rows.
        from .mysql_connection import inspect_schema
        name = connection.execute(text('SELECT DATABASE()')).scalar_one()
        with connection.connection.driver_connection.cursor() as cursor:
            structure = inspect_schema(cursor, SimpleNamespace(name=name), {'tables': list(expected.values())})
        if structure['differences_total']:
            raise ValueError('portable_database_mysql_schema_mismatch')
    metadata = MetaData()
    metadata.reflect(bind=connection)
    for name, definition in expected.items():
        if [column.name for column in metadata.tables[name].columns] != [column['name'] for column in definition['columns']]:
            raise ValueError('portable_database_column_inventory_mismatch')
    versions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    if versions != [HEAD]:
        raise ValueError('portable_database_version_mismatch')
    return metadata


def _normalize(row, definition):
    result = {column['name']: row[column['name']] for column in definition['columns']}
    for column in definition['columns']:
        value = result[column['name']]
        kind = column['mysql_type']
        if kind == 'JSON' and value is None:
            # SQL NULL and the JSON document null deserialize to the same Python
            # value. Preserve the independently selected SQL IS NULL evidence.
            if row['__cardmig_sql_null_' + column['name']]:
                if not column['nullable']:
                    raise ValueError('portable_database_unexpected_null')
                result[column['name']] = SQL_NULL_JSON
        elif value is None:
            if not column['nullable']:
                raise ValueError('portable_database_unexpected_null')
        elif kind == 'BOOLEAN':
            if value not in (True, False, 0, 1):
                raise ValueError('portable_database_invalid_boolean')
            result[column['name']] = bool(value)
        elif kind == 'DOUBLE':
            result[column['name']] = float(value)
        elif kind.startswith('VARCHAR('):
            limit = int(kind.removeprefix('VARCHAR(').removesuffix(')'))
            if type(value) is not str or len(value) > limit:
                raise ValueError('portable_database_string_does_not_fit')
    return result


def _encoded(row):
    try:
        envelope = {'values': {key: None if value is SQL_NULL_JSON else value for key, value in row.items()},
                    'sql_null_json': sorted(key for key, value in row.items() if value is SQL_NULL_JSON)}
        return json.dumps(envelope, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        raise ValueError('portable_database_value_not_serializable') from None


def _parent_first(rows, table):
    """Respect self-referencing FKs without disabling constraints in MySQL."""
    dependencies = [fk for fk in table.foreign_key_constraints if fk.referred_table is table]
    if not dependencies:
        return rows
    indexes = {}
    for fk in dependencies:
        columns = tuple(element.column.name for element in fk.elements)
        indexes[columns] = {tuple(row[name] for name in columns): index for index, row in enumerate(rows)}
    parents = [set() for _ in rows]
    children = [set() for _ in rows]
    for index, row in enumerate(rows):
        for fk in dependencies:
            source = tuple(row[element.parent.name] for element in fk.elements)
            if any(value is None for value in source):
                continue
            target = tuple(element.column.name for element in fk.elements)
            parent = indexes[target].get(source)
            if parent is None:
                raise ValueError('portable_database_missing_self_reference')
            if parent == index:
                continue  # MySQL permits a row to reference itself on INSERT.
            parents[index].add(parent);children[parent].add(index)
    ready = [index for index, deps in enumerate(parents) if not deps]
    ordered = []
    while ready:
        index = ready.pop()
        ordered.append(rows[index])
        for child in children[index]:
            parents[child].discard(index)
            if not parents[child]:
                ready.append(child)
    if len(ordered) != len(rows):
        raise ValueError('portable_database_cyclic_self_reference')
    return ordered


def _rows(connection, table, definition):
    ordering = [table.c[name] for name in definition['primary_key']]
    return [_normalize(row, definition) for row in connection.execute(_select_rows(table, definition).order_by(*ordering)).mappings()]


def _select_rows(table, definition):
    flags = [table.c[column['name']].is_(None).label('__cardmig_sql_null_' + column['name'])
             for column in definition['columns'] if column['mysql_type'] == 'JSON']
    return select(table, *flags)


def _bind_row(row, definition):
    result = dict(row)
    for column in definition['columns']:
        if column['mysql_type'] == 'JSON':
            value = result[column['name']]
            result[column['name']] = None if value is SQL_NULL_JSON else JSON.NULL if value is None else value
    return result


def _digest(rows, definition):
    primary = definition['primary_key']
    ordered = sorted(rows, key=lambda row: tuple(row[name] for name in primary))
    fingerprint = sha256()
    for row in ordered:
        encoded = _encoded(row)
        fingerprint.update(len(encoded).to_bytes(8, 'big'));fingerprint.update(encoded)
    return fingerprint.hexdigest()


def copy_business_rows(source, destination, project, *, max_bytes=MAX_TRANSFER_BYTES, max_rows=MAX_TRANSFER_ROWS):
    """Copy to initialized empty tables; caller commits only after verification.

    Never insert/delete Alembic versions here, disable FKs, truncate data, commit
    the caller's transaction, reconnect, or retry an outcome-unknown operation.
    """
    expected = _snapshot(project)
    origin = _reflect(source, expected)
    target = _reflect(destination, expected)
    for table in target.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSON):
                column.type.none_as_null = True
    for name in expected:
        if name != 'alembic_version' and destination.execute(select(target.tables[name]).limit(1)).first():
            raise ValueError('portable_database_destination_not_empty')
    inventory = {};total_bytes=0;total_rows=0
    for table in origin.sorted_tables:
        name = table.name
        if name == 'alembic_version':
            continue
        definition = expected[name]
        rows = []
        ordering = [table.c[key] for key in definition['primary_key']]
        for row in source.execute(_select_rows(table, definition).order_by(*ordering)).mappings():
            row = _normalize(row, definition)
            total_bytes += len(_encoded(row));total_rows += 1
            if total_bytes > max_bytes or total_rows > max_rows:
                raise ValueError('portable_database_transfer_limit_exceeded')
            rows.append(row)
        wanted = _digest(rows, definition)
        ordered = _parent_first(rows, table)
        # Keep batches bounded even when reports contain large JSON documents.
        batch = [];batch_bytes = 0
        for row in ordered:
            size = len(_encoded(row))
            if batch and (len(batch) >= 100 or batch_bytes + size > 256 * 1024):
                destination.execute(target.tables[name].insert(), batch)
                batch = [];batch_bytes = 0
            batch.append(_bind_row(row, definition));batch_bytes += size
        if batch:
            destination.execute(target.tables[name].insert(), batch)
        actual = _rows(destination, target.tables[name], definition)
        if len(actual) != len(rows) or _digest(actual, definition) != wanted:
            raise ValueError('portable_database_roundtrip_mismatch')
        inventory[name] = {'rows': len(rows), 'sha256': wanted}
    return {'tables': inventory, 'rows': total_rows, 'encoded_bytes': total_bytes}


def snapshot_to_sqlite(settings, source_session, destination):
    """Create the existing portable archive format from a locked MySQL session."""
    if destination.name != 'business.sqlite3':
        raise ValueError('portable_database_snapshot_filename_invalid')
    if destination.exists() or destination.is_symlink():
        raise ValueError('portable_database_snapshot_destination_exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    local = replace(settings, database_backend='sqlite', mysql_connection_file=None,
                    runtime_dir=destination.parent)
    _upgrade(local)
    target = engine_for(destination)
    try:
        with target.begin() as connection:
            return copy_business_rows(source_session.connection(), connection, settings.project_root)
    finally:
        target.dispose()
