import { useEffect, useRef } from "react";
import { cancelVoiceAlerts, speakAlert } from "../../lib/voice-alerts";

export function useVoiceAlerts(alerts: string[], enabled: boolean) {
  const spoken = useRef(new Set<string>());

  useEffect(() => {
    if (!alerts.length) spoken.current.clear();
  }, [alerts.length]);

  useEffect(() => {
    if (!enabled) return;
    for (const alert of alerts) {
      if (spoken.current.has(alert)) continue;
      spoken.current.add(alert);
      speakAlert(alert);
    }
  }, [alerts, enabled]);

  useEffect(() => {
    if (!enabled) cancelVoiceAlerts();
  }, [enabled]);

  useEffect(() => () => cancelVoiceAlerts(), []);
}
