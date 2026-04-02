<template>
  <div class="app" :class="{ 'sidebar-open': sidebarOpen }">
    <Sidebar
      :chats="chats"
      :currentChatId="currentChatId"
      :theme="theme"
      @select-chat="selectChat"
      @new-chat="createNewChat"
      @delete-chat="deleteChat"
      @toggle-theme="toggleTheme"
    />

    <div class="main-container">
      <Header
        :title="currentChat ? currentChat.title : 'Qwen Chat'"
        :subtitle="modelStatus"
        :theme="theme"
        :rag-enabled="ragEnabled"
        @toggle-sidebar="sidebarOpen = !sidebarOpen"
        @clear-chat="clearCurrentChat"
        @toggle-theme="toggleTheme"
        @toggle-rag="toggleRAG"
      />

      <div class="chat-area" ref="chatAreaRef">
        <div class="chat-content">
          <template v-if="currentChat && currentChat.messages.length > 0">
            <ChatMessage
              v-for="(msg, index) in currentChat.messages"
              :key="index"
              :content="msg.content"
              :is-user="msg.role === 'user'"
              :timestamp="msg.timestamp"
              :rag-context="msg.ragContext"
            />

            <div v-if="currentChat.lastRagContexts && currentChat.lastRagContexts.length > 0" class="rag-context-panel">
              <div class="rag-context-header">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                <span>RAG Context ({{ currentChat.lastRagContexts.length }} sources)</span>
                <span v-if="currentChat.lastRagQuality" class="rag-quality-badge" :style="{ backgroundColor: currentChat.lastRagQuality.color }">
                  {{ currentChat.lastRagQuality.level_label || currentChat.lastRagQuality.level }}
                </span>
              </div>
              <div v-if="currentChat.lastRagQuality" class="rag-quality-info">
                <span>Confidence: {{ (currentChat.lastRagQuality.confidence * 100).toFixed(0) }}%</span>
                <span>Best Score: {{ (currentChat.lastRagQuality.best_score * 100).toFixed(1) }}%</span>
              </div>
              <div class="rag-context-list">
                <div
                  v-for="(ctx, idx) in currentChat.lastRagContexts"
                  :key="idx"
                  class="rag-context-item"
                >
                  <span class="rag-context-score">Score: {{ (ctx.score * 100).toFixed(1) }}%</span>
                  <p class="rag-context-content">{{ ctx.content }}</p>
                </div>
              </div>
            </div>
          </template>

          <div v-else class="empty-state">
            <div class="empty-icon">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
            </div>
            <h2>Start a conversation</h2>
            <p v-if="ragEnabled">RAG mode enabled - searching through your chat history</p>
            <p v-else>Ask me anything about your data, code, or any topic</p>
            <div class="suggestions">
              <button
                v-for="suggestion in suggestions"
                :key="suggestion"
                class="suggestion-btn"
                @click="useSuggestion(suggestion)"
              >
                {{ suggestion }}
              </button>
            </div>
          </div>

          <div v-if="isLoading" class="loading-indicator">
            <div class="loading-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <ChatInput
        v-model="inputText"
        :disabled="isLoading"
        :loading="isLoading"
        placeholder="Type your message, press Enter to send..."
        @send="handleSendMessage"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import Header from './components/Header.vue'
import Sidebar from './components/Sidebar.vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import { sendChatMessage, syncChatHistory, ragChatCompletions } from './api/chat.js'

const CHATS_KEY = 'qwen-chat-chats'
const THEME_KEY = 'qwen-chat-theme'
const RAG_ENABLED_KEY = 'qwen-chat-rag-enabled'

const inputText = ref('')
const isLoading = ref(false)
const sidebarOpen = ref(false)
const chatAreaRef = ref(null)
const chats = ref([])
const currentChatId = ref(null)
const theme = ref(localStorage.getItem(THEME_KEY) || 'dark')
const ragEnabled = ref(localStorage.getItem(RAG_ENABLED_KEY) === 'true')

const suggestions = [
  'Explain quantum computing in simple terms',
  'Write a Python function to sort a list',
  'What are the best practices for API design?',
  'Help me debug this code snippet',
]

const modelStatus = computed(() => {
  if (isLoading.value) return 'Generating response...'
  const ragStatus = ragEnabled.value ? ' | RAG ON' : ' | RAG OFF'
  return 'Qwen2.5-3B' + ragStatus
})

const currentChat = computed(() => {
  return chats.value.find(c => c.id === currentChatId.value) || null
})

watch(theme, (newTheme) => {
  localStorage.setItem(THEME_KEY, newTheme)
  document.documentElement.setAttribute('data-theme', newTheme)
})

const loadChats = () => {
  try {
    const saved = localStorage.getItem(CHATS_KEY)
    if (saved) {
      chats.value = JSON.parse(saved)
      if (chats.value.length > 0) {
        currentChatId.value = chats.value[0].id
      }
    }
  } catch (e) {
    console.error('Failed to load chats:', e)
  }
}

const saveChats = () => {
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats.value))
  } catch (e) {
    console.error('Failed to save chats:', e)
  }
}

const createNewChat = () => {
  const id = Date.now().toString()
  const chat = {
    id,
    title: 'New Chat',
    messages: [],
    lastRagContexts: null,
    createdAt: new Date().toISOString()
  }
  chats.value.unshift(chat)
  currentChatId.value = id
  saveChats()
}

const selectChat = (id) => {
  currentChatId.value = id
  sidebarOpen.value = false
}

const deleteChat = (id) => {
  const idx = chats.value.findIndex(c => c.id === id)
  if (idx !== -1) {
    chats.value.splice(idx, 1)
    if (currentChatId.value === id) {
      currentChatId.value = chats.value[0]?.id || null
    }
    saveChats()
  }
}

const clearCurrentChat = () => {
  if (currentChat.value) {
    currentChat.value.messages = []
    currentChat.value.title = 'New Chat'
    currentChat.value.lastRagContexts = null
    saveChats()
  }
}

const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

const toggleRAG = () => {
  ragEnabled.value = !ragEnabled.value
  localStorage.setItem(RAG_ENABLED_KEY, ragEnabled.value.toString())
}

const useSuggestion = (text) => {
  inputText.value = text
  handleSendMessage(text)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatAreaRef.value) {
      chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
    }
  })
}

// Sync chat history to RAG backend
const syncToRAG = async (chat) => {
  if (chat && chat.messages.length > 0) {
    try {
      await syncChatHistory(chat.id, chat.messages)
    } catch (e) {
      console.warn('RAG sync failed:', e)
    }
  }
}

const handleSendMessage = async (text) => {
  if (!text.trim() || isLoading.value) return

  if (!currentChat.value) {
    createNewChat()
  }

  const userMsg = {
    role: 'user',
    content: text,
    timestamp: new Date()
  }

  currentChat.value.messages.push(userMsg)

  if (currentChat.value.messages.length === 1) {
    currentChat.value.title = text.slice(0, 30) + (text.length > 30 ? '...' : '')
  }

  saveChats()
  inputText.value = ''
  isLoading.value = true
  scrollToBottom()

  const assistantMsg = {
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    ragContext: null,
    ragQuality: null
  }
  currentChat.value.messages.push(assistantMsg)

  try {
    const messages = currentChat.value.messages.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))

    if (ragEnabled.value) {
      // Use RAG-enhanced chat
      await ragChatCompletions(
        messages,
        currentChat.value.id,
        (chunk, fullContent, ragContexts, qualityInfo) => {
          assistantMsg.content = fullContent
          if (ragContexts) {
            assistantMsg.ragContext = ragContexts
          }
          if (qualityInfo) {
            assistantMsg.ragQuality = qualityInfo
          }
          scrollToBottom()
        },
        (fullContent, ragContexts, qualityInfo) => {
          if (ragContexts) {
            assistantMsg.ragContext = ragContexts
          }
          if (qualityInfo) {
            assistantMsg.ragQuality = qualityInfo
          }
          currentChat.value.lastRagContexts = assistantMsg.ragContext
          currentChat.value.lastRagQuality = assistantMsg.ragQuality
          saveChats()
          // Sync updated chat to RAG
          syncToRAG(currentChat.value)
        },
        (err) => {
          assistantMsg.content = `Error: ${err.message || 'Failed to get response'}`
        }
      )
    } else {
      // Regular chat without RAG
      await sendChatMessage(
        messages,
        (chunk) => {
          assistantMsg.content += chunk
          scrollToBottom()
        },
        () => {
          saveChats()
        },
        (err) => {
          assistantMsg.content = `Error: ${err.message || 'Failed to get response'}`
        }
      )
    }
  } catch (err) {
    assistantMsg.content = `Error: ${err.message || 'Failed to get response'}`
  } finally {
    isLoading.value = false
    saveChats()
  }
}

onMounted(() => {
  loadChats()
  document.documentElement.setAttribute('data-theme', theme.value)
})
</script>

<style scoped>
.app {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-primary);
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: margin-left 0.3s ease;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.chat-content {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  text-align: center;
  padding: 40px 20px;
}

.empty-icon {
  color: var(--accent-primary);
  opacity: 0.6;
  margin-bottom: 24px;
}

.empty-state h2 {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.empty-state p {
  font-size: 16px;
  color: var(--text-muted);
  margin-bottom: 32px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 600px;
}

.suggestion-btn {
  padding: 10px 18px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-btn:hover {
  background: var(--bg-tertiary);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
  transform: translateY(-2px);
}

.loading-indicator {
  display: flex;
  justify-content: center;
  padding: 20px;
}

.loading-dots {
  display: flex;
  gap: 6px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: var(--accent-primary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* RAG Context Panel */
.rag-context-panel {
  margin: 16px 0;
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
}

.rag-context-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: var(--accent-primary);
  font-size: 14px;
  font-weight: 500;
}

.rag-context-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rag-context-item {
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: 8px;
  font-size: 13px;
}

.rag-context-score {
  display: inline-block;
  padding: 2px 8px;
  background: var(--accent-primary);
  color: white;
  border-radius: 4px;
  font-size: 11px;
  margin-bottom: 8px;
}

.rag-quality-badge {
  padding: 2px 8px;
  color: white;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  margin-left: auto;
}

.rag-quality-info {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.rag-quality-info span {
  display: flex;
  align-items: center;
}

.rag-context-content {
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 768px) {
  .app.sidebar-open .main-container {
    margin-left: 280px;
  }

  .suggestions {
    flex-direction: column;
  }

  .suggestion-btn {
    width: 100%;
  }
}
</style>
