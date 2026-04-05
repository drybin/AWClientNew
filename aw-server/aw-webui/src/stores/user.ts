import { getClient } from '~/util/awclient';
import { defineStore } from 'pinia';
import { useSettingsStore } from '~/stores/settings';

function normalizeTeams(team: unknown): string[] {
  if (team == null || team === '') return [];
  if (Array.isArray(team)) return team.map(t => String(t));
  return [String(team)];
}

/** Shown when GFP/TIM returns error email_taken (duplicate email). */
export const GFPS_EMAIL_TAKEN_MESSAGE =
  'This email is already in use by another account. Choose a different email.';

function isRecord(data: unknown): data is Record<string, unknown> {
  return typeof data === 'object' && data !== null;
}

function throwIfEmailTakenPayload(data: unknown): void {
  if (!isRecord(data)) return;
  if (data.error === 'email_taken') {
    throw new Error(GFPS_EMAIL_TAKEN_MESSAGE);
  }
}

function axiosLikeResponseData(err: unknown): unknown {
  if (!isRecord(err) || !('response' in err)) return undefined;
  const r = err.response;
  if (!isRecord(r)) return undefined;
  return r.data;
}

/**
 * GFP/TIM reachable but no profile for this device UUID yet
 * (e.g. {"error":"User not found"} or message-only errors).
 * Must not be treated as "central server unavailable".
 */
function isGfpsUserNotRegisteredResponse(body: Record<string, unknown>): boolean {
  const st = body.status;
  if (st === 404 || st === '404') {
    return true;
  }
  const parts = [body.error, body.message, body.detail].filter(
    (x): x is string => typeof x === 'string'
  );
  for (const t of parts) {
    const s = t.toLowerCase().replace(/_/g, ' ');
    if (s.includes('invitation') && s.includes('not found')) {
      continue;
    }
    if (
      s.includes('user not found') ||
      s.includes('no user') ||
      s.includes('unknown user') ||
      s.includes('user does not exist') ||
      /user\s*not\s*found|usernotfound/.test(s) ||
      s === 'not found' ||
      s.trim() === 'not_found'
    ) {
      return true;
    }
    if (s.includes('not found') && /user|uuid|profile|account|device/.test(s)) {
      return true;
    }
  }
  return false;
}

export type GfpsAccountMode = 'loading' | 'disabled' | 'not_configured' | 'unreachable' | 'ready';

/** Poll interval when central GFPS is unreachable (any page, not only Account). */
const GFPS_RECONNECT_INTERVAL_MS = 10_000;

interface State {
  username: string;
  uuid: string;
  data: Record<string, unknown>;
  teams: string[];
  email: string;
  firstName: string;
  lastName: string;
  middleName: string;
  role_id: string;
  created: string;
  isExistOnServer: boolean;
  _loaded: boolean;
  gfpsAccountMode: GfpsAccountMode;
  /** Browser interval id for reconnect polling */
  gfpsReconnectTimer: number | null;
}

export const useUserStore = defineStore('user', {
  state: (): State => ({
    username: '',
    uuid: '',
    data: {},
    teams: [],
    email: '',
    firstName: '',
    lastName: '',
    middleName: '',
    role_id: '',
    created: '',
    isExistOnServer: false,
    _loaded: false,
    gfpsAccountMode: 'loading',
    gfpsReconnectTimer: null,
  }),
  actions: {
    async ensureLoaded() {
      if (!this._loaded) {
        await this.load();
      }
    },
    _applyGfpsDisabled() {
      this.gfpsAccountMode = 'disabled';
      this.isExistOnServer = false;
    },
    _applyGfpsNotConfigured() {
      this.gfpsAccountMode = 'not_configured';
      this.isExistOnServer = false;
    },
    _applyGfpsUnreachable() {
      this.gfpsAccountMode = 'unreachable';
      this.isExistOnServer = false;
    },
    _stopGfpsReconnect() {
      if (this.gfpsReconnectTimer != null) {
        clearInterval(this.gfpsReconnectTimer);
        this.gfpsReconnectTimer = null;
      }
    },
    _scheduleGfpsReconnect() {
      if (this.gfpsReconnectTimer != null) return;
      if (this.gfpsAccountMode !== 'unreachable') return;
      this.gfpsReconnectTimer = window.setInterval(() => {
        void this.load().catch(() => {
          /* avoid unhandled rejection if load throws before _loaded */
        });
      }, GFPS_RECONNECT_INTERVAL_MS);
    },
    _syncGfpsReconnectTimer() {
      if (this.gfpsAccountMode === 'unreachable') {
        this._scheduleGfpsReconnect();
      } else {
        this._stopGfpsReconnect();
      }
    },
    async load() {
      try {
        const client = getClient();
        const uuidRes = await client.req.get('/0/uuid');
        this.uuid = uuidRes.data.uuid;

        const settings = useSettingsStore();
        await settings.ensureLoaded();

        if (!settings.gfpsEnabled) {
          this._applyGfpsDisabled();
        } else if (!settings.gfpsServerIP || !settings.gfpsServerPort) {
          this._applyGfpsNotConfigured();
        } else {
          const res = await client.req.get('/0/gfps/user/' + this.uuid);
          const body = res.data as Record<string, unknown>;

          if (body.error === 'Address for GFPS server not set') {
            this._applyGfpsNotConfigured();
          } else if (body.error === 'GFPS disabled') {
            this._applyGfpsDisabled();
          } else if (isGfpsUserNotRegisteredResponse(body)) {
            this.isExistOnServer = false;
            this.username = '';
            this.teams = [];
            this.email = '';
            this.firstName = '';
            this.lastName = '';
            this.middleName = '';
            this.role_id = '';
            this.created = '';
            this.data = {};
            this.gfpsAccountMode = 'ready';
          } else if (body.status === 'error' || body.error) {
            this._applyGfpsUnreachable();
          } else if (body.user) {
            const u = body.user as Record<string, unknown>;
            this.username = (u.username as string) ?? '';
            this.teams = normalizeTeams(u.team);
            this.email = (u.email as string) ?? '';
            const raw = u as Record<string, unknown>;
            this.firstName = String(raw.firstName ?? raw.first_name ?? '');
            this.lastName = String(raw.lastName ?? raw.last_name ?? '');
            this.middleName = String(raw.middleName ?? raw.middle_name ?? '');
            this.role_id = (u.role_id as string) ?? '';
            this.created = (u.created as string) ?? '';
            this.data = (u.data as Record<string, unknown>) ?? {};
            this.isExistOnServer = true;
            this.gfpsAccountMode = 'ready';
          } else {
            this.isExistOnServer = false;
            this.username = '';
            this.teams = [];
            this.email = '';
            this.firstName = '';
            this.lastName = '';
            this.middleName = '';
            this.role_id = '';
            this.created = '';
            this.data = {};
            this.gfpsAccountMode = 'ready';
          }
        }
      } catch {
        this._applyGfpsUnreachable();
      }
      this._loaded = true;
      this._syncGfpsReconnectTimer();
    },
    addTeam(teamId: string) {
      const id = teamId.trim();
      if (!id || this.teams.includes(id)) return;
      this.teams.push(id);
    },
    removeTeam(index: number) {
      this.teams.splice(index, 1);
    },
    async register(data: { username?: string; teams?: string[]; email?: string }) {
      if (this.gfpsAccountMode !== 'ready') {
        throw new Error('Central server is not available');
      }
      const client = getClient();
      try {
        const response = await client.req.post('/0/gfps/user', {
          uuid: this.uuid,
          username: data.username ?? this.username,
          team: data.teams ?? this.teams,
          email: data.email ?? this.email,
        });
        const d = response.data as Record<string, unknown>;
        throwIfEmailTakenPayload(d);
        if (d && !d.error && (d.status === 'ok' || d.user)) {
          if (d.uuid) this.uuid = String(d.uuid);
          this.isExistOnServer = true;
        } else {
          this.isExistOnServer = false;
          const msg =
            (typeof d.message === 'string' && d.message) ||
            (typeof d.error === 'string' && d.error) ||
            'Registration failed';
          throw new Error(msg);
        }
      } catch (e: unknown) {
        throwIfEmailTakenPayload(axiosLikeResponseData(e));
        throw e;
      }
    },
    /** Claim uses only token; server adds uuid. Username/email: PUT /api/0/user after success (see Account flow). */
    async claimInvitation(token: string) {
      if (this.gfpsAccountMode !== 'ready') {
        throw new Error('Central server is not available');
      }
      const client = getClient();
      try {
        const res = await client.req.post('/0/gfps/invitations/claim', { token });
        const data = res.data as Record<string, unknown>;
        throwIfEmailTakenPayload(data);
        return data;
      } catch (e: unknown) {
        throwIfEmailTakenPayload(axiosLikeResponseData(e));
        throw e;
      }
    },
    async update(data: { username?: string; teams?: string[]; email?: string }) {
      if (this.gfpsAccountMode !== 'ready') {
        throw new Error('Central server is not available');
      }
      const client = getClient();
      try {
        const response = await client.req.put('/0/gfps/user', {
          uuid: this.uuid,
          username: data.username ?? this.username,
          team: data.teams ?? this.teams,
          email: data.email ?? this.email,
        });
        const d = response.data as Record<string, unknown>;
        throwIfEmailTakenPayload(d);
        this.isExistOnServer = !!(d && !d.error && (d.status === 'ok' || d.status === 'success'));
        if (!this.isExistOnServer && d.error) {
          const msg =
            (typeof d.message === 'string' && d.message) ||
            (typeof d.error === 'string' && d.error) ||
            'Update failed';
          throw new Error(msg);
        }
      } catch (e: unknown) {
        throwIfEmailTakenPayload(axiosLikeResponseData(e));
        throw e;
      }
    },
    async setState(new_state: Partial<State>) {
      this.$patch(new_state);
    },
  },
  getters: {
    loaded(state: State) {
      return state._loaded;
    },
  },
});
