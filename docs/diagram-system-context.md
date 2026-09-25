# System Context — cpompa-ai-cloud

```mermaid
flowchart LR
    U[User / Tenant] -->|HTTPS| CF[Cloudflare Access]
    CF --> API[Control Plane API<br/>FastAPI :8000<br/>Mac Mini]
    API --> PG[(Postgres 16<br/>users / subs / models)]
    API --> RD[(Redis 7<br/>sessions / usage)]
    API --> STR[Stripe TEST MODE<br/>billing + webhooks]
    API -->|node presence events| UNIFI[Unifi Network<br/>cron bot]
    API -.->|agent lifecycle| AG[Per-tenant Hermes agents]

    subgraph PAIR["NVIDIA PAIR peer cluster (mDNS + mTLS)"]
        PMINI[Mac Mini<br/>PAIR proxy :1234]
        PD2[Desktop2<br/>RTX 3080 10GB]
    end

    AG -->|OpenAI-compatible :1234| PMINI
    PMINI <-->|5353/udp + 14318-14323| PD2
    PMINI --> LMS[LM Studio engine]
    PD2 --> OLL[Ollama / LM Studio engine]
    PD2 -.->|later| MB[MacBook qwen3.6-35b]
    PD2 -.->|later| POMPS[Pomps RTX box]
```

## Components

| Component | Host | Purpose |
|---|---|---|
| Control Plane API | Mac Mini | Users, subscriptions, model catalog, agent provisioning |
| Postgres / Redis | Mac Mini (compose) | Persistence + sessions/usage |
| PAIR proxy | Mac Mini `127.0.0.1:1234` | Inference routing — claims LM Studio's port; clients unchanged |
| GPU node | Desktop2 (RTX 3080) | Ollama/LM Studio engines serving models |
| Stripe | SaaS | Test-mode subscriptions + metered usage |
| Unifi bot | Hermes cron | Node presence events feeding node inventory |
