import type { InputHTMLAttributes, ReactNode } from 'react'
import { standardInputClasses } from '../../styles/inputStyles'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helpText?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export default function Input({ 
  label, 
  error, 
  helpText, 
  leftIcon, 
  rightIcon, 
  className = '', 
  id,
  ...props 
}: InputProps) {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`
  
  return (
    <div className="w-full">
      {label && (
        <label 
          htmlFor={inputId} 
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
        >
          {label}
        </label>
      )}
      
      <div className="relative">
        {leftIcon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <span className="text-gray-400 w-4 h-4">{leftIcon}</span>
          </div>
        )}
        
        <input
          id={inputId}
          className={`
            ${standardInputClasses} 
            ${leftIcon ? 'pl-10' : ''} 
            ${rightIcon ? 'pr-10' : ''} 
            ${error ? 'border-red-300 dark:border-red-600 focus:ring-red-500 focus:border-red-500' : ''} 
            ${className}
          `}
          {...props}
        />
        
        {rightIcon && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <span className="text-gray-400 w-4 h-4">{rightIcon}</span>
          </div>
        )}
      </div>
      
      {error && (
        <p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
      
      {helpText && !error && (
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{helpText}</p>
      )}
    </div>
  )
}