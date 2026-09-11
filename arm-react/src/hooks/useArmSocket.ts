import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { io, type Socket } from 'socket.io-client'

interface JobProgressPayload {
  job_id: number
  progress: {
    job_id: number
    status: string
    stage: string
    progress: number
    progress_round: number
    eta: string
  }
}

export function useArmSocket(isAuthenticated: boolean): boolean {
  const queryClient = useQueryClient()
  const [isConnected, setIsConnected] = useState(false)
  const socketRef = useRef<Socket | null>(null)

  useEffect(() => {
    if (!isAuthenticated) {
      if (socketRef.current) {
        socketRef.current.disconnect()
        socketRef.current = null
        setIsConnected(false)
      }
      return
    }

    if (socketRef.current) {
      return
    }

    const socket = io({
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 30000,
      reconnectionAttempts: Infinity,
    })

    socketRef.current = socket

    socket.on('connect', () => {
      setIsConnected(true)
      socket.emit('subscribe_all_jobs', {})
    })

    socket.on('disconnect', () => {
      setIsConnected(false)
    })

    socket.on('job_progress', (payload: JobProgressPayload) => {
      const { job_id, progress } = payload

      queryClient.setQueryData(['jobs', job_id, 'progress'], {
        job_id: progress.job_id,
        status: progress.status,
        stage: progress.stage,
        progress: progress.progress,
        eta: progress.eta,
      })

      queryClient.setQueryData(['jobs', 'active'], (old: unknown) => {
        if (!Array.isArray(old)) return old
        return old.map((job: { job_id?: string | number; [key: string]: unknown }) => {
          const jid = job.job_id
          if (String(jid) === String(job_id) || jid === job_id) {
            return {
              ...job,
              status: progress.status,
              stage: progress.stage,
              progress: progress.progress,
              eta: progress.eta,
            }
          }
          return job
        })
      })
    })

    socket.on('job_status_change', () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    })

    socket.on('job_completed', () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    })

    return () => {
      socket.disconnect()
      socketRef.current = null
      setIsConnected(false)
    }
  }, [isAuthenticated, queryClient])

  return isConnected
}
