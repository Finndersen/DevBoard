import { memo } from 'react'
import { PlusIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline'
import { useDiffReviewOptional } from '../../contexts/DiffReviewContext'

interface DiffLineCommentButtonProps {
  onClick: () => void
  filePath: string
  lineNumber: number
}

export default memo(function DiffLineCommentButton({ onClick, filePath, lineNumber }: DiffLineCommentButtonProps) {
  const reviewContext = useDiffReviewOptional()
  const hasComment = reviewContext?.hasComment(filePath, lineNumber) ?? false

  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      className={`
        w-5 h-5 flex items-center justify-center rounded
        transition-all duration-150
        ${hasComment
          ? 'bg-blue-500 text-white opacity-100'
          : 'opacity-0 group-hover:opacity-100 bg-blue-500 hover:bg-blue-600 text-white'
        }
      `}
      title={hasComment ? 'Edit comment' : 'Add comment'}
    >
      {hasComment ? (
        <ChatBubbleLeftIcon className="w-3.5 h-3.5" />
      ) : (
        <PlusIcon className="w-3.5 h-3.5 stroke-[2.5]" />
      )}
    </button>
  )
})
