import { createContext, useContext } from 'react'

export type ToastSeverity = 'success' | 'error' | 'info' | 'warning'

export interface ToastOptions {
  severity?: ToastSeverity
  duration?: number
  notificationId?: string
}

export interface ToastItem {
  id: string
  message: string
  severity: ToastSeverity
  duration: number
  notificationId?: string
}

export interface ToastContextValue {
  notify: (message: string, options?: ToastOptions) => void
  unreadCount: number
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}
