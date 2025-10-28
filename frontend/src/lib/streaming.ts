import type { ConversationEvent } from './api'

/**
 * Utility class for parsing newline-delimited JSON (NDJSON) streams.
 *
 * Used to consume streaming responses from the API that send ConversationEvent
 * objects as they are generated, one JSON object per line.
 */
export class StreamParser {
  /**
   * Parse a streaming response as newline-delimited JSON.
   *
   * @param url - The URL to fetch from
   * @param options - Fetch options (headers, method, body, etc.)
   * @returns AsyncGenerator yielding ConversationEvent objects
   * @throws Error if the stream request fails
   *
   * @example
   * ```typescript
   * const url = '/api/conversations/1/messages/stream'
   * const options = {
   *   method: 'POST',
   *   headers: { 'Content-Type': 'application/json' },
   *   body: JSON.stringify({ message: 'Hello' })
   * }
   *
   * for await (const event of StreamParser.parseStream(url, options)) {
   *   console.log('Received event:', event)
   * }
   * ```
   */
  static async *parseStream(
    url: string,
    options: RequestInit,
  ): AsyncGenerator<ConversationEvent> {
    const response = await fetch(url, options)

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status} ${response.statusText}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let accumulated = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        accumulated += decoder.decode(value, { stream: true })
        const lines = accumulated.split('\n')

        // Keep last incomplete line in accumulated
        accumulated = lines[lines.length - 1]

        // Process complete lines
        for (let i = 0; i < lines.length - 1; i++) {
          if (lines[i].trim()) {
            try {
              const event = JSON.parse(lines[i]) as ConversationEvent
              yield event
            } catch (e) {
              console.error('Failed to parse JSON line:', lines[i], e)
            }
          }
        }
      }

      // Process final incomplete line if any
      if (accumulated.trim()) {
        const event = JSON.parse(accumulated) as ConversationEvent
        yield event
      }
    } finally {
      reader.releaseLock()
    }
  }
}
