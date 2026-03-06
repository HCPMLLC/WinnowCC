import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
} from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";
import { handleFeatureGateResponse } from "../lib/featureGate";
import type { EmailDraft } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  matchId: number;
}

export default function EmailDraftModal({ visible, onClose, matchId }: Props) {
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    if (visible) {
      loadDraft();
    } else {
      setDraft(null);
    }
  }, [visible, matchId]);

  const loadDraft = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/matches/${matchId}/draft-email`);
      if (await handleFeatureGateResponse(res)) {
        onClose();
        return;
      }
      if (res.ok) {
        setDraft(await res.json());
      } else {
        Alert.alert("Error", "Could not generate email draft.");
        onClose();
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const res = await api.post(`/api/matches/${matchId}/draft-email`);
      if (!(await handleFeatureGateResponse(res)) && res.ok) {
        setDraft(await res.json());
      }
    } catch {
      Alert.alert("Error", "Could not regenerate.");
    } finally {
      setRegenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!draft) return;
    await Clipboard.setStringAsync(`Subject: ${draft.subject}\n\n${draft.body}`);
    Alert.alert("Copied", "Email copied to clipboard.");
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Draft Email</Text>
          <TouchableOpacity onPress={onClose}>
            <Ionicons name="close" size={24} color={colors.gray600} />
          </TouchableOpacity>
        </View>

        {loading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.loadingText}>Generating draft...</Text>
          </View>
        ) : draft ? (
          <ScrollView style={styles.scrollContent} contentContainerStyle={styles.scrollInner}>
            <Text style={styles.subjectLabel}>Subject</Text>
            <Text style={styles.subjectText}>{draft.subject}</Text>

            <Text style={styles.bodyLabel}>Body</Text>
            <Text style={styles.bodyText}>{draft.body}</Text>

            <View style={styles.actions}>
              <TouchableOpacity style={styles.copyBtn} onPress={handleCopy}>
                <Ionicons name="copy-outline" size={18} color={colors.primary} />
                <Text style={styles.copyBtnText}>Copy to Clipboard</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.regenerateBtn}
                onPress={handleRegenerate}
                disabled={regenerating}
              >
                {regenerating ? (
                  <ActivityIndicator color={colors.gray600} />
                ) : (
                  <>
                    <Ionicons name="refresh" size={18} color={colors.gray600} />
                    <Text style={styles.regenerateBtnText}>Regenerate</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </ScrollView>
        ) : null}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.gray50,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
  },
  loadingWrap: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.md,
  },
  scrollContent: {
    flex: 1,
  },
  scrollInner: {
    padding: spacing.md,
  },
  subjectLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: spacing.xs,
  },
  subjectText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.lg,
  },
  bodyLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: spacing.xs,
  },
  bodyText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  actions: {
    gap: spacing.sm,
  },
  copyBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
  },
  copyBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  regenerateBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
  },
  regenerateBtnText: {
    fontSize: fontSize.md,
    fontWeight: "500",
    color: colors.gray600,
  },
});
