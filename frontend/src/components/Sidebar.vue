<template>
  <aside class="sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-header">
      <button class="new-chat-btn" @click="$emit('new-chat')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        <span>New Chat</span>
      </button>
    </div>

    <div class="chat-history">
      <div
        v-for="(chat, index) in chatHistory"
        :key="index"
        class="chat-item"
        :class="{ active: activeChatIndex === index }"
        @click="$emit('select-chat', index)"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span class="chat-title">{{ chat.title }}</span>
        <button class="delete-btn" @click.stop="$emit('delete-chat', index)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="model-info">
        <div class="model-badge">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
            <polyline points="2 17 12 22 22 17"></polyline>
            <polyline points="2 12 12 17 22 12"></polyline>
          </svg>
          <span>{{ modelName }}</span>
        </div>
        <div class="status-dot" :class="{ connected: isConnected }"></div>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  chatHistory: {
    type: Array,
    default: () => []
  },
  activeChatIndex: {
    type: Number,
    default: -1
  },
  modelName: {
    type: String,
    default: 'Qwen2.5-3B'
  },
  isConnected: {
    type: Boolean,
    default: false
  },
  isCollapsed: {
    type: Boolean,
    default: false
  }
})

defineEmits(['new-chat', 'select-chat', 'delete-chat'])
</script>

<style scoped>
.sidebar {
  width: 280px;
  height: 100vh;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease, transform 0.3s ease;
}

.sidebar.collapsed {
  width: 0;
  overflow: hidden;
}

.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid var(--border-color);
}

.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--accent-gradient);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.new-chat-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 12px 8px;
}

.chat-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.2s;
  position: relative;
}

.chat-item:hover {
  background: var(--bg-hover);
}

.chat-item.active {
  background: var(--bg-tertiary);
}

.chat-item svg {
  flex-shrink: 0;
  color: var(--text-muted);
}

.chat-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn {
  opacity: 0;
  padding: 4px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: opacity 0.2s, color 0.2s;
}

.delete-btn:hover {
  color: #ef4444;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}

.model-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
}

.model-badge svg {
  color: var(--accent-primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
}

.status-dot.connected {
  background: #22c55e;
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
}
</style>
