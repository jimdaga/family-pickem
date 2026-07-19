# Pitfalls Research

**Domain:** Secure family-logo image upload  
**Researched:** 2026-07-18  
**Confidence:** HIGH

## Critical Pitfalls

### Trusting browser metadata

**Risk:** An executable/HTML payload masquerades as an image.

**Prevention:** Allowlist JPEG/PNG/WebP, verify with Pillow decoder, cap bytes and pixels before full processing, and emit a brand-new raster asset with a generated name.

**Phase to address:** Validation and storage foundation.

### Serving original user bytes from the application origin

**Risk:** Stored XSS/content-sniffing exposure; Django specifically warns that a PNG header plus HTML can pass image verification.

**Prevention:** Never retain or serve originals. Render only fixed Content-Type server-generated assets from controlled storage/delivery with `nosniff`.

**Phase to address:** Delivery integration and security verification.

### Image decompression bombs and resource exhaustion

**Risk:** Small files expand to huge pixel buffers and exhaust pod memory/CPU.

**Prevention:** Enforce ingress and form byte limits, set/retain a Pillow pixel cap, promote decompression-bomb warnings to errors, and bound crop/output dimensions.

**Phase to address:** Validation and storage foundation.

### Orphaned S3 objects or cross-family overwrite

**Risk:** Replacing a logo leaks storage or attacker-controlled keys affect another family.

**Prevention:** Generate keys server-side under a family-derived prefix, never accept object key/family ID from the form, and test replace/remove transactional behavior.

**Phase to address:** Delivery integration and security verification.

### Excessive IAM or accidental public access

**Risk:** Credentials can write arbitrary bucket data or a policy/ACL exposes all stored assets.

**Prevention:** Prefix-only least privilege; retain Block Public Access and bucket-owner-enforced ownership; use existing ESO/Secrets Manager path; grant no `PutObjectAcl` or public policy.

**Phase to address:** AWS and deployment configuration.

## Security Checklist

- [ ] Role check and CSRF test precede every mutation.
- [ ] Tests prove extension, header, and decoder disagreements are rejected.
- [ ] Tests prove SVG/GIF/HTML/polyglot-like inputs, huge byte inputs, and huge pixel inputs fail safely.
- [ ] Tests prove only server-generated raster bytes and generated object keys reach S3.
- [ ] Tests prove outsiders and wrong-family administrators cannot mutate or infer another logo.

## Sources

- https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- https://pillow.readthedocs.io/en/stable/handbook/security.html
- https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content

