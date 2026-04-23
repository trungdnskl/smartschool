import { useEffect, useRef } from 'react'
import useAppStore from '../../store/appStore'

function drawGauge(canvas, value) {
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width, h = canvas.height
  const cx = w / 2, cy = h - 10
  const radius = Math.min(w, h) - 30

  ctx.clearRect(0, 0, w, h)

  ctx.beginPath()
  ctx.arc(cx, cy, radius, Math.PI, 2 * Math.PI)
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'
  ctx.lineWidth = 20
  ctx.lineCap = 'round'
  ctx.stroke()

  const angle = Math.PI + (value / 100) * Math.PI
  const gradient = ctx.createLinearGradient(0, h, w, 0)
  if (value >= 70) {
    gradient.addColorStop(0, '#10b981'); gradient.addColorStop(1, '#34d399')
  } else if (value >= 40) {
    gradient.addColorStop(0, '#f59e0b'); gradient.addColorStop(1, '#fbbf24')
  } else {
    gradient.addColorStop(0, '#ef4444'); gradient.addColorStop(1, '#f87171')
  }

  ctx.beginPath()
  ctx.arc(cx, cy, radius, Math.PI, angle)
  ctx.strokeStyle = gradient
  ctx.lineWidth = 20
  ctx.lineCap = 'round'
  ctx.shadowColor = value >= 70 ? '#10b981' : value >= 40 ? '#f59e0b' : '#ef4444'
  ctx.shadowBlur = 15
  ctx.stroke()
  ctx.shadowBlur = 0

  ctx.fillStyle = 'rgba(255,255,255,0.3)'
  ctx.font = '11px Inter'
  ctx.textAlign = 'center'
  ctx.fillText('0', cx - radius - 5, cy + 20)
  ctx.fillText('50', cx, cy - radius - 8)
  ctx.fillText('100', cx + radius + 5, cy + 20)
}

function getLabel(score) {
  if (score >= 80) return 'Xuất sắc 🎉'
  if (score >= 60) return 'Tốt 👍'
  if (score >= 40) return 'Trung bình ⚠️'
  if (score >= 20) return 'Thấp 😟'
  if (score > 0) return 'Rất thấp 🚨'
  return 'Chưa hoạt động'
}

export default function EngagementGauge() {
  const canvasRef = useRef(null)
  const { engagementData, sessionActive } = useAppStore()
  const value = Math.round(engagementData?.avg_engagement || 0)

  useEffect(() => {
    drawGauge(canvasRef.current, value)
  }, [value])

  return (
    <div className="card card-gauge">
      <div className="card-header">
        <h3>Chỉ số tham gia lớp</h3>
        {sessionActive && <span className="badge-live">● TRỰC TIẾP</span>}
      </div>
      <div className="gauge-container">
        <canvas ref={canvasRef} width={280} height={180} />
        <div className="gauge-value">{value}%</div>
        <div className="gauge-label">{getLabel(value)}</div>
      </div>
    </div>
  )
}
