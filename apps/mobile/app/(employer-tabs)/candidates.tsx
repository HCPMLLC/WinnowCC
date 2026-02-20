import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import SkillTag from "../../components/SkillTag";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface CandidateResult {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  match_score: number | null;
  profile_visibility: string;
}

export default function CandidateSearchScreen() {
  const router = useRouter();
  const [skillsInput, setSkillsInput] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [titleInput, setTitleInput] = useState("");
  const [results, setResults] = useState<CandidateResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());

  const doSearch = async (pageNum: number) => {
    setLoading(true);
    try {
      const filters: Record<string, unknown> = {};
      const skills = skillsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const locations = locationInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const titles = titleInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      if (skills.length) filters.skills = skills;
      if (locations.length) filters.locations = locations;
      if (titles.length) filters.job_titles = titles;

      const res = await api.post(
        `/api/employer/candidates/search?page=${pageNum}`,
        filters,
      );
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setTotal(data.total || 0);
        setPage(data.page || pageNum);
        setHasMore(data.has_more || false);
      } else {
        const err = await res.json().catch(() => null);
        Alert.alert("Error", err?.detail || "Search failed");
      }
    } catch {
      Alert.alert("Error", "Could not connect to server.");
    } finally {
      setLoading(false);
      setHasSearched(true);
    }
  };

  const handleSearch = () => doSearch(1);
  const handleNext = () => doSearch(page + 1);
  const handlePrev = () => {
    if (page > 1) doSearch(page - 1);
  };

  const handleSave = async (candidateId: number) => {
    try {
      const res = await api.post("/api/employer/candidates/save", {
        candidate_id: candidateId,
      });
      if (res.ok) {
        setSavedIds((prev) => new Set(prev).add(candidateId));
      } else {
        const err = await res.json().catch(() => null);
        Alert.alert("Error", err?.detail || "Failed to save candidate");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    }
  };

  return (
    <View style={styles.container}>
      {/* Search form */}
      <View style={styles.searchForm}>
        <TextInput
          style={styles.input}
          placeholder="Skills (comma separated)"
          placeholderTextColor={colors.gray400}
          value={skillsInput}
          onChangeText={setSkillsInput}
        />
        <View style={styles.row}>
          <TextInput
            style={[styles.input, styles.halfInput]}
            placeholder="Location"
            placeholderTextColor={colors.gray400}
            value={locationInput}
            onChangeText={setLocationInput}
          />
          <TextInput
            style={[styles.input, styles.halfInput]}
            placeholder="Job Titles"
            placeholderTextColor={colors.gray400}
            value={titleInput}
            onChangeText={setTitleInput}
          />
        </View>
        <TouchableOpacity
          style={[styles.searchBtn, loading && styles.btnDisabled]}
          onPress={handleSearch}
          disabled={loading}
        >
          <Ionicons name="search" size={18} color={colors.primary} />
          <Text style={styles.searchBtnText}>
            {loading ? "Searching..." : "Search"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Results */}
      <FlatList
        data={results}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => router.push(`/employer/candidate/${item.id}`)}
          >
            <View style={styles.cardHeader}>
              <View style={styles.cardInfo}>
                <Text style={styles.cardName}>{item.name}</Text>
                {item.headline && (
                  <Text style={styles.cardHeadline} numberOfLines={1}>
                    {item.headline}
                  </Text>
                )}
              </View>
              <TouchableOpacity
                style={[
                  styles.saveBtn,
                  savedIds.has(item.id) && styles.saveBtnSaved,
                ]}
                onPress={() => handleSave(item.id)}
                disabled={savedIds.has(item.id)}
              >
                <Ionicons
                  name={savedIds.has(item.id) ? "bookmark" : "bookmark-outline"}
                  size={18}
                  color={
                    savedIds.has(item.id) ? colors.gold : colors.gray500
                  }
                />
              </TouchableOpacity>
            </View>

            <View style={styles.cardMeta}>
              {item.location && (
                <Text style={styles.metaText}>{item.location}</Text>
              )}
              {item.years_experience != null && (
                <Text style={styles.metaText}>
                  {item.years_experience}y exp
                </Text>
              )}
            </View>

            {item.top_skills.length > 0 && (
              <View style={styles.skillsRow}>
                {item.top_skills.slice(0, 5).map((s) => (
                  <SkillTag key={s} name={s} />
                ))}
              </View>
            )}
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          hasSearched ? (
            <View style={styles.empty}>
              <Ionicons
                name="people-outline"
                size={48}
                color={colors.gray300}
              />
              <Text style={styles.emptyTitle}>No candidates found</Text>
              <Text style={styles.emptyDesc}>
                Try adjusting your search filters
              </Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          results.length > 0 ? (
            <View style={styles.pagination}>
              <TouchableOpacity
                style={[styles.pageBtn, page <= 1 && styles.pageBtnDisabled]}
                onPress={handlePrev}
                disabled={page <= 1}
              >
                <Text style={styles.pageBtnText}>Previous</Text>
              </TouchableOpacity>
              <Text style={styles.pageInfo}>
                Page {page} ({total} total)
              </Text>
              <TouchableOpacity
                style={[styles.pageBtn, !hasMore && styles.pageBtnDisabled]}
                onPress={handleNext}
                disabled={!hasMore}
              >
                <Text style={styles.pageBtnText}>Next</Text>
              </TouchableOpacity>
            </View>
          ) : null
        }
        contentContainerStyle={styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  searchForm: {
    backgroundColor: colors.white,
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
  },
  input: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  row: { flexDirection: "row", gap: spacing.sm },
  halfInput: { flex: 1 },
  searchBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
  },
  btnDisabled: { opacity: 0.6 },
  searchBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  listContent: { padding: spacing.md },
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
  cardName: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  cardHeadline: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: 2,
  },
  saveBtn: {
    padding: spacing.xs,
  },
  saveBtnSaved: {
    opacity: 0.7,
  },
  cardMeta: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.xs,
    marginBottom: spacing.sm,
  },
  metaText: { fontSize: fontSize.xs, color: colors.gray400 },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  empty: {
    alignItems: "center",
    paddingTop: spacing.xxl,
  },
  emptyTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  emptyDesc: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
  pagination: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.md,
  },
  pageBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
    backgroundColor: colors.gray100,
  },
  pageBtnDisabled: { opacity: 0.4 },
  pageBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray700,
  },
  pageInfo: {
    fontSize: fontSize.sm,
    color: colors.gray500,
  },
});
