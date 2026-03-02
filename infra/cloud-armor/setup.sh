#!/usr/bin/env bash
# Cloud Armor WAF setup for Winnow API
# Run manually after GCP project is configured.
# Requires: gcloud CLI authenticated with appropriate permissions.
#
# Usage: bash infra/cloud-armor/setup.sh <PROJECT_ID> <BACKEND_SERVICE_NAME>

set -euo pipefail

PROJECT_ID="${1:?Usage: setup.sh <PROJECT_ID> <BACKEND_SERVICE_NAME>}"
BACKEND_SERVICE="${2:?Usage: setup.sh <PROJECT_ID> <BACKEND_SERVICE_NAME>}"
POLICY_NAME="winnow-waf-policy"

echo "=== Creating Cloud Armor security policy: ${POLICY_NAME} ==="

gcloud compute security-policies create "${POLICY_NAME}" \
  --project="${PROJECT_ID}" \
  --description="Winnow API WAF policy"

# --- OWASP Top 10 preconfigured rules ---
echo "=== Adding OWASP ModSecurity CRS rules ==="

# SQL injection
gcloud compute security-policies rules create 1000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
  --action=deny-403 \
  --description="Block SQL injection"

# Cross-site scripting
gcloud compute security-policies rules create 1001 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
  --action=deny-403 \
  --description="Block XSS"

# Remote file inclusion
gcloud compute security-policies rules create 1002 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('rfi-v33-stable')" \
  --action=deny-403 \
  --description="Block remote file inclusion"

# Local file inclusion
gcloud compute security-policies rules create 1003 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('lfi-v33-stable')" \
  --action=deny-403 \
  --description="Block local file inclusion"

# Remote code execution
gcloud compute security-policies rules create 1004 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('rce-v33-stable')" \
  --action=deny-403 \
  --description="Block remote code execution"

# Scanner detection
gcloud compute security-policies rules create 1005 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('scannerdetection-v33-stable')" \
  --action=deny-403 \
  --description="Block scanners"

# Protocol attack
gcloud compute security-policies rules create 1006 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('protocolattack-v33-stable')" \
  --action=deny-403 \
  --description="Block protocol attacks"

# Session fixation
gcloud compute security-policies rules create 1007 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('sessionfixation-v33-stable')" \
  --action=deny-403 \
  --description="Block session fixation"

# --- Edge rate limiting ---
echo "=== Adding edge rate limiting rules ==="

# Global rate limit: 300 requests per minute per IP
gcloud compute security-policies rules create 2000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --src-ip-ranges="*" \
  --action=throttle \
  --rate-limit-threshold-count=300 \
  --rate-limit-threshold-interval-sec=60 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Global rate limit: 300 req/min per IP"

# Auth endpoint rate limit: 20 requests per minute per IP
gcloud compute security-policies rules create 2001 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="request.path.matches('/api/auth/.*')" \
  --action=throttle \
  --rate-limit-threshold-count=20 \
  --rate-limit-threshold-interval-sec=60 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Auth rate limit: 20 req/min per IP"

# --- Attach policy to backend service ---
echo "=== Attaching policy to backend service: ${BACKEND_SERVICE} ==="

gcloud compute backend-services update "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --global

echo "=== Cloud Armor WAF setup complete ==="
echo "Policy: ${POLICY_NAME}"
echo "Backend: ${BACKEND_SERVICE}"
echo ""
echo "View policy: gcloud compute security-policies describe ${POLICY_NAME} --project=${PROJECT_ID}"
echo "View rules:  gcloud compute security-policies rules list --security-policy=${POLICY_NAME} --project=${PROJECT_ID}"
