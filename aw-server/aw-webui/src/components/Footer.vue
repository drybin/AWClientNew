<template lang="pug">
div.container(style="color: #555; font-size: 0.9em")
  div.mb-2(v-if="info")
    span.mr-2(style="color: #888; font-size: 0.8em")
      b Host:
      | &nbsp; {{ info.hostname }}
    span(style="color: #888; font-size: 0.8em")
      b Version:
      | &nbsp; {{ info.version }}
</template>

<script lang="ts">
import { mapState } from 'pinia';
import { useServerStore } from '~/stores/server';

export default {
  name: 'Footer',
  computed: {
    ...mapState(useServerStore, ['info']),
  },
};
</script>
