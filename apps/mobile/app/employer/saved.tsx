import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import SkillTag from "../../components/SkillTag";
import type { SavedCandidate } from "../../lib/employer-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function SavedCandidatesScreen() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<SavedCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNotes, setEditNotes] = useState("");

  const loadData = async () => {
    try {
      const res = await api.get("/api/employer/candidates/saved");
      if (res.ok) {
        const data = await res.json();
        setCandidates(Array.isArray(data) ? data : data.results ?? []);
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleStartEdit = (item: SavedCandidate) => {
    setEditingId(item.id);
    setEditNotes(item.notes ?? "");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditNotes("");
  };

  const handleSaveNotes = async (id: number) => {
    try {
      const res = await api.patch(`/api/employer/candidates/saved/${id}`, {
        notes: editNotes.trim(),
      });
      if (res.ok) {
        setEditingId(null);
        loadData();
      } else {
        Alert.alert("Error", "Failed to save notes.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    }
  };

  const handleUnsave = (id: number) => {
    Alert.alert(
      "Remove Candidate",
      "Are you sure you want to unsave this candidate?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: async () => {
            try {
              const res = await api.delete(
                `/api/employer/candidates/saved/${id}`,
              );
              if (res.ok) {
                setCandidates((prev) => prev.filter((c) => c.id !== id));
              } else {
                Alert.alert("Error", "Failed to unsave candidate.");
              }
            } catch {
              Alert.alert("Error", "Something went wrong.");
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingSpinner />;

  return (
    <FlatList
      style={styles.container}
      data={candidates}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => {
        const c = item.candidate;
        const isEditing = editingId === item.id;

        return (
          <TouchableOpacity
            style={styles.card}
            onPress={() =>
              router.push(`/employer/candidate/${item.candidate_id}`)
            }
            activeOpacity={0.7}
          >
            <View style={styles.cardHeader}>
              <View style={styles.cardInfo}>
                <Text style={styles.name}>
                  {c?.name ?? `Candidate #${item.candidate_id}`}
                </Text>
                {c?.headline && (
                  <Text style={styles.headline} numberOfLines={1}>
                    {c.headline}
                  </Text>
                )}
              </View>
              <TouchableOpacity
                onPress={(e) => {
                  e.stopPropagation?.();
                  handleUnsave(item.id);
                }}
                hitSlop={8}
              >
                <Ionicons name="bookmark" size={20} color={colors.gold} />
              </TouchableOpacity>
            </View>

            <View style={styles.metaRow}>
              {c?.location && (
                <View style={styles.metaItem}>
                  <Ionicons
                    name="location-outline"
                    size={14}
                    color={colors.gray500}
                  />
                  <Text style={styles.metaText}>{c.location}</Text>
                </View>
              )}
              {c?.years_experience != null && (
                <Text style={styles.metaText}>
                  {c.years_experience}y exp
                </Text>
              )}
              <Text style={styles.metaText}>
                Saved {new Date(item.saved_at).toLocaleDateString()}
              </Text>
            </View>

            {c?.top_skills && c.top_skills.length > 0 && (
              <View style={styles.skillsRow}>
                {c.top_skills.slice(0, 5).map((s) => (
                  <SkillTag key={s} name={s} />
                ))}
              </View>
            )}

            {/* Notes section */}
            {isEditing ? (
              <View style={styles.notesEdit}>
                <TextInput
                  style={styles.notesInput}
                  value={editNotes}
                  onChangeText={setEditNotes}
                  placeholder="Add notes..."
                  placeholderTextColor={colors.gray400}
                  multiline
                  numberOfLines={2}
                />
                <View style={styles.notesActions}>
                  <TouchableOpacity
                    style={styles.notesSaveBtn}
                    onPress={() => handleSaveNotes(item.id)}
                  >
                    <Text style={styles.notesSaveBtnText}>Save</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={handleCancelEdit}>
                    <Text style={styles.notesCancelText}>Cancel</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <TouchableOpacity
                style={styles.notesRow}
                onPress={(e) => {
                  e.stopPropagation?.();
                  handleStartEdit(item);
                }}
              >
                <Text
                  style={[
                    styles.notesText,
                    !item.notes && styles.notesPlaceholder,
                  ]}
                  numberOfLines={2}
                >
                  {item.notes || "Tap to add notes..."}
                </Text>
                <Ionicons
                  name="create-outline"
                  size={16}
                  color={colors.gray400}
                />
              </TouchableOpacity>
            )}
          </TouchableOpacity>
        );
      }}
      ListEmptyComponent={
        <View style={styles.empty}>
          <Ionicons
            name="bookmark-outline"
            size={48}
            color={colors.gray300}
          />
          <Text style={styles.emptyTitle}>No saved candidates</Text>
          <Text style={styles.emptyDesc}>
            Search candidates and save them to review later
          </Text>
        </View>
      }
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      contentContainerStyle={
        candidates.length === 0 ? styles.emptyContainer : styles.listContent
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  listContent: { padding: spacing.md },
  emptyContainer: { flexGrow: 1 },
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  cardInfo: { flex: 1, marginRight: spacing.sm },
  name: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  headline: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: 2,
  },
  metaRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.xs,
    marginBottom: spacing.sm,
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metaText: {
    fontSize: fontSize.xs,
    color: colors.gray400,
  },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  notesRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
    paddingTop: spacing.sm,
  },
  notesText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginRight: spacing.sm,
  },
  notesPlaceholder: {
    color: colors.gray400,
    fontStyle: "italic",
  },
  notesEdit: {
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
    paddingTop: spacing.sm,
  },
  notesInput: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.gray900,
    minHeight: 60,
    textAlignVertical: "top",
  },
  notesActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  notesSaveBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  notesSaveBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  notesCancelText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
  },
  empty: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  emptyTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  emptyDesc: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    textAlign: "center",
    marginTop: spacing.xs,
  },
});
