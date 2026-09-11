import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RefreshIcon from '@mui/icons-material/Refresh'
import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { labels } from '../labels'
import type { ToolTag } from '../utils/logParser'
import { parseLogLines } from '../utils/logParser'

const TOOL_COLORS: Record<string, string> = {
  ARM: '#90a4ae',
  MKV: '#4FC3F7',
  HB: '#FFB74D',
  FFMPEG: '#CE93D8',
  ABCDE: '#81C784',
}

const TOOL_BORDER_COLORS: Record<string, string> = {
  ARM: '#546e7a',
  MKV: '#0288d1',
  HB: '#f57c00',
  FFMPEG: '#8e24aa',
  ABCDE: '#388e3c',
}

type ToolKey = 'ARM' | 'MKV' | 'HB' | 'FFMPEG' | 'ABCDE'

const TOOL_KEYS: ToolKey[] = ['ARM', 'MKV', 'HB', 'FFMPEG', 'ABCDE']

interface LogViewerProps {
  content: string
  isLoading: boolean
  onRefresh?: () => void
}

export function LogViewer({ content, isLoading, onRefresh }: LogViewerProps) {
  const [autoScroll, setAutoScroll] = useState(true)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [collapsedJson, setCollapsedJson] = useState<Record<number, boolean>>({})
  const [collapsedBanners, setCollapsedBanners] = useState<Record<number, boolean>>({})
  const containerRef = useRef<HTMLDivElement | null>(null)

  const segments = useMemo(() => parseLogLines(content), [content])

  const toolColor = useCallback((tool: ToolTag): string | undefined => {
    return tool ? TOOL_COLORS[tool] : undefined
  }, [])

  const handleToolToggle = (_event: React.MouseEvent<HTMLElement>, value: string[]) => {
    setActiveTools(value)
  }

  const toggleJson = useCallback((idx: number) => {
    setCollapsedJson((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }, [])

  const toggleBanner = useCallback((idx: number) => {
    setCollapsedBanners((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }, [])

  useEffect(() => {
    if (autoScroll) {
      const el = containerRef.current
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    }
  }, [autoScroll, content, segments])

  const visibleSegments = useMemo(() => {
    if (activeTools.length === 0) {
      return segments
    }
    return segments.filter((seg) => {
      if (seg.type === 'line') {
        return seg.tool === null || activeTools.includes(seg.tool)
      }
      return true
    })
  }, [segments, activeTools])

  const getIsCollapsedJson = (idx: number): boolean => {
    if (idx in collapsedJson) return collapsedJson[idx]
    return true
  }

  const getIsCollapsedBanner = (idx: number): boolean => {
    if (idx in collapsedBanners) return collapsedBanners[idx]
    return true
  }

  if (isLoading && !content) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography color="text.secondary">{labels.logViewer.loading}</Typography>
      </Paper>
    )
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 2,
          mb: 1,
        }}
      >
        <ToggleButtonGroup
          size="small"
          value={activeTools}
          onChange={handleToolToggle}
          aria-label={labels.logViewer.filterLabel}
          sx={{ flexWrap: 'wrap' }}
        >
          <ToggleButton
            key="all"
            value="all"
            sx={
              activeTools.length === 0
                ? {
                    color: '#e2e8f0',
                    '&.Mui-selected': {
                      backgroundColor: 'rgba(255,255,255,0.1)',
                      color: '#e2e8f0',
                      borderColor: '#e2e8f0',
                    },
                  }
                : undefined
            }
          >
            {labels.logViewer.allTools}
          </ToggleButton>
          {TOOL_KEYS.map((tool) => (
            <ToggleButton
              key={tool}
              value={tool}
              sx={{
                color: TOOL_COLORS[tool],
                '&.Mui-selected': {
                  backgroundColor: `${TOOL_COLORS[tool]}22`,
                  color: TOOL_COLORS[tool],
                  borderColor: TOOL_COLORS[tool],
                },
              }}
            >
              {labels.logViewer.toolNames[tool]}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        <Box sx={{ flexGrow: 1 }} />

        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={autoScroll}
              onChange={(event) => setAutoScroll(event.target.checked)}
            />
          }
          label={labels.logViewer.autoScroll}
        />

        {onRefresh && (
          <Button size="small" startIcon={<RefreshIcon />} onClick={onRefresh}>
            {labels.logViewer.refresh}
          </Button>
        )}
      </Box>

      <Paper
        variant="outlined"
        ref={containerRef}
        sx={{
          maxHeight: 480,
          overflow: 'auto',
          bgcolor: '#0f172a',
          color: '#e2e8f0',
          borderRadius: 1,
          fontFamily: 'monospace',
          fontSize: 13,
          lineHeight: 1.5,
        }}
      >
        {visibleSegments.length === 0 && (
          <Box sx={{ p: 2 }}>
            <Typography color="text.secondary">{labels.logViewer.empty}</Typography>
          </Box>
        )}
        {visibleSegments.map((seg) => {
          const key = `${seg.type}-${seg.lineIndex}`
          if (seg.type === 'line') {
            const borderColor = seg.tool ? TOOL_BORDER_COLORS[seg.tool] : undefined
            return (
              <Box
                key={key}
                sx={{
                  px: 2,
                  py: 0.25,
                  borderLeft: borderColor ? `3px solid ${borderColor}` : '3px solid transparent',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {seg.tool && (
                  <Box
                    component="span"
                    sx={{
                      color: toolColor(seg.tool),
                      fontWeight: 600,
                      mr: 1,
                    }}
                  >
                    [{seg.tool}]
                  </Box>
                )}
                <Box component="span">{seg.line}</Box>
              </Box>
            )
          }

          if (seg.type === 'json-block') {
            const collapsed = getIsCollapsedJson(seg.lineIndex)
            return (
              <Box
                key={key}
                sx={{
                  mx: 0,
                  borderBottom: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <Box
                  onClick={() => toggleJson(seg.lineIndex)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    px: 2,
                    py: 0.5,
                    cursor: 'pointer',
                    userSelect: 'none',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' },
                  }}
                >
                  {collapsed ? (
                    <ChevronRightIcon fontSize="small" />
                  ) : (
                    <ExpandMoreIcon fontSize="small" />
                  )}
                  <Box
                    component="span"
                    sx={{ color: '#90a4ae', fontFamily: 'monospace', fontSize: 13 }}
                  >
                    {collapsed ? seg.preview : labels.logViewer.jsonExpanded}
                  </Box>
                </Box>
                {!collapsed && (
                  <Box
                    sx={{
                      px: 2,
                      pb: 1,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontSize: 12,
                      color: '#b0bec5',
                    }}
                  >
                    {seg.content}
                  </Box>
                )}
              </Box>
            )
          }

          const collapsed = getIsCollapsedBanner(seg.lineIndex)
          const lineCount = seg.content.split('\n').length
          return (
            <Box
              key={key}
              sx={{
                mx: 0,
                borderBottom: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <Box
                onClick={() => toggleBanner(seg.lineIndex)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  px: 2,
                  py: 0.5,
                  cursor: 'pointer',
                  userSelect: 'none',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' },
                }}
              >
                {collapsed ? (
                  <ChevronRightIcon fontSize="small" />
                ) : (
                  <ExpandMoreIcon fontSize="small" />
                )}
                <Box
                  component="span"
                  sx={{ color: '#f48fb1', fontFamily: 'monospace', fontSize: 13, fontWeight: 600 }}
                >
                  {seg.header}
                </Box>
                <Box component="span" sx={{ color: '#78909c', fontSize: 12, ml: 1 }}>
                  {collapsed ? `▼ ${lineCount} ${labels.logViewer.linesSuffix}` : ''}
                </Box>
              </Box>
              {!collapsed && (
                <Box
                  sx={{
                    px: 2,
                    pb: 1,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontSize: 12,
                    color: '#b0bec5',
                  }}
                >
                  {seg.content}
                </Box>
              )}
            </Box>
          )
        })}
      </Paper>
    </Box>
  )
}
