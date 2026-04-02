<template>
  <div class="message" :class="{ 'user-message': isUser }">
    <div class="message-avatar">
      <div v-if="isUser" class="avatar user-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
        </svg>
      </div>
      <div v-else class="avatar bot-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </div>
    </div>
    <div class="message-content">
      <div class="message-bubble" v-html="renderedContent"></div>
      <div class="message-meta">
        <span class="timestamp">{{ formattedTime }}</span>
        <div class="message-actions" v-if="!isUser">
          <button class="action-btn" @click="copyContent" :title="copied ? 'Copied!' : 'Copy'">
            <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

const props = defineProps({
  content: {
    type: String,
    required: true
  },
  isUser: {
    type: Boolean,
    default: false
  },
  timestamp: {
    type: Date,
    default: () => new Date()
  }
})

const copied = ref(false)

// Configure marked with syntax highlighting
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (e) {}
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

const renderedContent = computed(() => {
  if (props.isUser) {
    return props.content
  }
  return marked(props.content)
})

const formattedTime = computed(() => {
  return props.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}
</script>

<style scoped>
.message {
  display: flex;
  gap: 16px;
  padding: 20px 24px;
  animation: fadeIn 0.3s ease;
}

.user-message {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-avatar {
  background: var(--accent-gradient);
  color: white;
}

.bot-avatar {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid var(--border-color);
  color: var(--accent-primary);
}

.message-content {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.user-message .message-content {
  align-items: flex-end;
}

.message-bubble {
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  position: relative;
}

.user-message .message-bubble {
  background: var(--accent-gradient);
  border: none;
  color: white;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
}

.timestamp {
  font-size: 11px;
  color: var(--text-muted);
}

.message-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message:hover .message-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
}

.action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* User message markdown styles */
.user-message .message-bubble {
  word-wrap: break-word;
}

.user-message .message-bubble :deep(p) {
  margin-bottom: 8px;
}

.user-message .message-bubble :deep(p:last-child) {
  margin-bottom: 0;
}

.user-message .message-bubble :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

.user-message .message-bubble :deep(pre) {
  background: rgba(0, 0, 0, 0.2);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}

.user-message .message-bubble :deep(pre code) {
  background: transparent;
  padding: 0;
}
</style>
