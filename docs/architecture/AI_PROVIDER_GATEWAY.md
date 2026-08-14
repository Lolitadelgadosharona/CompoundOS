# AI Provider Gateway — Architecture

> **Phase**: 3.4-B Provider Gateway Architecture
> **Date**: 2026-08-14

---

## 1. Purpose

The Provider Gateway layer isolates the application from any specific model
provider. It sits between the provider adapters and the model providers
(Anthropic, OpenAI, Gemini) so that:

- credentials are resolved uniformly and fail closed,
- model names are decoupled from provider-specific identifiers,
- the choice of provider, gateway endpoint, or model can be changed without
  touching application code.

---

## 2. Architecture

Application
 ↓
Provider Adapter
 ↓
Gateway Layer
 ↓
Model Provider

Each provider adapter wraps its SDK lazily and delegates credential resolution
and model translation to the gateway layer before issuing a call.

---

## 3. Credential resolution

Anthropic

- ANTHROPIC_AUTH_TOKEN — priority 1 (Authorization: Bearer)
- ANTHROPIC_API_KEY — fallback (x-api-key)

OpenAI

- OPENAI_API_KEY

Resolution is fail-closed: when no credential is available, the adapter raises
ConfigurationError before any network call.

---

## 4. Model alias

COMPOUNDOS_MODEL_ALIASES

Example:

 claude-sonnet-4=claude-sonnet-4-6

The canonical internal model name is preserved end-to-end (database, routing,
cost tables). The alias map translates it to the provider-facing name only at
the SDK call boundary.

---

## 5. Design principles

- canonical model identity preserved
- provider implementation replaceable
- gateway compatible
- provenance maintained
