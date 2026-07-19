#!/usr/bin/env bash
# Provision or verify one least-privilege logo-storage identity per environment.
# This script never prints access-key secrets or writes them to disk.
set -Eeuo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: provision.sh <dev|prd>

Requires authenticated aws and kubectl CLIs plus jq. Set LOGO_STORAGE_NAMESPACE
when the release is not in the default namespace (default: family-pickem).
EOF
  exit 64
}

environment=${1:-}
[[ "$environment" == "dev" || "$environment" == "prd" ]] || usage

for command in aws kubectl jq; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 69; }
done

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
bucket=family-pickem
region=us-east-1
prefix=family-logos
user_name="family-pickem-${environment}-logo-storage"
policy_name="${user_name}-objects-only"
secret_id="family-pickem/${environment}/family-logo-storage"
namespace=${LOGO_STORAGE_NAMESPACE:-family-pickem}
release_name="family-pickem-${environment}"
external_secret="${release_name}-logo-storage"
deployment="${release_name}"

old_secret_json=''
old_key_id=''
replacement_key_id=''
replacement_key_secret=''
secret_was_created=false
secret_was_updated=false

redact_id() {
  local value=${1:-}
  if [[ -z "$value" ]]; then
    printf '<none>'
  else
    printf '***%s' "${value: -4}"
  fi
}

rollback() {
  local status=$?
  trap - ERR
  if [[ -n "$replacement_key_id" ]]; then
    echo "Rolling back unadopted replacement key $(redact_id "$replacement_key_id")" >&2
    if [[ "$secret_was_updated" == true && -n "$old_secret_json" ]]; then
      aws secretsmanager put-secret-value --secret-id "$secret_id" --secret-string "$old_secret_json" >/dev/null || true
    elif [[ "$secret_was_created" == true ]]; then
      aws secretsmanager delete-secret --secret-id "$secret_id" --force-delete-without-recovery >/dev/null || true
    fi
    aws iam update-access-key --user-name "$user_name" --access-key-id "$replacement_key_id" --status Inactive >/dev/null || true
    aws iam delete-access-key --user-name "$user_name" --access-key-id "$replacement_key_id" >/dev/null || true
  fi
  echo "Provisioning failed; no replacement credential was adopted (exit $status)." >&2
  exit "$status"
}
trap rollback ERR

assert_bucket_posture() {
  local location public_access ownership encryption policy_status
  location=$(aws s3api get-bucket-location --bucket "$bucket" --query LocationConstraint --output text)
  [[ "$location" == "$region" ]] || { echo "Unsafe bucket region: expected $region, got $location" >&2; exit 1; }

  public_access=$(aws s3api get-public-access-block --bucket "$bucket" --query PublicAccessBlockConfiguration --output json)
  jq -e '.BlockPublicAcls and .IgnorePublicAcls and .BlockPublicPolicy and .RestrictPublicBuckets' <<<"$public_access" >/dev/null \
    || { echo "Bucket Block Public Access is incomplete; refusing to continue." >&2; exit 1; }

  ownership=$(aws s3api get-bucket-ownership-controls --bucket "$bucket" --query 'OwnershipControls.Rules[0].ObjectOwnership' --output text)
  [[ "$ownership" == "BucketOwnerEnforced" ]] \
    || { echo "Bucket ownership is not BucketOwnerEnforced; refusing to continue." >&2; exit 1; }

  encryption=$(aws s3api get-bucket-encryption --bucket "$bucket" --query 'ServerSideEncryptionConfiguration.Rules[0]' --output json)
  jq -e '.ApplyServerSideEncryptionByDefault.SSEAlgorithm == "AES256" or .ApplyServerSideEncryptionByDefault.SSEAlgorithm == "aws:kms"' <<<"$encryption" >/dev/null \
    || { echo "Bucket default encryption is missing or invalid; refusing to continue." >&2; exit 1; }

  policy_status=$(aws s3api get-bucket-policy-status --bucket "$bucket" --query PolicyStatus.IsPublic --output text)
  [[ "$policy_status" == "False" ]] \
    || { echo "Bucket policy is public; refusing to continue." >&2; exit 1; }
}

upsert_policy() {
  local account_id policy_arn version_id old_versions version_count
  account_id=$(aws sts get-caller-identity --query Account --output text)
  policy_arn="arn:aws:iam::${account_id}:policy/${policy_name}"
  if aws iam get-policy --policy-arn "$policy_arn" >/dev/null 2>&1; then
    version_count=$(aws iam list-policy-versions --policy-arn "$policy_arn" --query 'length(Versions)' --output text)
    if [[ "$version_count" -ge 5 ]]; then
      old_version=$(aws iam list-policy-versions --policy-arn "$policy_arn" --query 'Versions[?IsDefaultVersion==`false`]|[0].VersionId' --output text)
      aws iam delete-policy-version --policy-arn "$policy_arn" --version-id "$old_version" >/dev/null
    fi
    version_id=$(aws iam create-policy-version --policy-arn "$policy_arn" --policy-document "file://${script_dir}/iam-policy.json" --set-as-default --query PolicyVersion.VersionId --output text)
    old_versions=$(aws iam list-policy-versions --policy-arn "$policy_arn" --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text)
    for old_version in $old_versions; do
      aws iam delete-policy-version --policy-arn "$policy_arn" --version-id "$old_version" >/dev/null
    done
    echo "Updated policy version $(redact_id "$version_id")." >&2
  else
    aws iam create-policy --policy-name "$policy_name" --policy-document "file://${script_dir}/iam-policy.json" >/dev/null
    echo "Created constrained IAM policy." >&2
  fi
  printf '%s' "$policy_arn"
}

simulate_policy() {
  local principal_arn target="arn:aws:s3:::${bucket}/${prefix}/verification-object.webp"
  principal_arn=$(aws iam get-user --user-name "$user_name" --query 'User.Arn' --output text)
  assert_decision() {
    local expected=$1 action=$2 resource=$3 decision
    decision=$(aws iam simulate-principal-policy --policy-source-arn "$principal_arn" --action-names "$action" --resource-arns "$resource" --query 'EvaluationResults[0].EvalDecision' --output text)
    [[ "$decision" == "$expected" ]] || { echo "IAM simulation expected $expected for $action, got $decision" >&2; exit 1; }
  }
  for action in s3:GetObject s3:PutObject s3:DeleteObject; do
    assert_decision allowed "$action" "$target"
  done
  assert_decision implicitDeny s3:GetObject "arn:aws:s3:::${bucket}/other-prefix/private.webp"
  assert_decision implicitDeny s3:GetObject "arn:aws:s3:::${bucket}/family-logos"
  assert_decision implicitDeny s3:PutObjectAcl "$target"
  assert_decision implicitDeny s3:ListBucket "arn:aws:s3:::${bucket}"
  assert_decision implicitDeny s3:PutBucketPolicy "arn:aws:s3:::${bucket}"
}

assert_bucket_posture
aws iam get-user --user-name "$user_name" >/dev/null 2>&1 || aws iam create-user --user-name "$user_name" >/dev/null
policy_arn=$(upsert_policy)
aws iam attach-user-policy --user-name "$user_name" --policy-arn "$policy_arn"
simulate_policy

if aws secretsmanager describe-secret --secret-id "$secret_id" >/dev/null 2>&1; then
  old_secret_json=$(aws secretsmanager get-secret-value --secret-id "$secret_id" --query SecretString --output text)
  old_key_id=$(jq -r '.FAMILY_LOGO_AWS_ACCESS_KEY_ID // empty' <<<"$old_secret_json")
fi

active_key_ids=$(aws iam list-access-keys --user-name "$user_name" --query 'AccessKeyMetadata[?Status==`Active`].AccessKeyId' --output text)
if [[ -n "$old_key_id" ]] && grep -qx "$old_key_id" <<<"$active_key_ids"; then
  echo "Reusing active dedicated key $(redact_id "$old_key_id"); no credential rotation is needed."
else
  key_json=$(aws iam create-access-key --user-name "$user_name" --output json)
  replacement_key_id=$(jq -r '.AccessKey.AccessKeyId' <<<"$key_json")
  replacement_key_secret=$(jq -r '.AccessKey.SecretAccessKey' <<<"$key_json")
  new_secret_json=$(jq -cn \
    --arg key "$replacement_key_id" \
    --arg secret "$replacement_key_secret" \
    --arg bucket "$bucket" \
    --arg region "$region" \
    '{FAMILY_LOGO_STORAGE_BUCKET_NAME:$bucket, FAMILY_LOGO_AWS_S3_REGION_NAME:$region, FAMILY_LOGO_AWS_ACCESS_KEY_ID:$key, FAMILY_LOGO_AWS_SECRET_ACCESS_KEY:$secret, FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE:"300"}')
  if [[ -n "$old_secret_json" ]]; then
    aws secretsmanager put-secret-value --secret-id "$secret_id" --secret-string "$new_secret_json" >/dev/null
    secret_was_updated=true
  else
    aws secretsmanager create-secret --name "$secret_id" --secret-string "$new_secret_json" >/dev/null
    secret_was_created=true
  fi
  unset key_json new_secret_json replacement_key_secret

  kubectl -n "$namespace" annotate externalsecret "$external_secret" "force-sync=$(date +%s)" --overwrite
  kubectl -n "$namespace" wait --for=condition=Ready "externalsecret/${external_secret}" --timeout=2m
  kubectl -n "$namespace" rollout status "deployment/${deployment}" --timeout=5m

  # Retire only the previously adopted key after ESO and the web/migration pod rollout prove adoption.
  if [[ -n "$old_key_id" ]]; then
    aws iam update-access-key --user-name "$user_name" --access-key-id "$old_key_id" --status Inactive
    aws iam delete-access-key --user-name "$user_name" --access-key-id "$old_key_id"
  fi
  replacement_key_id=''
  echo "Dedicated logo credential rotation completed."
fi

echo "Logo storage identity and private-bucket posture verified for ${environment}."
