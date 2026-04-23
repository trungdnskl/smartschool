import SessionControlBar from '../../components/Dashboard/SessionControlBar'
import LiveView from '../../components/Dashboard/LiveView'
import StatsRow from '../../components/Dashboard/StatsRow'
import EngagementGauge from '../../components/Dashboard/EngagementGauge'
import EmotionDistribution from '../../components/Dashboard/EmotionDistribution'
import LearningStates from '../../components/Dashboard/LearningStates'
import EngagementTimeline from '../../components/Dashboard/EngagementTimeline'
import AlertsList from '../../components/Dashboard/AlertsList'
import AttentionGrid from '../../components/Dashboard/AttentionGrid'
import StudentEmotions from '../../components/Dashboard/StudentEmotions'

export default function DashboardPage() {
  return (
    <div className="page-enter">
      <SessionControlBar />
      <LiveView />
      <StatsRow />
      <div className="dashboard-grid">
        <EngagementGauge />
        <EmotionDistribution />
        <LearningStates />
        <AttentionGrid />
        <EngagementTimeline />
        <AlertsList />
        <StudentEmotions />
      </div>
    </div>
  )
}

