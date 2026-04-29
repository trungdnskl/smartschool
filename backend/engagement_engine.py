"""
Classroom Engagement System - Engagement Engine
Tính toán chỉ số tham gia (engagement score) từ cảm xúc + hướng nhìn + hành vi
"""

import logging
import time
import numpy as np
from typing import Dict, Any, List, Optional
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

# Vietnamese alert messages
ALERT_MESSAGES = {
    "low_engagement": "⚠️ Mức độ tham gia của lớp đang thấp ({score:.0f}%). Cân nhắc thay đổi phương pháp giảng dạy.",
    "confusion_spike": "🤔 Nhiều học sinh đang có biểu hiện bối rối. Có thể cần giải thích lại nội dung.",
    "boredom_detected": "😴 Phát hiện nhiều học sinh chán nản. Nên thêm hoạt động tương tác.",
    "attention_drop": "👀 Mức độ chú ý giảm đáng kể. Có thể cần nghỉ giải lao hoặc đổi hoạt động.",
    "student_confused": "🙋 Học sinh {name} có biểu hiện bối rối kéo dài. Có thể cần hỗ trợ riêng.",
    "student_sleeping": "💤 Phát hiện học sinh có thể đang ngủ gật.",
    "engagement_recovered": "✅ Mức độ tham gia đã cải thiện lên {score:.0f}%.",
    "peak_engagement": "🎯 Mức độ tham gia đạt đỉnh: {score:.0f}%!",
}


class EngagementEngine:
    """
    Tính toán và theo dõi chỉ số engagement cho lớp học.

    Formula:
    Engagement Score = w1 × Emotion_Score + w2 × Attention_Score + w3 × Behavior_Score

    Alerts are generated based on class-level and student-level thresholds.
    """

    def __init__(
        self,
        weights: Dict[str, float] = None,
        alert_threshold: int = 40,
        confusion_alert_duration: int = 120,
        update_interval: float = 2.0,
    ):
        self.weights = weights or {
            "emotion": 0.35,
            "attention": 0.45,
            "behavior": 0.20,
        }
        self.alert_threshold = alert_threshold
        self.confusion_alert_duration = confusion_alert_duration
        self.update_interval = update_interval

        # Class engagement history
        self._engagement_history = deque(maxlen=500)  # ~16 min at 2s intervals
        self._last_update = 0

        # Per-student tracking
        self._student_states: Dict[int, Dict] = {}

        # Duration-based state timers (FR-06.2, FR-06.5)
        # Maps face_id -> timestamp when state started
        self._confusion_timers: Dict[int, float] = {}   # confused > 120s
        self._sleep_timers: Dict[int, float] = {}        # head_down > 30s
        self._sleep_alert_duration = 30     # seconds (SRS FR-06.5)

        # Alert tracking
        self._active_alerts: List[Dict] = []
        self._last_alert_time: Dict[str, float] = {}
        self._alert_cooldown = 30  # 30 seconds between same type alerts

        # Peak/low tracking
        self._peak_engagement = 0.0
        self._peak_time = None
        self._low_engagement = 100.0
        self._low_time = None

    def calculate_engagement(
        self,
        emotion_results: List[Dict],
        head_pose_results: List[Dict],
        total_faces: int,
        total_persons: int = 0,
        face_person_ratio: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate class-wide engagement metrics.
        Returns classroom snapshot with scores, distributions, and alerts.
        """
        now = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Calculate individual student scores
        students = []
        face_ids = set()

        for emotion_r in emotion_results:
            face_id = emotion_r["face_id"]
            face_ids.add(face_id)

            # Find matching head pose result
            head_pose = None
            for hp in head_pose_results:
                if hp["face_id"] == face_id:
                    head_pose = hp
                    break

            student_score = self._calculate_student_score(
                face_id, emotion_r, head_pose
            )
            students.append(student_score)

        # Class-level aggregation
        if students:
            avg_engagement = sum(s["engagement_score"] for s in students) / len(students)
            avg_emotion = sum(s["emotion_score"] for s in students) / len(students)
            avg_attention = sum(s["attention_score"] for s in students) / len(students)
        else:
            avg_engagement = 0
            avg_emotion = 0
            avg_attention = 0

        # Emotion distribution
        emotion_dist = {}
        learning_state_dist = {}
        attention_dist = {}

        for s in students:
            em = s.get("emotion", "neutral")
            ls = s.get("learning_state", "neutral")
            ad = s.get("attention_direction", "looking_at_teacher")

            emotion_dist[em] = emotion_dist.get(em, 0) + 1
            learning_state_dist[ls] = learning_state_dist.get(ls, 0) + 1
            attention_dist[ad] = attention_dist.get(ad, 0) + 1

        # Track peak/low
        if avg_engagement > self._peak_engagement:
            self._peak_engagement = avg_engagement
            self._peak_time = timestamp

        if avg_engagement < self._low_engagement and avg_engagement > 0:
            self._low_engagement = avg_engagement
            self._low_time = timestamp

        # Generate alerts (including person detection alerts)
        new_alerts = self._check_alerts(
            avg_engagement, students, learning_state_dist, timestamp,
            total_persons=total_persons,
            face_person_ratio=face_person_ratio,
        )

        # Store history
        snapshot = {
            "timestamp": timestamp,
            "total_faces": total_faces,
            "total_persons": total_persons,
            "face_person_ratio": round(face_person_ratio, 2),
            "tracked_students": len(students),
            "avg_engagement": round(avg_engagement, 1),
            "avg_emotion_score": round(avg_emotion, 1),
            "avg_attention_score": round(avg_attention, 1),
            "emotion_distribution": emotion_dist,
            "learning_state_distribution": learning_state_dist,
            "attention_distribution": attention_dist,
            "students": students,
            "alerts": new_alerts,
        }

        self._engagement_history.append(snapshot)
        self._last_update = now

        return snapshot

    def _calculate_student_score(
        self,
        face_id: int,
        emotion_result: Dict,
        head_pose_result: Optional[Dict],
    ) -> Dict[str, Any]:
        """Calculate engagement score for a single student."""
        emotion_score = emotion_result.get("emotion_score", 60)
        attention_score = 100  # Default if no head pose

        if head_pose_result:
            attention_score = head_pose_result.get("attention_score", 100)

        # Behavior score: based on stability (less movement = more focused)
        behavior_score = self._calculate_behavior_score(face_id)

        # Weighted combination
        engagement_score = (
            self.weights["emotion"] * emotion_score +
            self.weights["attention"] * attention_score +
            self.weights["behavior"] * behavior_score
        )

        engagement_score = max(0, min(100, engagement_score))

        # Track student state
        self._student_states[face_id] = {
            "face_id": face_id,
            "emotion": emotion_result.get("emotion", "neutral"),
            "emotion_vi": emotion_result.get("emotion_vi", "Bình thường"),
            "learning_state": emotion_result.get("learning_state", "neutral"),
            "learning_state_vi": emotion_result.get("learning_state_vi", "Bình thường"),
            "attention_direction": head_pose_result.get("attention_direction", "looking_at_teacher") if head_pose_result else "looking_at_teacher",
            "attention_direction_vi": head_pose_result.get("attention_direction_vi", "Nhìn bảng/GV") if head_pose_result else "Nhìn bảng/GV",
            "engagement_score": round(engagement_score, 1),
            "emotion_score": round(emotion_score, 1),
            "attention_score": round(attention_score, 1),
            "behavior_score": round(behavior_score, 1),
            "student_name": emotion_result.get("student_name"),
            "student_id": emotion_result.get("student_id"),
        }

        return self._student_states[face_id]

    def _calculate_behavior_score(self, face_id: int, face_person_ratio: float = 1.0) -> float:
        """
        Calculate behavior score based on engagement stability.
        Higher score = more consistent engagement over time.
        Incorporates face_person_ratio: low ratio = some students may be turned away.
        """
        # Check history for this face_id
        recent_scores = []
        for snapshot in list(self._engagement_history)[-10:]:
            for s in snapshot.get("students", []):
                if s.get("face_id") == face_id:
                    recent_scores.append(s.get("engagement_score", 50))

        if not recent_scores:
            return 60  # Default

        # Stability: lower variance = higher behavior score
        mean_score = np.mean(recent_scores)
        std_score = np.std(recent_scores)

        # Low variance + high mean = good behavior
        stability = max(0, 100 - std_score * 2)
        behavior_score = 0.5 * mean_score + 0.5 * stability

        # Penalize slightly when face_person_ratio is low
        # (indicates some people in frame aren't showing faces)
        if face_person_ratio < 0.5:
            behavior_score *= 0.9  # 10% penalty

        return min(100, max(0, behavior_score))

    def _check_alerts(
        self,
        avg_engagement: float,
        students: List[Dict],
        learning_states: Dict,
        timestamp: str,
        total_persons: int = 0,
        face_person_ratio: float = 1.0,
    ) -> List[Dict]:
        """Check conditions and generate alerts (SRS FR-06)."""
        alerts = []
        now = time.time()

        # ── FR-06.1: Low class engagement ──────────────
        if avg_engagement < self.alert_threshold and avg_engagement > 0:
            if self._can_alert("low_engagement", now):
                alerts.append(self._make_alert(
                    timestamp, "low_engagement", "warning",
                    ALERT_MESSAGES["low_engagement"].format(score=avg_engagement),
                    "Thay đổi phương pháp giảng dạy: thêm câu hỏi tương tác hoặc thảo luận nhóm.",
                ))
                self._last_alert_time["low_engagement"] = now

        # ── FR-06.2: Confusion spike (class-level) ────
        confused_count = learning_states.get("confused", 0)
        total = sum(learning_states.values()) if learning_states else 1
        if total > 0 and confused_count / total > 0.3:
            if self._can_alert("confusion_spike", now):
                alerts.append(self._make_alert(
                    timestamp, "confusion_spike", "warning",
                    ALERT_MESSAGES["confusion_spike"],
                    "Giải thích lại nội dung vừa dạy, thêm ví dụ minh họa cụ thể.",
                ))
                self._last_alert_time["confusion_spike"] = now

        # ── FR-06.2: Per-student confusion > 120s ─────
        self._check_confusion_duration(students, now, timestamp, alerts)

        # ── FR-06.3: Boredom > 30% ────────────────────
        bored_count = learning_states.get("bored", 0)
        if total > 0 and bored_count / total > 0.3:
            if self._can_alert("boredom_detected", now):
                alerts.append(self._make_alert(
                    timestamp, "boredom_detected", "warning",
                    ALERT_MESSAGES["boredom_detected"],
                    "Thêm hoạt động game, quiz, hoặc cho học sinh đứng dậy vận động.",
                ))
                self._last_alert_time["boredom_detected"] = now

        # ── FR-06.4: Attention drop > 3 students ──────
        looking_away_count = sum(
            1 for s in students
            if s.get("attention_direction") in ("looking_away", "looking_down", "head_down")
        )
        if looking_away_count > 3:
            if self._can_alert("attention_drop", now):
                alerts.append(self._make_alert(
                    timestamp, "attention_drop", "warning",
                    ALERT_MESSAGES["attention_drop"],
                    f"{looking_away_count} học sinh mất tập trung. Cân nhắc nghỉ giải lao hoặc đổi hoạt động.",
                ))
                self._last_alert_time["attention_drop"] = now

        # ── FR-06.5: Student sleeping > 30s ───────────
        self._check_sleep_duration(students, now, timestamp, alerts)

        # ── Person Detection: Low face ratio alert ─────
        if total_persons > 3 and face_person_ratio < 0.4:
            if self._can_alert("low_face_ratio", now):
                alerts.append(self._make_alert(
                    timestamp, "low_face_ratio", "info",
                    f"👥 Chỉ phát hiện {int(face_person_ratio*100)}% khuôn mặt so với số người ({total_persons}). "
                    f"Một số học sinh có thể đang quay lưng.",
                    "Kiểm tra vị trí ngồi của học sinh hoặc điều chỉnh góc camera.",
                ))
                self._last_alert_time["low_face_ratio"] = now

        # ── FR-06.6: Engagement recovered ─────────────
        if len(self._engagement_history) > 5:
            prev_scores = [
                h["avg_engagement"] for h in list(self._engagement_history)[-6:-1]
            ]
            if prev_scores:
                prev_avg = sum(prev_scores) / len(prev_scores)
                if prev_avg < self.alert_threshold and avg_engagement >= self.alert_threshold + 10:
                    if self._can_alert("engagement_recovered", now):
                        alerts.append(self._make_alert(
                            timestamp, "engagement_recovered", "info",
                            ALERT_MESSAGES["engagement_recovered"].format(score=avg_engagement),
                            "Tiếp tục phương pháp hiện tại, duy trì nhịp độ tốt.",
                        ))
                        self._last_alert_time["engagement_recovered"] = now

        # Store active alerts
        self._active_alerts = alerts
        return alerts

    def _make_alert(
        self, timestamp: str, alert_type: str, severity: str,
        message: str, suggestion: str,
    ) -> Dict[str, str]:
        """Create alert dict with suggestion field (FR-06.8)."""
        return {
            "timestamp": timestamp,
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "suggestion": suggestion,
        }

    def _check_confusion_duration(
        self, students: List[Dict], now: float,
        timestamp: str, alerts: List[Dict],
    ):
        """FR-06.2: Alert when a student stays confused > confusion_alert_duration (120s)."""
        current_confused_ids = set()
        for s in students:
            fid = s.get("face_id")
            if s.get("learning_state") == "confused":
                current_confused_ids.add(fid)
                if fid not in self._confusion_timers:
                    self._confusion_timers[fid] = now      # start timer
                else:
                    elapsed = now - self._confusion_timers[fid]
                    if elapsed >= self.confusion_alert_duration:
                        name = s.get("student_name") or f"Face #{fid}"
                        alert_key = f"student_confused_{fid}"
                        if self._can_alert(alert_key, now):
                            alerts.append(self._make_alert(
                                timestamp, "student_confused", "warning",
                                ALERT_MESSAGES["student_confused"].format(name=name),
                                f"Hỗ trợ riêng {name}: giải thích lại hoặc cho bài tập phụ.",
                            ))
                            self._last_alert_time[alert_key] = now
                            # Reset timer after alert so it can fire again later
                            self._confusion_timers[fid] = now

        # Clear timers for students no longer confused
        expired = [fid for fid in self._confusion_timers if fid not in current_confused_ids]
        for fid in expired:
            del self._confusion_timers[fid]

    def _check_sleep_duration(
        self, students: List[Dict], now: float,
        timestamp: str, alerts: List[Dict],
    ):
        """FR-06.5: Alert when a student has head_down > 30 seconds."""
        current_sleeping_ids = set()
        for s in students:
            fid = s.get("face_id")
            if s.get("attention_direction") == "head_down":
                current_sleeping_ids.add(fid)
                if fid not in self._sleep_timers:
                    self._sleep_timers[fid] = now          # start timer
                else:
                    elapsed = now - self._sleep_timers[fid]
                    if elapsed >= self._sleep_alert_duration:
                        name = s.get("student_name") or f"Face #{fid}"
                        alert_key = f"student_sleeping_{fid}"
                        if self._can_alert(alert_key, now):
                            alerts.append(self._make_alert(
                                timestamp, "student_sleeping", "info",
                                f"💤 {name} có thể đang ngủ gật ({int(elapsed)}s).",
                                f"Nhắc nhẹ {name} hoặc cho cả lớp đứng dậy vận động.",
                            ))
                            self._last_alert_time[alert_key] = now
                            self._sleep_timers[fid] = now

        # Clear timers for students who lifted their head
        expired = [fid for fid in self._sleep_timers if fid not in current_sleeping_ids]
        for fid in expired:
            del self._sleep_timers[fid]

    def _can_alert(self, alert_type: str, now: float) -> bool:
        """Check if we can send this alert type (cooldown)."""
        last = self._last_alert_time.get(alert_type, 0)
        return now - last >= self._alert_cooldown

    def get_engagement_timeline(self) -> List[Dict]:
        """Get engagement history for charts."""
        return [
            {
                "timestamp": s["timestamp"],
                "avg_engagement": s["avg_engagement"],
                "total_faces": s["total_faces"],
                "emotion_distribution": s.get("emotion_distribution", {}),
            }
            for s in self._engagement_history
        ]

    def get_session_summary(self) -> Dict[str, Any]:
        """Generate summary for the entire session."""
        if not self._engagement_history:
            return {}

        scores = [h["avg_engagement"] for h in self._engagement_history if h["avg_engagement"] > 0]

        if not scores:
            return {}

        # Aggregate emotion distribution
        total_emotion_dist = {}
        for snapshot in self._engagement_history:
            for emotion, count in snapshot.get("emotion_distribution", {}).items():
                total_emotion_dist[emotion] = total_emotion_dist.get(emotion, 0) + count

        # Normalize to percentages
        total_emotions = sum(total_emotion_dist.values())
        if total_emotions > 0:
            emotion_pct = {k: round(v / total_emotions * 100, 1) for k, v in total_emotion_dist.items()}
        else:
            emotion_pct = {}

        # Generate recommendations
        recommendations = self._generate_recommendations(scores, emotion_pct)

        # Person detection aggregated stats
        person_counts = [h.get("total_persons", 0) for h in self._engagement_history]
        avg_persons = round(sum(person_counts) / len(person_counts), 1) if person_counts else 0
        ratios = [h.get("face_person_ratio", 1.0) for h in self._engagement_history if h.get("face_person_ratio", 0) > 0]
        avg_ratio = round(sum(ratios) / len(ratios), 2) if ratios else 0

        return {
            "avg_engagement": round(sum(scores) / len(scores), 1),
            "peak_engagement": round(self._peak_engagement, 1),
            "lowest_engagement": round(self._low_engagement, 1),
            "peak_time": self._peak_time,
            "low_time": self._low_time,
            "emotion_distribution": emotion_pct,
            "data_points": len(self._engagement_history),
            "recommendations": recommendations,
            "avg_persons_detected": avg_persons,
            "avg_face_person_ratio": avg_ratio,
        }

    def _generate_recommendations(
        self, scores: List[float], emotion_pct: Dict
    ) -> List[str]:
        """Generate teaching recommendations based on session data."""
        recs = []
        avg = sum(scores) / len(scores)

        if avg < 40:
            recs.append("📉 Mức engagement trung bình thấp. Nên tăng cường hoạt động thực hành và thảo luận nhóm.")

        if emotion_pct.get("sad", 0) + emotion_pct.get("angry", 0) > 20:
            recs.append("😟 Tỷ lệ cảm xúc tiêu cực cao. Cân nhắc điều chỉnh độ khó bài giảng hoặc thêm hoạt động vui nhộn.")

        confused_pct = emotion_pct.get("fear", 0) + emotion_pct.get("surprise", 0)
        if confused_pct > 25:
            recs.append("🤔 Nhiều học sinh bối rối. Nên giải thích lại các khái niệm khó và thêm ví dụ minh họa.")

        if len(scores) > 10:
            # Check for declining trend
            first_half = scores[:len(scores)//2]
            second_half = scores[len(scores)//2:]
            if sum(second_half)/len(second_half) < sum(first_half)/len(first_half) - 10:
                recs.append("📊 Engagement giảm dần theo thời gian. Nên thêm các hoạt động nghỉ giải lao giữa giờ.")

        if avg > 70:
            recs.append("🎯 Mức engagement tốt! Phương pháp giảng dạy hiệu quả.")

        if not recs:
            recs.append("✅ Buổi học diễn ra bình thường. Tiếp tục theo dõi để cải thiện.")

        return recs

    def reset(self):
        """Reset engine for new session."""
        self._engagement_history.clear()
        self._student_states.clear()
        self._confusion_timers.clear()
        self._sleep_timers.clear()
        self._active_alerts.clear()
        self._last_alert_time.clear()
        self._peak_engagement = 0.0
        self._peak_time = None
        self._low_engagement = 100.0
        self._low_time = None
