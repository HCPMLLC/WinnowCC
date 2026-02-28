import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";

const GoldenSieveStatic = require("../assets/golden-sieve-static.png");

const GREETING =
  "Greetings. I\u2019m Sieve, your personal concierge. Ask me anything and I\u2019ll start sifting.";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function SieveScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const scrollRef = useRef<ScrollView>(null);

  // Load conversation history on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get("/api/sieve/history");
        if (res.ok) {
          const data = await res.json().catch(() => null);
          if (!data) return;
          const raw = data.messages || data;
          const history = Array.isArray(raw) ? raw : [];
          setMessages(
            history
              .filter(
                (m: any) =>
                  m && typeof m.content === "string" && typeof m.role === "string"
              )
              .map((m: any, i: number) => ({
                id: `h-${i}`,
                role: m.role as "user" | "assistant",
                content: m.content,
              }))
          );
        }
      } catch {
        // Non-critical
      }
    })();
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
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

      try {
        const recentHistory = [...messages, userMsg]
          .slice(-20)
          .map((m) => ({ role: m.role, content: m.content }));

        const res = await api.post("/api/sieve/chat", {
          message: trimmed,
          conversation_history: recentHistory,
        });

        if (res.ok) {
          const data = await res.json().catch(() => ({}));
          const responseText =
            typeof data.response === "string"
              ? data.response
              : typeof data.message === "string"
                ? data.message
                : "...";
          setMessages((prev) => [
            ...prev,
            { id: `a-${Date.now()}`, role: "assistant", content: responseText },
          ]);

          try {
            if (
              Array.isArray(data.suggested_actions) &&
              data.suggested_actions.length
            ) {
              setSuggestedActions(
                data.suggested_actions
                  .map((a: any) =>
                    typeof a === "string" ? a : a?.label || a?.message || ""
                  )
                  .filter(Boolean)
              );
            }
          } catch {
            // Non-critical
          }
        } else {
          let errorContent = "Sorry, I couldn\u2019t process that.";
          if (res.status === 403 || res.status === 429) {
            errorContent =
              "For the best experience with all features, please visit WinnowCC.ai.";
          } else {
            const err = await res.json().catch(() => ({}));
            errorContent = (err as any)?.detail || errorContent;
          }
          setMessages((prev) => [
            ...prev,
            {
              id: `e-${Date.now()}`,
              role: "assistant",
              content: errorContent,
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
        setTimeout(
          () => scrollRef.current?.scrollToEnd({ animated: true }),
          100
        );
      }
    },
    [messages, sending]
  );

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
      keyboardVerticalOffset={0}
    >
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerRow}>
          <TouchableOpacity
            style={styles.closeBtn}
            onPress={() => router.back()}
            hitSlop={8}
          >
            <Ionicons name="close" size={22} color="#E8C84A" />
          </TouchableOpacity>
          <View style={styles.headerLeft}>
            <Text style={styles.headerTitle}>
              Sieve <Text style={styles.headerPronunciation}>/siv/</Text>
            </Text>
            <Text style={styles.headerSubtitle}>Your Personal Concierge</Text>
          </View>
          <Image
            source={GoldenSieveStatic}
            style={styles.headerLogo}
            resizeMode="contain"
          />
          <View style={styles.headerRight}>
            <TouchableOpacity style={styles.headerBtn} onPress={handleClear}>
              <Ionicons
                name="trash-outline"
                size={14}
                color="rgba(232, 200, 74, 0.7)"
              />
            </TouchableOpacity>
            <View style={styles.onlineRow}>
              <View style={styles.onlineDot} />
              <Text style={styles.onlineText}>Online</Text>
            </View>
          </View>
        </View>
      </View>

      {/* Messages */}
      <ScrollView
        ref={scrollRef}
        style={styles.messageArea}
        contentContainerStyle={styles.messagesContent}
        onContentSizeChange={() =>
          scrollRef.current?.scrollToEnd({ animated: true })
        }
      >
        {messages.length === 0 && (
          <View style={styles.greetingBubble}>
            <Text style={styles.greetingText}>{GREETING}</Text>
          </View>
        )}
        {messages.map((msg) => (
          <View
            key={msg.id}
            style={[
              styles.msgRow,
              msg.role === "user"
                ? styles.msgRowUser
                : styles.msgRowAssistant,
            ]}
          >
            <View
              style={[
                styles.msgBubble,
                msg.role === "user"
                  ? styles.userBubble
                  : styles.assistantBubble,
              ]}
            >
              <Text
                style={[
                  styles.msgText,
                  msg.role === "user"
                    ? styles.userText
                    : styles.assistantText,
                ]}
              >
                {msg.content}
              </Text>
            </View>
          </View>
        ))}
        {sending && (
          <View style={[styles.msgRow, styles.msgRowAssistant]}>
            <View style={[styles.msgBubble, styles.assistantBubble]}>
              <View style={styles.typingDots}>
                {[0, 1, 2].map((i) => (
                  <View
                    key={i}
                    style={[
                      styles.typingDot,
                      { opacity: 0.4 + i * 0.2 },
                    ]}
                  />
                ))}
              </View>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Suggested actions */}
      {suggestedActions.length > 0 && !sending && messages.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.suggestionsRow}
        >
          {suggestedActions.map((action, i) => (
            <TouchableOpacity
              key={i}
              style={styles.suggestionChip}
              onPress={() => sendMessage(action)}
            >
              <Text style={styles.suggestionText} numberOfLines={1}>{action}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* Input */}
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
          <Text
            style={[
              styles.sendArrow,
              !canSend && styles.sendArrowDisabled,
            ]}
          >
            {"\u2191"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FAF6EE" },

  // Header
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "#1B3025",
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.08)",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  headerLeft: { flex: 1 },
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
  headerLogo: { width: 120, height: 60, marginHorizontal: 12 },
  headerRight: { flex: 1, alignItems: "flex-end" },
  headerBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.08)",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 6,
  },
  onlineRow: { flexDirection: "row", alignItems: "center" },
  onlineDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: "#5CB87A",
    marginRight: 5,
  },
  onlineText: { fontSize: 11, color: "#FFFFFF" },

  // Messages
  messageArea: { flex: 1 },
  messagesContent: { padding: 16, paddingBottom: 8, flexGrow: 1 },
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
    marginBottom: 12,
    shadowColor: "#8B6318",
    shadowOpacity: 0.06,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  greetingText: { fontSize: 14, lineHeight: 22, color: "#3E3525" },

  // Message bubbles
  msgRow: { marginBottom: 10 },
  msgRowUser: { alignItems: "flex-end" },
  msgRowAssistant: { alignItems: "flex-start" },
  msgBubble: { maxWidth: "82%", paddingHorizontal: 14, paddingVertical: 10 },
  userBubble: {
    backgroundColor: "#1B3025",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 4,
    shadowColor: "#1B3025",
    shadowOpacity: 0.15,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  assistantBubble: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 4,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(196, 149, 40, 0.12)",
    shadowColor: "#8B6318",
    shadowOpacity: 0.06,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  msgText: { fontSize: 14, lineHeight: 21 },
  userText: { color: "#F0E8D0" },
  assistantText: { color: "#3E3525" },

  // Typing indicator
  typingDots: { flexDirection: "row", alignItems: "center" },
  typingDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: "#C49528",
    marginHorizontal: 2.5,
  },

  // Suggestions
  suggestionsRow: { paddingHorizontal: 12, paddingVertical: 4 },
  suggestionChip: {
    borderWidth: 1,
    borderColor: "#E8C84A",
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 3,
    backgroundColor: "transparent",
    marginRight: 5,
  },
  suggestionText: { fontSize: 11, color: "#3E3525" },

  // Input bar
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
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
    marginRight: 8,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#1B3025",
    justifyContent: "center",
    alignItems: "center",
  },
  sendBtnDisabled: { backgroundColor: "rgba(196, 149, 40, 0.12)" },
  sendArrow: { fontSize: 18, color: "#E8C84A", fontWeight: "700" },
  sendArrowDisabled: { color: "rgba(62, 53, 37, 0.3)" },
});
