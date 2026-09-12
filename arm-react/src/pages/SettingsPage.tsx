import { useCallback, useMemo, useState } from 'react'
import type { FormEvent, SyntheticEvent } from 'react'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import EjectIcon from '@mui/icons-material/Eject'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import RefreshIcon from '@mui/icons-material/Refresh'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControlLabel,
  Grid,
  IconButton,
  LinearProgress,
  Link,
  MenuItem,
  Paper,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link as RouterLink } from 'react-router-dom'
import { updatePassword } from '../api/authApi'
import { ApiError } from '../api/http'
import {
  fetchAbcdeSettings,
  fetchAppriseSettings,
  fetchArmSettings,
  fetchUiSettings,
  testAppriseNotification,
  updateAbcdeSettings,
  updateAppriseSettings,
  updateArmSettings,
  updateUiSettings,
} from '../api/settingsApi'
import type { ArmSettingValue, ArmSettingsValues, UiSettings, UiSettingsUpdate } from '../api/settingsApi'
import {
  ejectSystemDrive,
  fetchSystemDrivesAdmin,
  manualStartSystemDrive,
  removeSystemDrive,
  scanSystemDrives,
  updateSystemDrive,
} from '../api/systemApi'
import type { SystemDriveUpdate } from '../api/systemApi'
import type { DriveJobInfo, DriveMode, SystemDrive } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { labels } from '../labels'
import { useToast } from '../providers/useToast'

type SettingsTab = 'ripper' | 'ui' | 'abcde' | 'apprise' | 'drives' | 'security'

const MIN_PASSWORD_LENGTH = 6

type NotifySeverity = 'success' | 'error' | 'info'

interface SettingsSection {
  id: string
  label: string
  keys: string[]
}

const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    id: 'general',
    label: labels.settings.sections.general,
    keys: [
      'ARM_NAME',
      'ARM_CHECK_UDF',
      'ARM_CHILDREN',
      'ARM_API_KEY',
      'INSTALLPATH',
      'LOGLEVEL',
      'LOGLIFE',
      'DATE_FORMAT',
      'DISABLE_LOGIN',
      'ALLOW_DUPLICATES',
      'VIDEOTYPE',
      'RIP_POSTER',
      'AUTO_EJECT',
      'DELRAWFILES',
    ],
  },
  {
    id: 'directories',
    label: labels.settings.sections.directories,
    keys: [
      'COMPLETED_PATH',
      'RAW_PATH',
      'TRANSCODE_PATH',
      'LOGPATH',
      'DBFILE',
      'ABCDE_CONFIG_FILE',
    ],
  },
  {
    id: 'webServer',
    label: labels.settings.sections.webServer,
    keys: ['WEBSERVER_IP', 'WEBSERVER_PORT', 'UI_BASE_URL'],
  },
  {
    id: 'permissions',
    label: labels.settings.sections.permissions,
    keys: [
      'SET_MEDIA_PERMISSIONS',
      'SET_MEDIA_OWNER',
      'CHMOD_VALUE',
      'CHOWN_USER',
      'CHOWN_GROUP',
      'UMASK',
    ],
  },
  {
    id: 'makemkv',
    label: labels.settings.sections.makemkv,
    keys: [
      'RIPMETHOD',
      'RIPMETHOD_DVD',
      'RIPMETHOD_BR',
      'MKV_ARGS',
      'MAKEMKV_PERMA_KEY',
      'MAX_CONCURRENT_MAKEMKVINFO',
      'MAINFEATURE',
      'MINLENGTH',
      'MAXLENGTH',
      'PREVENT_99',
    ],
  },
  {
    id: 'handbrake',
    label: labels.settings.sections.handbrake,
    keys: [
      'HB_PRESET_DVD',
      'HB_PRESET_BD',
      'HB_ARGS_DVD',
      'HB_ARGS_BD',
      'HANDBRAKE_CLI',
      'HANDBRAKE_LOCAL',
      'MAX_CONCURRENT_TRANSCODES',
    ],
  },
  {
    id: 'ffmpeg',
    label: labels.settings.sections.ffmpeg,
    keys: [
      'USE_FFMPEG',
      'FFMPEG_CLI',
      'FFMPEG_LOCAL',
      'FFMPEG_PRE_FILE_ARGS',
      'FFMPEG_POST_FILE_ARGS',
      'DEST_EXT',
    ],
  },
  {
    id: 'transcoding',
    label: labels.settings.sections.transcoding,
    keys: ['SKIP_TRANSCODE', 'DATA_RIP_PARAMETERS', 'BASH_SCRIPT', 'EXTRAS_SUB'],
  },
  {
    id: 'metadata',
    label: labels.settings.sections.metadata,
    keys: [
      'METADATA_PROVIDER',
      'OMDB_API_KEY',
      'TMDB_API_KEY',
      'GET_AUDIO_TITLE',
      'GET_VIDEO_TITLE',
    ],
  },
  {
    id: 'emby',
    label: labels.settings.sections.emby,
    keys: [
      'EMBY_SERVER',
      'EMBY_PORT',
      'EMBY_CLIENT',
      'EMBY_DEVICE',
      'EMBY_DEVICEID',
      'EMBY_USERNAME',
      'EMBY_PASSWORD',
      'EMBY_USERID',
      'EMBY_API_KEY',
      'EMBY_REFRESH',
    ],
  },
  {
    id: 'notifications',
    label: labels.settings.sections.notifications,
    keys: [
      'NOTIFY_RIP',
      'NOTIFY_TRANSCODE',
      'NOTIFY_JOBID',
      'PB_KEY',
      'PO_APP_KEY',
      'PO_USER_KEY',
      'IFTTT_KEY',
      'IFTTT_EVENT',
      'JSON_URL',
      'APPRISE',
    ],
  },
  {
    id: 'manual',
    label: labels.settings.sections.manual,
    keys: ['MANUAL_WAIT', 'MANUAL_WAIT_TIME'],
  },
]

const INTEGER_PATTERN = /^\s*-?\d+\s*$/
const COMMENT_LIMIT = 120
const LONG_VALUE_LENGTH = 60

const changedSx = {
  borderLeft: '2px solid',
  borderColor: 'warning.main',
  pl: 1.5,
} as const

function isSettingsTab(value: unknown): value is SettingsTab {
  return (
    value === 'ripper' ||
    value === 'ui' ||
    value === 'abcde' ||
    value === 'apprise' ||
    value === 'drives' ||
    value === 'security'
  )
}

function trimToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

function driveJobLabel(job: DriveJobInfo | null): string {
  if (!job) {
    return '—'
  }
  const title = trimToNull(job.title)
  const status = trimToNull(job.status)
  if (title && status) {
    return `${title} (${status})`
  }
  return title ?? status ?? labels.settings.drives.jobById.replace('{id}', String(job.job_id))
}

function flagValue(value: string | null | undefined): boolean {
  return value?.trim().toLowerCase() === 'true'
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

function numberDraftText(value: ArmSettingValue | undefined): string {
  return value === undefined ? '' : String(value)
}

function isDirtyValue(
  original: ArmSettingValue,
  draftValue: ArmSettingValue | undefined,
): boolean {
  if (typeof original === 'number') {
    const text = numberDraftText(draftValue)
    if (!INTEGER_PATTERN.test(text)) {
      return true
    }
    return Number(text) !== original
  }
  return draftValue !== original
}

function buildSections(values: ArmSettingsValues): SettingsSection[] {
  const mapped = new Set<string>()
  const sections: SettingsSection[] = []
  for (const section of SETTINGS_SECTIONS) {
    const keys = section.keys.filter((key) => key in values)
    for (const key of keys) {
      mapped.add(key)
    }
    if (keys.length > 0) {
      sections.push({ id: section.id, label: section.label, keys })
    }
  }
  const miscKeys = Object.keys(values)
    .filter((key) => !mapped.has(key))
    .sort()
  if (miscKeys.length > 0) {
    sections.push({ id: 'misc', label: labels.settings.sections.misc, keys: miscKeys })
  }
  return sections
}

function CommentText({ comment }: { comment: string }) {
  if (comment.length <= COMMENT_LIMIT) {
    return <>{comment}</>
  }
  const display = `${comment.slice(0, COMMENT_LIMIT).trimEnd()}…`
  return (
    <Tooltip title={comment}>
      <span>{display}</span>
    </Tooltip>
  )
}

function SettingsField({
  settingKey,
  original,
  draftValue,
  comment,
  disabled,
  changed,
  error,
  onChange,
}: {
  settingKey: string
  original: ArmSettingValue
  draftValue: ArmSettingValue | undefined
  comment: string | undefined
  disabled: boolean
  changed: boolean
  error: boolean
  onChange: (value: ArmSettingValue) => void
}) {
  const boxSx = changed ? changedSx : undefined
  if (typeof original === 'boolean') {
    return (
      <Box sx={boxSx}>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={draftValue === true}
              disabled={disabled}
              onChange={(event) => onChange(event.target.checked)}
            />
          }
          label={settingKey}
        />
      </Box>
    )
  }
  const isNumber = typeof original === 'number'
  const multiline =
    !isNumber && typeof original === 'string' && (original.length >= LONG_VALUE_LENGTH || original.includes('\n'))
  const invalidNumber = isNumber && !INTEGER_PATTERN.test(numberDraftText(draftValue))
  return (
    <Box sx={boxSx}>
      <TextField
        size="small"
        fullWidth
        label={settingKey}
        type={isNumber ? 'number' : 'text'}
        multiline={multiline}
        minRows={multiline ? 3 : undefined}
        value={numberDraftText(draftValue)}
        disabled={disabled}
        error={error}
        onChange={(event) => onChange(event.target.value)}
        helperText={
          invalidNumber ? (
            labels.settings.invalidInteger
          ) : comment ? (
            <CommentText comment={comment} />
          ) : undefined
        }
      />
    </Box>
  )
}

function SettingsToolbar({
  changedCount,
  saveDisabled,
  saving,
  readOnly,
  onSave,
  onReset,
}: {
  changedCount: number
  saveDisabled: boolean
  saving: boolean
  readOnly: boolean
  onSave: () => void
  onReset: () => void
}) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1.5, mb: 2 }}>
      {changedCount > 0 ? (
        <Chip
          size="small"
          color="warning"
          variant="outlined"
          label={`${changedCount} ${labels.settings.unsavedChanges}`}
        />
      ) : (
        <Typography variant="body2" color="text.secondary">
          {labels.settings.allSaved}
        </Typography>
      )}
      <Box sx={{ flexGrow: 1 }} />
      <Button size="small" onClick={onReset} disabled={changedCount === 0 || saving}>
        {labels.settings.reset}
      </Button>
      <Button
        size="small"
        variant="contained"
        onClick={onSave}
        disabled={saveDisabled || saving || readOnly}
        startIcon={saving ? <CircularProgress size={16} /> : undefined}
      >
        {labels.settings.save}
      </Button>
    </Box>
  )
}

function RipperSettingsTab({ notify }: { notify: (severity: NotifySeverity, message: string) => void }) {
  const queryClient = useQueryClient()
  const settingsQuery = useQuery({
    queryKey: ['settings', 'arm'],
    queryFn: fetchArmSettings,
  })
  const data = settingsQuery.data
  const [draftState, setDraftState] = useState<{
    source: ArmSettingsValues
    values: ArmSettingsValues
  } | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const values = useMemo<ArmSettingsValues>(() => data?.values ?? {}, [data])
  const currentDraft = draftState !== null && draftState.source === values ? draftState.values : values
  const changedKeys = useMemo(
    () => Object.keys(values).filter((key) => isDirtyValue(values[key], currentDraft[key])),
    [values, currentDraft],
  )
  const invalidKeys = useMemo(
    () =>
      Object.keys(values).filter((key) => {
        const original = values[key]
        if (typeof original !== 'number') {
          return false
        }
        return !INTEGER_PATTERN.test(numberDraftText(currentDraft[key]))
      }),
    [values, currentDraft],
  )
  const erroredKeys = useMemo(() => {
    if (!saveError) {
      return new Set<string>()
    }
    return new Set(
      Object.keys(values).filter((key) => new RegExp(`\\b${key}\\b`).test(saveError)),
    )
  }, [saveError, values])

  const saveMutation = useMutation({
    mutationFn: (changes: Record<string, ArmSettingValue>) => updateArmSettings(changes),
    onSuccess: () => {
      setSaveError(null)
      void queryClient.invalidateQueries({ queryKey: ['settings'] })
      notify('success', labels.settings.saved)
    },
    onError: (error) => {
      setSaveError(extractErrorMessage(error) ?? labels.settings.saveError)
    },
  })

  if (settingsQuery.isPending) {
    return <LinearProgress />
  }
  if (settingsQuery.isError || !data) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => void settingsQuery.refetch()}>
            {labels.settings.retry}
          </Button>
        }
      >
        {labels.settings.loadError}
      </Alert>
    )
  }

  const readOnly = data.read_only
  const disabled = readOnly || saveMutation.isPending
  const changedKeySet = new Set(changedKeys)
  const invalidKeySet = new Set(invalidKeys)
  const sections = buildSections(values)

  const handleSave = () => {
    const payload: Record<string, ArmSettingValue> = {}
    for (const key of changedKeys) {
      const original = values[key]
      if (typeof original === 'number') {
        payload[key] = Number(numberDraftText(currentDraft[key]))
      } else {
        payload[key] = currentDraft[key] as ArmSettingValue
      }
    }
    setSaveError(null)
    saveMutation.mutate(payload)
  }

  const handleReset = () => {
    setDraftState(null)
    setSaveError(null)
  }

  return (
    <Box>
      {readOnly && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {labels.settings.readOnly}
        </Alert>
      )}
      {saveError && (
        <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {saveError}
        </Alert>
      )}
      <SettingsToolbar
        changedCount={changedKeys.length}
        saveDisabled={changedKeys.length === 0 || invalidKeys.length > 0}
        saving={saveMutation.isPending}
        readOnly={readOnly}
        onSave={handleSave}
        onReset={handleReset}
      />
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {sections.map((section, index) => {
          const sectionChanged = section.keys.filter((key) => changedKeySet.has(key)).length
          return (
            <Accordion key={section.id} defaultExpanded={index === 0} variant="outlined" disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {section.label}
                  </Typography>
                  {sectionChanged > 0 && (
                    <Chip size="small" color="warning" variant="outlined" label={sectionChanged} />
                  )}
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  {section.keys.map((key) => (
                    <Grid key={key} size={{ xs: 12, md: 6 }}>
                      <SettingsField
                        settingKey={key}
                        original={values[key]}
                        draftValue={currentDraft[key]}
                        comment={data.comments[key]}
                        disabled={disabled}
                        changed={changedKeySet.has(key)}
                        error={invalidKeySet.has(key) || erroredKeys.has(key)}
                        onChange={(value) =>
                          setDraftState({
                            source: values,
                            values: { ...currentDraft, [key]: value },
                          })
                        }
                      />
                    </Grid>
                  ))}
                </Grid>
              </AccordionDetails>
            </Accordion>
          )
        })}
      </Box>
    </Box>
  )
}

type UiNumberField = 'index_refresh' | 'database_limit' | 'notify_refresh'

interface UiDraftState {
  index_refresh: string
  use_icons: boolean
  save_remote_images: boolean
  bootstrap_skin: string
  language: string
  database_limit: string
  notify_refresh: string
}

const UI_NUMBER_FIELDS: UiNumberField[] = ['index_refresh', 'database_limit', 'notify_refresh']

function uiDraftFromSettings(data: UiSettings): UiDraftState {
  return {
    index_refresh: data.index_refresh,
    use_icons: flagValue(data.use_icons),
    save_remote_images: flagValue(data.save_remote_images),
    bootstrap_skin: data.bootstrap_skin,
    language: data.language,
    database_limit: data.database_limit,
    notify_refresh: data.notify_refresh,
  }
}

function buildUiPayload(draft: UiDraftState, original: UiSettings): UiSettingsUpdate {
  const payload: UiSettingsUpdate = {}
  if (draft.use_icons !== flagValue(original.use_icons)) {
    payload.use_icons = draft.use_icons
  }
  if (draft.save_remote_images !== flagValue(original.save_remote_images)) {
    payload.save_remote_images = draft.save_remote_images
  }
  for (const field of UI_NUMBER_FIELDS) {
    const text = draft[field]
    if (INTEGER_PATTERN.test(text) && Number(text) !== Number(original[field])) {
      payload[field] = Number(text.trim())
    }
  }
  if (draft.bootstrap_skin !== original.bootstrap_skin) {
    payload.bootstrap_skin = draft.bootstrap_skin
  }
  if (draft.language !== original.language) {
    payload.language = draft.language
  }
  return payload
}

function UiSettingsTab({ notify }: { notify: (severity: NotifySeverity, message: string) => void }) {
  const queryClient = useQueryClient()
  const uiQuery = useQuery({
    queryKey: ['settings', 'ui'],
    queryFn: fetchUiSettings,
  })
  const data = uiQuery.data
  const [draftState, setDraftState] = useState<{
    source: UiSettings
    values: UiDraftState
  } | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const currentDraft = useMemo(
    () =>
      data ? (draftState !== null && draftState.source === data ? draftState.values : uiDraftFromSettings(data)) : null,
    [data, draftState],
  )
  const payload = useMemo(
    () => (data && currentDraft ? buildUiPayload(currentDraft, data) : {}),
    [data, currentDraft],
  )
  const invalidNumbers = useMemo(() => {
    if (!currentDraft) {
      return [] as UiNumberField[]
    }
    return UI_NUMBER_FIELDS.filter((field) => !INTEGER_PATTERN.test(currentDraft[field]))
  }, [currentDraft])

  const saveMutation = useMutation({
    mutationFn: (changes: UiSettingsUpdate) => updateUiSettings(changes),
    onSuccess: () => {
      setSaveError(null)
      void queryClient.invalidateQueries({ queryKey: ['settings'] })
      notify('success', labels.settings.saved)
    },
    onError: (error) => {
      setSaveError(extractErrorMessage(error) ?? labels.settings.saveError)
    },
  })

  if (uiQuery.isPending) {
    return <LinearProgress />
  }
  if (uiQuery.isError || !data || !currentDraft) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => void uiQuery.refetch()}>
            {labels.settings.retry}
          </Button>
        }
      >
        {labels.settings.loadError}
      </Alert>
    )
  }

  const changedCount = Object.keys(payload).length
  const saving = saveMutation.isPending

  const handleSave = () => {
    setSaveError(null)
    saveMutation.mutate(payload)
  }

  const handleReset = () => {
    setDraftState(null)
    setSaveError(null)
  }

  return (
    <Box>
      {saveError && (
        <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {saveError}
        </Alert>
      )}
      <SettingsToolbar
        changedCount={changedCount}
        saveDisabled={changedCount === 0 || invalidNumbers.length > 0}
        saving={saving}
        readOnly={false}
        onSave={handleSave}
        onReset={handleReset}
      />
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              size="small"
              fullWidth
              type="number"
              label={labels.settings.uiIndexRefresh}
              value={currentDraft.index_refresh}
              disabled={saving}
              error={invalidNumbers.includes('index_refresh')}
              helperText={invalidNumbers.includes('index_refresh') ? labels.settings.invalidInteger : undefined}
              onChange={(event) =>
                setDraftState({
                  source: data,
                  values: { ...currentDraft, index_refresh: event.target.value },
                })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              size="small"
              fullWidth
              type="number"
              label={labels.settings.uiDatabaseLimit}
              value={currentDraft.database_limit}
              disabled={saving}
              error={invalidNumbers.includes('database_limit')}
              helperText={invalidNumbers.includes('database_limit') ? labels.settings.invalidInteger : undefined}
              onChange={(event) =>
                setDraftState({
                  source: data,
                  values: { ...currentDraft, database_limit: event.target.value },
                })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              size="small"
              fullWidth
              type="number"
              label={labels.settings.uiNotifyRefresh}
              value={currentDraft.notify_refresh}
              disabled={saving}
              error={invalidNumbers.includes('notify_refresh')}
              helperText={invalidNumbers.includes('notify_refresh') ? labels.settings.invalidInteger : undefined}
              onChange={(event) =>
                setDraftState({
                  source: data,
                  values: { ...currentDraft, notify_refresh: event.target.value },
                })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              size="small"
              fullWidth
              label={labels.settings.uiBootstrapSkin}
              value={currentDraft.bootstrap_skin}
              disabled={saving}
              onChange={(event) =>
                setDraftState({
                  source: data,
                  values: { ...currentDraft, bootstrap_skin: event.target.value },
                })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              size="small"
              fullWidth
              label={labels.settings.uiLanguage}
              value={currentDraft.language}
              disabled={saving}
              onChange={(event) =>
                setDraftState({
                  source: data,
                  values: { ...currentDraft, language: event.target.value },
                })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={currentDraft.use_icons}
                  disabled={saving}
                  onChange={(event) =>
                    setDraftState({
                      source: data,
                      values: { ...currentDraft, use_icons: event.target.checked },
                    })
                  }
                />
              }
              label={labels.settings.uiUseIcons}
              sx={payload.use_icons !== undefined ? changedSx : undefined}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={currentDraft.save_remote_images}
                  disabled={saving}
                  onChange={(event) =>
                    setDraftState({
                      source: data,
                      values: { ...currentDraft, save_remote_images: event.target.checked },
                    })
                  }
                />
              }
              label={labels.settings.uiSaveRemoteImages}
              sx={payload.save_remote_images !== undefined ? changedSx : undefined}
            />
          </Grid>
        </Grid>
      </Paper>
    </Box>
  )
}

function FileSettingsTab({
  mode,
  notify,
}: {
  mode: 'abcde' | 'apprise'
  notify: (severity: NotifySeverity, message: string) => void
}) {
  const queryClient = useQueryClient()
  const isAbcde = mode === 'abcde'
  const contentQuery = useQuery({
    queryKey: ['settings', mode],
    queryFn: isAbcde ? fetchAbcdeSettings : fetchAppriseSettings,
  })
  const data = contentQuery.data
  const [draftState, setDraftState] = useState<{
    source: string
    value: string
  } | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const saveMutation = useMutation({
    mutationFn: (nextContent: string) =>
      isAbcde ? updateAbcdeSettings(nextContent) : updateAppriseSettings(nextContent),
    onSuccess: () => {
      setSaveError(null)
      void queryClient.invalidateQueries({ queryKey: ['settings'] })
      notify('success', labels.settings.fileSaved)
    },
    onError: (error) => {
      setSaveError(extractErrorMessage(error) ?? labels.settings.fileSaveError)
    },
  })

  const testMutation = useMutation({
    mutationFn: () => testAppriseNotification(),
    onSuccess: (result) => {
      notify('info', result.message || labels.settings.testSent)
    },
    onError: (error) => {
      notify('error', extractErrorMessage(error) ?? labels.settings.testError)
    },
  })

  if (contentQuery.isPending) {
    return <LinearProgress />
  }
  if (contentQuery.isError || !data) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => void contentQuery.refetch()}>
            {labels.settings.retry}
          </Button>
        }
      >
        {labels.settings.loadError}
      </Alert>
    )
  }

  const current = draftState !== null && draftState.source === data.content ? draftState.value : data.content
  const dirty = current !== data.content
  const readOnly = data.read_only
  const fileLabel = isAbcde ? labels.settings.abcdeFile : labels.settings.appriseFile

  const handleSave = () => {
    setSaveError(null)
    saveMutation.mutate(current)
  }

  const handleReset = () => {
    setDraftState(null)
    setSaveError(null)
  }

  return (
    <Box>
      {readOnly && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {labels.settings.readOnly}
        </Alert>
      )}
      {saveError && (
        <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {saveError}
        </Alert>
      )}
      <SettingsToolbar
        changedCount={dirty ? 1 : 0}
        saveDisabled={!dirty}
        saving={saveMutation.isPending}
        readOnly={readOnly}
        onSave={handleSave}
        onReset={handleReset}
      />
      {!isAbcde && (
        <Box sx={{ mb: 2 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
            startIcon={testMutation.isPending ? <CircularProgress size={16} /> : undefined}
          >
            {labels.settings.testNotification}
          </Button>
        </Box>
      )}
      <TextField
        fullWidth
        multiline
        minRows={8}
        aria-label={fileLabel}
        value={current}
        disabled={readOnly || saveMutation.isPending}
        onChange={(event) =>
          setDraftState({ source: data.content, value: event.target.value })
        }
        sx={{
          '& .MuiInputBase-input': {
            fontFamily: 'monospace',
            fontSize: 14,
            lineHeight: 1.5,
          },
        }}
      />
    </Box>
  )
}

type DriveDialog =
  | { kind: 'edit'; drive: SystemDrive }
  | { kind: 'manual'; drive: SystemDrive }
  | { kind: 'remove'; drive: SystemDrive }

function DriveEditDialog({
  drive,
  notify,
  onClose,
}: {
  drive: SystemDrive
  notify: (severity: NotifySeverity, message: string) => void
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(drive.name ?? '')
  const [description, setDescription] = useState(drive.description ?? '')
  const [mode, setMode] = useState<DriveMode>(drive.drive_mode === 'manual' ? 'manual' : 'auto')
  const [saveError, setSaveError] = useState<string | null>(null)

  const saveMutation = useMutation({
    mutationFn: (changes: SystemDriveUpdate) => updateSystemDrive(drive.drive_id, changes),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['system', 'drives'] })
      notify('success', labels.settings.drives.saved)
      onClose()
    },
    onError: (error) => {
      setSaveError(extractErrorMessage(error) ?? labels.settings.drives.saveError)
    },
  })

  const handleSave = () => {
    setSaveError(null)
    saveMutation.mutate({
      name: name.trim(),
      description: description.trim(),
      drive_mode: mode,
    })
  }

  return (
    <Dialog open onClose={saveMutation.isPending ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{labels.settings.drives.editTitle}</DialogTitle>
      <DialogContent>
        {saveError && (
          <Alert severity="error" sx={{ mb: 1 }}>
            {saveError}
          </Alert>
        )}
        <TextField
          autoFocus
          margin="dense"
          fullWidth
          label={labels.settings.drives.fieldName}
          value={name}
          disabled={saveMutation.isPending}
          onChange={(event) => setName(event.target.value)}
        />
        <TextField
          margin="dense"
          fullWidth
          label={labels.settings.drives.fieldDescription}
          value={description}
          disabled={saveMutation.isPending}
          onChange={(event) => setDescription(event.target.value)}
        />
        <TextField
          select
          margin="dense"
          fullWidth
          label={labels.settings.drives.fieldMode}
          value={mode}
          disabled={saveMutation.isPending}
          onChange={(event) => setMode(event.target.value === 'manual' ? 'manual' : 'auto')}
        >
          <MenuItem value="auto">{labels.settings.drives.modeAuto}</MenuItem>
          <MenuItem value="manual">{labels.settings.drives.modeManual}</MenuItem>
        </TextField>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saveMutation.isPending}>
          {labels.settings.drives.cancel}
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saveMutation.isPending}
          startIcon={saveMutation.isPending ? <CircularProgress size={16} /> : undefined}
        >
          {labels.settings.drives.save}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function DriveConfirmDialog({
  drive,
  mode,
  notify,
  onClose,
}: {
  drive: SystemDrive
  mode: 'manual' | 'remove'
  notify: (severity: NotifySeverity, message: string) => void
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const isManual = mode === 'manual'
  const mutation = useMutation({
    mutationFn: () =>
      isManual ? manualStartSystemDrive(drive.drive_id) : removeSystemDrive(drive.drive_id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['system', 'drives'] })
      notify(
        'success',
        isManual ? labels.settings.drives.manualStarted : labels.settings.drives.removed,
      )
      onClose()
    },
  })

  const title = isManual ? labels.settings.drives.manualStartTitle : labels.settings.drives.removeTitle
  const message = isManual
    ? labels.settings.drives.manualStartMessage
    : labels.settings.drives.removeMessage
  const confirmLabel = isManual
    ? labels.settings.drives.confirmStart
    : labels.settings.drives.confirmRemove
  const fallbackError = isManual
    ? labels.settings.drives.manualStartError
    : labels.settings.drives.removeError

  return (
    <Dialog open onClose={mutation.isPending ? undefined : onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
        {mutation.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {extractErrorMessage(mutation.error) ?? fallbackError}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={mutation.isPending}>
          {labels.settings.drives.cancel}
        </Button>
        <Button
          variant="contained"
          color={isManual ? 'primary' : 'error'}
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function DriveAdminTab({ notify }: { notify: (severity: NotifySeverity, message: string) => void }) {
  const queryClient = useQueryClient()
  const [dialog, setDialog] = useState<DriveDialog | null>(null)

  const drivesQuery = useQuery({
    queryKey: ['system', 'drives'],
    queryFn: fetchSystemDrivesAdmin,
  })

  const invalidateDrives = () => {
    void queryClient.invalidateQueries({ queryKey: ['system', 'drives'] })
  }

  const scanMutation = useMutation({
    mutationFn: scanSystemDrives,
    onSuccess: (result) => {
      invalidateDrives()
      notify(
        'success',
        result.new_drives > 0
          ? labels.settings.drives.scanFound.replace('{count}', String(result.new_drives))
          : labels.settings.drives.scanNone,
      )
    },
    onError: (error) => {
      notify('error', extractErrorMessage(error) ?? labels.settings.drives.scanError)
    },
  })

  const ejectMutation = useMutation({
    mutationFn: (driveName: string) => ejectSystemDrive(driveName),
    onSuccess: () => {
      invalidateDrives()
      notify('success', labels.settings.drives.ejected)
    },
    onError: (error) => {
      notify('error', extractErrorMessage(error) ?? labels.settings.drives.ejectError)
    },
  })

  if (drivesQuery.isPending) {
    return <LinearProgress />
  }
  if (drivesQuery.isError) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => void drivesQuery.refetch()}>
            {labels.settings.retry}
          </Button>
        }
      >
        {labels.settings.drives.loadError}
      </Alert>
    )
  }

  const drives = drivesQuery.data ?? []
  const driveLabels = labels.settings.drives

  return (
    <Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1.5, mb: 2 }}>
        <Box sx={{ flexGrow: 1 }} />
        <Button
          size="small"
          variant="outlined"
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          startIcon={scanMutation.isPending ? <CircularProgress size={16} /> : <RefreshIcon />}
        >
          {driveLabels.rescan}
        </Button>
      </Box>
      {drives.length === 0 ? (
        <Box sx={{ py: 5, textAlign: 'center', border: 1, borderColor: 'divider', borderRadius: 1 }}>
          <Typography color="text.secondary">{driveLabels.empty}</Typography>
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small" aria-label={labels.settings.tabDrives}>
            <TableHead>
              <TableRow>
                <TableCell>{driveLabels.colName}</TableCell>
                <TableCell>{driveLabels.colDescription}</TableCell>
                <TableCell>{driveLabels.colMount}</TableCell>
                <TableCell>{driveLabels.colMode}</TableCell>
                <TableCell>{driveLabels.colJob}</TableCell>
                <TableCell align="right">{driveLabels.colActions}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {drives.map((drive) => {
                const mode: DriveMode = drive.drive_mode === 'manual' ? 'manual' : 'auto'
                return (
                  <TableRow key={drive.drive_id} hover>
                    <TableCell sx={{ wordBreak: 'break-word' }}>
                      {trimToNull(drive.name) ?? trimToNull(drive.mount) ?? '—'}
                    </TableCell>
                    <TableCell sx={{ wordBreak: 'break-word' }}>
                      {trimToNull(drive.description) ?? '—'}
                    </TableCell>
                    <TableCell sx={{ wordBreak: 'break-word' }}>
                      {trimToNull(drive.mount) ?? '—'}
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={mode === 'manual' ? 'warning' : 'default'}
                        label={mode === 'manual' ? driveLabels.modeManual : driveLabels.modeAuto}
                      />
                    </TableCell>
                    <TableCell sx={{ wordBreak: 'break-word' }}>
                      {driveJobLabel(drive.job_current)}
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'inline-flex', gap: 0.5 }}>
                        <Tooltip title={driveLabels.eject}>
                          <span>
                            <IconButton
                              size="small"
                              aria-label={driveLabels.eject}
                              disabled={
                                !drive.name ||
                                (ejectMutation.isPending && ejectMutation.variables === drive.name)
                              }
                              onClick={() => {
                                if (drive.name) {
                                  ejectMutation.mutate(drive.name)
                                }
                              }}
                            >
                              <EjectIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title={driveLabels.edit}>
                          <IconButton
                            size="small"
                            aria-label={driveLabels.edit}
                            onClick={() => setDialog({ kind: 'edit', drive })}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={driveLabels.manualStart}>
                          <span>
                            <IconButton
                              size="small"
                              aria-label={driveLabels.manualStart}
                              disabled={drive.job_current !== null || !drive.mount}
                              onClick={() => setDialog({ kind: 'manual', drive })}
                            >
                              <PlayArrowIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title={driveLabels.remove}>
                          <IconButton
                            size="small"
                            aria-label={driveLabels.remove}
                            onClick={() => setDialog({ kind: 'remove', drive })}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {dialog?.kind === 'edit' && (
        <DriveEditDialog drive={dialog.drive} notify={notify} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'manual' && (
        <DriveConfirmDialog
          drive={dialog.drive}
          mode="manual"
          notify={notify}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === 'remove' && (
        <DriveConfirmDialog
          drive={dialog.drive}
          mode="remove"
          notify={notify}
          onClose={() => setDialog(null)}
        />
      )}
    </Box>
  )
}

function SecurityTab({ notify }: { notify: (severity: NotifySeverity, message: string) => void }) {
  const { logout } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const changeMutation = useMutation({
    mutationFn: () => updatePassword(currentPassword, newPassword),
    onSuccess: () => {
      notify('success', labels.settings.security.changed)
      logout()
    },
    onError: (error) => {
      setFormError(extractErrorMessage(error) ?? labels.settings.security.error)
    },
  })

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)
    if (!currentPassword || !newPassword || !confirmPassword) {
      setFormError(labels.settings.security.required)
      return
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setFormError(labels.settings.security.tooShort)
      return
    }
    if (newPassword !== confirmPassword) {
      setFormError(labels.settings.security.mismatch)
      return
    }
    changeMutation.mutate()
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, maxWidth: 480 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
        {labels.settings.security.title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {labels.settings.security.hint}
      </Typography>
      {formError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {formError}
        </Alert>
      )}
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
      >
        <TextField
          type="password"
          autoComplete="current-password"
          fullWidth
          label={labels.settings.security.currentPassword}
          value={currentPassword}
          disabled={changeMutation.isPending}
          onChange={(event) => setCurrentPassword(event.target.value)}
        />
        <TextField
          type="password"
          autoComplete="new-password"
          fullWidth
          label={labels.settings.security.newPassword}
          value={newPassword}
          disabled={changeMutation.isPending}
          onChange={(event) => setNewPassword(event.target.value)}
        />
        <TextField
          type="password"
          autoComplete="new-password"
          fullWidth
          label={labels.settings.security.confirmPassword}
          value={confirmPassword}
          disabled={changeMutation.isPending}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        <Box>
          <Button
            type="submit"
            variant="contained"
            disabled={changeMutation.isPending}
            startIcon={changeMutation.isPending ? <CircularProgress size={16} /> : undefined}
          >
            {labels.settings.security.submit}
          </Button>
        </Box>
      </Box>
    </Paper>
  )
}

export function SettingsPage() {
  const { isAuthenticated } = useAuth()
  const [tab, setTab] = useState<SettingsTab>('ripper')
  const { notify: notifyToast } = useToast()

  const notify = useCallback((severity: NotifySeverity, message: string) => {
    notifyToast(message, { severity })
  }, [notifyToast])

  const handleTabChange = (_event: SyntheticEvent<Element>, value: unknown) => {
    if (isSettingsTab(value)) {
      setTab(value)
    }
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 800 }}>
          {labels.settings.title}
        </Typography>
        {!isAuthenticated && (
          <Alert severity="info">
            {labels.settings.loginToView}{' '}
            <Link component={RouterLink} to="/login">
              {labels.nav.login}
            </Link>
          </Alert>
        )}
      </Box>

      {isAuthenticated && (
        <Paper variant="outlined" sx={{ mb: 3 }}>
          <Tabs
            value={tab}
            onChange={handleTabChange}
            variant="scrollable"
            allowScrollButtonsMobile
            aria-label={labels.settings.title}
          >
            <Tab value="ripper" label={labels.settings.tabRipper} />
            <Tab value="ui" label={labels.settings.tabUi} />
            <Tab value="abcde" label={labels.settings.tabAbcde} />
            <Tab value="apprise" label={labels.settings.tabApprise} />
            <Tab value="drives" label={labels.settings.tabDrives} />
            <Tab value="security" label={labels.settings.tabSecurity} />
          </Tabs>
        </Paper>
      )}

      {isAuthenticated && tab === 'ripper' && <RipperSettingsTab notify={notify} />}
      {isAuthenticated && tab === 'ui' && <UiSettingsTab notify={notify} />}
      {isAuthenticated && tab === 'abcde' && <FileSettingsTab mode="abcde" notify={notify} />}
      {isAuthenticated && tab === 'apprise' && <FileSettingsTab mode="apprise" notify={notify} />}
      {isAuthenticated && tab === 'drives' && <DriveAdminTab notify={notify} />}
      {isAuthenticated && tab === 'security' && <SecurityTab notify={notify} />}
    </Container>
  )
}
