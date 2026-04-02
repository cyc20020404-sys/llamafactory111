<template>
  <div class="chat-input-container">
    <div class="input-wrapper" :class="{ disabled: disabled }">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        @keydown="handleKeyDown"
        @input="autoResize"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="1"
      ></textarea>
      <div class="input-actions">
        <span class="char-count" v-if="inputText.length > 0">{{ inputText.length }}</span>
        <button
          class="send-btn"
          :class="{ active: canSend }"
          :disabled="!canSend"
          @click="handleSend"
        >
          <svg v-if="!loading" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          <svg v-else class="spinner" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="32"></circle>
          </svg>
        </button>
      </div>
    </div>
    <p class="hint">Press Enter to send, Shift+Enter for new line</p>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  placeholder: {
    type: String,
    default: 'Type your message here...'
  }
})

const emit = defineEmits(['update:modelValue', 'send'])

const textareaRef = ref(null)
const inputText = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !props.disabled && !props.loading
})

const handleKeyDown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (canSend.value) {
      handleSend()
    }
  }
}

const handleSend = () => {
  if (canSend.value) {
    emit('send', inputText.value.trim())
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.style.height = 'auto'
      }
    })
  }
}

const autoResize = () => {
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
      textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 200) + 'px'
    }
  })
}

watch(() => props.loading, (newVal) => {
  if (!newVal && textareaRef.value) {
    textareaRef.value.focus()
  }
})
</script>

<style scoped>
.chat-input-container {
  padding: 16px 24px 24px;
  background: linear-gradient(to top, var(--bg-primary) 0%, transparent 100%);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-wrapper:focus-within {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.input-wrapper.disabled {
  opacity: 0.6;
  pointer-events: none;
}

textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 15px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  max-height: 200px;
}

textarea::placeholder {
  color: var(--text-muted);
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.char-count {
  font-size: 11px;
  color: var(--text-muted);
  padding: 4px 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border: none;
  border-radius: 50%;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn.active {
  background: var(--accent-gradient);
  color: white;
  transform: scale(1.05);
}

.send-btn.active:hover {
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}

.send-btn.active:active {
  transform: scale(0.95);
}

.spinner {
  animation: spin 1s linear infinite;
}

.hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}
</style>
