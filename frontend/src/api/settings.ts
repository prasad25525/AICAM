import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Severity } from './events'

export interface AppSettings {
  events_enabled: boolean // save detected violations as events
  notifications_enabled: boolean // pop-up alerts for new events
  notify_severities: Severity[]
}

const KEY = ['settings']

export function useAppSettings() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => (await api.get<AppSettings>('/settings')).data,
    refetchInterval: 30_000,
  })
}

let unsavedClicks = 0 // saves clicked but not finished (queued ones included)

/** Each change shows at once (optimistic), saves run one at a time in click order, and the page
 * re-syncs with the server only after the last one — so quick clicks never undo each other. */
export function useSaveAppSettings() {
  const qc = useQueryClient()
  const mutation = useMutation({
    scope: { id: 'app-settings' },
    mutationFn: async (data: Partial<AppSettings>) => (await api.put<AppSettings>('/settings', data)).data,
    onSettled: () => {
      unsavedClicks -= 1
      if (unsavedClicks === 0) qc.invalidateQueries({ queryKey: KEY })
    },
  })
  // Update the cache synchronously on click (not in onMutate, which runs only when a queued save
  // starts), so the next click already builds on this one.
  const mutate = (data: Partial<AppSettings>, options?: { onSettled?: () => void }) => {
    unsavedClicks += 1
    qc.cancelQueries({ queryKey: KEY })
    qc.setQueryData<AppSettings>(KEY, (old) => old && { ...old, ...data })
    mutation.mutate(data, options) // per-call callbacks fire for the latest call only
  }
  return { ...mutation, mutate }
}
