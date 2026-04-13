import type { PRFeedbackResponse } from '../../lib/api'

export function countPRComments(fb: PRFeedbackResponse): number {
  let count = 0
  for (const r of fb.reviews) {
    if (r.body.trim()) count++
    for (const t of r.comment_threads) {
      count += 1 + t.replies.length
    }
  }
  for (const t of fb.standalone_threads) {
    count += 1 + t.replies.length
  }
  return count
}
