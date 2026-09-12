export type ToolTag = 'ARM' | 'MKV' | 'HB' | 'FFMPEG' | 'ABCDE' | null

export type LogSegment =
  | { type: 'line'; line: string; tool: ToolTag; lineIndex: number }
  | { type: 'json-block'; content: string; lineIndex: number; collapsed: boolean; preview: string }
  | { type: 'banner-section'; header: string; content: string; lineIndex: number; collapsed: boolean }

const TOOL_TAG_RE = /^\[(ARM|MKV|HB|FFMPEG|ABCDE)\]\s*(.*)/

const BANNER_RE = /^\*{3,}\s+.*/

function isBalancedBraces(s: string): boolean {
  let depth = 0
  let inString = false
  let escape = false
  let quoteChar = ''
  for (const ch of s) {
    if (escape) {
      escape = false
      continue
    }
    if (ch === '\\' && inString) {
      escape = true
      continue
    }
    if (inString) {
      if (ch === quoteChar) {
        inString = false
      }
      continue
    }
    if (ch === '"' || ch === "'") {
      inString = true
      quoteChar = ch
      continue
    }
    if (ch === '{' || ch === '[') {
      depth++
    } else if (ch === '}' || ch === ']') {
      depth--
    }
  }
  return depth === 0 && !inString
}

function tryParseJson(s: string): unknown | null {
  try {
    return JSON.parse(s)
  } catch {
    return null
  }
}

function makeJsonPreview(_raw: string, parsed: unknown): string {
  if (Array.isArray(parsed)) {
    return `[…] ${parsed.length} items`
  }
  if (typeof parsed === 'object' && parsed !== null) {
    const keys = Object.keys(parsed)
    if (keys.length === 0) {
      return '{…}'
    }
    const first = keys[0]
    const val = (parsed as Record<string, unknown>)[first]
    const valStr =
      typeof val === 'string' ? `"${val.length > 24 ? val.slice(0, 24) + '…' : val}"` :
      typeof val === 'number' || typeof val === 'boolean' ? String(val) :
      '{…}'
    return `{…} ${first}: ${valStr}`
  }
  return '{…}'
}

function classifyToolTag(line: string): { tag: ToolTag; clean: string } {
  const m = TOOL_TAG_RE.exec(line)
  if (m) {
    return { tag: m[1] as ToolTag, clean: m[2] }
  }
  return { tag: null, clean: line }
}

function stripLeadingTag(raw: string): string {
  const m = TOOL_TAG_RE.exec(raw)
  return m ? m[2] : raw
}

function looksLikeJsonStart(line: string): boolean {
  const trimmed = stripLeadingTag(line).trimStart()
  return trimmed.startsWith('{') || trimmed.startsWith('[')
}

export function parseLogLines(content: string): LogSegment[] {
  const rawLines = content.split('\n')
  const segments: LogSegment[] = []
  let i = 0

  while (i < rawLines.length) {
    const raw = rawLines[i]

    if (BANNER_RE.test(raw)) {
      const header = raw
      const bannerContent: string[] = []
      i++
      while (i < rawLines.length && !BANNER_RE.test(rawLines[i])) {
        bannerContent.push(rawLines[i])
        i++
      }
      segments.push({
        type: 'banner-section',
        header,
        content: bannerContent.join('\n'),
        lineIndex: segments.length,
        collapsed: true,
      })
      continue
    }

    if (looksLikeJsonStart(raw)) {
      const jsonLines: string[] = [raw]
      let found = isBalancedBraces(raw)
      i++
      while (i < rawLines.length && !found) {
        if (rawLines[i].trim() === '') {
          break
        }
        jsonLines.push(rawLines[i])
        found = isBalancedBraces(jsonLines.join('\n'))
        i++
      }
      const candidate = jsonLines.join('\n')
      const parsed = tryParseJson(candidate)
      if (parsed !== null) {
        segments.push({
          type: 'json-block',
          content: candidate,
          lineIndex: segments.length,
          collapsed: true,
          preview: makeJsonPreview(candidate, parsed),
        })
        continue
      }
      for (const l of jsonLines) {
        const { tag, clean } = classifyToolTag(l)
        segments.push({ type: 'line', line: clean, tool: tag, lineIndex: segments.length })
      }
      continue
    }

    const { tag, clean } = classifyToolTag(raw)
    segments.push({ type: 'line', line: clean, tool: tag, lineIndex: segments.length })
    i++
  }

  return segments
}
