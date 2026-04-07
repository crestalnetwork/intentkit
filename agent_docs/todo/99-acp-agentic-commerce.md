# ACP (Agentic Commerce Protocol) Integration Research

> Status: Research / Low Priority
> Date: 2026-04-07
> Protocol repo: https://github.com/agentic-commerce-protocol/agentic-commerce-protocol

---

## 1. Protocol Overview

ACP is an open standard (Apache 2.0) co-maintained by OpenAI and Stripe. It enables AI agents to facilitate purchases from merchants on behalf of users. Latest spec version: 2026-01-30.

**Core principle**: Agent is NOT the merchant of record. Merchant retains full control over orders, payments, taxes, and compliance.

### What ACP covers (checkout only)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/checkout_sessions` | POST | Create checkout session |
| `/checkout_sessions/{id}` | POST | Update session (items, address, etc.) |
| `/checkout_sessions/{id}` | GET | Retrieve session state |
| `/checkout_sessions/{id}/complete` | POST | Complete purchase with payment token |
| `/checkout_sessions/{id}/cancel` | POST | Cancel session |

Additional:
- `POST /agentic_commerce/delegate_payment` — Tokenize payment credentials
- `GET /.well-known/acp.json` — Merchant capability discovery
- Webhooks: `order_create`, `order_update`

Authentication: Bearer Token + HMAC-SHA256 + `API-Version` header + `Idempotency-Key`.

### What ACP does NOT cover

- **Product catalog / search / browsing** — explicitly out of scope
- **Merchant directory / index** — intentionally excluded (anti-enumeration)
- **Cross-merchant search** — not supported

The protocol assumes the agent already knows the merchant's endpoint URL, has API credentials, and knows the product item IDs before initiating checkout.

---

## 2. Product Discovery Gap

### How others solve it

| Platform | Approach |
|----------|----------|
| **OpenAI (ChatGPT)** | Private Product Feed API at `developers.openai.com/commerce/`. Merchants upload structured product data (CSV/JSON). Not open to third-party agents. |
| **Stripe** | Agentic Commerce Suite — merchants upload catalog to Stripe, Stripe syndicates to approved AI platforms. B2B service, no public search API. |
| **Shopify** | Agentic Storefronts — auto-syncs merchant catalogs to AI platforms. Millions of merchants. Also has public Storefront API. |
| **PayPal** | Aggregation layer — distributes merchant catalogs to ChatGPT, Copilot, Perplexity via single integration. |

**Key insight**: Product discovery is the real moat, not the checkout protocol. Each AI platform builds its own private product index.

### Item ID format

ACP item IDs are **free-form strings defined by the merchant** in their product feed. No enforced format. Could be SKU, internal DB ID, or any stable identifier. The agent must know these IDs before creating a checkout session.

### Proposed Product Feeds API

GitHub issue #189 proposes adding product catalog endpoints to ACP. Not yet merged into spec.

---

## 3. Merchant Access Model

**ACP is a B2B authorized protocol, not a public API.**

To buy from a merchant via ACP, an agent platform needs:
1. The merchant's ACP endpoint URL (from `/.well-known/acp.json`)
2. A Bearer Token issued by the merchant to the agent platform
3. Knowledge of the merchant's product IDs

Merchants (or their platforms like Shopify/Etsy) must explicitly authorize each agent platform. There is no way to "discover and buy from" an arbitrary merchant without prior business relationship.

**Example: Etsy**
- Etsy listing IDs are in URLs: `etsy.com/listing/123456789/...`
- Web search can find these IDs, but Etsy's ACP endpoint is only open to ChatGPT
- A third-party agent cannot call Etsy's ACP checkout without Etsy's authorization

---

## 4. Payment Architecture

### Standard flow (user pays)

1. Agent creates checkout session
2. User sees payment UI, clicks "Pay"
3. SPT (SharedPaymentToken) is generated — scoped to merchant + amount + time
4. Agent calls `complete` with SPT
5. Merchant processes payment via Stripe

**Cannot be fully automated** — requires per-transaction user consent in UI. 3DS may also trigger in EU.

### Platform proxy payment (recommended for IntentKit)

Fully automated, no user UI needed:

```
User deposits USDC → Stripe Financial Account (holds USDC natively)
                         ↓
Agent creates ACP checkout session
                         ↓
Platform creates Issuing virtual card (funded by USDC balance)
                         ↓
Virtual card → PaymentMethod → SPT → ACP complete
                         ↓
Merchant receives normal Visa payment (Bridge auto-converts USDC→fiat)
```

| Component | Status | Notes |
|-----------|--------|-------|
| USDC deposit to Financial Account | Working | Private preview, 9 chains, 101 countries |
| USDC-funded Issuing card | Working | Private preview, US platforms |
| Issuing card → SPT | Not explicitly documented | Likely works (Issuing card = Visa = valid PaymentMethod) |
| ACP checkout via SPT | Working | Standard flow |

**Fallback**: If SPT doesn't accept Issuing cards, pass virtual card details through `delegate_payment` directly.

### Stablecoin support details

**Stripe Financial Account accepts:**
- USDC (Circle) — Ethereum, Solana, Base, Polygon, Arbitrum, Avalanche, Optimism, Stellar, Tempo
- USDB (Bridge/Stripe) — same networks

**Issuing card spending**: Bridge auto-converts USDC→fiat at point of sale. Merchant sees normal card payment.

**Limitations**: Stablecoin Financial Accounts and Issuing are in private preview. Platform must be US-based. Need to apply via Stripe waitlist.

### Alternative: fiat-only path

If stablecoin path is unavailable:
- Stripe Treasury (USD) + Top-Ups from bank account
- Stripe Issuing virtual card funded by USD balance
- Same ACP flow, just without crypto on-ramp

---

## 5. Ecosystem Status (as of 2026-04)

### ACP adopters

| Platform | Role | Status |
|----------|------|--------|
| **OpenAI / ChatGPT** | Co-creator, primary agent | Pivoted from Instant Checkout to discovery+redirect (March 2026) |
| **Microsoft Copilot** | Agent | Copilot Checkout launched Jan 2026, explicitly uses ACP |
| **Perplexity** | Agent | "Buy with Pro" via PayPal's ACP integration, 5000+ merchants |
| **Stripe** | PSP + catalog syndication | Co-creator, currently only production PSP |
| **PayPal** | Aggregation layer | Distributes catalogs across ChatGPT, Copilot, Perplexity |
| **Shopify** | Merchant platform | Agentic Storefronts, auto-enrolls millions of merchants |
| **Mastercard** | Payment rail | Agent Pay for Copilot Checkout |

### Competing protocols

| Protocol | Backed by | Focus |
|----------|-----------|-------|
| **UCP** (Universal Commerce Protocol) | Google + Shopify | Similar to ACP, used by Gemini |
| **MPP** (Machine Payments Protocol) | Stripe + Tempo | Agent-to-agent payments, supports stablecoin (USDC on Tempo) |
| **x402** | Coinbase + Cloudflare | HTTP-native stablecoin micropayments, 150M+ tx |
| **AP2** | Google | Enterprise auth mandates, x402 extension for settlement |

### OpenAI's pivot

OpenAI launched Instant Checkout (Sep 2025) but killed it (Mar 2026) due to:
- Only ~12 merchants went fully live (out of ~30 onboarded)
- Inaccurate product data
- No multi-item cart support
- Users preferred merchant websites with saved accounts

Now focuses on product discovery + redirect to merchant sites.

---

## 6. Integration Paths for IntentKit

### Path A: Become a Stripe ACP Agent Platform

- Apply to Stripe's Agentic Commerce Suite
- Stripe syndicates merchant catalogs to you
- Use Stripe Issuing + Financial Accounts for payment
- **Pros**: Largest merchant coverage via Stripe
- **Cons**: Requires business development, private preview access

### Path B: PayPal Aggregation Layer

- Integrate PayPal's ACP aggregation
- One integration covers merchants already on PayPal
- **Pros**: Quick multi-merchant coverage
- **Cons**: PayPal as dependency

### Path C: Middleware (Rye, CartAI, Firmly)

- Use third-party checkout aggregators
- **Rye**: Universal Checkout API, no per-merchant integration
- **CartAI**: White-label, supports both ACP and UCP
- **Pros**: Fastest path to working prototype
- **Cons**: Additional dependency and cost

### Path D: Direct Shopify Integration

- Shopify has public Storefront API (product search) + Agentic Storefronts (ACP checkout)
- Could be the most open path for a third-party agent
- **Pros**: Millions of merchants, public APIs available
- **Cons**: Shopify-only

### Path E: Web Search + Browser Automation

- Search for products via web search skills (already in IntentKit)
- Complete purchases via browser automation (Induced AI, Zinc-style APIs)
- Bypasses ACP entirely
- **Pros**: Works with any merchant
- **Cons**: Fragile, not standardized

---

## 7. Recommended Architecture

### Phase 1: Foundation (no ACP yet)

- Implement Stripe Financial Account integration for USDC deposits
- Implement Stripe Issuing for virtual card creation
- Build the "platform wallet" model: user deposits → platform holds → agent spends

### Phase 2: ACP Skill Category

```
intentkit/skills/acp/
├── __init__.py
├── base.py                  # HTTP client, auth, signing, merchant registry
├── schema.json
├── discover_merchant.py     # Fetch /.well-known/acp.json
├── create_checkout.py
├── update_checkout.py
├── get_checkout.py
├── complete_checkout.py
├── cancel_checkout.py
├── list_merchants.py        # List configured merchants
├── add_merchant.py          # Runtime merchant addition (private)
└── acp.svg
```

Config:
```python
class Config(SkillConfig):
    enabled: bool
    states: SkillStates
    merchants: list[MerchantConfig] | None  # Pre-configured merchants
    stripe_api_key: str | None              # For Issuing + Financial Accounts
```

### Phase 3: Merchant Access

- Apply to Stripe / PayPal / Shopify for catalog access
- Or integrate middleware like Rye for immediate multi-merchant coverage

### Phase 4: Product Discovery

- Build product search using Shopify Storefront API and/or web search
- Or integrate with Stripe/PayPal catalog syndication once approved

---

## 8. Key References

- ACP spec: https://github.com/agentic-commerce-protocol/agentic-commerce-protocol
- ACP official site: https://www.agenticcommerce.dev/
- Stripe ACP docs: https://docs.stripe.com/agentic-commerce
- Stripe Stablecoin Financial Accounts: https://docs.stripe.com/financial-accounts/stablecoins
- Stripe Issuing: https://docs.stripe.com/issuing
- OpenAI Commerce: https://developers.openai.com/commerce
- Shopify Agentic Storefronts: https://www.shopify.com/news/agentic-commerce-momentum
- MPP: https://stripe.com/blog/machine-payments-protocol
- x402: https://www.x402.org
