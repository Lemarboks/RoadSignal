"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { REPLAY_SECONDS, replaySnapshot } from "../../lib/demo-telemetry";

export function useDemoReplay(enabled = true) {
  const [seconds, setSeconds] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [reducedMotion, setReducedMotion] = useState(true);
  const [visible, setVisible] = useState(false);
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => { setReducedMotion(preference.matches); if (preference.matches) setPlaying(false); };
    change();
    setPlaying(!preference.matches);
    preference.addEventListener("change", change);
    return () => preference.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    let onScreen = false;
    const update = () => setVisible(onScreen && !document.hidden);
    const observer = new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; update(); });
    if (element.current) observer.observe(element.current);
    document.addEventListener("visibilitychange", update);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", update); };
  }, []);
  useEffect(() => {
    if (!enabled || !playing || !visible) return;
    let previous = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      const elapsed = Math.min(1, (now - previous) / 1000); previous = now;
      setSeconds((value) => Math.min(REPLAY_SECONDS, value + elapsed * speed));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [enabled, playing, visible, speed]);
  useEffect(() => { if (seconds >= REPLAY_SECONDS) setPlaying(false); }, [seconds]);
  return { ...useMemo(() => replaySnapshot(seconds), [seconds]), element, seconds, playing, speed, reducedMotion,
    animating: enabled && playing && visible && !reducedMotion,
    setSpeed, toggle: () => { if (seconds >= REPLAY_SECONDS) setSeconds(0); setPlaying((value) => !value); },
    reset: () => { setPlaying(false); setSeconds(0); },
  };
}
