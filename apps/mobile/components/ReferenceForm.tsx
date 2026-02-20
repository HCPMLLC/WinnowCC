import { useState, useEffect } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Modal,
  ScrollView,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const RELATIONSHIPS = [
  "Peer",
  "Co-Worker",
  "Supervisor",
  "Manager",
  "Mentor",
  "Direct Report",
  "Customer",
  "End-User",
  "Subordinate",
  "Other",
];

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
}

interface ReferenceFormProps {
  visible: boolean;
  reference: Reference | null;
  onSave: (data: any) => Promise<void>;
  onClose: () => void;
}

export default function ReferenceForm({
  visible,
  reference,
  onSave,
  onClose,
}: ReferenceFormProps) {
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [relationship, setRelationship] = useState("Peer");
  const [yearsKnown, setYearsKnown] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (reference) {
      setName(reference.name);
      setTitle(reference.title || "");
      setCompany(reference.company);
      setPhone(reference.phone);
      setEmail(reference.email || "");
      setRelationship(reference.relationship || "Peer");
      setYearsKnown(reference.years_known != null ? String(reference.years_known) : "");
      setNotes(reference.notes || "");
    } else {
      setName("");
      setTitle("");
      setCompany("");
      setPhone("");
      setEmail("");
      setRelationship("Peer");
      setYearsKnown("");
      setNotes("");
    }
  }, [reference, visible]);

  async function handleSave() {
    if (!name.trim() || !company.trim() || !phone.trim()) {
      Alert.alert("Required", "Name, company, and phone are required.");
      return;
    }
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        title: title.trim() || undefined,
        company: company.trim(),
        phone: phone.trim(),
        email: email.trim() || undefined,
        relationship,
        years_known: yearsKnown ? parseInt(yearsKnown, 10) : undefined,
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch (e: any) {
      Alert.alert("Error", e?.message || "Failed to save reference.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.header}>
          <Text style={styles.headerTitle}>
            {reference ? "Edit Reference" : "Add Reference"}
          </Text>
          <TouchableOpacity onPress={onClose}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
        </View>
        <ScrollView style={styles.form} contentContainerStyle={styles.formContent}>
          <Text style={styles.label}>Full Name *</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Jane Smith"
          />

          <Text style={styles.label}>Title</Text>
          <TextInput
            style={styles.input}
            value={title}
            onChangeText={setTitle}
            placeholder="Senior Engineer"
          />

          <Text style={styles.label}>Company *</Text>
          <TextInput
            style={styles.input}
            value={company}
            onChangeText={setCompany}
            placeholder="Acme Corp"
          />

          <Text style={styles.label}>Phone *</Text>
          <TextInput
            style={styles.input}
            value={phone}
            onChangeText={setPhone}
            placeholder="+1 555-123-4567"
            keyboardType="phone-pad"
          />

          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="jane@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
          />

          <Text style={styles.label}>Relationship</Text>
          <View style={styles.pickerWrap}>
            <Picker
              selectedValue={relationship}
              onValueChange={setRelationship}
              style={styles.picker}
            >
              {RELATIONSHIPS.map((r) => (
                <Picker.Item key={r} label={r} value={r} />
              ))}
            </Picker>
          </View>

          <Text style={styles.label}>Years Known</Text>
          <TextInput
            style={styles.input}
            value={yearsKnown}
            onChangeText={setYearsKnown}
            placeholder="5"
            keyboardType="number-pad"
          />

          <Text style={styles.label}>Notes</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            value={notes}
            onChangeText={setNotes}
            placeholder="How do you know this person?"
            multiline
            numberOfLines={3}
          />

          <TouchableOpacity
            style={[styles.saveBtn, saving && styles.disabled]}
            onPress={handleSave}
            disabled={saving}
          >
            <Text style={styles.saveBtnText}>
              {saving ? "Saving..." : reference ? "Update" : "Add Reference"}
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
    backgroundColor: colors.white,
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
  },
  cancelText: {
    fontSize: fontSize.md,
    color: colors.blue500,
  },
  form: { flex: 1 },
  formContent: { padding: spacing.md, paddingBottom: spacing.xxl },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray700,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray200,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.gray900,
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: "top",
  },
  pickerWrap: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray200,
    borderRadius: borderRadius.md,
    overflow: "hidden",
  },
  picker: { height: 50 },
  saveBtn: {
    backgroundColor: colors.gold,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: "center",
    marginTop: spacing.lg,
  },
  saveBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  disabled: { opacity: 0.6 },
});
