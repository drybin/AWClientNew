<template lang="pug">
  div.user-account-page
    header.user-account-page__hero.mb-4.mt-4
      h2.user-account-page__title Account
      p.user-account-page__lead(v-if="userStore.gfpsAccountMode === 'ready'")
        | Profile from the GFP server. Identity fields are read-only; update email, username, and teams here.

    //- Loading
    div(v-if="!userStore._loaded")
      p.text-muted Loading…

    //- Central server down — no token UI until connection is back
    div(v-else-if="userStore.gfpsAccountMode === 'unreachable'")
      b-alert(show, variant="warning")
        strong Central server unavailable.
        |  ActivityWatch continues to work locally; timeline and buckets are stored on this device.
      p.text-muted.mb-0
        | Reconnecting automatically in the background (about every 10 seconds).

    //- GFPS disabled in settings
    div(v-else-if="userStore.gfpsAccountMode === 'disabled'")
      b-alert(show, variant="secondary")
        | Remote account sync is disabled. Enable GFPS in Settings if you need the central profile and teams.

    //- No address configured
    div(v-else-if="userStore.gfpsAccountMode === 'not_configured'")
      b-alert(show, variant="secondary")
        | Set the GFPS server address in Settings to load your account from the central server.

    //- ——— Ready: full account UI ———
    template(v-else)
      b-alert(v-if="error", variant="danger", dismissible, show, @dismissed="error = ''")
        | {{ error }}

      //- ——— Registered user ———
      div(v-if="userStore.isExistOnServer && userStore._loaded")
        //- no `no-body` here so FIO block always renders inside the card body
        b-card.aw-account-card.mb-3
          template(#header)
            div.aw-account-card__head
              .aw-account-card__icon.aw-account-card__icon--identity
                icon(name="id-card")
              div
                .aw-account-card__title Identity
                .aw-account-card__subtitle Legal name as stored on the server.

          b-card-body.aw-account-card__body
            div.row
              div.col-md-4.mb-3
                .aw-field-label First name
                .aw-readonly {{ userStore.firstName || '—' }}
              div.col-md-4.mb-3
                .aw-field-label Last name
                .aw-readonly {{ userStore.lastName || '—' }}
              div.col-md-4.mb-3
                .aw-field-label Middle name
                .aw-readonly {{ userStore.middleName || '—' }}

        b-card.aw-account-card.mb-3(no-body)
          template(#header)
            div.aw-account-card__head
              .aw-account-card__icon.aw-account-card__icon--contact
                icon(name="envelope")
              div
                .aw-account-card__title Contact & username
                .aw-account-card__subtitle Editable on save.

          b-card-body.aw-account-card__body
            div.row
              div.col-md-6.mb-3.mb-md-0
                label.aw-field-label(for="acc-email") Email
                b-form-input#acc-email.aw-input(
                  v-model="email",
                  type="email",
                  autocomplete="email",
                  placeholder="you@company.com"
                )
              div.col-md-6
                label.aw-field-label(for="acc-username") Username
                b-form-input#acc-username.aw-input(
                  v-model="username",
                  type="text",
                  autocomplete="username",
                  placeholder="Your username"
                )

        div.account-teams-gap
          teams-membership-card

        b-card.aw-account-card.aw-account-card--dim.mb-3(no-body)
          template(#header)
            div.aw-account-card__head
              .aw-account-card__icon.aw-account-card__icon--meta
                icon(name="fingerprint")
              div
                .aw-account-card__title Device & record
                .aw-account-card__subtitle Local identifiers (read-only).

          b-card-body.aw-account-card__body.pt-3
            div.row
              div.col-md-12.mb-3
                .aw-field-label UUID
                .aw-readonly.aw-readonly--mono.aw-readonly--sm {{ userStore.uuid }}
              div.col-md-12
                .aw-field-label Created
                .aw-readonly.aw-readonly--sm {{ userStore.created || '—' }}

        div.d-flex.justify-content-end.pt-1
          b-button(variant="dark", class="aw-btn-save", @click="submit")
            | Save changes

      //- ——— Not registered ———
      div(v-if="!userStore.isExistOnServer && userStore._loaded")
        b-card.aw-account-card.mb-3(no-body)
          template(#header)
            div.aw-account-card__head
              .aw-account-card__icon.aw-account-card__icon--welcome
                icon(name="user-plus")
              div
                .aw-account-card__title Get started
                .aw-account-card__subtitle
                  | Register this device on GFP, or apply an invitation. Invitation claim sends only the token; username and email below are saved after a successful claim via profile update. If the installer created preload.txt but you still see this screen, restart the service or paste the token under “Invitation token”.

          b-card-body.aw-account-card__body
            div.row
              div.col-md-6.mb-3.mb-md-0
                label.aw-field-label(for="reg-username") Username
                b-form-input#reg-username.aw-input(v-model="username", placeholder="Your username")
              div.col-md-6
                label.aw-field-label(for="reg-email") Email
                b-form-input#reg-email.aw-input(v-model="email", type="email", placeholder="you@company.com")

        b-card.aw-account-card.mb-3(no-body)
          template(#header)
            div.aw-account-card__head
              .aw-account-card__icon.aw-account-card__icon--welcome
                icon(name="key")
              div
                .aw-account-card__title Invitation token
                .aw-account-card__subtitle
                  | Shown only when the server is reachable and this device UUID is not registered on GFP. Paste a token you were given, or if the preload file was already used.

          b-card-body.aw-account-card__body
            b-alert(v-if="claimError", variant="danger", dismissible, show, @dismissed="claimError = ''")
              | {{ claimError }}
            label.aw-field-label(for="inv-token") Token
            b-form-textarea#inv-token.aw-input(
              v-model="invitationToken",
              rows="3",
              placeholder="Paste your invitation token here",
              :disabled="claimBusy"
            )
            div.d-flex.justify-content-end.mt-3
              b-button(
                variant="outline-dark",
                :disabled="claimBusy || !invitationToken.trim()",
                @click="submitClaimInvitation"
              )
                span(v-if="claimBusy") Applying…
                span(v-else) Apply invitation

        div.account-teams-gap
          teams-membership-card(
            subtitle="Add team IDs you should belong to. You can edit this later under Account after registration."
          )

        b-card.aw-account-card.aw-account-card--dim.mb-4(no-body)
          b-card-body.aw-account-card__body
            .d-flex.align-items-start
              .aw-account-card__icon.aw-account-card__icon--meta.mr-3(style="width:40px;height:40px;")
                icon(name="info-circle")
              div
                .aw-field-label Device UUID
                .aw-readonly.aw-readonly--mono.aw-readonly--sm.mb-0 {{ userStore.uuid }}
                small.text-muted Generated on this device and sent when you register.

        div.d-flex.justify-content-end.pt-1
          b-button(variant="dark", class="aw-btn-save", @click="submitRegister")
            | Register
</template>

<script lang="ts">
import { useUserStore } from '~/stores/user';
import TeamsMembershipCard from '@/components/TeamsMembershipCard.vue';
import 'vue-awesome/icons/id-card.js';
import 'vue-awesome/icons/envelope.js';
import 'vue-awesome/icons/fingerprint.js';
import 'vue-awesome/icons/user-plus.js';
import 'vue-awesome/icons/info-circle.js';
import 'vue-awesome/icons/key.js';
export default {
  name: 'User',
  components: { TeamsMembershipCard },
  data() {
    return {
      error: '',
      username: '',
      email: '',
      userStore: useUserStore(),
      invitationToken: '',
      claimBusy: false,
      claimError: '',
    };
  },
  watch: {
    'userStore.gfpsAccountMode'(mode: string, prev: string) {
      if (mode === 'ready' && prev === 'unreachable') {
        this.username = this.userStore.username;
        this.email = this.userStore.email;
      }
    },
  },
  mounted: async function () {
    await this.init();
  },
  methods: {
    async init() {
      await this.userStore.ensureLoaded();
      this.username = this.userStore.username;
      this.email = this.userStore.email;
    },
    async submit() {
      this.error = '';
      try {
        await this.userStore.update({
          username: this.username,
          email: this.email,
          teams: [...this.userStore.teams],
        });
        await this.userStore.load();
        this.username = this.userStore.username;
        this.email = this.userStore.email;
        window.location.reload();
      } catch (e: unknown) {
        this.error = e instanceof Error ? e.message : String(e);
      }
    },
    async submitRegister() {
      this.error = '';
      try {
        await this.userStore.register({
          username: this.username,
          email: this.email,
          teams: [...this.userStore.teams],
        });
        await this.userStore.load();
        this.username = this.userStore.username;
        this.email = this.userStore.email;
        window.location.reload();
      } catch (e: unknown) {
        this.error = e instanceof Error ? e.message : String(e);
      }
    },
    async submitClaimInvitation() {
      this.claimError = '';
      const t = this.invitationToken.trim();
      if (!t) return;
      this.claimBusy = true;
      try {
        const body = await this.userStore.claimInvitation(t);
        const st = body.status;
        if (st === 'success') {
          this.invitationToken = '';
          await this.userStore.load();
          const name = this.username.trim();
          const em = this.email.trim();
          if (name || em || this.userStore.teams.length) {
            try {
              await this.userStore.update({
                username: name || this.userStore.username,
                email: em || this.userStore.email,
                teams: [...this.userStore.teams],
              });
            } catch (updErr) {
              this.claimError =
                (updErr instanceof Error ? updErr.message : String(updErr)) +
                ' — account was created; you can set username and email under Account.';
              return;
            }
          }
          window.location.reload();
          return;
        }
        const msg =
          (typeof body.message === 'string' && body.message) ||
          (typeof body.error === 'string' && body.error) ||
          'This invitation token is not valid or has already been used.';
        this.claimError = msg;
      } catch (e: unknown) {
        this.claimError = e instanceof Error ? e.message : String(e);
      } finally {
        this.claimBusy = false;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.user-account-page {
  max-width: 52rem;
  margin: 0 auto;
}

.user-account-page__hero {
  padding-bottom: 0.25rem;
}

.user-account-page__title {
  font-weight: 700;
  font-size: 1.75rem;
  letter-spacing: -0.02em;
  color: #1a1a1a;
  margin-bottom: 0.35rem;
}

.user-account-page__lead {
  font-size: 0.95rem;
  color: #6c757d;
  line-height: 1.45;
  margin-bottom: 0;
  max-width: 40rem;
}

/* Cards — aligned with TeamsMembershipCard */
.aw-account-card {
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  border: 1px solid #e8e8e8;
  overflow: hidden;

  ::v-deep .card-header {
    background: linear-gradient(180deg, #fafbfc 0%, #f4f5f7 100%);
    border-bottom: 1px solid #e8e8e8;
    padding: 1rem 1.25rem;
  }

  ::v-deep .card-body {
    padding: 1.25rem;
  }
}

.aw-account-card--dim {
  ::v-deep .card-header {
    background: #fafbfc;
  }
}

.aw-account-card__head {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.aw-account-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  color: #fff;
  flex-shrink: 0;
}

.aw-account-card__icon--identity {
  background: linear-gradient(135deg, #5b7cfa 0%, #4a69d4 100%);
}

.aw-account-card__icon--contact {
  background: linear-gradient(135deg, #2bb673 0%, #229a5f 100%);
}

.aw-account-card__icon--meta {
  background: linear-gradient(135deg, #8892a6 0%, #6b7588 100%);
}

.aw-account-card__icon--welcome {
  background: linear-gradient(135deg, #5b7cfa 0%, #4a69d4 100%);
}

.aw-account-card__title {
  font-weight: 600;
  font-size: 1.05rem;
  color: #222;
  line-height: 1.2;
}

.aw-account-card__subtitle {
  font-size: 0.8rem;
  color: #6c757d;
  margin-top: 0.15rem;
  line-height: 1.35;
}

.aw-field-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #868e96;
  margin-bottom: 0.4rem;
}

.aw-readonly {
  display: block;
  padding: 0.65rem 0.85rem;
  background: #f4f6f9;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  color: #212529;
  font-size: 0.95rem;
  line-height: 1.4;
  min-height: 2.65rem;
}

.aw-readonly--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.88rem;
}

.aw-readonly--sm {
  font-size: 0.85rem;
  padding: 0.5rem 0.75rem;
  min-height: auto;
}

/* Inputs — softer than default Bootstrap */
.aw-input {
  border-radius: 8px !important;
  border: 1px solid #d8dde3 !important;
  padding: 0.6rem 0.9rem !important;
  font-size: 0.95rem !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;

  &:focus {
    border-color: #7c9cff !important;
    box-shadow: 0 0 0 3px rgba(91, 124, 250, 0.2) !important;
  }
}

/* Space between Teams card and the following block (collapse-safe) */
.account-teams-gap {
  margin-bottom: 2rem;
  padding-bottom: 0.125rem;
}

/* Primary actions: neutral / tool UI, not glossy primary */
.aw-btn-save {
  min-width: 11rem;
  font-weight: 500;
  font-size: 0.8125rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-radius: 4px;
  padding: 0.55rem 1.35rem;
  box-shadow: none !important;
}

.aw-btn-save:focus {
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.85), 0 0 0 4px rgba(52, 58, 64, 0.45) !important;
}
</style>
