# Architecture Research

**Domain:** Secure image upload and delivery  
**Researched:** 2026-07-18  
**Confidence:** HIGH

## Recommended Architecture

```
Commissioner browser
  -> authenticated, CSRF-protected Django form
    -> family-admin authorization and tenant resolution
      -> bounded Pillow validation + re-encode
        -> private S3 `family-logos/<family-id>/<uuid>.webp`
          -> Family stores generated object key / image field
            -> server-controlled image URL or signed read delivery
```

### Responsibilities

| Component | Responsibility |
|---|---|
| Cropper.js UI | Local preview and crop coordinates; no security decision. |
| Django form/service | Role check, request-size/format/pixel validation, crop-coordinate validation, re-encode, atomic record update. |
| S3 storage | Private durable object storage; block public access, bucket-owner-enforced objects, encryption. |
| ESO + AWS Secrets Manager | Inject least-privilege S3 credentials/configuration into dev and production pods; never commit credentials. |
| Tests | Cover positive lifecycle and malicious/authorization input cases. |

## Data Flow

1. A family owner/admin reaches the existing tenant commissioner settings page.
2. Browser previews the candidate and submits the original file plus bounded crop data to Django.
3. Django resolves the tenant from the URL/session context, not form fields; verifies the content with Pillow; strips metadata by generating a fresh output.
4. Django writes a generated object key in the logo prefix and updates the family transactionally; then removes the previous generated key only when it is no longer referenced.
5. Templates render only the server-owned output URL, falling back to the default logo when absent.

## AWS Integration

- Existing `family-pickem` bucket is in `us-east-1`, has all four Block Public Access controls, `BucketOwnerEnforced` ownership, and SSE-S3 enabled.
- Add a narrowly scoped IAM principal/policy permitting only `GetObject`, `PutObject`, and `DeleteObject` in the `family-logos/` prefix, with no ACL permissions and no bucket-wide administration.
- Add non-secret bucket/region/prefix settings and credential keys to the existing `family-pickem/{prd,dev}/envvars` Secrets Manager objects so the existing Helm `ExternalSecret` materializes them into pods.
- Keep delivery private. Decide during implementation between an app-mediated image endpoint and short-lived presigned GET URLs; neither requires making the bucket public.

## Anti-Patterns

- Do not retain `Family.logo_url` as a general URL input alongside uploads.
- Do not upload an unprocessed browser blob directly to a public S3 key.
- Do not use `Content-Type` supplied by the browser as format validation.
- Do not serve untrusted originals from `family-pickem.com`; Django warns that valid image headers can be followed by HTML.

## Sources

- https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/configuring-block-public-access-bucket.html

