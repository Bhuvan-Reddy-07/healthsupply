"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-28 22:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. facilities
    op.create_table(
        'facilities',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('country', sa.String(length=64), nullable=False, index=True),
        sa.Column('region', sa.String(length=128), nullable=False),
        sa.Column('district', sa.String(length=128), nullable=False, index=True),
        sa.Column('tier', sa.String(length=32), nullable=False, index=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('has_cold_chain', sa.Boolean(), nullable=False, default=False),
        sa.Column('cold_chain_capacity_liters', sa.Float(), default=0.0),
        sa.Column('population_served', sa.Integer(), default=10000),
        sa.Column('contact_phone', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. items
    op.create_table(
        'items',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False, index=True),
        sa.Column('dosage_form', sa.String(length=64), nullable=False),
        sa.Column('unit_of_measure', sa.String(length=32), nullable=False),
        sa.Column('velocity_class', sa.String(length=32), nullable=False, index=True),
        sa.Column('requires_cold_chain', sa.Boolean(), nullable=False, index=True, default=False),
        sa.Column('temp_min_c', sa.Float(), nullable=True),
        sa.Column('temp_max_c', sa.Float(), nullable=True),
        sa.Column('unit_cost_usd', sa.Float(), nullable=False, default=1.0),
        sa.Column('shelf_life_days', sa.Integer(), nullable=False, default=730),
        sa.Column('criticality_tier', sa.String(length=16), nullable=False, default='B'),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 3. stock_batches
    op.create_table(
        'stock_batches',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('batch_number', sa.String(length=64), nullable=False, index=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('current_quantity', sa.Float(), nullable=False, default=0.0),
        sa.Column('initial_quantity', sa.Float(), nullable=False, default=0.0),
        sa.Column('mfg_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False, index=True),
        sa.Column('gs1_gtin', sa.String(length=32), nullable=False, index=True),
        sa.Column('qr_data_matrix', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, default='active', index=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('current_quantity >= 0', name='chk_stock_quantity_non_negative'),
        sa.CheckConstraint('expiry_date >= mfg_date', name='chk_expiry_after_mfg')
    )

    # 4. stock_transactions
    op.create_table(
        'stock_transactions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('crdt_tx_id', sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('batch_id', sa.String(length=64), sa.ForeignKey('stock_batches.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('tx_type', sa.String(length=32), nullable=False, index=True),
        sa.Column('quantity', sa.Float(), nullable=False, default=0.0),
        sa.Column('censored', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('unfulfilled_quantity', sa.Float(), nullable=False, default=0.0),
        sa.Column('tx_timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('source', sa.String(length=32), nullable=False, default='edge_pwa'),
        sa.Column('source_reliability_score', sa.Float(), nullable=False, default=1.0),
        sa.Column('data_quality_score', sa.Float(), nullable=False, default=1.0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('quantity >= 0', name='chk_tx_quantity_non_negative')
    )

    # 5. bed_states
    op.create_table(
        'bed_states',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('total_beds', sa.Integer(), nullable=False, default=10),
        sa.Column('occupied_beds', sa.Integer(), nullable=False, default=0),
        sa.Column('icu_occupied', sa.Integer(), default=0),
        sa.Column('pediatric_occupied', sa.Integer(), default=0),
        sa.Column('maternity_occupied', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 6. staff_attendance
    op.create_table(
        'staff_attendance',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('date', sa.Date(), nullable=False, index=True),
        sa.Column('doctors_present', sa.Integer(), nullable=False, default=1),
        sa.Column('nurses_present', sa.Integer(), nullable=False, default=2),
        sa.Column('pharmacists_present', sa.Integer(), nullable=False, default=1),
        sa.Column('shift', sa.String(length=16), nullable=False, default='day'),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 7. forecasts
    op.create_table(
        'forecasts',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('forecast_date', sa.Date(), nullable=False, index=True),
        sa.Column('model_version', sa.String(length=64), nullable=False),
        sa.Column('p10', sa.Float(), nullable=False),
        sa.Column('p50', sa.Float(), nullable=False),
        sa.Column('p90', sa.Float(), nullable=False),
        sa.Column('reconciled_p50', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 8. alerts
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('alert_type', sa.String(length=64), nullable=False, index=True),
        sa.Column('severity', sa.String(length=16), nullable=False, index=True),
        sa.Column('days_remaining', sa.Float(), nullable=True),
        sa.Column('p_stockout_before_lead', sa.Float(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 9. transfer_proposals
    op.create_table(
        'transfer_proposals',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('donor_facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('recipient_facility_id', sa.String(length=64), sa.ForeignKey('facilities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('batch_id', sa.String(length=64), sa.ForeignKey('stock_batches.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('donor_cover_days_before', sa.Float(), nullable=False),
        sa.Column('donor_cover_days_after', sa.Float(), nullable=False),
        sa.Column('recipient_cover_days_before', sa.Float(), nullable=False),
        sa.Column('recipient_cover_days_after', sa.Float(), nullable=False),
        sa.Column('eta_days', sa.Float(), nullable=False, default=1.0),
        sa.Column('cold_chain_required', sa.Boolean(), nullable=False, default=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default='proposed', index=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.String(length=64), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 10. audit_log
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('table_name', sa.String(length=64), nullable=False, index=True),
        sa.Column('record_id', sa.String(length=64), nullable=False, index=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('actor', sa.String(length=128), nullable=False, default='system'),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('previous_state', sa.Text(), nullable=True),
        sa.Column('new_state', sa.Text(), nullable=True),
        sa.Column('previous_hash', sa.String(length=64), nullable=False, default='GENESIS'),
        sa.Column('tamper_hash', sa.String(length=64), nullable=False)
    )


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('transfer_proposals')
    op.drop_table('alerts')
    op.drop_table('forecasts')
    op.drop_table('staff_attendance')
    op.drop_table('bed_states')
    op.drop_table('stock_transactions')
    op.drop_table('stock_batches')
    op.drop_table('items')
    op.drop_table('facilities')
