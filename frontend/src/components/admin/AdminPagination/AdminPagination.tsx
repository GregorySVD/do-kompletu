import { NavigateBefore, NavigateNext } from '@mui/icons-material'
import { Button } from '@mui/material'

interface AdminPaginationProps {
  isFetching: boolean
  itemCount: number
  offset: number
  pageSize: number
  onOffsetChange: (offset: number) => void
}

function AdminPagination({
  isFetching,
  itemCount,
  offset,
  pageSize,
  onOffsetChange,
}: AdminPaginationProps) {
  const currentPage = Math.floor(offset / pageSize) + 1

  return (
    <nav className="admin-pagination" aria-label="Nawigacja po stronach">
      <Button
        disabled={offset === 0 || isFetching}
        startIcon={<NavigateBefore aria-hidden="true" />}
        variant="outlined"
        onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
      >
        Poprzednia
      </Button>
      <span aria-current="page">Strona {currentPage}</span>
      <Button
        disabled={itemCount < pageSize || isFetching}
        endIcon={<NavigateNext aria-hidden="true" />}
        variant="outlined"
        onClick={() => onOffsetChange(offset + pageSize)}
      >
        Następna
      </Button>
    </nav>
  )
}

export default AdminPagination
