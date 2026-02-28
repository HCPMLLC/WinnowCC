import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, errorMessage: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error?.message || String(error) };
  }

  componentDidCatch(error: Error) {
    console.error("[ErrorBoundary]", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.body}>
            The app ran into an unexpected error. Tap below to try again.
          </Text>
          <Text style={styles.errorDetail} selectable>
            {this.state.errorMessage}
          </Text>
          <TouchableOpacity
            style={styles.btn}
            onPress={() => this.setState({ hasError: false, errorMessage: "" })}
          >
            <Text style={styles.btnText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.lg,
    backgroundColor: colors.gray50,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  body: {
    fontSize: fontSize.md,
    color: colors.gray500,
    textAlign: "center",
    marginBottom: spacing.lg,
    lineHeight: 22,
  },
  errorDetail: {
    fontSize: 12,
    color: "#B91C1C",
    textAlign: "center",
    marginBottom: spacing.lg,
    paddingHorizontal: spacing.md,
    fontFamily: "monospace",
  },
  btn: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  btnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gold,
  },
});
