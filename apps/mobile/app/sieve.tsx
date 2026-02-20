import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";
import SieveChatBubble from "../components/SieveChatBubble";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface SuggestedAction {
  label: string;
  message: string;
}

export default function SieveScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestedActions, setSuggestedActions] = useState<SuggestedAction[]>(
    [],
  );
  const flatListRef = useRef<FlatList>(null);

  const loadHistory = useCallback(async () => {
    try {
      const res = await api.get("/api/sieve/history");
      if (res.ok) {
        const data = await res.json();
        const history = (data.messages || data || []) as Array<{
          role: string;
          content: string;
        }>;
        setMessages(
          history.map((m, i) => ({
            id: String(i),
            role: m.role as "user" | "assistant",
            content: m.content,
          })),
        );
      }
    } catch {
      // Non-critical — start fresh
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

    // Build conversation history (last 20 messages)
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
        const assistantMsg: Message = {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: data.response || data.message || "...",
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (data.suggested_actions?.length) {
          setSuggestedActions(
            data.suggested_actions.map((a: any) => ({
              label: a.label || a,
              message: a.message || a.label || a,
            })),
          );
        }
      } else {
        const err = await res.json().catch(() => ({}));
        const errMsg: Message = {
          id: `e-${Date.now()}`,
          role: "assistant",
          content:
            (err as any).detail || "Sorry, I couldn't process that request.",
        };
        setMessages((prev) => [...prev, errMsg]);
      }
    } catch {
      const errMsg: Message = {
        id: `e-${Date.now()}`,
        role: "assistant",
        content: "Could not connect to server. Please try again.",
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setSending(false);
    }
  }

  function handleClear() {
    Alert.alert(
      "Clear Chat",
      "Delete all Sieve conversation history?",
      [
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
      ],
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      {/* Header actions */}
      <View style={styles.headerBar}>
        <Text style={styles.headerTitle}>Sieve</Text>
        <TouchableOpacity onPress={handleClear}>
          <Ionicons name="trash-outline" size={20} color={colors.gray500} />
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() =>
          flatListRef.current?.scrollToEnd({ animated: true })
        }
        ListEmptyComponent={
          <View style={styles.welcome}>
            <Ionicons
              name="chatbubble-ellipses"
              size={48}
              color={colors.sage}
            />
            <Text style={styles.welcomeTitle}>Hi, I'm Sieve!</Text>
            <Text style={styles.welcomeText}>
              Your AI career concierge. Ask me about your matches, resume tips,
              interview prep, or career strategy.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <SieveChatBubble role={item.role} content={item.content} />
        )}
      />

      {/* Typing indicator */}
      {sending && (
        <View style={styles.typingRow}>
          <View style={styles.typingBubble}>
            <Text style={styles.typingDots}>...</Text>
          </View>
        </View>
      )}

      {/* Suggested actions */}
      {suggestedActions.length > 0 && (
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={suggestedActions}
          keyExtractor={(_, i) => String(i)}
          contentContainerStyle={styles.suggestionsRow}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.suggestionChip}
              onPress={() => sendMessage(item.message)}
            >
              <Text style={styles.suggestionText}>{item.label}</Text>
            </TouchableOpacity>
          )}
        />
      )}

      {/* Input */}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Ask Sieve anything..."
          placeholderTextColor={colors.gray400}
          multiline
          maxLength={2000}
          editable={!sending}
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!input.trim() || sending) && styles.sendBtnDisabled]}
          onPress={() => sendMessage(input)}
          disabled={!input.trim() || sending}
        >
          <Ionicons
            name="send"
            size={20}
            color={input.trim() && !sending ? colors.primary : colors.gray400}
          />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  headerBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
    backgroundColor: colors.white,
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
  },
  messageList: {
    padding: spacing.md,
    paddingBottom: spacing.sm,
    flexGrow: 1,
  },
  welcome: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.lg,
  },
  welcomeTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  welcomeText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    textAlign: "center",
    marginTop: spacing.sm,
    lineHeight: 20,
  },
  typingRow: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.xs,
  },
  typingBubble: {
    alignSelf: "flex-start",
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  typingDots: {
    fontSize: fontSize.xl,
    color: colors.gray400,
    letterSpacing: 4,
  },
  suggestionsRow: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.xs,
  },
  suggestionChip: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  suggestionText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.primary,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray200,
    backgroundColor: colors.white,
  },
  input: {
    flex: 1,
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.gray900,
    maxHeight: 100,
    borderWidth: 1,
    borderColor: colors.gray200,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.gold,
    justifyContent: "center",
    alignItems: "center",
    marginLeft: spacing.sm,
  },
  sendBtnDisabled: {
    backgroundColor: colors.gray200,
  },
});
