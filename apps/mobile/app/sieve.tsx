import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  Image,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";
import SieveChatBubble from "../components/SieveChatBubble";

const GoldenSieveStatic = require("../assets/golden-sieve-static.png");

const GREETING =
  "Greetings. I\u2019m Sieve, your personal concierge. Ask me anything and I\u2019ll start sifting.";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

class SieveErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: string }
> {
  state = { hasError: false, error: "" };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: "#FAF6EE" }}>
          <Text style={{ fontSize: 16, fontWeight: "600", color: "#3E3525", marginBottom: 8 }}>
            Sieve ran into an issue
          </Text>
          <Text style={{ fontSize: 13, color: "#9CA3AF", textAlign: "center", marginBottom: 16 }}>
            {this.state.error}
          </Text>
          <TouchableOpacity
            onPress={() => this.setState({ hasError: false, error: "" })}
            style={{ paddingHorizontal: 20, paddingVertical: 10, backgroundColor: "#1B3025", borderRadius: 8 }}
          >
            <Text style={{ color: "#E8C84A", fontWeight: "600" }}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}

export default function SieveScreen() {
  return (
    <SieveErrorBoundary>
      <SieveScreenInner />
    </SieveErrorBoundary>
  );
}

function SieveScreenInner() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const flatListRef = useRef<FlatList>(null);

  const loadHistory = useCallback(async () => {
    try {
      const res = await api.get("/api/sieve/history");
      if (res.ok) {
        const data = await res.json();
        const raw = data.messages || data;
        const history = Array.isArray(raw) ? raw : [];
        setMessages(
          history
            .filter((m: any) => m && typeof m.content === "string" && typeof m.role === "string")
            .map((m: any, i: number) => ({
              id: `h-${i}`,
              role: m.role as "user" | "assistant",
              content: m.content,
            }))
        );
      }
    } catch {
      // Non-critical — history just won't load
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    setSuggestedActions([]);

    const recentHistory = [...messages, userMsg]
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const res = await api.post("/api/sieve/chat", {
        message: trimmed,
        conversation_history: recentHistory,
      });

      if (res.ok) {
        const data = await res.json();
        const responseText =
          (typeof data.response === "string" ? data.response : null) ||
          (typeof data.message === "string" ? data.message : null) ||
          "...";
        const assistantMsg: Message = {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: responseText,
        };
        setMessages((prev) => [...prev, assistantMsg]);

        try {
          if (Array.isArray(data.suggested_actions) && data.suggested_actions.length) {
            setSuggestedActions(
              data.suggested_actions
                .map((a: any) => (typeof a === "string" ? a : a?.label || a?.message || ""))
                .filter(Boolean)
            );
          }
        } catch {
          // Non-critical
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}`,
            role: "assistant",
            content: (err as any)?.detail || "Sorry, I couldn\u2019t process that.",
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          content: "Could not connect to server. Please try again.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleClear() {
    Alert.alert("Clear Chat", "Delete all Sieve conversation history?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Clear",
        style: "destructive",
        onPress: async () => {
          try {
            await api.delete("/api/sieve/history");
            setMessages([]);
            setSuggestedActions([]);
          } catch {
            Alert.alert("Error", "Could not clear history.");
          }
        },
      },
    ]);
  }

  const canSend = input.trim().length > 0 && !sending;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      {/* ── Header ── */}
      <View style={styles.header}>
        <View style={styles.headerGrid}>
          {/* Left: Title */}
          <View style={styles.headerLeft}>
            <Text style={styles.headerTitle}>
              Sieve{" "}
              <Text style={styles.headerPronunciation}>/siv/</Text>
            </Text>
            <Text style={styles.headerSubtitle}>Your Personal Concierge</Text>
          </View>

          {/* Center: Logo */}
          <View style={styles.headerCenter}>
            <Image
              source={GoldenSieveStatic}
              style={{ width: 120, height: 60 }}
              resizeMode="contain"
            />
          </View>

          {/* Right: Actions */}
          <View style={styles.headerRight}>
            <View style={styles.headerActions}>
              <TouchableOpacity
                style={styles.headerBtn}
                onPress={handleClear}
              >
                <Ionicons name="trash-outline" size={14} color="rgba(232, 200, 74, 0.7)" />
              </TouchableOpacity>
            </View>
            <View style={styles.onlineRow}>
              <View style={styles.onlineDot} />
              <Text style={styles.onlineText}>Online</Text>
            </View>
          </View>
        </View>
      </View>

      {/* ── Messages ── */}
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() =>
          flatListRef.current?.scrollToEnd({ animated: true })
        }
        ListEmptyComponent={
          <View style={styles.greetingRow}>
            <View style={styles.greetingBubble}>
              <Text style={styles.greetingText}>{GREETING}</Text>
            </View>
          </View>
        }
        renderItem={({ item }) => (
          <SieveChatBubble role={item.role} content={item.content} />
        )}
      />

      {/* ── Typing indicator ── */}
      {sending && (
        <View style={styles.typingRow}>
          <View style={styles.typingBubble}>
            <View style={styles.typingDots}>
              {[0, 1, 2].map((i) => (
                <View key={i} style={[styles.typingDot, { opacity: 0.4 + (i * 0.2) }]} />
              ))}
            </View>
          </View>
        </View>
      )}

      {/* ── Suggested actions ── */}
      {suggestedActions.length > 0 && !sending && messages.length > 0 && (
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={suggestedActions}
          keyExtractor={(_, i) => String(i)}
          contentContainerStyle={styles.suggestionsRow}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.suggestionChip}
              onPress={() => sendMessage(item)}
            >
              <Text style={styles.suggestionText}>{item}</Text>
            </TouchableOpacity>
          )}
        />
      )}

      {/* ── Input bar ── */}
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Type a message\u2026"
          placeholderTextColor="#9CA3AF"
          multiline
          maxLength={2000}
          editable={!sending}
        />
        <TouchableOpacity
          style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
          onPress={() => sendMessage(input)}
          disabled={!canSend}
        >
          <Text style={[styles.sendArrow, !canSend && styles.sendArrowDisabled]}>
            {"\u2191"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FAF6EE",
  },

  // ── Header ──
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "#1B3025",
    overflow: "visible",
    zIndex: 10,
  },
  headerGrid: {
    flexDirection: "row",
    alignItems: "center",
    overflow: "visible",
  },
  headerLeft: {
    flex: 1,
    minWidth: 0,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#E8C84A",
    letterSpacing: 0.5,
    fontFamily: Platform.OS === "ios" ? "Georgia" : "serif",
  },
  headerPronunciation: {
    fontWeight: "400",
    fontStyle: "italic",
    fontSize: 13,
  },
  headerSubtitle: {
    fontSize: 11,
    color: "#FFFFFF",
    letterSpacing: 0.5,
    marginTop: 2,
  },
  headerCenter: {
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: 12,
    overflow: "visible",
    zIndex: 10,
  },
  headerRight: {
    flex: 1,
    alignItems: "flex-end",
    gap: 6,
  },
  headerActions: {
    flexDirection: "row",
    gap: 4,
  },
  headerBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.08)",
    justifyContent: "center",
    alignItems: "center",
  },
  onlineRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  onlineDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: "#5CB87A",
    shadowColor: "#5CB87A",
    shadowOpacity: 0.5,
    shadowRadius: 4,
    elevation: 2,
  },
  onlineText: {
    fontSize: 11,
    color: "#FFFFFF",
  },

  // ── Messages ──
  messageList: {
    padding: 16,
    paddingBottom: 8,
    flexGrow: 1,
  },
  greetingRow: {
    marginBottom: 12,
  },
  greetingBubble: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "rgba(196, 149, 40, 0.15)",
    borderTopLeftRadius: 4,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    padding: 12,
    paddingHorizontal: 16,
    maxWidth: "88%",
    shadowColor: "#8B6318",
    shadowOpacity: 0.06,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  greetingText: {
    fontSize: 14,
    lineHeight: 22,
    color: "#3E3525",
  },

  // ── Typing ──
  typingRow: {
    paddingHorizontal: 16,
    paddingBottom: 4,
  },
  typingBubble: {
    alignSelf: "flex-start",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "rgba(196, 149, 40, 0.12)",
    borderTopLeftRadius: 4,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    paddingHorizontal: 18,
    paddingVertical: 12,
  },
  typingDots: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  typingDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: "#C49528",
  },

  // ── Suggestions ──
  suggestionsRow: {
    paddingHorizontal: 16,
    paddingBottom: 8,
    gap: 6,
  },
  suggestionChip: {
    borderWidth: 1,
    borderColor: "#E8C84A",
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 6,
    backgroundColor: "transparent",
  },
  suggestionText: {
    fontSize: 12,
    color: "#3E3525",
  },

  // ── Input bar ──
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "#FFFDF7",
    borderTopWidth: 1,
    borderTopColor: "rgba(196, 149, 40, 0.12)",
  },
  input: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(196, 149, 40, 0.2)",
    backgroundColor: "#FFFFFF",
    fontSize: 14,
    color: "#3E3525",
    maxHeight: 100,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#1B3025",
    justifyContent: "center",
    alignItems: "center",
  },
  sendBtnDisabled: {
    backgroundColor: "rgba(196, 149, 40, 0.12)",
  },
  sendArrow: {
    fontSize: 18,
    color: "#E8C84A",
    fontWeight: "700",
  },
  sendArrowDisabled: {
    color: "rgba(62, 53, 37, 0.3)",
  },
});
