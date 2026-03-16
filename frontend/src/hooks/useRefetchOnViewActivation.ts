import { useEffect, useRef } from 'react'
import { useViewContext } from '../contexts/ViewContext'
import { useUIStore } from '../stores/uiStore'

export function useRefetchOnViewActivation(refetchFns: Array<() => Promise<void> | void>) {
  const { viewId } = useViewContext()
  const activeViewId = useUIStore((state) => state.activeViewId)
  const isActive = activeViewId === viewId

  const prevIsActiveRef = useRef(isActive)
  const hasBeenActivatedRef = useRef(false)
  const refetchFnsRef = useRef(refetchFns)
  refetchFnsRef.current = refetchFns

  useEffect(() => {
    const wasActive = prevIsActiveRef.current
    prevIsActiveRef.current = isActive

    if (!wasActive && isActive) {
      if (!hasBeenActivatedRef.current) {
        hasBeenActivatedRef.current = true
        return
      }
      Promise.all(refetchFnsRef.current.map((fn) => fn()))
    }
  }, [isActive])
}
