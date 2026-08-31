<script setup>
const image = u => u ? `/api/image?url=${encodeURIComponent(u)}` : '/avatar.svg'
defineProps({ item: { type: Object, required: true } })
</script>
<template>
  <div class="comment">
    <div class="comment-head"><img :src="image(item.avatar_url)" @error="$event.target.src='/avatar.svg'"/><span>{{ item.uname || item.uid }}</span><small>{{ item.publish_at }}</small></div>
    <div>{{ item.content }}</div>
    <small v-if="item.like_count > 0">👍 {{ item.like_count }}</small>
    <CommentItem v-for="child in item.children" :key="child.rpid" :item="child"/>
  </div>
</template>
