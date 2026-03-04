import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth";
import LoadingSpinner from "../../components/LoadingSpinner";
import ScoreBadge from "../../components/ScoreBadge";
import SkillTag from "../../components/SkillTag";
import StatusPredictionCard from "../../components/StatusPredictionCard";
import InterviewPrepPanel from "../../components/InterviewPrepPanel";
import RejectionFeedbackCard from "../../components/RejectionFeedbackCard";
import CultureSummaryCard from "../../components/CultureSummaryCard";
import GapRecommendationsCard from "../../components/GapRecommendationsCard";
import EmailDraftModal from "../../components/EmailDraftModal";
import SalaryCoachModal from "../../components/SalaryCoachModal";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

const STATUS_OPTIONS = [
  { value: "saved", label: "Saved" },
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "rejected", label: "Rejected" },
  { value: "offer", label: "Offer" },
];

interface MatchDetail {
  id: number;
  job: {
    id: number;
    title: string;
    company: string;
    location: string | null;
    remote_flag: boolean | null;
    salary_min: number | null;
    salary_max: number | null;
    currency: string | null;
    salary: string | null;
    url: string;
    description_text: string | null;
  };
  match_score: number;
  interview_readiness_score: number;
  interview_probability: number | null;
  reasons: {
    matched_skills?: string[];
    missing_skills?: string[];
    salary_estimate?: number[];
  };
  match_explanation?: string;
  application_status: string | null;
  notes: string | null;
}

export default function MatchDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [tailorResult, setTailorResult] = useState<{
    resume_url?: string;
    cover_letter_url?: string;
  } | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [emailModalVisible, setEmailModalVisible] = useState(false);
  const [salaryModalVisible, setSalaryModalVisible] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/matches/${id}`);
        if (res.ok) {
          const data = await res.json();
          setMatch(data);
          setStatus(data.application_status);
        }
      } catch {
        Alert.alert("Error", "Could not load match details.");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const updateStatus = async (newStatus: string) => {
    setStatus(newStatus);
    try {
      await api.patch(`/api/matches/${id}/status`, { status: newStatus });
    } catch {
      Alert.alert("Error", "Failed to update status.");
    }
  };

  const handleTailor = async () => {
    if (!match) return;
    setTailoring(true);
    setTailorResult(null);
    try {
      const res = await api.post(`/api/tailor/${match.job.id}`);
      if (!res.ok) {
        if (res.status === 403) {
          Alert.alert(
            "Feature Available on Web",
            "To access this feature, please log in at WinnowCC.ai."
          );
          return;
        }
        const err = await res.json();
        Alert.alert("Error", err.detail || "Failed to generate resume.");
        return;
      }
      const data = await res.json();

      if (data.status === "queued" && data.job_id) {
        // Poll for completion
        let attempts = 0;
        while (attempts < 30) {
          await new Promise((r) => setTimeout(r, 2000));
          const pollRes = await api.get(`/api/tailor/status/${data.job_id}`);
          if (pollRes.ok) {
            const pollData = await pollRes.json();
            if (pollData.status === "finished") {
              setTailorResult({
                resume_url: pollData.resume_url,
                cover_letter_url: pollData.cover_letter_url,
              });
              return;
            }
            if (pollData.status === "failed") {
              Alert.alert(
                "Error",
                pollData.error_message || "Tailoring failed."
              );
              return;
            }
          }
          attempts++;
        }
        Alert.alert("Timeout", "Resume generation is taking too long.");
      } else if (data.resume_url) {
        setTailorResult({
          resume_url: data.resume_url,
          cover_letter_url: data.cover_letter_url,
        });
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setTailoring(false);
    }
  };

  const handleDownload = async (url: string, type: string) => {
    setDownloading(true);
    try {
      const token = await getToken();
      const fileUri =
        FileSystem.cacheDirectory + `tailored_${type}_${id}.docx`;

      const download = await FileSystem.downloadAsync(
        `${API_BASE}${url}`,
        fileUri,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (download.status !== 200) {
        Alert.alert("Error", "Download failed.");
        return;
      }

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(download.uri, {
          mimeType:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          dialogTitle: `Share Tailored ${type === "resume" ? "Resume" : "Cover Letter"}`,
        });
      } else {
        Alert.alert("Success", "File downloaded to cache.");
      }
    } catch {
      Alert.alert("Error", "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!match) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Match not found.</Text>
      </View>
    );
  }

  const matchedSkills = match.reasons?.matched_skills || [];
  const missingSkills = match.reasons?.missing_skills || [];
  const salaryEstimate = match.reasons?.salary_estimate;

  const salaryDisplay = match.job.salary
    ? match.job.salary
    : match.job.salary_min && match.job.salary_max
      ? `$${(match.job.salary_min / 1000).toFixed(0)}k - $${(match.job.salary_max / 1000).toFixed(0)}k`
      : salaryEstimate
        ? `~$${(salaryEstimate[0] / 1000).toFixed(0)}k - $${(salaryEstimate[1] / 1000).toFixed(0)}k (est.)`
        : null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <Text style={styles.title}>{match.job.title}</Text>
      <Text style={styles.company}>{match.job.company}</Text>
      <Text style={styles.location}>
        {match.job.location}
        {match.job.remote_flag && "  Remote"}
      </Text>
      {salaryDisplay && <Text style={styles.salary}>{salaryDisplay}</Text>}

      {match.match_explanation && (
        <Text style={styles.matchExplanation}>{match.match_explanation}</Text>
      )}

      {/* Scores */}
      <View style={styles.scoresRow}>
        <View style={styles.scoreItem}>
          <ScoreBadge score={match.match_score} label="Match" />
        </View>
        <View style={styles.scoreItem}>
          <ScoreBadge
            score={match.interview_probability ?? match.interview_readiness_score}
            label="Interview"
          />
        </View>
      </View>

      {/* Matched Skills */}
      {matchedSkills.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Matched Skills</Text>
          <View style={styles.skillsWrap}>
            {matchedSkills.map((s) => (
              <View key={s} style={styles.skillRow}>
                <Ionicons
                  name="checkmark-circle"
                  size={16}
                  color={colors.green500}
                />
                <Text style={styles.skillText}>{s}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Missing Skills */}
      {missingSkills.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Skill Gaps</Text>
          <View style={styles.skillsWrap}>
            {missingSkills.map((s) => (
              <View key={s} style={styles.skillRow}>
                <Ionicons
                  name="warning"
                  size={16}
                  color={colors.amber500}
                />
                <Text style={styles.skillText}>{s}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Gap Recommendations — only when missing skills exist */}
      {missingSkills.length > 0 && <GapRecommendationsCard matchId={match.id} />}

      {/* Culture Summary */}
      <CultureSummaryCard jobId={match.job.id} />

      {/* Application Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Application Status</Text>
        <View style={styles.statusRow}>
          {STATUS_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.value}
              style={[
                styles.statusChip,
                status === opt.value && styles.statusChipActive,
              ]}
              onPress={() => updateStatus(opt.value)}
            >
              <Text
                style={[
                  styles.statusChipText,
                  status === opt.value && styles.statusChipTextActive,
                ]}
              >
                {opt.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Status Prediction — only when applied */}
      {status === "applied" && <StatusPredictionCard matchId={match.id} />}

      {/* Interview Prep — when interviewing or offer */}
      {(status === "interviewing" || status === "offer") && (
        <InterviewPrepPanel matchId={match.id} />
      )}

      {/* Rejection Feedback — when rejected */}
      {status === "rejected" && <RejectionFeedbackCard matchId={match.id} />}

      {/* Generate ATS Resume */}
      <View style={styles.section}>
        <TouchableOpacity
          style={[styles.tailorBtn, tailoring && styles.btnDisabled]}
          onPress={handleTailor}
          disabled={tailoring}
        >
          {tailoring ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.tailorBtnText}>Generate ATS Resume</Text>
          )}
        </TouchableOpacity>

        {tailorResult && (
          <View style={styles.downloadRow}>
            {tailorResult.resume_url && (
              <TouchableOpacity
                style={styles.downloadBtn}
                onPress={() => handleDownload(tailorResult.resume_url!, "resume")}
                disabled={downloading}
              >
                <Ionicons
                  name="download-outline"
                  size={18}
                  color={colors.white}
                />
                <Text style={styles.downloadBtnText}>Resume</Text>
              </TouchableOpacity>
            )}
            {tailorResult.cover_letter_url && (
              <TouchableOpacity
                style={styles.downloadBtn}
                onPress={() =>
                  handleDownload(tailorResult.cover_letter_url!, "cover_letter")
                }
                disabled={downloading}
              >
                <Ionicons
                  name="download-outline"
                  size={18}
                  color={colors.white}
                />
                <Text style={styles.downloadBtnText}>Cover Letter</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </View>

      {/* Draft Email */}
      <View style={styles.section}>
        <TouchableOpacity
          style={styles.secondaryBtn}
          onPress={() => setEmailModalVisible(true)}
        >
          <Ionicons name="mail-outline" size={18} color={colors.primary} />
          <Text style={styles.secondaryBtnText}>Draft Email</Text>
        </TouchableOpacity>
      </View>

      {/* Salary Coach — only when offer */}
      {status === "offer" && (
        <View style={styles.section}>
          <TouchableOpacity
            style={styles.secondaryBtn}
            onPress={() => setSalaryModalVisible(true)}
          >
            <Ionicons name="cash-outline" size={18} color={colors.primary} />
            <Text style={styles.secondaryBtnText}>Salary Coach</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* View Job Posting */}
      {match.job.url && (
        <TouchableOpacity
          style={styles.linkBtn}
          onPress={() => Linking.openURL(match.job.url)}
        >
          <Ionicons name="open-outline" size={18} color={colors.blue500} />
          <Text style={styles.linkBtnText}>View Job Posting</Text>
        </TouchableOpacity>
      )}

      {/* Modals */}
      <EmailDraftModal
        visible={emailModalVisible}
        onClose={() => setEmailModalVisible(false)}
        matchId={match.id}
      />
      <SalaryCoachModal
        visible={salaryModalVisible}
        onClose={() => setSalaryModalVisible(false)}
        matchId={match.id}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.gray50,
  },
  errorText: { fontSize: fontSize.md, color: colors.gray500 },
  title: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  company: {
    fontSize: fontSize.lg,
    color: colors.gray600,
    marginBottom: 2,
  },
  location: {
    fontSize: fontSize.md,
    color: colors.gray400,
    marginBottom: spacing.xs,
  },
  salary: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.green500,
    marginBottom: spacing.xs,
  },
  matchExplanation: {
    fontSize: fontSize.sm,
    fontStyle: "italic",
    color: colors.green500,
    marginBottom: spacing.md,
    lineHeight: 20,
  },
  scoresRow: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xl,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  scoreItem: { alignItems: "center" },
  section: { marginBottom: spacing.lg },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  skillsWrap: { gap: spacing.xs },
  skillRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  skillText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
  },
  statusRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  statusChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.gray300,
    backgroundColor: colors.white,
  },
  statusChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  statusChipText: {
    fontSize: fontSize.xs,
    color: colors.gray600,
    fontWeight: "500",
  },
  statusChipTextActive: {
    color: colors.gold,
  },
  tailorBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.6 },
  tailorBtnText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
  downloadRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  downloadBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.primaryLight,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
  },
  downloadBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.white,
  },
  linkBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingVertical: spacing.md,
  },
  secondaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
  },
  secondaryBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  linkBtnText: {
    fontSize: fontSize.md,
    color: colors.blue500,
    fontWeight: "500",
  },
});
