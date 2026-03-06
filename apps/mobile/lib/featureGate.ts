import { Alert } from "react-native";

const BILLING_PATTERN = /upgrade|subscribe|plan|tier|billing|pricing|payment|checkout|purchase/i;
const NEUTRAL_MESSAGE = "This feature is not currently available.";

/**
 * Sanitize a server message to strip any billing/upgrade language
 * that would violate Apple App Store commission-exemption rules.
 */
export function sanitizeMessage(msg: string): string {
  return BILLING_PATTERN.test(msg) ? NEUTRAL_MESSAGE : msg;
}

/**
 * Check if an API response indicates a feature gate (402/403/429).
 * Parses the response body for a specific error message and shows an alert.
 * Returns true if the feature is unavailable.
 */
export async function handleFeatureGateResponse(res: Response): Promise<boolean> {
  if (res.status === 402 || res.status === 403 || res.status === 429) {
    let message = NEUTRAL_MESSAGE;
    try {
      const body = await res.clone().json();
      if (body?.detail && typeof body.detail === "string") {
        message = sanitizeMessage(body.detail);
      }
    } catch {
      // Use default message
    }

    Alert.alert("Unavailable", message);
    return true;
  }
  return false;
}
