# Feature Research

**Domain:** Secure family-logo image upload  
**Researched:** 2026-07-18  
**Confidence:** HIGH

## Feature Landscape

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Select image and preview | Lets commissioner verify the intended file | Low | Local preview must not bypass server validation. |
| Square crop/reposition | Logos need predictable presentation in compact UI | Medium | Fix aspect ratio; preserve a clear default crop. |
| Save, replace, remove | Covers normal logo lifecycle | Medium | Replacement must not leave orphaned S3 objects. |
| Clear validation errors | Makes failure actionable | Medium | Distinguish unsupported type, byte limit, and pixel limit without exposing internals. |
| Safe delivery | Prevents active content/XSS exposure | High | Only render server-produced image bytes. |

### Differentiators

| Feature | Value | Complexity | Decision |
|---|---|---|---|
| Live result preview at display size | Prevents poor logos in the family lobby | Low | Include. |
| Transparent PNG support | Works for many team-style logos | Medium | Include if normalized safely. |
| Multiple logo variants | Useful for future headers/avatars | Medium | Defer; one canonical square asset is sufficient now. |
| Direct-to-S3 multipart upload | Useful for large media | High | Exclude; logos have tight size limits. |

### Anti-Features

| Feature | Why Problematic | Alternative |
|---|---|---|
| Arbitrary external logo URL | Broken UX, tracking/privacy exposure, and remote-content dependency | Remove URL entry entirely. |
| SVG support | Can contain active content and is unnecessary for this use case | Raster allowlist only. |
| Original-file download | Preserves attacker-controlled bytes | Persist only re-encoded output. |

## MVP Definition

- [ ] Authorized commissioner can upload a JPEG, PNG, or WebP below the byte/pixel limits.
- [ ] Commissioner can select a square crop and preview the rendered result.
- [ ] Server creates and stores a fixed-size image asset, replaces/removes prior asset safely, and renders it in the family UI.
- [ ] Unauthorized, malformed, oversized, spoofed, and cross-family attempts are rejected and audited.

## Dependencies

```
Authorization + CSRF
  -> server-side validation/normalization
       -> private S3 persistence
            -> commissioner crop/save UI
                 -> family logo display
```

