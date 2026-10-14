import type { ReactNode } from 'react'
import { CircularProgress, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { checkBackendHealth } from '../../../api/healthApi'
import ServiceUnavailable from '../ServiceUnavailable/ServiceUnavailable'
import './BackendStatusGate.css'

interface BackendStatusGateProps {
  children: ReactNode
}

function BackendStatusGate({ children }: BackendStatusGateProps) {
  const { data, isFetching, isPending, refetch } = useQuery({
    queryKey: ['backend-health'],
    queryFn: checkBackendHealth,
    retry: false,
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  })

  if (isPending) {
    return (
      <main className="backend-status-gate__checking" aria-live="polite">
        <CircularProgress
          className="backend-status-gate__spinner"
          aria-hidden="true"
        />
        <Typography>Łączenie z DoKompletu...</Typography>
      </main>
    )
  }

  if (data !== true) {
    return (
      <ServiceUnavailable
        isRetrying={isFetching}
        onRetry={() => void refetch()}
      />
    )
  }

  return children
}

export default BackendStatusGate
