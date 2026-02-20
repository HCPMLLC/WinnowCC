import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Modal,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const INDUSTRIES = [
  "Technology",
  "Healthcare",
  "Finance",
  "Manufacturing",
  "Retail",
  "Education",
  "Energy",
  "Media",
  "Real Estate",
  "Transportation",
  "Hospitality",
  "Legal",
  "Government",
  "Nonprofit",
  "Consulting",
  "Telecommunications",
  "Agriculture",
  "Aerospace",
  "Automotive",
  "Construction",
  "Insurance",
  "Pharmaceuticals",
  "Biotech",
  "Entertainment",
  "Food & Beverage",
  "Fashion",
  "Other",
];

interface AddClientFormProps {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function AddClientForm({
  visible,
  onClose,
  onCreated,
}: AddClientFormProps) {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    company_name: "",
    contact_name: "",
    contact_email: "",
    industry: "",
    status: "active",
  });

  const handleSubmit = async () => {
    if (!form.company_name.trim()) {
      Alert.alert("Required", "Please enter the company name.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/recruiter/clients", {
        company_name: form.company_name.trim(),
        contact_name: form.contact_name.trim() || null,
        contact_email: form.contact_email.trim() || null,
        industry: form.industry || null,
        status: form.status,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Failed to add client");
      }

      setForm({
        company_name: "",
        contact_name: "",
        contact_email: "",
        industry: "",
        status: "active",
      });
      onCreated();
      onClose();
    } catch (err: any) {
      Alert.alert("Error", err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <KeyboardAvoidingView
        style={styles.overlay}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.modal}>
          <View style={styles.header}>
            <Text style={styles.title}>Add Client</Text>
            <TouchableOpacity onPress={onClose}>
              <Ionicons name="close" size={24} color={colors.gray600} />
            </TouchableOpacity>
          </View>

          <ScrollView keyboardShouldPersistTaps="handled">
            <Text style={styles.label}>Company Name *</Text>
            <TextInput
              style={styles.input}
              placeholder="Company name"
              placeholderTextColor={colors.gray400}
              value={form.company_name}
              onChangeText={(v) =>
                setForm((f) => ({ ...f, company_name: v }))
              }
            />

            <Text style={styles.label}>Contact Name</Text>
            <TextInput
              style={styles.input}
              placeholder="Primary contact"
              placeholderTextColor={colors.gray400}
              value={form.contact_name}
              onChangeText={(v) =>
                setForm((f) => ({ ...f, contact_name: v }))
              }
            />

            <Text style={styles.label}>Contact Email</Text>
            <TextInput
              style={styles.input}
              placeholder="email@company.com"
              placeholderTextColor={colors.gray400}
              keyboardType="email-address"
              autoCapitalize="none"
              value={form.contact_email}
              onChangeText={(v) =>
                setForm((f) => ({ ...f, contact_email: v }))
              }
            />

            <Text style={styles.label}>Industry</Text>
            <View style={styles.pickerWrapper}>
              <Picker
                selectedValue={form.industry}
                onValueChange={(v) =>
                  setForm((f) => ({ ...f, industry: v }))
                }
                style={styles.picker}
              >
                <Picker.Item label="Select industry..." value="" />
                {INDUSTRIES.map((i) => (
                  <Picker.Item key={i} label={i} value={i} />
                ))}
              </Picker>
            </View>

            <Text style={styles.label}>Status</Text>
            <View style={styles.pickerWrapper}>
              <Picker
                selectedValue={form.status}
                onValueChange={(v) =>
                  setForm((f) => ({ ...f, status: v }))
                }
                style={styles.picker}
              >
                <Picker.Item label="Active" value="active" />
                <Picker.Item label="Prospect" value="prospect" />
              </Picker>
            </View>

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleSubmit}
              disabled={loading}
            >
              <Text style={styles.buttonText}>
                {loading ? "Adding..." : "Add Client"}
              </Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.5)",
  },
  modal: {
    backgroundColor: colors.white,
    borderTopLeftRadius: borderRadius.lg,
    borderTopRightRadius: borderRadius.lg,
    padding: spacing.lg,
    maxHeight: "85%",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
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
  pickerWrapper: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
  button: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
});
