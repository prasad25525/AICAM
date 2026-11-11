import { useIndustry, zoneTypeOf } from '../../api/industry'
import { centroid, useZones } from '../../api/zones'

/** Zone outlines over the live video. Uses the frame size as viewBox with "meet" scaling so it lines
 * up with the <img>'s object-contain, like the detection overlay. */
export default function ZonesOverlay({ cameraId, width, height }: { cameraId: number; width: number; height: number }) {
  const { data: zones } = useZones(cameraId)
  const { data: industry } = useIndustry()
  if (!zones?.length) return null
  const font = Math.max(16, width / 32) // ~13px on a 520px-wide tile
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Zones">
      {zones.map((z) => {
        const colour = zoneTypeOf(industry, z.zone_type).colour
        const [cx, cy] = centroid(z.polygon)
        return (
          <g key={z.id} data-testid="live-zone">
            <polygon
              points={z.polygon.map(([x, y]) => `${x * width},${y * height}`).join(' ')}
              fill={colour}
              fillOpacity={0.12}
              stroke={colour}
              strokeWidth={Math.max(1.5, width / 400)}
              strokeDasharray={`${width / 80} ${width / 160}`}
            />
            <text x={cx * width} y={cy * height} textAnchor="middle" dominantBaseline="middle" fontSize={font} fontWeight={700} fill="#fff" stroke="#06120b" strokeWidth={font / 5} paintOrder="stroke">
              {z.name}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
