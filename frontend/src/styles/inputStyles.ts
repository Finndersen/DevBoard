/**
 * Standardized input and textarea styling classes for consistent theming across the application
 */
import { textColors, borderColors, focusStyles } from './designSystem'

// Base input styling with proper light/dark mode support
export const baseInputClasses = `w-full px-3 py-2 ${textColors.primary} bg-white dark:bg-white/[0.06] border ${borderColors.input} rounded-md shadow-sm ${focusStyles} transition-colors`

// Chat input styling (smaller, more compact)
export const chatInputClasses = `w-full px-3 py-2 text-sm ${textColors.primary} bg-white dark:bg-white/[0.06] border ${borderColors.input} rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors`

// Large textarea styling for content editing
export const textareaClasses = `w-full px-3 py-2 ${textColors.primary} bg-white dark:bg-white/[0.06] border ${borderColors.input} rounded-md shadow-sm ${focusStyles} font-mono text-sm transition-colors`

// Small feedback textarea styling
export const feedbackTextareaClasses = `w-full px-2 py-1 text-sm ${textColors.primary} bg-white dark:bg-white/[0.06] border ${borderColors.input} rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors`

// Disabled state classes
export const disabledClasses = "disabled:opacity-50 disabled:cursor-not-allowed"

// Common combinations
export const standardInputClasses = `${baseInputClasses} ${disabledClasses}`
export const standardChatInputClasses = `${chatInputClasses} ${disabledClasses}`
export const standardTextareaClasses = `${textareaClasses} ${disabledClasses}`
export const standardFeedbackTextareaClasses = `${feedbackTextareaClasses} ${disabledClasses}`
