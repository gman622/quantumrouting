import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'
import useStore from '../store'
import type { SolverProgress, SolverCompleted } from '../types'

const WS_URL = window.location.origin

export default function useSolver() {
  const socketRef = useRef<Socket | null>(null)
  const setSolverElapsed = useStore((s) => s.setSolverElapsed)
  const setSolving = useStore((s) => s.setSolving)
  const onSolverCompleted = useStore((s) => s.onSolverCompleted)

  useEffect(() => {
    const socket = io(WS_URL, { transports: ['websocket', 'polling'] })
    socketRef.current = socket

    socket.on('connect', () => {
      console.log('WebSocket connected')
    })

    socket.on('solver_progress', (data: SolverProgress) => {
      setSolverElapsed(data.elapsed)
    })

    socket.on('solver_completed', (data: SolverCompleted) => {
      console.log('Solver completed:', data)
      setSolving(false)
      socket.emit('request_assignments')
      onSolverCompleted()
    })

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected')
    })

    return () => {
      socket.disconnect()
    }
  }, [setSolverElapsed, setSolving, onSolverCompleted])

  return socketRef
}
