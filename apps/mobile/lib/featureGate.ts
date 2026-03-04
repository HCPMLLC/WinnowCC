import { Alert } from "react-native";

/**
 * Check if an API response indicates a feature gate (402/403/429).
 * Shows a generic alert and returns true if gated.
 */
export function handleFeatureGateResponse(res: Response): boolean {
  if (res.status === 402 || res.status === 403 || res.status === 429) {
    Alert.alert(
      "Feature Unavailable",
      "This feature is not available on your current plan.",
    );
    return true;
  }
  return false;
}
