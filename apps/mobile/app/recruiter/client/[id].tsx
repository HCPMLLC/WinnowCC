import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";
import {
  CLIENT_STATUS_COLORS,
  type Client,
  type ClientStatus,
} from "../../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

export default function ClientDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editStatus, setEditStatus] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const loadData = async () => {
    try {
      const res = await api.get(`/api/recruiter/clients/${id}`);
      if (res.ok) {
        const data = await res.json();
        setClient(data);
        setEditStatus(data.status);
        setEditNotes(data.notes ?? "");
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
  }, [id]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/api/recruiter/clients/${id}`, {
        status: editStatus,
        notes: editNotes.trim() || null,
      });
      if (res.ok) {
        Alert.alert("Saved", "Client updated successfully.");
        loadData();
      } else {
        Alert.alert("Error", "Failed to save changes.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      "Delete Client",
      "Are you sure you want to delete this client? This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await api.delete(`/api/recruiter/clients/${id}`);
              router.back();
            } catch {
              Alert.alert("Error", "Failed to delete client.");
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingSpinner />;

  if (!client) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>Client not found</Text>
      </View>
    );
  }

  const statusColor =
    CLIENT_STATUS_COLORS[client.status as ClientStatus] ?? colors.gray400;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.headerCard}>
        <View style={styles.titleRow}>
          <Text style={styles.name}>{client.company_name}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
            <Text style={styles.statusText}>
              {client.status.charAt(0).toUpperCase() + client.status.slice(1)}
            </Text>
          </View>
        </View>
        {client.industry && (
          <Text style={styles.industry}>{client.industry}</Text>
        )}
      </View>

      {/* Details */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Details</Text>
        {client.website && (
          <DetailRow label="Website" value={client.website} />
        )}
        {client.contract_type && (
          <DetailRow label="Contract" value={client.contract_type} />
        )}
        {client.fee_percentage != null && (
          <DetailRow label="Fee" value={`${client.fee_percentage}%`} />
        )}
        <DetailRow label="Jobs" value={String(client.job_count)} />
      </View>

      {/* Contacts */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Contacts</Text>
        {client.contacts && client.contacts.length > 0 ? (
          client.contacts.map((contact, i) => (
            <View key={i} style={styles.contactCard}>
              <View style={styles.contactRow}>
                <Ionicons
                  name="person-outline"
                  size={16}
                  color={colors.gray500}
                />
                <Text style={styles.contactName}>{contact.name}</Text>
                {contact.role && (
                  <Text style={styles.contactRole}>({contact.role})</Text>
                )}
              </View>
              {contact.email && (
                <View style={styles.contactRow}>
                  <Ionicons
                    name="mail-outline"
                    size={14}
                    color={colors.gray400}
                  />
                  <Text style={styles.contactDetail}>{contact.email}</Text>
                </View>
              )}
              {contact.phone && (
                <View style={styles.contactRow}>
                  <Ionicons
                    name="call-outline"
                    size={14}
                    color={colors.gray400}
                  />
                  <Text style={styles.contactDetail}>{contact.phone}</Text>
                </View>
              )}
            </View>
          ))
        ) : client.contact_name ? (
          <View style={styles.contactCard}>
            <View style={styles.contactRow}>
              <Ionicons
                name="person-outline"
                size={16}
                color={colors.gray500}
              />
              <Text style={styles.contactName}>{client.contact_name}</Text>
            </View>
            {client.contact_email && (
              <View style={styles.contactRow}>
                <Ionicons
                  name="mail-outline"
                  size={14}
                  color={colors.gray400}
                />
                <Text style={styles.contactDetail}>{client.contact_email}</Text>
              </View>
            )}
          </View>
        ) : (
          <Text style={styles.noData}>No contacts added</Text>
        )}
      </View>

      {/* Edit section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Update</Text>

        <Text style={styles.label}>Status</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={editStatus}
            onValueChange={setEditStatus}
            style={styles.picker}
          >
            <Picker.Item label="Active" value="active" />
            <Picker.Item label="Inactive" value="inactive" />
            <Picker.Item label="Prospect" value="prospect" />
          </Picker>
        </View>

        <Text style={styles.label}>Notes</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Add notes about this client..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          value={editNotes}
          onChangeText={setEditNotes}
        />

        <TouchableOpacity
          style={[styles.saveBtn, saving && styles.btnDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          <Text style={styles.saveBtnText}>
            {saving ? "Saving..." : "Save Changes"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Delete */}
      <TouchableOpacity style={styles.deleteBtn} onPress={handleDelete}>
        <Ionicons name="trash-outline" size={18} color={colors.red500} />
        <Text style={styles.deleteBtnText}>Delete Client</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={detailStyles.row}>
      <Text style={detailStyles.label}>{label}</Text>
      <Text style={detailStyles.value}>{value}</Text>
    </View>
  );
}

const detailStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  label: { fontSize: fontSize.sm, color: colors.gray500 },
  value: { fontSize: fontSize.sm, fontWeight: "600", color: colors.gray900 },
});

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  emptyContainer: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyText: { fontSize: fontSize.md, color: colors.gray500 },
  headerCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  titleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  name: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    flex: 1,
    marginRight: spacing.sm,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
  },
  statusText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
  },
  industry: {
    fontSize: fontSize.md,
    color: colors.gray600,
    marginTop: spacing.xs,
  },
  section: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  contactCard: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  contactRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: 4,
  },
  contactName: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  contactRole: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  contactDetail: {
    fontSize: fontSize.xs,
    color: colors.gray600,
  },
  noData: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    fontStyle: "italic",
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  textArea: { minHeight: 100 },
  pickerWrapper: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
  saveBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.6 },
  saveBtnText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
  deleteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    borderWidth: 1,
    borderColor: colors.red500,
    marginBottom: spacing.lg,
  },
  deleteBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.red500,
  },
});
