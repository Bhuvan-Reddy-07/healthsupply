"""0002_add_quarantine_and_sensor_hypertables

Revision ID: 0002_add_quarantine_and_sensor_hypertables
Revises: 0001_initial_schema
Create Date: 2026-09-29 21:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_add_quarantine_and_sensor_hypertables'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. quarantined_events
    op.create_table(
        'quarantined_events',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('subject', sa.String(length=64), nullable=False, index=True),
        sa.Column('source', sa.String(length=32), nullable=False, index=True),
        sa.Column('raw_payload', sa.Text(), nullable=False),
        sa.Column('reason_code', sa.String(length=64), nullable=False, index=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('quarantined_at', sa.DateTime(), nullable=False, index=True)
    )

    # 2. sensor_temp
    op.create_table(
        'sensor_temp',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('batch_id', sa.String(length=64), sa.ForeignKey('stock_batches.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('device_id', sa.String(length=64), nullable=False, index=True),
        sa.Column('temperature_c', sa.Float(), nullable=False),
        sa.Column('is_breached', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('data_quality_score', sa.Float(), nullable=False, default=1.0),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 3. TimescaleDB hypertables conversion (conditional on Postgres engine with Timescale)
    bind = op.get_bind()
    if bind.engine.name == 'postgresql':
        try:
            bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            bind.execute(sa.text("SELECT create_hypertable('stock_transactions', 'tx_timestamp', if_not_exists => TRUE);"))
            bind.execute(sa.text("SELECT create_hypertable('bed_states', 'timestamp', if_not_exists => TRUE);"))
            bind.execute(sa.text("SELECT create_hypertable('sensor_temp', 'timestamp', if_not_exists => TRUE);"))
        except Exception as e:
            print(f"Timescale hypertable setup notice: {e}")

def downgrade() -> None:
    op.drop_table('sensor_temp')
    op.drop_table('quarantined_events')
