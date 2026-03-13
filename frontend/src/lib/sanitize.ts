/**
 * Frontend XSS sanitization for AI-generated content.
 *
 * Defense-in-depth layer — ReactMarkdown already sanitizes HTML by default,
 * but this adds an extra pass for any AI response text before rendering.
 */

/**
 * Strip potentially dangerous HTML/JS from AI response text.
 *
 * Removes:
 * - <script> tags and content
 * - Event handler attributes (onclick, onerror, onload, etc.)
 * - javascript: URI schemes
 * - <iframe>, <object>, <embed> tags
 * - data: URI schemes (can embed executable content)
 *
 * @param text - Raw AI response text (may contain markdown)
 * @returns Sanitized text safe for rendering
 */
export function sanitizeAIResponse(text: string): string {
  if (!text) return ""

  let cleaned = text

  // 1. Remove <script> tags and their content
  cleaned = cleaned.replace(/<script[\s\S]*?<\/script>/gi, "")

  // 2. Remove <style> tags and their content
  cleaned = cleaned.replace(/<style[\s\S]*?<\/style>/gi, "")

  // 3. Remove dangerous HTML tags
  cleaned = cleaned.replace(/<\s*\/?\s*(iframe|object|embed|applet|form)\b[^>]*>/gi, "")

  // 4. Remove event handler attributes (on*)
  cleaned = cleaned.replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, "")
  cleaned = cleaned.replace(/\s+on\w+\s*=\s*[^\s>]+/gi, "")

  // 5. Remove javascript: and data: URI schemes
  cleaned = cleaned.replace(/javascript\s*:/gi, "")
  cleaned = cleaned.replace(/data\s*:\s*text\/html/gi, "")

  // 6. Remove base64-encoded content in data URIs that could be executable
  cleaned = cleaned.replace(/data\s*:[^;]*;base64\s*,\s*[A-Za-z0-9+/=]+/gi, "")

  return cleaned
}
