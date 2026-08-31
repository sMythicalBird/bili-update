<script setup>
import { ref, onMounted, watch } from 'vue'
import CommentItem from './CommentItem.vue'
const api = async (u, o) => { const r = await fetch(u, o), d = await r.json(); if (!r.ok) throw Error(d.error || '请求失败'); return d }; const fmt = v => v ? new Date(/^\d+$/.test(v) ? Number(v) * 1000 : v).toLocaleString('zh-CN') : ''; const image = u => u ? `/api/image?url=${encodeURIComponent(u)}` : '/avatar.svg'
const items = ref([]), users = ref([]), uid = ref(''), detail = ref(null), loading = ref(false), error = ref('')
async function load() { loading.value = true; try { items.value = (await api(`/api/dynamics?limit=30${uid.value ? '&uid=' + uid.value : ''}`)).items } catch (e) { error.value = e.message } finally { loading.value = false } }
async function open(id) { try { detail.value = await api(`/api/dynamics/${id}`) } catch (e) { error.value = e.message } }
async function refreshComments() { try { detail.value.comments = (await api(`/api/dynamics/${detail.value.id}/refresh-comments`, { method: 'POST' })).comments } catch (e) { error.value = e.message } }
async function refresh(id) { try { await api(`/api/dynamics/${id}/refresh`, { method: 'POST' }); await load(); await open(id) } catch (e) { error.value = e.message } }
watch(uid, load); onMounted(async () => { await load(); try { users.value = await api('/api/users') } catch { } })
</script>
<template>
    <header>
        <div class="brand">Bili<span>·</span>Update</div>
        <div class="filters"><select v-model="uid">
                <option value="">全部 UP 主</option>
                <option v-for="u in users" :key="u.uid" :value="u.uid">{{ u.name || u.uid }}</option>
            </select><button @click="load">{{ loading ? '刷新中…' : '刷新列表' }}</button></div>
    </header>
    <main>
        <h1>动态归档</h1>
        <div v-if="error" class="error">{{ error }}</div>
        <article v-for="i in items" :key="i.id" class="card">
            <div class="author"><img :src="image(i.author_avatar)" @error="$event.target.src='/avatar.svg'" />
                <div><b>{{ i.author_name || i.uid }}</b><small>{{ fmt(i.publish_at) }}</small></div>
            </div>
            <div class="text">{{ i.text || '（无文字内容）' }}</div>
            <div v-if="i.pics?.length" class="pics"><img v-for="(p, n) in i.pics" :key="n" :src="image(p.url)" @error="$event.target.style.display='none'" /></div>
            <div class="card-foot"><span>{{ i.type }}</span><button @click="open(i.id)">查看评论</button><a :href="i.url"
                    target="_blank">打开 B 站</a></div>
        </article>
        <div v-if="!loading && !items.length" class="empty">暂无动态，请先运行后端同步。</div>
    </main>
    <div v-if="detail" class="overlay" @click.self="detail = null">
        <section class="drawer"><button class="close" @click="detail = null">×</button>
            <article class="card">
                <div class="author"><img :src="image(detail.author_avatar)" @error="$event.target.src='/avatar.svg'" />
                    <div><b>{{ detail.author_name || detail.uid }}</b><small>{{ fmt(detail.publish_at) }}</small></div>
                </div>
                <div class="text">{{ detail.text }}</div>
                <div v-if="detail.pics?.length" class="pics"><img v-for="(p, n) in detail.pics" :key="n" :src="image(p.url)" @error="$event.target.style.display='none'" />
                </div>
            </article>
            <div class="comments">
                <h2>评论</h2>
                <CommentItem v-for="c in detail.comments" :key="c.rpid" :item="c" />
                <p v-if="!detail.comments?.length">暂无评论</p>
            </div><button @click="refreshComments">更新评论</button><button @click="refresh(detail.id)">更新动态</button>
        </section>
    </div>
</template>
