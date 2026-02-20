import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";
import SkillTag from "../../../components/SkillTag";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

interface ExperienceItem {
  title: string;
  company: string;
  start_date: string | null;
  end_date: string | null;
}

interface EducationItem {
  institution: string;
  degree: string | null;
  field_of_study: string | null;
}

interface CandidateDetail {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  profile_visibility: string;
  anonymized?: boolean;
  profile_json?: {
    basics?: { first_name?: string; last_name?: string; location?: string };
    skills?: string[];
    experience?: ExperienceItem[];
    education?: EducationItem[];
  };
}

export default function CandidateDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadCandidate = async () => {
    try {
      const res = await api.get(`/api/employer/candidates/${id}`);
      if (res.ok) {
        setCandidate(await res.json());
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCandidate();
  }, [id]);

  const onRefresh = () => {
    setRefreshing(true);
    loadCandidate();
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.post("/api/employer/candidates/save", {
        candidate_id: Number(id),
      });
      if (res.ok) {
        setSaved(true);
        Alert.alert("Saved", "Candidate added to your saved list.");
      } else {
        const err = await res.json().catch(() => null);
        Alert.alert("Error", err?.detail || "Failed to save candidate");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  if (!candidate) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Candidate not found.</Text>
      </View>
    );
  }

  const pj = candidate.profile_json;
  const skills = pj?.skills || candidate.top_skills || [];
  const experience = pj?.experience || [];
  const education = pj?.education || [];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Anonymized notice */}
      {candidate.anonymized && (
        <View style={styles.noticeBanner}>
          <Ionicons name="eye-off-outline" size={16} color={colors.primary} />
          <Text style={styles.noticeText}>
            This candidate's identity is anonymous
          </Text>
        </View>
      )}

      {/* Header */}
      <Text style={styles.name}>{candidate.name}</Text>
      {candidate.headline && (
        <Text style={styles.headline}>{candidate.headline}</Text>
      )}

      <View style={styles.metaRow}>
        {candidate.location && (
          <View style={styles.metaItem}>
            <Ionicons
              name="location-outline"
              size={16}
              color={colors.gray500}
            />
            <Text style={styles.metaText}>{candidate.location}</Text>
          </View>
        )}
        {candidate.years_experience != null && (
          <View style={styles.metaItem}>
            <Ionicons name="time-outline" size={16} color={colors.gray500} />
            <Text style={styles.metaText}>
              {candidate.years_experience} years experience
            </Text>
          </View>
        )}
      </View>

      {/* Save button */}
      <TouchableOpacity
        style={[styles.saveBtn, saved && styles.saveBtnSaved]}
        onPress={handleSave}
        disabled={saved || saving}
      >
        <Ionicons
          name={saved ? "bookmark" : "bookmark-outline"}
          size={18}
          color={saved ? colors.primary : colors.white}
        />
        <Text style={[styles.saveBtnText, saved && styles.saveBtnTextSaved]}>
          {saving ? "Saving..." : saved ? "Saved" : "Save Candidate"}
        </Text>
      </TouchableOpacity>

      {/* Skills */}
      {skills.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Skills</Text>
          <View style={styles.skillsRow}>
            {skills.map((s: string) => (
              <SkillTag key={s} name={s} />
            ))}
          </View>
        </>
      )}

      {/* Experience */}
      {experience.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Experience</Text>
          {experience.map((exp, i) => (
            <View key={i} style={styles.itemCard}>
              <Text style={styles.itemTitle}>{exp.title}</Text>
              <Text style={styles.itemSubtitle}>{exp.company}</Text>
              {(exp.start_date || exp.end_date) && (
                <Text style={styles.itemMeta}>
                  {exp.start_date || "?"} - {exp.end_date || "Present"}
                </Text>
              )}
            </View>
          ))}
        </>
      )}

      {/* Education */}
      {education.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Education</Text>
          {education.map((edu, i) => (
            <View key={i} style={styles.itemCard}>
              <Text style={styles.itemTitle}>{edu.institution}</Text>
              {edu.degree && (
                <Text style={styles.itemSubtitle}>
                  {edu.degree}
                  {edu.field_of_study ? ` in ${edu.field_of_study}` : ""}
                </Text>
              )}
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  errorText: { fontSize: fontSize.md, color: colors.gray500 },
  noticeBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.sage,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  noticeText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.primary,
  },
  name: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
  },
  headline: {
    fontSize: fontSize.md,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
  metaRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 4 },
  metaText: { fontSize: fontSize.sm, color: colors.gray500 },
  saveBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.lg,
  },
  saveBtnSaved: {
    backgroundColor: colors.sage,
  },
  saveBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.white,
  },
  saveBtnTextSaved: {
    color: colors.primary,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  itemCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  itemTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  itemSubtitle: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginTop: 2,
  },
  itemMeta: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: spacing.xs,
  },
});
