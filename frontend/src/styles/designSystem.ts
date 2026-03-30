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
    100: 'bg-gray-100 dark:bg-white/[0.03]',
    200: 'bg-gray-200 dark:bg-white/[0.06]',
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
  default: 'border-gray-200 dark:border-white/[0.08]',
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

// Surface backgrounds
export const surfaces = {
  base: 'bg-gray-50 dark:bg-gray-900',
  raised: 'bg-white dark:bg-gray-800',
  sunken: 'bg-gray-50 dark:bg-white/[0.05]',
  overlay: 'bg-black bg-opacity-50'
}

// Status/semantic color sets
export const statusColors = {
  error: {
    bg: 'bg-red-50 dark:bg-red-900/20',
    text: 'text-red-800 dark:text-red-200',
    border: 'border-red-200 dark:border-red-800',
    icon: 'bg-red-100 dark:bg-red-900/30'
  },
  warning: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800',
    icon: 'bg-amber-100 dark:bg-amber-900/30'
  },
  success: {
    bg: 'bg-green-50 dark:bg-green-900/20',
    text: 'text-green-800 dark:text-green-200',
    border: 'border-green-200 dark:border-green-800',
    icon: 'bg-green-100 dark:bg-green-900/30'
  },
  info: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-600 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-800',
    icon: 'bg-blue-100 dark:bg-blue-900/30'
  }
}

// Hover backgrounds
export const hoverColors = {
  subtle: 'hover:bg-gray-50 dark:hover:bg-white/[0.05]',
  default: 'hover:bg-gray-100 dark:hover:bg-white/[0.08]'
}