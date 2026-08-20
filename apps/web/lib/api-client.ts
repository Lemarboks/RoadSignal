export type SessionUser = {
  id: string;
  email: string;
  name: string;
  role: "driver" | "fleet_manager" | "incident_moderator" | "administrator";
};

type TokenResponse = {
  access_token: string;
  expires_in: number;
  user?: SessionUser;
};

export type SessionSnapshot = {
  user: SessionUser;
  accessToken: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(status: number, payload: unknown) {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const message = detail
        .map((item) =>
          item && typeof item === "object" && typeof item.msg === "string"
            ? item.msg.replace(/^Value error, /, "")
            : "",
        )
        .filter(Boolean)
        .join(" ");
      if (message) return message;
    }
  }
  if (status === 401) return "Your email or password was not accepted.";
  if (status === 403) return "Your account does not have permission for this action.";
  if (status === 429) return "Too many attempts. Wait a minute and try again.";
  if (status >= 500) return "The RoadSignal service is temporarily unavailable.";
  return "The request could not be completed.";
}

export class RoadSignalApiClient {
  private accessToken = "";
  private user: SessionUser | null = null;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(readonly baseUrl: string) {}

  get session(): SessionSnapshot | null {
    return this.user && this.accessToken
      ? { user: this.user, accessToken: this.accessToken }
      : null;
  }

  async login(email: string, password: string) {
    return this.authenticate("login", { email, password });
  }

  async register(name: string, email: string, password: string) {
    return this.authenticate("register", { name, email, password });
  }

  async logout() {
    const hadSession = Boolean(this.user);
    this.clear();
    if (!hadSession) return;
    try {
      await fetch(`${this.baseUrl}/api/v1/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: "{}",
      });
    } catch {
      // The local session is still cleared if the network is unavailable.
    }
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetchWithToken(path, init);
    if (response.status === 401 && this.user && (await this.refresh())) {
      const retry = await this.fetchWithToken(path, init);
      return this.parse<T>(retry);
    }
    return this.parse<T>(response);
  }

  private async authenticate(endpoint: "login" | "register", body: object) {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const tokens = await this.parse<TokenResponse>(response);
    if (!tokens.user) throw new ApiError("The service returned an incomplete session.", 502);
    this.store(tokens, tokens.user);
    return this.session as SessionSnapshot;
  }

  private fetchWithToken(path: string, init: RequestInit) {
    const headers = new Headers(init.headers);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (this.accessToken) headers.set("Authorization", `Bearer ${this.accessToken}`);
    return fetch(`${this.baseUrl}${path}`, { ...init, headers, credentials: "include" });
  }

  private async refresh() {
    if (this.refreshPromise) return this.refreshPromise;
    this.refreshPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: "{}",
        });
        const tokens = await this.parse<TokenResponse>(response);
        if (!this.user) return false;
        this.store(tokens, this.user);
        return true;
      } catch {
        this.clear();
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();
    return this.refreshPromise;
  }

  private store(tokens: TokenResponse, user: SessionUser) {
    this.accessToken = tokens.access_token;
    this.user = user;
  }

  private clear() {
    this.accessToken = "";
    this.user = null;
  }

  private async parse<T>(response: Response): Promise<T> {
    let payload: unknown = null;
    if (response.status !== 204) {
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
    }
    if (!response.ok) throw new ApiError(errorMessage(response.status, payload), response.status);
    return payload as T;
  }
}
