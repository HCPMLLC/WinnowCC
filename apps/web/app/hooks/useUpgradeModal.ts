"use client";

import { useState } from "react";
import { parseApiError } from "../lib/api-error";

interface ModalState {
  open: boolean;
  featureName: string;
  message: string;
  limitReached: boolean;
}

export function useUpgradeModal() {
  const [state, setState] = useState<ModalState | null>(null);

  async function handleBillingError(
    res: Response,
    featureName: string,
  ): Promise<boolean> {
    if (res.status !== 403 && res.status !== 429) return false;
    const data = await res.json().catch(() => ({}));
    const message = parseApiError(data, "This feature requires a plan upgrade.");
    // Skip non-billing 403s (e.g. "Admin access required", "Complete onboarding first")
    if (
      res.status === 403 &&
      !(/plan|upgrade|starter|pro|tier/i.test(message))
    ) {
      return false;
    }
    setState({
      open: true,
      featureName,
      message,
      limitReached: res.status === 429,
    });
    return true;
  }

  function closeModal() {
    setState(null);
  }

  return {
    modalProps: state ?? {
      open: false,
      featureName: "",
      message: "",
      limitReached: false,
    },
    handleBillingError,
    closeModal,
  };
}
