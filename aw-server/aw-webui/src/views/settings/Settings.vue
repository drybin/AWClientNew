<template lang="pug">
div
  h3 Settings

  hr

  DaystartSettings

  hr

  TimelineDurationSettings

  hr

  LandingPageSettings

  hr

  Theme

  hr

  ColorSettings

  hr

  ActivePatternSettings

  hr

  CategorizationSettings

  //hr

  //DeveloperSettings

  hr

  GFPSServer
</template>

<script lang="ts">
import { useSettingsStore } from '~/stores/settings';

import DaystartSettings from '~/views/settings/DaystartSettings.vue';
import TimelineDurationSettings from '~/views/settings/TimelineDurationSettings.vue';
import CategorizationSettings from '~/views/settings/CategorizationSettings.vue';
import LandingPageSettings from '~/views/settings/LandingPageSettings.vue';
import DeveloperSettings from '~/views/settings/DeveloperSettings.vue';
import Theme from '~/views/settings/Theme.vue';
import ColorSettings from '~/views/settings/ColorSettings.vue';
import ActivePatternSettings from '~/views/settings/ActivePatternSettings.vue';
import GFPSServer from '@/views/settings/GFPSServerSettings.vue';

export default {
  name: 'Settings',
  components: {
    GFPSServer,
    DaystartSettings,
    TimelineDurationSettings,
    CategorizationSettings,
    LandingPageSettings,
    Theme,
    ColorSettings,
    DeveloperSettings,
    ActivePatternSettings,
  },
  async created() {
    await this.init();
  },
  methods: {
    async init() {
      const settingsStore = useSettingsStore();
      return settingsStore.load();
    },
  },
};
</script>
