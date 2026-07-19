# Phase 8: Private AWS Delivery and Adversarial Verification - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Finish the production security boundary for family-logo assets: least-privilege S3 access under `family-logos/`, dedicated AWS credentials delivered through AWS Secrets Manager and External Secrets Operator, safe replacement/removal object lifecycle, and production-grade hostile-request verification. This phase does not add direct browser-to-S3 uploads, public objects, or arbitrary remote-image URLs.

</domain>

<decisions>
## Implementation Decisions

### Private delivery
- **D-01:** Serve family logos directly from the existing private S3 bucket with short-lived signed URLs. Do not make objects or the bucket public and do not add a Django image-proxy endpoint.

### AWS credentials and deployment
- **D-02:** Use a dedicated least-privilege IAM principal for family-logo access, restricted to the `family-logos/` prefix in the existing `family-pickem` bucket in `us-east-1`.
- **D-03:** Store that principal's credentials and logo-storage configuration in a dedicated AWS Secrets Manager secret; synchronize them into the application namespace only through the existing ESO `ClusterSecretStore` and Helm ExternalSecret flow. No credentials may enter Git or manually-created Kubernetes Secrets.

### Object lifecycle
- **D-04:** After a successful replacement or removal database transaction, delete the now-obsolete generated S3 object immediately. Preserve compensation behavior so a failed database/audit mutation cannot orphan or break the currently referenced object.

### Release gate
- **D-05:** Require automated security coverage plus a staging upload/replace/remove smoke test and a production smoke test before release.

### the agent's Discretion
- Select the signed-URL lifetime, exact IAM/Secrets Manager names, and test mechanics consistent with the existing deployment conventions and AWS security guidance.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and security requirements
- `.planning/ROADMAP.md` — Phase 8 goal, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — S3-02, S3-03, SAFE-02, and SAFE-03 acceptance requirements.
- `.planning/phases/06-secure-logo-foundation/06-RESEARCH.md` — existing bucket/region findings and security constraints.
- `.planning/phases/06-secure-logo-foundation/06-VERIFICATION.md` — prior validated processing and authorization guarantees that must remain intact.
- `.planning/phases/07-commissioner-upload-and-delivery-experience/07-CONTEXT.md` — Phase 7 storage/lifecycle boundary inherited by this phase.

### Application and deployment integration
- `pickem/pickem_api/storage.py` — private `FamilyLogoStorage` prefix, signed-URL, and content-type contract.
- `pickem/pickem_homepage/views.py` — tenant-locked logo create/replace/remove persistence and current compensation behavior.
- `pickem/pickem/settings.py` — AWS environment-variable configuration.
- `charts/family-pickem/templates/external-secret-envvars.yaml` — existing ESO extraction pattern.
- `charts/family-pickem/templates/deployment.yaml` — application environment injection path.
- `charts/family-pickem/values.yaml` — ExternalSecret and service-account configuration surface.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FamilyLogoStorage` already isolates generated keys beneath `family-logos/`, disables public ACLs, uses WebP parameters, and requests signed URLs.
- `family_pool_admin_settings` already locks the tenant target, records logo-presence audit metadata, and compensates a newly written storage object if its database/audit transaction fails.
- Helm already supports an ESO-managed environment Secret through `external-secret-envvars.yaml` and injects it into both migrations and application containers.

### Established Patterns
- Uploads pass through the Django server; browser-to-S3 writes and original-file retention are explicitly out of scope.
- Tenant routes derive family/pool identity server-side and use explicit negative authorization tests.
- The bucket is expected to remain private with Block Public Access and bucket-owner-enforced controls.

### Integration Points
- Extend logo storage/settings only for dedicated logo credentials and bounded signed delivery.
- Extend the family settings mutation seam for successful obsolete-object deletion and failure-safe compensation.
- Extend Helm values/templates and AWS setup documentation/scripts without embedding secrets.
- Add focused application and deployment tests plus staging/production smoke instructions.

</code_context>

<specifics>
## Specific Ideas

- The user approved all recommended security and release defaults without further design discussion.
- Existing local development may continue to use isolated filesystem media when AWS logo configuration is absent; production must use the dedicated private S3 configuration.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-Private AWS Delivery and Adversarial Verification*
*Context gathered: 2026-07-18*
