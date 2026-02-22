import { useState, useRef, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";

const GREETING =
  "Greetings. I\u2019m Sieve, your personal concierge. Ask me anything and I\u2019ll start sifting.";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function SieveScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

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

      try {
        const recentHistory = [...messages, userMsg]
          .slice(-20)
          .map((m) => ({ role: m.role, content: m.content }));

        const res = await api.post("/api/sieve/chat", {
          message: trimmed,
          conversation_history: recentHistory,
        });

        if (res.ok) {
          const data = await res.json();
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
        setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
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
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.headerTitle}>Sieve</Text>
            <Text style={styles.headerSubtitle}>Your Personal Concierge</Text>
          </View>
          <TouchableOpacity style={styles.headerBtn} onPress={handleClear}>
            <Ionicons name="trash-outline" size={16} color="rgba(232, 200, 74, 0.7)" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Messages */}
      <ScrollView
        ref={scrollRef}
        style={styles.messages}
        contentContainerStyle={styles.messagesContent}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
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
              msg.role === "user" ? styles.msgRowUser : styles.msgRowAssistant,
            ]}
          >
            <View
              style={[
                styles.msgBubble,
                msg.role === "user" ? styles.userBubble : styles.assistantBubble,
              ]}
            >
              <Text
                style={[
                  styles.msgText,
                  msg.role === "user" ? styles.userText : styles.assistantText,
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
              <Text style={styles.assistantText}>Thinking...</Text>
            </View>
          </View>
        )}
      </ScrollView>

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
          <Text style={[styles.sendArrow, !canSend && styles.sendArrowDisabled]}>
            {"\u2191"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FAF6EE" },

  header: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: "#1B3025",
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#E8C84A",
  },
  headerSubtitle: {
    fontSize: 11,
    color: "#FFFFFF",
    marginTop: 2,
  },
  headerBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.08)",
    justifyContent: "center",
    alignItems: "center",
  },

  messages: { flex: 1 },
  messagesContent: { padding: 16, paddingBottom: 8 },

  greetingBubble: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "rgba(196, 149, 40, 0.15)",
    borderRadius: 16,
    borderTopLeftRadius: 4,
    padding: 14,
    maxWidth: "88%",
    marginBottom: 12,
  },
  greetingText: { fontSize: 14, lineHeight: 22, color: "#3E3525" },

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
  },
  assistantBubble: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 4,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(196, 149, 40, 0.12)",
  },
  msgText: { fontSize: 14, lineHeight: 21 },
  userText: { color: "#F0E8D0" },
  assistantText: { color: "#3E3525" },

  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "#FFFDF7",
    borderTopWidth: 1,
    borderTopColor: "rgba(196, 149, 40, 0.12)",
    gap: 8,
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
  sendBtnDisabled: { backgroundColor: "rgba(196, 149, 40, 0.12)" },
  sendArrow: { fontSize: 18, color: "#E8C84A", fontWeight: "700" },
  sendArrowDisabled: { color: "rgba(62, 53, 37, 0.3)" },
});
