import { useCallback, useEffect, useState } from "react";
import { checkHealth } from "../services/api";

const HEALTH_INTERVAL_MS = 30_000;

export function useBackendHealth() {
  const [status, setStatus] = useState("checking");

  const refresh = useCallback(async () => {
    setStatus("checking");
    const healthy = await checkHealth();
    setStatus(healthy ? "online" : "offline");
  }, []);

  useEffect(() => {
    let active = true;

    const check = async () => {
      const healthy = await checkHealth();
      if (active) setStatus(healthy ? "online" : "offline");
    };

    check();
    const timer = window.setInterval(check, HEALTH_INTERVAL_MS);
    const handleOnline = () => check();
    const handleOffline = () => setStatus("offline");
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return { status, refresh };
}
