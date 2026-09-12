import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardMedia,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { applyTitleSearch, fetchTitleDetails, searchJobTitles } from '../api/jobsApi'
import { ApiError } from '../api/http'
import type {
  TitleSearchApplyPayload,
  TitleSearchDetails,
  TitleSearchResponse,
  TitleSearchResult,
} from '../api/types'
import { labels } from '../labels'
import { useToast } from '../providers/useToast'

type TitleSearchStep = 'search' | 'results' | 'details'

function meaningfulText(value: string | null | undefined): string | null {
  if (!value) {
    return null
  }
  const trimmed = value.trim()
  if (!trimmed || trimmed.toLowerCase() === 'none' || trimmed.toLowerCase() === 'unknown') {
    return null
  }
  return trimmed
}

function extractErrorMessage(error: unknown): string | null {
  if (error instanceof ApiError) {
    const bodyError = (error.body as { error?: unknown } | null | undefined)?.error
    if (typeof bodyError === 'string' && bodyError.trim()) {
      return bodyError
    }
    return error.message
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return null
}

function PosterBox({
  src,
  alt,
  height,
  objectFit,
}: {
  src: string
  alt: string
  height: number
  objectFit: 'cover' | 'contain'
}) {
  const [failed, setFailed] = useState(false)
  if (failed || src.trim() === '') {
    return null
  }
  return (
    <Box
      sx={{
        height,
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'action.hover',
        overflow: 'hidden',
      }}
    >
      <CardMedia
        component="img"
        image={src}
        alt={alt}
        onError={() => setFailed(true)}
        sx={{ width: '100%', height, objectFit }}
      />
    </Box>
  )
}

function ResultCard({
  result,
  onSelect,
}: {
  result: TitleSearchResult
  onSelect: (result: TitleSearchResult) => void
}) {
  const poster = meaningfulText(result.poster)
  const title = meaningfulText(result.title) ?? result.imdb_id
  const year = meaningfulText(result.year)
  const type = meaningfulText(result.type)
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardActionArea onClick={() => onSelect(result)} sx={{ height: '100%' }}>
        {poster !== null ? (
          <PosterBox src={poster} alt={title} height={240} objectFit="cover" />
        ) : (
          <Box sx={{ height: 240, bgcolor: 'action.hover' }} />
        )}
        <CardContent sx={{ pt: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, wordBreak: 'break-word' }}>
            {title}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {year ?? '—'}
            </Typography>
            {type !== null && <Chip label={type} size="small" variant="outlined" />}
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  )
}

function DetailsView({ details }: { details: TitleSearchDetails }) {
  const poster = meaningfulText(details.poster)
  const title = meaningfulText(details.title) ?? details.imdb_id
  const year = meaningfulText(details.year)
  const type = meaningfulText(details.type)
  const plot = meaningfulText(details.plot)
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="overline" color="text.secondary">
        {labels.jobDetail.titleSearchDetailsHeading}
      </Typography>
      <Grid container spacing={2}>
        {poster !== null && (
          <Grid size={{ xs: 12, sm: 4 }}>
            <PosterBox src={poster} alt={title} height={240} objectFit="contain" />
          </Grid>
        )}
        <Grid size={{ xs: 12, sm: poster !== null ? 8 : 12 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, wordBreak: 'break-word' }}>
              {title}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {year ?? '—'}
              </Typography>
              {type !== null && <Chip label={type} size="small" variant="outlined" />}
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {labels.jobDetail.titleSearchPlot}
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {plot ?? '—'}
              </Typography>
            </Box>
          </Box>
        </Grid>
      </Grid>
    </Box>
  )
}

export function TitleSearchDialog({
  jobId,
  initialTitle,
  initialYear,
  onClose,
}: {
  jobId: string
  initialTitle: string
  initialYear: string
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [step, setStep] = useState<TitleSearchStep>('search')
  const [customMode, setCustomMode] = useState(false)
  const [title, setTitle] = useState(initialTitle)
  const [year, setYear] = useState(initialYear)
  const [yearError, setYearError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [searchResponse, setSearchResponse] = useState<TitleSearchResponse | null>(null)
  const [selected, setSelected] = useState<TitleSearchResult | null>(null)

  const searchMutation = useMutation({
    mutationFn: () => searchJobTitles(jobId, title.trim(), year.trim()),
    onSuccess: (data) => {
      setSearchError(null)
      setSearchResponse(data)
      setStep('results')
    },
    onError: (error) => {
      setSearchError(extractErrorMessage(error) ?? labels.jobDetail.titleSearchSearchError)
    },
  })

  const applyMutation = useMutation({
    mutationFn: (payload: TitleSearchApplyPayload) => applyTitleSearch(jobId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      notify(labels.jobDetail.titleSearchApplied)
      onClose()
    },
    onError: (error) => {
      notify(labels.jobDetail.titleSearchApplyError, { severity: 'error' })
      setApplyError(extractErrorMessage(error) ?? labels.jobDetail.titleSearchApplyError)
    },
  })

  const detailsQuery = useQuery({
    queryKey: ['titlesearch', jobId, selected?.imdb_id],
    queryFn: () => fetchTitleDetails(jobId, selected?.imdb_id ?? ''),
    enabled: step === 'details' && selected !== null,
  })

  const handleSearch = () => {
    setSearchError(null)
    setApplyError(null)
    searchMutation.mutate()
  }

  const handleCustomApply = () => {
    setYearError(null)
    setSearchError(null)
    setApplyError(null)
    const trimmedYear = year.trim()
    if (trimmedYear !== '' && !/^\d{1,4}$/.test(trimmedYear)) {
      setYearError(labels.jobDetail.fieldYearInvalid)
      return
    }
    const payload: TitleSearchApplyPayload = { title: title.trim() }
    if (trimmedYear !== '') {
      payload.year = trimmedYear
    }
    applyMutation.mutate(payload)
  }

  const handleSelectResult = (result: TitleSearchResult) => {
    setSelected(result)
    setApplyError(null)
    setStep('details')
  }

  const trimmedTitle = title.trim()

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{labels.jobDetail.titleSearchTitle}</DialogTitle>
      <DialogContent>
        {step === 'search' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, pt: 1 }}>
            {searchError && <Alert severity="error">{searchError}</Alert>}
            {applyError && <Alert severity="error">{applyError}</Alert>}
            <TextField
              margin="dense"
              label={labels.jobDetail.fieldTitle}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              fullWidth
            />
            <TextField
              margin="dense"
              label={labels.jobDetail.fieldYear}
              value={year}
              onChange={(event) => setYear(event.target.value)}
              fullWidth
              error={Boolean(yearError)}
              helperText={yearError}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={customMode}
                  onChange={(event) => {
                    setCustomMode(event.target.checked)
                    setSearchError(null)
                    setYearError(null)
                    setApplyError(null)
                  }}
                />
              }
              label={labels.jobDetail.titleSearchCustomMode}
            />
            {customMode && (
              <Typography variant="caption" color="text.secondary">
                {labels.jobDetail.titleSearchCustomHint}
              </Typography>
            )}
          </Box>
        )}
        {step === 'results' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {searchResponse?.retried_without_year && (
              <Alert severity="info">{labels.jobDetail.titleSearchRetriedWithoutYear}</Alert>
            )}
            {searchResponse === null || searchResponse.results.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {labels.jobDetail.titleSearchResultsEmpty}
              </Typography>
            ) : (
              <Grid container spacing={2}>
                {searchResponse.results.map((result, index) => (
                  <Grid key={`${result.imdb_id}-${index}`} size={{ xs: 6, sm: 4, md: 3 }}>
                    <ResultCard result={result} onSelect={handleSelectResult} />
                  </Grid>
                ))}
              </Grid>
            )}
          </Box>
        )}
        {step === 'details' && (
          <>
            {applyError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {applyError}
              </Alert>
            )}
            {detailsQuery.isPending ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : detailsQuery.isError || detailsQuery.data === undefined ? (
              <Alert severity="error">
                {extractErrorMessage(detailsQuery.error) ?? labels.jobDetail.titleSearchDetailsError}
              </Alert>
            ) : (
              <DetailsView details={detailsQuery.data} />
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        {step === 'results' && (
          <Button
            onClick={() => setStep('search')}
            disabled={searchMutation.isPending || applyMutation.isPending}
          >
            {labels.jobDetail.titleSearchBack}
          </Button>
        )}
        {step === 'details' && (
          <Button
            onClick={() => setStep('results')}
            disabled={searchMutation.isPending || applyMutation.isPending}
          >
            {labels.jobDetail.titleSearchBack}
          </Button>
        )}
        <Button onClick={onClose} disabled={searchMutation.isPending || applyMutation.isPending}>
          {labels.jobDetail.cancel}
        </Button>
        {step === 'search' &&
          (customMode ? (
            <Button
              variant="contained"
              onClick={handleCustomApply}
              disabled={trimmedTitle === '' || applyMutation.isPending}
              startIcon={applyMutation.isPending ? <CircularProgress size={16} /> : undefined}
            >
              {labels.jobDetail.titleSearchApply}
            </Button>
          ) : (
            <Button
              variant="contained"
              onClick={handleSearch}
              disabled={trimmedTitle === '' || searchMutation.isPending}
              startIcon={searchMutation.isPending ? <CircularProgress size={16} /> : undefined}
            >
              {labels.jobDetail.titleSearchSearch}
            </Button>
          ))}
        {step === 'details' && selected !== null && (
          <Button
            variant="contained"
            onClick={() => applyMutation.mutate({ imdb_id: selected.imdb_id })}
            disabled={applyMutation.isPending}
            startIcon={applyMutation.isPending ? <CircularProgress size={16} /> : undefined}
          >
            {labels.jobDetail.titleSearchApply}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
}
