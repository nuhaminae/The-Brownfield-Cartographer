# Reconnaissance

---

[Meltano](https://github.com/meltano/meltano) is an open‑source data integration and orchestration engine. It takes a declarative statement about type of data that needed to be pulled, transformed, and loaded. It then handles the heavy lifting of running, scheduling, and monitoring those pipelines. It is written in python and yaml.

## Day one Q & A

### 1. What is the primary data ingestion path?

The primary ingestion path shows how data first enters the system, how it flows through connections, and what transformations happen before it lands in sotrage.

In the case of Melanto, there are different ingestion paths, but the setup remains the same regadless.The ingestion path is always defined by the extractor-loader chain inside each meltano.yml.

#### **Tap (extractor) → optional intermediate blocks → Target (loader)**

Examples of how Meltano handles different contexts (local vs S3 state, envvar configs, manifests, migrations), while keeping the ingestion path consistent.

- **meltano-basics/meltano.yml** → A minimal path: one tap feeding directly into one target.  
- **meltano-config/meltano.yml** → Same extractor → loader flow, but with environment‑specific overrides.  
- **meltano-custom-python/meltano.yml** → Tap → loader, with a custom Python utility in between.  
- **meltano-env-precedence/meltano.yml** → Tap → loader, configs controlled by environment variable precedence.  
- **meltano-expand-envvars-in-array/meltano.yml** → Tap → loader, configs expanded from envvar arrays.  
- **meltano-manifest/meltano.yml** → Tap → loader, with manifest metadata shaping schema.  
- **meltano-migrations/meltano.yml** → Tap → loader, with migration steps included.  
- **meltano-objects/meltano.yml** → Tap → loader, with object definitions enriching the path.  
- **meltano-state-local/meltano.yml** → Tap → loader, state stored locally (SQLite).  
- **meltano-state-s3/meltano.yml** → Tap → loader, state stored in S3.  
- **meltano-run/meltano.yml** → Tap → loader, run orchestration demonstrated.  
- **meltano-run-merge-states/meltano.yml** → Tap → loader, merging multiple state files.  
- **meltano-annotations/meltano.yml** → Tap → loader, with annotations attached to streams.

### 2. What are the 3-5 most critical output datasets/endpoints?

The most critical outputs in the Meltano repo are the datasets and endpoints that represent the final results of its ELT (Extract–Load–Transform) pipelines. Those are the plugin discovery via Meltano Hub, extracted data streams from Singer taps, loaded datasets into targets (databases, warehouses, or files), and orchestrated pipeline states. These are the outputs that downstream systems and users rely on.

1. **Meltano Hub Plugin Metadata**
   - **Output type:** Dataset (JSON/YAML metadata)
   - **Purpose:** Provides the catalog of available Singer taps (extractors) and targets (loaders).
   - **Criticality:** It is the single source of truth for integrations; without it, users cannot discover or configure connectors.

2. **Extracted Data Streams (Singer Taps)**
   - **Output type:** Raw datasets (JSON streams)
   - **Purpose:** Data pulled from APIs, databases, or SaaS platforms.
   - **Criticality:** These are the *primary inputs* to the Meltano pipeline, but also an *output* of the extraction step. They represent the raw business data (e.g., Salesforce records, Google Analytics events).

3. **Loaded Datasets (Singer Targets)**
   - **Output type:** Final datasets in warehouses, databases, or files (e.g., PostgreSQL tables, Snowflake schemas, CSV/Parquet files).
   - **Purpose:** The canonical outputs of Meltano pipelines, consumed by BI tools, ML models, or downstream apps.
   - **Criticality:** These are the most business-critical outputs—if they fail, dashboards and analytics break.

4. **Pipeline Orchestration State**
   - **Output type:** Logs, metadata tables, and orchestration endpoints
   - **Purpose:** Tracks job runs, success/failure, and lineage.
   - **Criticality:** Essential for monitoring and debugging; ensures reproducibility and reliability of data workflows.

5. **Meltano API/CLI Endpoints**
   - **Output type:** Command-line and API responses (e.g., `meltano run`, `meltano invoke`)
   - **Purpose:** Exposes pipeline execution, plugin management, and configuration.
   - **Criticality:** These endpoints are how users and automation trigger workflows; they are critical for operational integration.

### 3. What is the blast radius if the most critical module fails?

Here is how far downstream a damage can spread if one of the core components breaks.

1. **Singer Tap (Extractor) Failure**
   - **Blast radius**: No data enters the pipeline.  
   - All downstream loaders, transformations, and dashboards receive *empty or stale data*.  
   - Business impact: analytics, ML models, and reporting grind to a halt.

2. **Singer Target (Loader) Failure**
   - **Blast radius**: Data is extracted but never lands in the destination warehouse or lake.  
   - Downstream consumers (BI tools, ML pipelines) see *missing datasets*.  
   - Business impact: dashboards break, decision-making is based on outdated data.

3. **Meltano Hub Registry Failure**
   - **Blast radius**: Teams can not discover or install plugins.  
   - Pipelines depending on new taps/targets can not be built or updated.  
   - Business impact: slows down development and onboarding, but existing pipelines may still run.

4. **Pipeline Orchestration Failure**
   - **Blast radius**: Pipelines don not run on schedule.  
   - Even if taps and targets work, jobs don not execute.  
   - Business impact: data freshness collapses, SLAs are missed, alerts trigger.

5. **dbt Transformation Failure**
   - **Blast radius**: Raw data lands in the warehouse, but transformed datasets are broken.  
   - BI dashboards and ML models consume *incorrect or incomplete data*.  
   - Business impact: decisions made on bad data, potentially worse than no data.

---

### 4. Where is the business logic concentrated vs. distributed?

#### Concentrated Business Logic

- **Core Orchestration Layer (`/src/meltano/core/`)**
  - This is where the orchestration of ELT pipelines lives.
  - Logic for running jobs, managing state, handling errors, and sequencing extract → load → transform is centralised.
  - The CLI (`meltano run`, `meltano elt`) is tightly coupled to this layer, so the “brains” of the system are concentrated here.

- **Configuration (`meltano.yml`)**
  - Business rules about *which* extractors, loaders, and transformers to use are concentrated in a single config file.
  - This makes pipeline definitions declarative and centralised.

#### Distributed Business Logic

- **Plugins (Extractors, Loaders, Transformers)**
  - Each plugin (Singer tap/target, dbt transformer, etc.) contains its own logic for interacting with external systems.
  - Business logic about *how* to talk to Salesforce, GitHub, Postgres, or Snowflake is distributed across many plugin repos.
  - Meltano itself doesn’t own this logic—it delegates to the plugin ecosystem.

- **Hub Metadata**
  - Plugin discovery and metadata are distributed across the Meltano Hub.
  - The “business logic” of what integrations exist and how they’re configured is spread out, not concentrated in the core repo.

### 5. What has changed most frequently in the last 90 days (git velocity map)?

In the last 90 days, the Meltano repo has seen the highest velocity of changes in its core engine depenedecy, workflows, plugin, and tests.

``` bash
# Commit Logs
git log --since="90 days ago" --pretty=format:"%h %an %ad %s" --date=short

# Identify Hot Files
git log --since="90 days ago" --name-only --pretty=format:"" \
  | sort | uniq -c | sort -nr | head -20

# Aggregate by directory
git log --since="90 days ago" --name-only --pretty=format:"" \
  | grep -v '^$' \
  | sed 's|/[^/]*$||' \
  | sort | uniq -c | sort -nr | head -20

# Visualise commit frequency
git log --since="90 days ago" --date=short --pretty="format:%ad" \
  | sort | uniq -c
```

Output of running the above inofromed the following changes:

- **`uv.lock` (63 changes)** and **`pyproject.toml` (40 changes)**  
  → These are dependency and build configuration files. High velocity here means Meltano’s team is actively updating dependencies, packaging, and build tooling.  

- **`.github/workflows/*` (multiple files, 15–10 changes each)**  
  → Heavy churn in CI/CD workflows (tests, benchmarks, integration tests, version bumps).  

- **`src/meltano/core/plugin/singer/tap.py` (6 changes)**  
  → This is a **core module** that defines how Meltano interacts with Singer taps (extractors).  

- **`tests/meltano/core/tracking/test_tracker.py` (4 changes)**  
  → Indicates active testing around Meltano’s tracking/telemetry.  

- **Other files like `noxfile.py`, `CHANGELOG.md`, `.pre-commit-config.yaml`**  
  → Developer tooling and documentation.  

The **highest velocity** is in dependency configs and CI/CD workflows, but the **most critical velocity hotspot** is `src/meltano/core/plugin/singer/tap.py`, since it directly controls data extraction.  

---

## Difficulty Analysis

The most difficult parts were accurately distinguishing which modules were truly critical, since dependencies and business impact were not always obvious. Trying to locate and understand business logic scattered across multiple layers of code was another difficulty. The other one was generating a meaningful git velocity map that focused on the genuinely important modules rather than trivial ones like dependency updates. Those areas consumed the most manual effort and often led to confusion, which highlights the need for stronger architectural visibility and tooling around module criticality, logic boundaries, and change‑tracking.
