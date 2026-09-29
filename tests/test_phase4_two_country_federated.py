"""
Phase 4 Verification Suite: Two-Country Federated Intelligence Layer.
Acceptance Criteria:
1. No raw data crosses nodes (test-enforced by NetworkEnvelope and DataLeakageSecurityViolation).
2. Federated >= Isolated on in-distribution data.
3. Federated > Isolated by measurable margin on novel-pattern outbreak transfer.
4. Secure aggregation protocol stub demonstrates exact mask cancellation.
5. Personalization separates shared representation from local prediction head.
"""
import pytest
import numpy as np
import torch
from ml.fl.model import DemandMLP
from ml.fl.client import FacilityFlowerClient
from ml.fl.server import FederatedCoordinator
from ml.fl.mtls_transport import NetworkEnvelope, DataLeakageSecurityViolation, SecureAggregationProtocolStub
from ml.fl.two_country_experiment import TwoCountryFLExperiment

def test_zero_raw_data_leakage_enforced():
    """
    CRITICAL ACCEPTANCE TEST:
    Asserts that NO raw personal health data, dispense records, or DataFrames
    can cross the client-aggregator boundary.
    """
    # 1. Valid parameter serialization works cleanly
    model = DemandMLP(input_dim=8)
    weights = model.get_weights()
    valid_metrics = {"train_loss": 0.35, "samples": 120}

    envelope = NetworkEnvelope.serialize_parameters(
        node_id="NODE_COUNTRY_A",
        round_id=1,
        parameters=weights,
        metrics=valid_metrics
    )
    assert envelope["protocol"] == "mTLS_v1.3_SecAgg_v1"
    assert envelope["num_tensors"] == len(weights)

    # 2. Deserialization reconstructs exact numerical tensors
    reconstructed, rec_metrics = NetworkEnvelope.deserialize_parameters(envelope)
    assert len(reconstructed) == len(weights)
    for orig, rec in zip(weights, reconstructed):
        np.testing.assert_allclose(orig, rec, rtol=1e-5)

    # 3. Attempting to transmit raw data or DataFrames raises DataLeakageSecurityViolation
    with pytest.raises(DataLeakageSecurityViolation):
        NetworkEnvelope.serialize_parameters(
            node_id="ROGUE_NODE",
            round_id=1,
            parameters=weights,
            metrics={"train_loss": 0.2, "patient_records": ["ID101", "ID102"]}
        )

    with pytest.raises(DataLeakageSecurityViolation):
        NetworkEnvelope.serialize_parameters(
            node_id="ROGUE_NODE",
            round_id=1,
            parameters=["RAW_STRING_NOT_NUMERIC_TENSOR"], # Non-numeric payload
            metrics={"train_loss": 0.2}
        )

def test_secure_aggregation_exact_mask_cancellation():
    """
    Verifies Bonawitz Secure Aggregation:
    Pairwise Diffie-Hellman masks cancel out to exactly zero upon aggregation.
    """
    client_ids = ["CLIENT_A", "CLIENT_B", "CLIENT_C"]
    sec_agg = SecureAggregationProtocolStub(client_ids=client_ids)

    base_weights = [np.ones((4, 4), dtype=np.float32), np.full((4,), 2.0, dtype=np.float32)]

    masked_a = sec_agg.mask_client_weights("CLIENT_A", base_weights)
    masked_b = sec_agg.mask_client_weights("CLIENT_B", base_weights)
    masked_c = sec_agg.mask_client_weights("CLIENT_C", base_weights)

    # Verify each client's individual payload is masked (scrambled)
    assert not np.allclose(masked_a[0], base_weights[0])
    assert not np.allclose(masked_b[0], base_weights[0])
    assert not np.allclose(masked_c[0], base_weights[0])

    # Aggregate across all 3 clients: sum(masked) must equal sum(unmasked) = 3 * base_weights
    sum_masked_0 = masked_a[0] + masked_b[0] + masked_c[0]
    sum_unmasked_0 = 3.0 * base_weights[0]
    np.testing.assert_allclose(sum_masked_0, sum_unmasked_0, rtol=1e-5)

def test_personalization_representation_sharing_with_local_heads():
    """
    Verifies Task 4.2:
    Shared feature-extractor is federated; per-country prediction head stays local.
    """
    # 2 clients with different input data
    X1 = np.random.normal(10, 2, (50, 8)).astype(np.float32)
    y1 = np.random.normal(15, 2, (50,)).astype(np.float32)
    X2 = np.random.normal(20, 4, (50, 8)).astype(np.float32)
    y2 = np.random.normal(30, 4, (50,)).astype(np.float32)

    c1 = FacilityFlowerClient("C1", X1, y1, X1[:10], y1[:10], personalized=True)
    c2 = FacilityFlowerClient("C2", X2, y2, X2[:10], y2[:10], personalized=True)

    # Initially randomize heads differently
    c1.model.head[0].weight.data.fill_(1.0)
    c2.model.head[0].weight.data.fill_(5.0)

    head1_initial = c1.model.get_head_weights()[0].copy()
    head2_initial = c2.model.get_head_weights()[0].copy()

    # Get feature weights (only representation)
    feat_weights_1 = c1.get_parameters()
    assert len(feat_weights_1) == 4 # 2 layers * (weight + bias)

    # Simulate server round dispatch
    c1.fit(feat_weights_1)
    c2.fit(feat_weights_1)

    # Verify local heads were NOT overwritten by global weights
    head1_after = c1.model.get_head_weights()[0]
    head2_after = c2.model.get_head_weights()[0]

    # Heads remain distinct and personalized to each client
    assert not np.allclose(head1_after, head2_after)

def test_killer_experiment_and_four_configurations():
    """
    CRITICAL ACCEPTANCE TEST (Tasks 4.1, 4.2, 4.3):
    1. Compares 4 configurations: (a) isolated, (b) FedAvg, (c) FedProx, (d) FedProx + personalization.
    2. Runs Killer Experiment: Federated knowledge transfer from Country A to Country B during novel outbreak.
    3. Asserts federated model beats isolated Country B by a measurable margin (> 10%).
    """
    experiment = TwoCountryFLExperiment(seed=123)
    results = experiment.run_full_ablation_and_killer_experiment()

    table = results["benchmark_table"]
    killer = results["killer_experiment"]

    # 1. Verify all 4 configurations are benchmarked
    configs = [row["Configuration"] for row in table]
    assert "(a) Isolated Local" in configs
    assert "(b) Naive FedAvg (mu=0)" in configs
    assert "(c) FedProx (mu=0.1)" in configs
    assert "(d) FedProx + Personalization" in configs

    # 2. Verify in-distribution: Federated models achieve competitive/superior performance over isolated
    iso_row = next(r for r in table if "(a)" in r["Configuration"])
    pers_row = next(r for r in table if "(d)" in r["Configuration"])
    assert pers_row["Average MAE"] < iso_row["Average MAE"], (
        f"FedProx + Personalization ({pers_row['Average MAE']}) must beat Isolated ({iso_row['Average MAE']})"
    )

    # 3. Verify Killer Experiment: Federated model beats isolated Country B on novel outbreak
    assert killer["hypothesis_verified"] is True
    assert killer["mae_improvement_pct"] >= 10.0, (
        f"Federated outbreak transfer improvement {killer['mae_improvement_pct']}% must exceed 10%"
    )
    assert killer["federated_country_b_mae"] < killer["isolated_country_b_mae"]
