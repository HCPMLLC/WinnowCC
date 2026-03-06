import { Alert } from "react-native";

/**
 * Check if an API response indicates a feature gate (402/403/429).
 * Parses the response body for a specific error message and shows an alert.
 * Returns true if gated.
 */
export async function handleFeatureGateResponse(res: Response): Promise<boolean> {
  if (res.status === 402 || res.status === 403 || res.status === 429) {
    let message = "This feature is not available on your current plan.";
    try {
      const body = await res.clone().json();
      if (body?.detail && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Use default message
    }

    const title = res.status === 429 ? "Limit Reached" : "Upgrade Required";
    Alert.alert(title, message);
    return true;
  }
  return false;
}
