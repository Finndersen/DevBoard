import type { TextareaHTMLAttributes } from 'react'
import { standardTextareaClasses } from '../../styles/inputStyles'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helpText?: string
}

export default function Textarea({ 
  label, 
  error, 
  helpText, 
  className = '', 
  id,
  ...props 
}: TextareaProps) {
  const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`
  
  return (
    <div className="w-full">
      {label && (
        <label 
          htmlFor={textareaId} 
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          {label}
        </label>
      )}
      
      <textarea
        id={textareaId}
        className={`
          ${standardTextareaClasses} 
          ${error ? 'border-red-300 dark:border-red-600 focus:ring-red-500 focus:border-red-500' : ''} 
          ${className}
        `}
        {...props}
      />
      
      {error && (
        <p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
      
      {helpText && !error && (
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{helpText}</p>
      )}
    </div>
  )
}