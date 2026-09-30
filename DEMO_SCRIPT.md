# HealthSupply: 3-Minute Live Presentation Script & Demonstration Walkthrough

**Target Audience:** Hackathon Judges, Technical Reviewers, Global Health System Architects  
**Demonstration Runtime:** ~3 minutes  
**Execution Time of Automated Engine:** 0.78–0.93 seconds (`make demo` or `python -m demo.runner`)  
**Live UI:** `http://localhost:8000/dashboard/`

---

## ⏱️ Timeline & Presentation Flow

```
[0:00 - 0:35]  HOOK & PROBLEM: Healthcare Supply Chain Fragility in Resource-Constrained Clinics
[0:35 - 1:15]  ACT I: OUTBREAK INJECTION & SUB-SECOND CUSUM SURVEILLANCE
[1:15 - 1:55]  ACT II: PROACTIVE REDISTRIBUTION & HITL AUDIT TRAIL
[1:55 - 2:35]  ACT III: THE KILLER EXPERIMENT — CROSS-BORDER KNOWLEDGE TRANSFER
[2:35 - 3:00]  ACT IV: COUNTERFACTUAL IMPACT & CONCLUSION
```

---

## Act-by-Act Speaking Points & Actions

### 0:00 – 0:35 | Hook & Core Problem
> **Presenter:**
> *"Every year, millions of preventable maternal deaths and malaria complications occur not because medicines don't exist in a country, but because they are in the wrong place at the wrong time.*
>
> *Centralized healthcare supply chains suffer from three fatal flaws:*
> 1. *Districts run blind: rural Primary Health Centres (PHCs) lose power and connectivity, and stockouts artificially censor true patient demand.*
> 2. *Privacy laws strictly forbid sharing individual patient records across district or international borders.*
> 3. *Stockouts are handled reactively via emergency air freight after patients leave empty-handed, while nearby district hospitals discard expired surplus.*
>
> *We built **HealthSupply**: an offline-tolerant, privacy-preserving federated intelligence and proactive redistribution system engineered specifically for low-connectivity primary healthcare clinics."*

---

### 0:35 – 1:15 | Act I: Outbreak Injection & CUSUM Early Warning
> **Action:**  
> Run the sub-second automated demo in terminal:
> ```bash
> make demo
> # Or: python -m demo.runner
> ```
> Switch browser to `http://localhost:8000/dashboard/` on the **Overview** tab.

> **Presenter:**
> *"Watch our live terminal and dashboard. With one command, our synthetic data engine initializes 200 health facilities across two sovereign countries with realistic clinic schedules, seasonal demand, and cold-chain constraints.*
>
> *We simulate an epidemic surge in District Kolar—a 4.2× rise in antimalarial consumption over 7 days.*
>
> *Traditional supply systems miss this until shelves are empty because stockouts suppress recorded demand. But our **CUSUM Outbreak Radar** flags the anomaly at **Week 2 (Period 6)** while the clinic still has safety stock. The alert is published to our Control Center feed in under **12 milliseconds**, well within our 500ms latency SLA.*
>
> *Notice on our Live Stock Heat Map: Kolar PHC transitions from a healthy green halo to a pulsing purple outbreak halo, with cover plummeting to 2.2 days."*

---

### 1:15 – 1:55 | Act II: Proactive Redistribution & Cryptographic Audit
> **Action:**  
> Click the **Transfer Proposals** tab on the dashboard, displaying Proposal `PROP-633558DF`. Click **Approve**.

> **Presenter:**
> *"Instead of waiting for an emergency emergency requisition, our **Google OR-Tools Mixed-Integer Linear Programming (MILP)** engine solves a multi-facility redistribution model in **35.7 milliseconds**.*
>
> *Look at the parameters of this proposal:*
> - *It sources 675 units of Artemether-Lumefantrine from District Hospital `FAC-A-015`, just 28.5 km away.*
> - *The donor hospital's safety stock remains strictly protected: its buffer transitions from 112 days down to 62 days (well above the 30-day policy floor).*
> - *The recipient clinic's cover is lifted from an imminent 2.2-day stockout to **36.0 days of protected cover**.*
> - *Cold-chain products like Oxytocin are hard-constrained to ≤100 km transit routes with active solar-refrigeration logging.*
>
> *When the District Medical Officer clicks **Approve**, the transaction is cryptographically sealed into an **append-only SHA-256 audit hash chain**. Even a root database administrator cannot alter or delete this decision without breaking the tamper-evident cryptographic chain."*

---

### 1:55 – 2:35 | Act III: The Killer Experiment — Federated Knowledge Transfer
> **Action:**  
> Click the **Federated Learning** tab on the dashboard. Point to the **RDP Privacy Meter** ($\epsilon=3.84 \le 4.0$) and the **Outbreak Knowledge Transfer** comparison.

> **Presenter:**
> *"Now let's examine the architectural centerpiece: **Cross-Border Outbreak Knowledge Transfer without Data Leakage**.*
>
> *Under international data sovereignty rules, Country B cannot send patient records to Country A. Country B had never experienced a high-intensity malaria surge before.*
>
> *In isolation, Country B's local model had a Mean Absolute Error of **31.71**, failing completely during the outbreak.*
>
> *Under HealthSupply's **FedProx + Representation Sharing** federated learning framework:*
> - *Only model parameter tensors traverse the wire over mTLS.*
> - *Our programmatic `NetworkEnvelope` security guard strictly rejects any patient record, dispense event, or tabular structure with a `DataLeakageSecurityViolation`.*
> - *We apply DP-SGD with Rényi Differential Privacy accounting: our privacy budget is **$\epsilon = 3.84 \le 4.0$** at $\delta = 10^{-5}$.*
>
> *The result? Country B absorbs the latent epidemic dynamics from Country A's experience, cutting prediction error to **3.66**—an **88.45% error reduction** with zero raw data shared."*

---

### 2:35 – 3:00 | Act IV: Counterfactual Proof & Conclusion
> **Action:**  
> Point to the Counterfactual Comparison Table on the screen (and printed in terminal output):

```
=================== COUNTERFACTUAL IMPACT COMPARISON ===================
Metric                              | Without HealthSupply | With HealthSupply   
------------------------------------|----------------------|---------------------
Stockout Onset                      | Day 3 of surge       | Averted (Cover > 20d)
Unfulfilled Prescription Rate       | 68.4%                | 0.0%                
Expiring Stock Wastage              | 350 units lost       | 0 units (Salvaged)  
Emergency Air Freight Cost          | $12,400 USD          | $45 USD (Road)      
Cross-Border Outbreak Transfer      | 0% (Blind)           | 88.45% MAE Gain     
Total Execution Time                | N/A                  | 0.78 - 0.93 seconds 
Budget SLA (< 300s)                 | N/A                  | PASSED (384x faster)
========================================================================
```

> **Presenter:**
> *"In summary, the counterfactual numbers speak for themselves:*
> - *Stockouts are completely averted, keeping unfulfilled prescriptions at **0.0%**.*
> - *Expiry wastage is reduced from 350 discarded units to zero.*
> - *Logistics cost plunges from **$12,400 in emergency air freight to just $45 in local road dispatch**—a **99.6% financial savings**.*
> - *And all 53 automated verification tests pass across all six architectural phases.*
>
> *HealthSupply proves that cutting-edge AI—federated learning, differential privacy, and mathematical optimization—can be deployed robustly into the most constrained environments to save lives and resources. Thank you."*

---

## 🛠️ Backup & FAQ Guide for Judges

| Question | Answer |
| :--- | :--- |
| **What happens if a clinic has no internet for 3 weeks?** | Facilities run a Progressive Web App with Dexie/IndexedDB storage. Transactions synchronize via Automerge CRDTs with state-vector deduplication. In zero-connectivity areas, staff send structured SMS messages via our authenticated HMAC-SHA256 GSM gateway. |
| **How do you prevent hospitals from hoarding supplies?** | The OR-Tools MILP optimization enforces donor safety buffer constraints: donor facilities cannot fall below their 30-day minimum stock cover. |
| **How do you guarantee cold-chain integrity?** | Cold-chain items (e.g., Oxytocin) are restricted to transit routes $\le 100\text{ km}$, and recipient facilities must have verified solar or cold-chain capabilities. Continuous temperature monitoring flags excursions ($<2^\circ\text{C}$ or $>8^\circ\text{C}$). |
| **Why does the demo finish in under 1 second?** | The modular monolith integrates high-performance vectorized operations, compiled OSQP hierarchical reconciliation, and pre-warmed OR-Tools solvers, fulfilling the 5-minute hackathon evaluation in 0.78 seconds. |
