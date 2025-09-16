/**
 * Design system utilities and standardized styles
 */

// Color palette
export const colors = {
  primary: {
    50: 'bg-blue-50 dark:bg-blue-900/20',
    100: 'bg-blue-100 dark:bg-blue-900/30',
    500: 'bg-blue-500',
    600: 'bg-blue-600',
    700: 'bg-blue-700'
  },
  gray: {
    50: 'bg-gray-50 dark:bg-gray-900',
    100: 'bg-gray-100 dark:bg-gray-800',
    200: 'bg-gray-200 dark:bg-gray-700',
    300: 'bg-gray-300 dark:bg-gray-600',
    700: 'bg-gray-700 dark:bg-gray-300',
    800: 'bg-gray-800 dark:bg-gray-200',
    900: 'bg-gray-900 dark:bg-gray-100'
  }
}

// Text colors
export const textColors = {
  primary: 'text-gray-900 dark:text-white',
  secondary: 'text-gray-600 dark:text-gray-400',
  muted: 'text-gray-500 dark:text-gray-500',
  accent: 'text-blue-600 dark:text-blue-400'
}

// Border colors
export const borderColors = {
  default: 'border-gray-200 dark:border-gray-700',
  input: 'border-gray-300 dark:border-gray-600',
  focus: 'border-blue-500'
}

// Focus states
export const focusStyles = 'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

// Transition classes
export const transitions = {
  colors: 'transition-colors',
  all: 'transition-all',
  shadow: 'transition-shadow'
}

// Common layout patterns
export const layouts = {
  flexCenter: 'flex items-center justify-center',
  flexBetween: 'flex items-center justify-between',
  flexCol: 'flex flex-col',
  gridAuto: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'
}

// Loading spinner component class
export const loadingSpinner = 'animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600'