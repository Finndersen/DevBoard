import { useEffect, useRef } from 'react'
import { useTabContext } from '../contexts/TabContext'
import { useUIStore } from '../stores/uiStore'

export function useRefetchOnTabActivation(refetchFns: Array<() => Promise<void> | void>) {
  const { tabId } = useTabContext()
  const activeTabId = useUIStore((state) => state.activeTabId)
  const isActive = activeTabId === tabId

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
