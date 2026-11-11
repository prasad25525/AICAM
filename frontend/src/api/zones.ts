import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

// Zone types (labels and colours) come from the industry pack: see api/industry.ts zoneTypeOf().
export type ZoneType = string
export type Point = [number, number] // fractions (0-1) of the frame width / height

export interface Zone {
  id: number
  camera_id: number
  name: string
  zone_type: ZoneType
  polygon: Point[]
  created_at: string
}

const key = (cameraId?: number) => (cameraId === undefined ? ['zones'] : ['zones', cameraId])

export function useZones(cameraId: number | undefined) {
  return useQuery({
    queryKey: key(cameraId),
    queryFn: async () => (await api.get<Zone[]>(`/cameras/${cameraId}/zones`)).data,
    enabled: cameraId !== undefined,
  })
}

export function useAllZones() {
  return useQuery({ queryKey: ['zones', 'all'], queryFn: async () => (await api.get<Zone[]>('/zones')).data })
}

export function useCreateZone(cameraId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Pick<Zone, 'name' | 'zone_type' | 'polygon'>) => (await api.post<Zone>(`/cameras/${cameraId}/zones`, data)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['zones'] }),
  })
}

export function useUpdateZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...data }: Partial<Pick<Zone, 'name' | 'zone_type' | 'polygon'>> & { id: number }) =>
      (await api.patch<Zone>(`/zones/${id}`, data)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['zones'] }),
  })
}

export function useDeleteZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => api.delete(`/zones/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['zones'] }),
  })
}

export function centroid(points: Point[]): Point {
  const n = points.length
  return [points.reduce((s, p) => s + p[0], 0) / n, points.reduce((s, p) => s + p[1], 0) / n]
}
