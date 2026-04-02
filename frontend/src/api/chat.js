const API_BASE_URL = import.meta.env.VITE_API_URL || ''
const RAG_API_URL = import.meta.env.VITE_RAG_API_URL || ''

export async function sendMessage(messages, onChunk, onComplete, onError) {
  const controller = new AbortController()

  try {
    const response = await fetch(`${API_BASE_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'qwen2.5-3b',
        messages: messages,
        stream: true,
        temperature: 0.7,
        max_tokens: 2048,
        top_p: 0.9,
      }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullContent = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)

          if (data === '[DONE]') {
            continue
          }

          try {
            const parsed = JSON.parse(data)
            const content = parsed.choices?.[0]?.delta?.content

            if (content) {
              fullContent += content
              onChunk(content, fullContent)
            }
          } catch (e) {
            // Ignore parse errors for incomplete JSON
          }
        }
      }
    }

    onComplete(fullContent)
    return fullContent
  } catch (error) {
    if (error.name === 'AbortError') {
      onComplete(fullContent)
      return fullContent
    }
    try { onError(error) } catch (e) { console.error('onError callback failed:', e) }
    return
  }
}

// RAG API Methods
export async function syncChatHistory(chatId, messages) {
  try {
    const response = await fetch(`${RAG_API_URL}/api/rag/index`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        chat_id: chatId,
        messages: messages.map((msg, idx) => ({
          id: `${chatId}-${idx}`,
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp || new Date().toISOString()
        }))
      })
    })

    if (!response.ok) {
      throw new Error(`Sync failed: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Failed to sync chat history:', error)
    return { status: 'error', error: error.message }
  }
}

export async function ragQuery(query, chatId = null, topK = 5) {
  try {
    const response = await fetch(`${RAG_API_URL}/api/rag/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        chat_id: chatId,
        top_k: topK,
        include_context: true
      })
    })

    if (!response.ok) {
      throw new Error(`RAG query failed: ${response.status}`)
    }

    const result = await response.json()

    // Add quality label for display
    if (result.quality_info) {
      const level = result.quality_info.level
      const confidence = result.quality_info.confidence
      result.quality_info.level_label = {
        'high': 'High Quality',
        'medium': 'Medium Quality',
        'low': 'Low Quality',
        'none': 'No Match',
        'insufficient': 'Below Threshold'
      }[level] || level

      // Color coding
      result.quality_info.color = {
        'high': '#4CAF50',
        'medium': '#FF9800',
        'low': '#F44336',
        'none': '#9E9E9E',
        'insufficient': '#9E9E9E'
      }[level] || '#9E9E9E'
    }

    return result
  } catch (error) {
    console.error('RAG query failed:', error)
    return {
      enhanced_prompt: query,
      retrieved_contexts: [],
      context_count: 0,
      quality_info: {
        level: 'error',
        level_label: 'Error',
        color: '#F44336',
        confidence: 0
      }
    }
  }
}

export async function ragChatCompletions(messages, chatId = null, onChunk, onComplete, onError) {
  const controller = new AbortController()

  try {
    // Get RAG enhanced context with quality analysis
    const ragResult = await ragQuery(messages[messages.length - 1].content, chatId)

    // Build enhanced messages based on quality
    let systemPrompt = `You are a helpful AI assistant.`

    if (ragResult.quality_info) {
      const quality = ragResult.quality_info.level
      if (quality === 'high' || quality === 'medium') {
        systemPrompt = `You are a helpful AI assistant. Use the provided context from the conversation history to answer questions accurately.`
      } else if (quality === 'low') {
        systemPrompt = `You are a helpful AI assistant. The provided context has low relevance - answer primarily based on your knowledge and use context as supplementary reference only.`
      } else if (quality === 'none') {
        systemPrompt = `You are a helpful AI assistant. No relevant context was found in the conversation history - answer based on your general knowledge.`
      }
    }

    const enhancedMessages = [
      { role: 'system', content: systemPrompt },
      ...messages.slice(0, -1),
      { role: 'user', content: ragResult.enhanced_prompt }
    ]

    // Call LLaMA Factory API with enhanced prompt
    const response = await fetch(`${RAG_API_URL}/api/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'qwen2.5-3b',
        messages: enhancedMessages,
        stream: true,
        temperature: 0.7,
        max_tokens: 2048,
      }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullContent = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)

          if (data === '[DONE]') {
            continue
          }

          try {
            const parsed = JSON.parse(data)
            const content = parsed.choices?.[0]?.delta?.content

            if (content) {
              fullContent += content
              onChunk(content, fullContent, ragResult.retrieved_contexts, ragResult.quality_info)
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
      }
    }

    // Pass quality info to completion
    onComplete(fullContent, ragResult.retrieved_contexts, ragResult.quality_info)
    return fullContent
  } catch (error) {
    if (error.name === 'AbortError') {
      onComplete('')
      return ''
    }
    try { onError(error) } catch (e) { console.error('onError callback failed:', e) }
    return
  }
}

export async function getRAGStats() {
  try {
    const response = await fetch(`${RAG_API_URL}/api/rag/stats`)
    if (!response.ok) {
      throw new Error(`Stats failed: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Failed to get RAG stats:', error)
    return null
  }
}

export function abortCurrentRequest() {
  // Controller is managed externally
}

export const sendChatMessage = sendMessage
