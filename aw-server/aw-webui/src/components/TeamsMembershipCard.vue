<template lang="pug">
  b-card.aw-teams-card(no-body)
    template(#header)
      div.d-flex.align-items-start.justify-content-between.flex-wrap
        div.d-flex.align-items-center.mb-1.mb-md-0
          .aw-teams-card__icon.mr-3
            icon(name="users")
          div
            .aw-teams-card__title Teams
            .aw-teams-card__subtitle
              | {{ subtitle }}
        b-badge(v-if="userStore.teams.length", pill, variant="light", class="border")
          | {{ userStore.teams.length }}&nbsp;
          span.text-muted {{ teamCountLabel }}

    //- List
    div.aw-teams-card__list(v-if="userStore.teams.length")
      div.aw-teams-row(
        v-for="(teamId, idx) in userStore.teams",
        :key="'team-' + teamId + '-' + idx"
      )
        span.aw-teams-row__id(:title="teamId") {{ teamId }}
        b-button.aw-teams-row__remove(
          variant="link",
          size="sm",
          :title="'Remove ' + teamId",
          @click="removeAt(idx)"
        )
          icon(name="times")

    div.aw-teams-card__empty(v-else)
      icon.aw-teams-card__empty-icon(name="inbox")
      p.mb-0 No teams yet
      small.text-muted Add a team identifier to sync with GFP.

    //- Add row
    b-card-body.aw-teams-card__footer
      b-form-group.mb-0(:state="hintState", :invalid-feedback="hintText")
        label.sr-only(for="aw-team-id-input") Team ID
        b-input-group(size="lg")
          b-input-group-prepend(is-text)
            icon(name="plus")
          b-form-input#aw-team-id-input(
            v-model="draftId",
            type="text",
            autocomplete="off",
            placeholder="Enter team ID…",
            @keydown.enter.prevent="tryAdd"
          )
          b-input-group-append
            b-button(variant="primary", :disabled="!draftId.trim()", @click="tryAdd")
              span.d-none.d-sm-inline Add team
              span.d-sm-none Add
      small.form-text.text-muted.mt-2.d-block
        | Press Enter to add. IDs are case-sensitive.
</template>

<script lang="ts">
import { useUserStore } from '~/stores/user';
import 'vue-awesome/icons/users';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/inbox';

export default {
  name: 'TeamsMembershipCard',
  props: {
    subtitle: {
      type: String,
      default: 'You can belong to several teams. Changes apply after you save your profile.',
    },
  },
  data() {
    return {
      userStore: useUserStore(),
      draftId: '',
      hint: '' as '' | 'duplicate' | 'empty',
    };
  },
  computed: {
    teamCountLabel(): string {
      return this.userStore.teams.length === 1 ? 'team' : 'teams';
    },
    hintState(): boolean | null {
      if (this.hint === 'duplicate') return false;
      return null;
    },
    hintText(): string {
      if (this.hint === 'duplicate') return 'This team is already in your list.';
      return '';
    },
  },
  methods: {
    tryAdd() {
      const id = this.draftId.trim();
      this.hint = '';
      if (!id) {
        this.hint = 'empty';
        return;
      }
      if (this.userStore.teams.includes(id)) {
        this.hint = 'duplicate';
        return;
      }
      this.userStore.addTeam(id);
      this.draftId = '';
    },
    removeAt(idx: number) {
      this.userStore.removeTeam(idx);
      this.hint = '';
    },
  },
};
</script>

<style lang="scss" scoped>
.aw-teams-card {
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  border: 1px solid #e8e8e8;
  overflow: hidden;

  ::v-deep .card-header {
    background: linear-gradient(180deg, #fafbfc 0%, #f4f5f7 100%);
    border-bottom: 1px solid #e8e8e8;
    padding: 1rem 1.25rem;
  }
}

.aw-teams-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(135deg, #5b7cfa 0%, #4a69d4 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.aw-teams-card__title {
  font-weight: 600;
  font-size: 1.05rem;
  color: #222;
  line-height: 1.2;
}

.aw-teams-card__subtitle {
  font-size: 0.8rem;
  color: #6c757d;
  max-width: 36rem;
  margin-top: 0.15rem;
  line-height: 1.35;
}

.aw-teams-card__list {
  max-height: 280px;
  overflow-y: auto;
}

.aw-teams-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 1.25rem;
  border-bottom: 1px solid #eee;
  gap: 0.75rem;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: #fafafa;
  }
}

.aw-teams-row__id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.9rem;
  word-break: break-all;
  color: #1a1a1a;
}

.aw-teams-row__remove {
  flex-shrink: 0;
  padding: 0.15rem 0.5rem;
  color: #999 !important;

  &:hover {
    color: #c00 !important;
  }
}

.aw-teams-card__empty {
  text-align: center;
  padding: 2rem 1.5rem 1.75rem;
  color: #888;
}

.aw-teams-card__empty-icon {
  font-size: 2rem;
  opacity: 0.35;
  margin-bottom: 0.5rem;
}

.aw-teams-card__footer {
  background: #fafbfc;
  border-top: 1px solid #e8e8e8;
  padding-top: 1rem;
  padding-bottom: 1rem;
}
</style>
