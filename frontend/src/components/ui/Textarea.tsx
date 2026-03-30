import type { TextareaHTMLAttributes } from 'react'
import { standardTextareaClasses } from '../../styles/inputStyles'
import { textColors, statusColors } from '../../styles/designSystem'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helpText?: string
  fillHeight?: boolean
}

export default function Textarea({ 
  label, 
  error, 
  helpText, 
  fillHeight = false,
  className = '', 
  id,
  ...props 
}: TextareaProps) {
  const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`
  
  return (
    <div className={fillHeight ? "w-full h-full flex flex-col" : "w-full"}>
      {label && (
        <label 
          htmlFor={textareaId} 
          className={`block text-sm font-medium ${textColors.secondary} mb-2`}
        >
          {label}
        </label>
      )}
      
      <textarea
        id={textareaId}
        className={`
          ${standardTextareaClasses} 
          ${error ? 'border-red-300 dark:border-red-600 focus:ring-red-500 focus:border-red-500' : ''} 
          ${fillHeight ? 'flex-1 resize-none' : ''}
          ${className}
        `}
        {...props}
      />
      
      {error && (
        <p className={`mt-1 text-sm ${statusColors.error.text}`}>{error}</p>
      )}

      {helpText && !error && (
        <p className={`mt-1 text-sm ${textColors.muted}`}>{helpText}</p>
      )}
    </div>
  )
}