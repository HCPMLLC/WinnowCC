import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import LoadingSpinner from "../../components/LoadingSpinner";
import ReferenceForm from "../../components/ReferenceForm";

interface Reference {
  id: string;
  name: string;
  title: string | null;
  company: string;
  phone: string;
  email: string | null;
  relationship: string;
  years_known: number | null;
  notes: string | null;
  is_active: boolean;
}

export default function ReferencesScreen() {
  const [references, setReferences] = useState<Reference[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingRef, setEditingRef] = useState<Reference | null>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await api.get("/api/profile/references");
      if (res.ok) {
        const data = await res.json();
        setReferences(data);
      }
    } catch {
      Alert.alert("Error", "Could not load references.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  async function handleSave(data: any) {
    if (editingRef) {
      const res = await api.put(`/api/profile/references/${editingRef.id}`, data);
      if (!res.ok) throw new Error("Failed to update reference.");
    } else {
      const res = await api.post("/api/profile/references", data);
      if (!res.ok) throw new Error("Failed to add reference.");
    }
    setEditingRef(null);
    loadData();
  }

  function handleEdit(ref: Reference) {
    setEditingRef(ref);
    setShowForm(true);
  }

  function handleDelete(ref: Reference) {
    Alert.alert(
      "Delete Reference",
      `Remove ${ref.name} from your references?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await api.delete(`/api/profile/references/${ref.id}`);
              loadData();
            } catch {
              Alert.alert("Error", "Could not delete reference.");
            }
          },
        },
      ],
    );
  }

  if (loading) return <LoadingSpinner />;

  return (
    <View style={styles.container}>
      <FlatList
        contentContainerStyle={styles.list}
        data={references}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListHeaderComponent={
          <View style={styles.headerRow}>
            <Text style={styles.countBadge}>
              {references.length} of 3 references
            </Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={48} color={colors.gray300} />
            <Text style={styles.emptyTitle}>No references yet</Text>
            <Text style={styles.emptyText}>
              Add professional references to strengthen your profile.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.name}</Text>
                {item.title && (
                  <Text style={styles.titleCompany}>
                    {item.title} at {item.company}
                  </Text>
                )}
                {!item.title && (
                  <Text style={styles.titleCompany}>{item.company}</Text>
                )}
              </View>
              <View style={styles.cardActions}>
                <TouchableOpacity onPress={() => handleEdit(item)}>
                  <Ionicons name="create-outline" size={20} color={colors.blue500} />
                </TouchableOpacity>
                <TouchableOpacity onPress={() => handleDelete(item)}>
                  <Ionicons name="trash-outline" size={20} color={colors.red500} />
                </TouchableOpacity>
              </View>
            </View>
            <Text style={styles.phone}>{item.phone}</Text>
            {item.email && <Text style={styles.email}>{item.email}</Text>}
            <View style={styles.metaRow}>
              <View style={styles.relationBadge}>
                <Text style={styles.relationText}>{item.relationship}</Text>
              </View>
              {item.years_known != null && (
                <Text style={styles.years}>{item.years_known} years</Text>
              )}
            </View>
          </View>
        )}
      />

      <TouchableOpacity
        style={styles.fab}
        onPress={() => {
          setEditingRef(null);
          setShowForm(true);
        }}
      >
        <Ionicons name="add" size={28} color={colors.primary} />
      </TouchableOpacity>

      <ReferenceForm
        visible={showForm}
        reference={editingRef}
        onSave={handleSave}
        onClose={() => {
          setShowForm(false);
          setEditingRef(null);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  list: { padding: spacing.md, paddingBottom: 80 },
  headerRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginBottom: spacing.md,
  },
  countBadge: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
    backgroundColor: colors.sage,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between" },
  cardActions: { flexDirection: "row", gap: spacing.md },
  name: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
  },
  titleCompany: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginTop: 2,
  },
  phone: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    marginTop: spacing.sm,
  },
  email: {
    fontSize: fontSize.sm,
    color: colors.blue500,
    marginTop: 2,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  relationBadge: {
    backgroundColor: colors.sage,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
  },
  relationText: {
    fontSize: fontSize.xs,
    fontWeight: "500",
    color: colors.primary,
  },
  years: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  empty: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
  },
  emptyTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.sm,
    textAlign: "center",
  },
  fab: {
    position: "absolute",
    bottom: spacing.lg,
    right: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.gold,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
});
