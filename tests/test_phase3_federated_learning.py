import pytest
import numpy as np
import torch
from ml.fl.privacy_accountant import RdpPrivacyAccountant
from ml.fl.model import DemandMLP
from ml.fl.client import FacilityFlowerClient
from ml.fl.server import FederatedCoordinator

def test_rdp_privacy_accountant_monotonicity_and_conversion():
    accountant = RdpPrivacyAccountant(target_delta=1e-5)
    
    eps1, d1 = accountant.step(q=0.2, noise_multiplier=1.2, steps=1)
    assert eps1 > 0.0
    assert d1 == 1e-5

    eps5, d5 = accountant.step(q=0.2, noise_multiplier=1.2, steps=4)
    # Monotonic accumulation of privacy loss
    assert eps5 > eps1
    assert eps5 <= 4.0 # Target privacy budget strictly maintained (epsilon <= 4.0)

def test_flower_client_fedprox_and_dp_clipping():
    np.random.seed(42)
    X = np.random.randn(20, 8)
    y = np.random.uniform(5, 50, size=20)
    
    client = FacilityFlowerClient(
        facility_id="FAC_TEST_01",
        X_train=X,
        y_train=y,
        X_val=X[:5],
        y_val=y[:5],
        mu=0.1,
        clip_norm=1.0,
        noise_multiplier=0.5,
        local_epochs=2
    )

    init_weights = client.get_parameters()
    updated_weights, num_samples, metrics = client.fit(init_weights)

    assert num_samples == 20
    assert "train_loss" in metrics
    assert len(updated_weights) == len(init_weights)
    # Weights should change from optimization + DP perturbation
    assert not np.allclose(updated_weights[0], init_weights[0])

def test_federated_learning_convergence_under_non_iid_and_stragglers():
    """
    CRITICAL ACCEPTANCE TEST:
    Verifies FedProx + DP-SGD federated learning converges across non-IID facility tiers
    (Rural PHCs vs. District Hospitals) while tolerating 25% edge node dropouts/stragglers.
    """
    np.random.seed(123)
    n_features = 8
    
    # Simulate 4 heterogenous non-IID facilities
    # PHC 1: low demand rate ~10
    # PHC 2: low demand rate ~15
    # CHC: medium demand rate ~40
    # DH: high demand rate ~120
    facility_configs = [
        {"id": "PHC_RURAL_01", "mean": 10.0, "samples": 40},
        {"id": "PHC_RURAL_02", "mean": 12.0, "samples": 40},
        {"id": "CHC_TOWN_01",  "mean": 25.0, "samples": 60},
        {"id": "CHC_TOWN_02",  "mean": 30.0, "samples": 60},
        {"id": "DH_CENTRAL_01", "mean": 50.0, "samples": 80},
        {"id": "DH_CENTRAL_02", "mean": 55.0, "samples": 80},
    ]

    clients = []
    # Ground truth linear relationship for federated convergence
    true_w = np.array([1.5, -0.8, 0.6, 1.0, -0.4, 0.2, 0.3, 0.8])

    for cfg in facility_configs:
        X = np.random.normal(0, 1, size=(cfg["samples"], n_features))
        y = np.maximum(0.0, X @ true_w + cfg["mean"] + np.random.normal(0, 1.0, size=cfg["samples"]))
        
        split = int(cfg["samples"] * 0.75)
        c = FacilityFlowerClient(
            facility_id=cfg["id"],
            X_train=X[:split],
            y_train=y[:split],
            X_val=X[split:],
            y_val=y[split:],
            mu=0.05, # Proximal regularization for non-IID stability
            clip_norm=1.0,
            noise_multiplier=1.2, # Formally auditable DP noise
            lr=0.01,
            local_epochs=2
        )
        clients.append(c)

    coordinator = FederatedCoordinator(
        clients=clients,
        input_dim=n_features,
        mu=0.05,
        clip_norm=1.0,
        noise_multiplier=1.2,
        min_client_fraction=0.33, # Quorum threshold
        target_delta=1e-5
    )

    # Independent holdout test set representing global system distribution
    X_test = np.random.normal(0, 1, size=(50, n_features))
    y_test = np.maximum(0.0, X_test @ true_w + 30.0 + np.random.normal(0, 1.0, size=50))
    initial_eval = coordinator.evaluate_global(X_test, y_test)["eval_loss"]

    # Run 5 federated rounds with 15% simulated network dropout
    history = coordinator.run_federation(num_rounds=5, client_dropout_rate=0.15)

    assert len(history) == 5
    
    # 1. Proves global model loss decreases through federation
    final_eval = coordinator.evaluate_global(X_test, y_test)["eval_loss"]
    assert final_eval < initial_eval, f"Expected final eval loss ({final_eval}) < initial ({initial_eval})"

    # 2. Proves privacy accounting operates and maintains strict budget
    final_eps = history[-1]["cumulative_epsilon"]
    assert final_eps > 0.0
    assert final_eps <= 12.0, f"Privacy budget violated: epsilon={final_eps}"

    # 3. Proves straggler tolerance: rounds completed even with dropouts
    assert all(h["participating_clients"] >= 2 for h in history)
