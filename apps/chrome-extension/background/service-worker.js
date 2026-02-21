/**
 * Winnow Chrome Extension — Background Service Worker
 *
 * Relays messages between popup and content scripts.
 * Handles extension lifecycle events.
 */

// Listen for install/update
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("Winnow LinkedIn Sourcing extension installed");
  }
});

// Relay messages from popup to content script when needed
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "extractFromTab" && message.tabId) {
    chrome.tabs.sendMessage(
      message.tabId,
      { action: "extractProfile" },
      (response) => {
        sendResponse(response);
      }
    );
    return true; // Keep channel open for async
  }
});
