import { router } from "expo-router";
import { useVideoPlayer, VideoView } from "expo-video";
import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { ApiError } from "../lib/api-client";
import { apiClient, useSessionStore } from "../lib/session-store";

const BACKGROUND_VIDEO =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260620_185230_f7f71ef4-6655-469f-b9c6-efbdc1f7684a.mp4";

export default function Login() {
  const setSession = useSessionStore((state) => state.setSession);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const player = useVideoPlayer(BACKGROUND_VIDEO, (videoPlayer) => {
    videoPlayer.loop = true;
    videoPlayer.muted = true;
    videoPlayer.play();
  });

  async function submit() {
    if (!email.trim() || !password) {
      setError("Enter your email and password to continue.");
      return;
    }
    if (mode === "register" && !name.trim()) {
      setError("Enter your name to create an account.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const session =
        mode === "login"
          ? await apiClient.login(email.trim(), password)
          : await apiClient.register(name.trim(), email.trim(), password);
      setSession(session);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The service is unavailable. Try again.");
    } finally {
      setLoading(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <View style={s.page}>
      <VideoView
        accessibilityElementsHidden
        contentFit="cover"
        nativeControls={false}
        player={player}
        style={StyleSheet.absoluteFill}
      />
      <View pointerEvents="none" style={s.baseScrim} />
      <View pointerEvents="none" style={s.topScrim} />
      <View pointerEvents="none" style={s.bottomScrim} />

      <SafeAreaView style={s.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={s.keyboardView}
        >
          <ScrollView
            contentContainerStyle={s.content}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View style={s.brandRow}>
              <View style={s.signalMark}>
                <View style={s.signalDot} />
              </View>
              <Text style={s.brand}>ROADSIGNAL</Text>
            </View>

            <View style={s.statement}>
              <Text style={s.kicker}>SAFER MOVEMENT STARTS HERE</Text>
              <Text style={s.heroLine}>BEYOND</Text>
              <Text style={[s.heroLine, s.heroAccent]}>RISK.</Text>
              <Text style={s.heroLine}>ONWARD.</Text>
            </View>

            <View style={s.formPanel}>
              <Text style={s.title}>{isLogin ? "Welcome back" : "Join RoadSignal"}</Text>
              <Text style={s.note}>
                {isLogin
                  ? "Sign in to plan safer routes and receive live trip alerts."
                  : "Create your account to keep routes, reports and alerts together."}
              </Text>

              {mode === "register" && (
                <TextInput
                  accessibilityLabel="Name"
                  autoCapitalize="words"
                  onChangeText={setName}
                  placeholder="Name"
                  placeholderTextColor="#94A1A8"
                  returnKeyType="next"
                  style={s.input}
                  value={name}
                />
              )}
              <TextInput
                accessibilityLabel="Email"
                autoCapitalize="none"
                autoComplete="email"
                keyboardType="email-address"
                onChangeText={setEmail}
                placeholder="Email"
                placeholderTextColor="#94A1A8"
                returnKeyType="next"
                style={s.input}
                value={email}
              />
              <TextInput
                accessibilityLabel="Password"
                autoCapitalize="none"
                autoComplete={isLogin ? "current-password" : "new-password"}
                onChangeText={setPassword}
                onSubmitEditing={() => void submit()}
                placeholder="Password"
                placeholderTextColor="#94A1A8"
                returnKeyType="go"
                secureTextEntry
                style={s.input}
                value={password}
              />

              {error ? (
                <Text accessibilityLiveRegion="polite" style={s.error}>
                  {error}
                </Text>
              ) : null}

              <Pressable
                accessibilityRole="button"
                disabled={loading}
                onPress={() => void submit()}
                style={({ pressed }) => [s.primary, pressed && s.primaryPressed, loading && s.disabled]}
              >
                {loading ? (
                  <ActivityIndicator color="#08232B" />
                ) : (
                  <>
                    <Text style={s.primaryText}>{isLogin ? "Sign in" : "Create account"}</Text>
                    <Text accessibilityElementsHidden style={s.arrow}>↗</Text>
                  </>
                )}
              </Pressable>

              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  setMode(isLogin ? "register" : "login");
                  setError("");
                }}
                style={({ pressed }) => [s.switchButton, pressed && s.switchPressed]}
              >
                <Text style={s.switchText}>
                  {isLogin ? "New to RoadSignal? Create an account" : "Already registered? Sign in"}
                </Text>
              </Pressable>
              <Text style={s.privacy}>Your session is cleared when the app restarts.</Text>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: "#06171D" },
  safeArea: { flex: 1 },
  keyboardView: { flex: 1 },
  baseScrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(4,20,27,0.34)" },
  topScrim: {
    position: "absolute",
    top: 0,
    right: 0,
    left: 0,
    height: "45%",
    backgroundColor: "rgba(2,14,19,0.22)",
  },
  bottomScrim: {
    position: "absolute",
    right: 0,
    bottom: 0,
    left: 0,
    height: "64%",
    backgroundColor: "rgba(3,19,25,0.72)",
  },
  content: { flexGrow: 1, justifyContent: "space-between", paddingHorizontal: 22, paddingTop: 14, paddingBottom: 18 },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  signalMark: {
    width: 26,
    height: 26,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 13,
    backgroundColor: "#FFDA00",
  },
  signalDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#08232B" },
  brand: { color: "#FFFFFF", fontSize: 17, fontWeight: "900", letterSpacing: -0.3 },
  statement: { marginTop: 56, marginBottom: 34 },
  kicker: { color: "#FFFFFF", fontSize: 11, fontWeight: "800", letterSpacing: 1.3, marginBottom: 9 },
  heroLine: { color: "#FFFFFF", fontSize: 56, lineHeight: 48, fontWeight: "900", letterSpacing: -2 },
  heroAccent: { color: "#FFDA00", textAlign: "right" },
  formPanel: {
    backgroundColor: "rgba(7,27,35,0.92)",
    borderRadius: 16,
    padding: 20,
    shadowColor: "#001016",
    shadowOffset: { width: 0, height: 14 },
    shadowOpacity: 0.34,
    shadowRadius: 24,
    elevation: 12,
  },
  title: { color: "#FFFFFF", fontSize: 25, fontWeight: "800", letterSpacing: -0.5 },
  note: { color: "#B8C5CA", fontSize: 13, lineHeight: 19, marginTop: 5, marginBottom: 14 },
  input: {
    height: 52,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.10)",
    color: "#FFFFFF",
    fontSize: 16,
    paddingHorizontal: 16,
    marginTop: 9,
  },
  error: { color: "#FFD3CD", fontSize: 13, lineHeight: 18, marginTop: 10 },
  primary: {
    height: 54,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderRadius: 14,
    backgroundColor: "#FFDA00",
    paddingLeft: 19,
    paddingRight: 8,
    marginTop: 16,
  },
  primaryPressed: { transform: [{ scale: 0.98 }] },
  disabled: { opacity: 0.64 },
  primaryText: { color: "#08232B", fontSize: 17, fontWeight: "800" },
  arrow: {
    width: 38,
    height: 38,
    borderRadius: 19,
    overflow: "hidden",
    backgroundColor: "#08232B",
    color: "#FFFFFF",
    textAlign: "center",
    lineHeight: 38,
    fontSize: 21,
  },
  switchButton: { paddingVertical: 14, alignItems: "center" },
  switchPressed: { opacity: 0.65 },
  switchText: { color: "#FFFFFF", fontSize: 13, fontWeight: "700", textAlign: "center" },
  privacy: { color: "#8F9DA3", fontSize: 11, textAlign: "center" },
});
