#!/usr/bin/env bash
# Cloud Monitoring alerts for Cloud Armor WAF blocks
# Run manually after setup.sh has been executed.
#
# Usage: bash infra/cloud-armor/alerts.sh <PROJECT_ID> <NOTIFICATION_CHANNEL_ID>

set -euo pipefail

PROJECT_ID="${1:?Usage: alerts.sh <PROJECT_ID> <NOTIFICATION_CHANNEL_ID>}"
CHANNEL_ID="${2:?Usage: alerts.sh <PROJECT_ID> <NOTIFICATION_CHANNEL_ID>}"

echo "=== Creating Cloud Armor WAF block alert ==="

# Alert when WAF blocks exceed 100 in 5 minutes
gcloud alpha monitoring policies create \
  --project="${PROJECT_ID}" \
  --display-name="Cloud Armor WAF - High Block Rate" \
  --condition-display-name="WAF blocks > 100 in 5 min" \
  --condition-filter='resource.type="network_security_policy" AND metric.type="networksecurity.googleapis.com/https/request_count" AND metric.labels.blocked="true"' \
  --condition-threshold-value=100 \
  --condition-threshold-duration=300s \
  --condition-threshold-comparison=COMPARISON_GT \
  --aggregation-alignment-period=300s \
  --aggregation-per-series-aligner=ALIGN_RATE \
  --notification-channels="${CHANNEL_ID}" \
  --documentation='Cloud Armor WAF is blocking a high volume of requests. Check security policy logs for attack patterns. Dashboard: https://console.cloud.google.com/net-security/securitypolicies/list?project='"${PROJECT_ID}"

echo "=== Creating auth endpoint abuse alert ==="

# Alert on high 429 rate on auth endpoints
gcloud alpha monitoring policies create \
  --project="${PROJECT_ID}" \
  --display-name="Auth Endpoint - Rate Limit Exceeded" \
  --condition-display-name="Auth 429s > 50 in 5 min" \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code="429"' \
  --condition-threshold-value=50 \
  --condition-threshold-duration=300s \
  --condition-threshold-comparison=COMPARISON_GT \
  --aggregation-alignment-period=300s \
  --aggregation-per-series-aligner=ALIGN_RATE \
  --notification-channels="${CHANNEL_ID}" \
  --documentation='High rate of 429 responses on auth endpoints indicates possible credential stuffing or brute force attack.'

echo "=== Alerts created ==="
echo "View alerts: https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
