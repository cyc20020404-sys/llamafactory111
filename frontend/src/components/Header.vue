<template>
  <header class="header">
    <div class="header-left">
      <button class="menu-btn" @click="$emit('toggle-sidebar')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
    </div>
    <div class="header-center">
      <h1 class="title">{{ title }}</h1>
      <div class="subtitle" v-if="subtitle">{{ subtitle }}</div>
    </div>
    <div class="header-right">
      <button class="icon-btn" @click="$emit('clear-chat')" title="Clear Chat">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
      <button class="icon-btn" @click="$emit('toggle-rag')" :class="{ 'active': ragEnabled }" :title="ragEnabled ? 'RAG ON' : 'RAG OFF'">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
      </button>
      <button class="icon-btn" @click="$emit('toggle-theme')" title="Toggle Theme">
        <svg v-if="theme === 'dark'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
        <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      </button>
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: 'Qwen Chat'
  },
  subtitle: {
    type: String,
    default: ''
  },
  theme: {
    type: String,
    default: 'dark'
  },
  ragEnabled: {
    type: Boolean,
    default: false
  }
})

defineEmits(['toggle-sidebar', 'clear-chat', 'toggle-theme', 'toggle-rag'])
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-center {
  text-align: center;
}

.title {
  font-size: 18px;
  font-weight: 600;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.menu-btn,
.icon-btn {
  padding: 8px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.menu-btn:hover,
.icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.icon-btn.active {
  background: var(--accent-primary);
  color: white;
}
</style>
