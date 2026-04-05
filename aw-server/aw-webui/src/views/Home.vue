<template lang="pug">
div
  b-alert(v-if="$isAndroid" show)
    | #[b Note:] ActivityWatch on Android is in a very early stage of development.

  h3 Welcome
  p.mb-0
    | Use the menu to open Activity, Timeline, or Account. You can change the default landing page in
    | #[router-link(to="/settings") Settings].

</template>

<script lang="ts">
export default {
  name: 'Home',
};
</script>
