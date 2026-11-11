import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Severity } from './events'

export interface IndustrySummary {
  key: string
  name: string
  description: string
  icon: string // icon name, see IndustryIcon
}

export interface IndustryList {
  industries: IndustrySummary[]
  active: string
  locked: boolean // a customer installation fixed to one industry: no tabs, no switching
}

export interface PPECheck {
  key: string
  item: string // what should be worn, e.g. "Safety helmet"
  missing: string // short label, e.g. "No helmet"
}

export interface ZoneRule {
  key: string
  label: string
  needs: string // e.g. "Needs a Hand-wash sink zone"
  zone_types: string[][] // every group needed; any type in a group will do
  counts: string | null // a counting rule (e.g. "bags") instead of an alert
}

/** Everything that differs between industries: what to detect, labels, zone types and areas. */
export interface IndustryProfile extends IndustrySummary {
  score_label: string // "Hygiene score" / "Safety score"
  locked: boolean
  areas: { key: string; label: string }[]
  default_area: string
  zone_types: { key: string; label: string; colour: string }[]
  ppe_checks: PPECheck[]
  zone_rules: ZoneRule[]
  event_types: { key: string; label: string; severity: Severity; area: string }[]
  planned: string[] // use cases on the roadmap, shown as "coming soon"
}

/** For the login page: no login needed. */
export function useIndustries() {
  return useQuery({
    queryKey: ['industries'],
    queryFn: async () => (await api.get<IndustryList>('/industries')).data,
    staleTime: 60_000,
  })
}

export const INDUSTRY_KEY = ['industry']

/** The active industry. Polled too, so a switch made in another browser shows up here. */
export function useIndustry() {
  return useQuery({
    queryKey: INDUSTRY_KEY,
    queryFn: async () => (await api.get<IndustryProfile>('/industry')).data,
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
}

/** After a switch every list, chart and count belongs to another industry: drop them all and refetch. */
export function resetForNewIndustry(qc: QueryClient) {
  return qc.resetQueries()
}

export function useSwitchIndustry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (industry: string) => (await api.put<IndustryProfile>('/industry', { industry })).data,
    onSuccess: async (profile) => {
      await resetForNewIndustry(qc)
      qc.setQueryData(INDUSTRY_KEY, profile)
    },
  })
}

// Label helpers that fall back to the raw key, so nothing breaks while the profile loads.
export const areaLabel = (p: IndustryProfile | undefined, key: string) => p?.areas.find((a) => a.key === key)?.label ?? key
export const zoneTypeOf = (p: IndustryProfile | undefined, key: string) =>
  p?.zone_types.find((z) => z.key === key) ?? { key, label: key, colour: '#8f9690' }
export const missingLabel = (p: IndustryProfile | undefined, check: string) => p?.ppe_checks.find((c) => c.key === check)?.missing ?? check
