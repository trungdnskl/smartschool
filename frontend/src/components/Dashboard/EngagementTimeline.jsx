import {
  Area, AreaChart, CartesianGrid, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import useAppStore from '../../store/appStore'

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1e2642', border: '1px solid rgba(255,255,255,0.1)', padding: '8px 12px', borderRadius: 8, fontSize: 12 }}>
      <p style={{ color: '#00d4ff', fontWeight: 700 }}>{payload[0].value}%</p>
      <p style={{ color: '#8b95a8' }}>{payload[0].payload.faces} khuôn mặt</p>
    </div>
  )
}

export default function EngagementTimeline() {
  const { engagementTimeline } = useAppStore()

  if (engagementTimeline.length < 2) {
    return (
      <div className="card card-timeline">
        <div className="card-header"><h3>Biểu đồ engagement theo thời gian</h3></div>
        <div className="timeline-chart-container" style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.2)', fontSize: 13 }}>
          Đang chờ dữ liệu...
        </div>
      </div>
    )
  }

  return (
    <div className="card card-timeline">
      <div className="card-header"><h3>Biểu đồ engagement theo thời gian</h3></div>
      <div className="timeline-chart-container">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={engagementTimeline} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="engGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={40} stroke="rgba(239,68,68,0.4)" strokeDasharray="5 5" label={{ value: 'Ngưỡng', fill: 'rgba(239,68,68,0.5)', fontSize: 9, position: 'insideTopRight' }} />
            <Area type="monotone" dataKey="value" stroke="#00d4ff" strokeWidth={2} fill="url(#engGrad)" dot={false} activeDot={{ r: 5, fill: '#00d4ff' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
