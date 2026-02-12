import { ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline'
import { useDiffReviewOptional } from '../../contexts/DiffReviewContext'
import Button from '../ui/Button'

export default function SubmitAllCommentsButton() {
  const context = useDiffReviewOptional()

  if (!context) return null

  const { pendingComments, submitAllComments, isSubmitting, clearAllComments } = context
  const commentCount = pendingComments.size

  if (commentCount === 0) return null

  const validComments = Array.from(pendingComments.values()).filter(c => c.commentText.trim())
  if (validComments.length === 0) return null

  return (
    <div className="flex items-center space-x-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={clearAllComments}
        disabled={isSubmitting}
        className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        Clear All
      </Button>
      <Button
        variant="primary"
        size="sm"
        onClick={submitAllComments}
        disabled={isSubmitting}
        loading={isSubmitting}
        icon={<ChatBubbleLeftRightIcon className="w-4 h-4" />}
      >
        Submit {validComments.length} Comment{validComments.length !== 1 ? 's' : ''}
      </Button>
    </div>
  )
}
