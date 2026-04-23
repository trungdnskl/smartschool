import { useEffect, useState } from 'react'
import api from '../../hooks/useApi'
import useAppStore from '../../store/appStore'

export default function AttendancePage() {
  const { sessionActive } = useAppStore()
  const [data, setData] = useState({ present: 0, late: 0, absent: 0, records: [] })

  const load = async () => {
    const r = await api.get('/api/attendance/current')
    if (r.ok) setData(r.data)
  }

  useEffect(() => { load() }, [sessionActive])

  const statusMap = { present: 'Có mặt', late: 'Muộn', absent: 'Vắng' }

  // P2-5: Engine icon + confidence bar helper
  const renderEngine = (record) => {
    if (!record.match_engine) return <span className="engine-badge none">—</span>
    const isArcface = record.match_engine === 'arcface'
    const icon = isArcface ? '🔵' : '🟡'
    const label = isArcface ? 'ArcFace' : 'LBPH'
    return <span className={`engine-badge ${record.match_engine}`}>{icon} {label}</span>
  }

  const renderConfidence = (record) => {
    const conf = record.match_confidence || 0
    if (conf === 0) return <span className="conf-none">—</span>
    const pct = Math.round(conf * 100)
    const level = conf >= 0.55 ? 'high' : conf >= 0.40 ? 'mid' : 'low'
    return (
      <div className="conf-bar-wrap">
        <div className={`conf-bar ${level}`} style={{ width: `${pct}%` }} />
        <span className="conf-text">{pct}%</span>
      </div>
    )
  }

  return (
    <div className="page-enter">
      <div className="view-header">
        <h2>📋 Điểm danh</h2>
        <div className="attendance-summary">
          <span className="att-stat present">Có mặt: <b>{data.present || 0}</b></span>
          <span className="att-stat late">Muộn: <b>{data.late || 0}</b></span>
          <span className="att-stat absent">Vắng: <b>{data.absent || 0}</b></span>
        </div>
      </div>
      <div className="attendance-table-container">
        <table className="attendance-table">
          <thead>
            <tr>
              <th>STT</th><th>Mã HS</th><th>Họ tên</th><th>Trạng thái</th>
              <th>Giờ vào</th><th>Engine</th><th>Độ tin cậy</th>
            </tr>
          </thead>
          <tbody>
            {(data.records || []).length === 0
              ? <tr><td colSpan={7} className="table-empty">Chưa có dữ liệu điểm danh</td></tr>
              : data.records.map((r, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{r.student_id || '-'}</td>
                  <td>{r.student_name || `Học sinh #${i + 1}`}</td>
                  <td><span className={`status-badge ${r.status}`}>{statusMap[r.status] || r.status}</span></td>
                  <td>{r.arrival_time || '-'}</td>
                  <td>{renderEngine(r)}</td>
                  <td>{renderConfidence(r)}</td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>
    </div>
  )
}
