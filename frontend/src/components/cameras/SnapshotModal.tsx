import { useQuery, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { ImageOff, LoaderCircle, RefreshCw } from 'lucide-react'
import { useEffect } from 'react'
import { fetchSnapshot, type Camera } from '../../api/cameras'
import { apiErrorMessage } from '../../lib/api'
import Modal, { btnPrimary, btnSecondary } from '../Modal'

interface Shot {
  url: string
  takenAt: Date
  width: number
  height: number
}

export default function SnapshotModal({ camera, onClose }: { camera: Camera; onClose: () => void }) {
  const qc = useQueryClient()
  const snapshot = useQuery({
    queryKey: ['snapshot', camera.id],
    queryFn: async (): Promise<Shot> => {
      try {
        const url = await fetchSnapshot(camera.id)
        const img = new Image()
        img.src = url
        await img.decode()
        return { url, takenAt: new Date(), width: img.naturalWidth, height: img.naturalHeight }
      } finally {
        qc.invalidateQueries({ queryKey: ['cameras'] }) // the snapshot updated the camera's status
      }
    },
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  })

  const shot = snapshot.data
  const loading = snapshot.isFetching
  const error = snapshot.isError ? apiErrorMessage(snapshot.error) : ''

  // Free each image's memory once it is replaced or the dialog closes.
  useEffect(() => () => {
    if (shot) URL.revokeObjectURL(shot.url)
  }, [shot])

  return (
    <Modal
      title={`Snapshot · ${camera.name}`}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className={btnSecondary}>Close</button>
          <button onClick={() => snapshot.refetch()} disabled={loading} className={btnPrimary}>
            {loading ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCw size={14} />} Refresh
          </button>
        </>
      }
    >
      <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-forest-600 bg-forest-950">
        {shot && !error && <img src={shot.url} alt={`Snapshot from ${camera.name}`} className="h-full w-full object-contain" />}
        {!shot && loading && (
          <div className="flex flex-col items-center gap-2 text-sm text-emerald-100/60">
            <LoaderCircle size={24} className="animate-spin text-lime-glow" />
            Connecting to camera…
          </div>
        )}
        {error && !loading && (
          <div className="flex flex-col items-center gap-2 px-6 text-center text-sm text-red-200">
            <ImageOff size={28} />
            Camera unavailable
          </div>
        )}
        {shot && loading && <div className="absolute inset-0 bg-forest-950/40" />}
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</p>
      )}
      {shot && !error && (
        <p className="mt-3 text-xs text-emerald-100/60">
          {shot.width}×{shot.height} · taken at {format(shot.takenAt, 'HH:mm:ss')}
        </p>
      )}
    </Modal>
  )
}
