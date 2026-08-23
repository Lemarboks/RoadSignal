import * as Location from "expo-location";
import * as Notifications from "expo-notifications";
import * as SecureStore from "expo-secure-store";
import * as TaskManager from "expo-task-manager";
import { apiClient, restorePersistedSession } from "./session-store";

const LOCATION_TASK = "roadsignal-active-trip-location";
const ACTIVE_TRIP_KEY = "roadsignal.mobile.active-trip.v1";
const LAST_ALERT_KEY = "roadsignal.mobile.last-alert.v1";

type LocationTaskData = { locations: Location.LocationObject[] };

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

TaskManager.defineTask<LocationTaskData>(LOCATION_TASK, async ({ data, error }) => {
  if (error || !data?.locations.length) return;
  const tripId = await SecureStore.getItemAsync(ACTIVE_TRIP_KEY);
  if (!tripId) return;

  try {
    if (!apiClient.session && !(await restorePersistedSession())) return;
    const latest = data.locations[data.locations.length - 1];
    await apiClient.request(`/api/v1/trips/${tripId}/location`, {
      method: "POST",
      body: JSON.stringify({
        location: {
          latitude: latest.coords.latitude,
          longitude: latest.coords.longitude,
        },
        recorded_at: new Date(latest.timestamp).toISOString(),
      }),
    });
    const response = await apiClient.request<{ items: string[] }>(
      `/api/v1/trips/${tripId}/alerts`,
    );
    const alert = response.items.at(-1);
    const lastAlert = await SecureStore.getItemAsync(LAST_ALERT_KEY);
    if (alert && alert !== lastAlert) {
      await Notifications.scheduleNotificationAsync({
        content: { title: "RoadSignal route alert", body: alert, data: { tripId } },
        trigger: null,
      });
      await SecureStore.setItemAsync(LAST_ALERT_KEY, alert);
    }
  } catch {
    // The next background update retries; no precise location is logged locally.
  }
});

export async function registerTripNotifications() {
  if (process.env.EXPO_OS === "android") {
    await Notifications.setNotificationChannelAsync("trip-alerts", {
      name: "Active trip alerts",
      importance: Notifications.AndroidImportance.HIGH,
    });
  }
  const existing = await Notifications.getPermissionsAsync();
  const permission = existing.granted
    ? existing
    : await Notifications.requestPermissionsAsync();
  if (!permission.granted) return "denied" as const;
  try {
    const token = await Notifications.getDevicePushTokenAsync();
    await SecureStore.setItemAsync("roadsignal.mobile.device-push-token.v1", String(token.data));
  } catch {
    // Local trip alerts still work when a remote push credential is unavailable.
  }
  return "granted" as const;
}

export async function startActiveTripTracking(tripId: string) {
  const foreground = await Location.requestForegroundPermissionsAsync();
  if (foreground.status !== Location.PermissionStatus.GRANTED) return "foreground-denied" as const;
  const background = await Location.requestBackgroundPermissionsAsync();
  if (background.status !== Location.PermissionStatus.GRANTED) return "background-denied" as const;
  await registerTripNotifications();
  await SecureStore.setItemAsync(ACTIVE_TRIP_KEY, tripId);
  await SecureStore.deleteItemAsync(LAST_ALERT_KEY);
  if (!(await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK))) {
    await Location.startLocationUpdatesAsync(LOCATION_TASK, {
      accuracy: Location.Accuracy.Balanced,
      distanceInterval: 100,
      deferredUpdatesDistance: 250,
      deferredUpdatesInterval: 60_000,
      pausesUpdatesAutomatically: true,
      activityType: Location.ActivityType.AutomotiveNavigation,
      foregroundService: {
        notificationTitle: "RoadSignal trip active",
        notificationBody: "Sharing location for route progress and safety alerts.",
        notificationColor: "#FFDA00",
      },
      showsBackgroundLocationIndicator: true,
    });
  }
  return "started" as const;
}

export async function stopActiveTripTracking() {
  await SecureStore.deleteItemAsync(ACTIVE_TRIP_KEY);
  await SecureStore.deleteItemAsync(LAST_ALERT_KEY);
  if (await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK)) {
    await Location.stopLocationUpdatesAsync(LOCATION_TASK);
  }
}
