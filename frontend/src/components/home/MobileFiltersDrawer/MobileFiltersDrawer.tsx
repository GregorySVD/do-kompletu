import { Button, Drawer } from '@mui/material'
import ActivityFilters, {
  type ActivityFilterProps,
} from '../ActivityFilters/ActivityFilters'
import './MobileFiltersDrawer.css'

interface MobileFiltersDrawerProps {
  open: boolean
  onClose: () => void
  filterProps: ActivityFilterProps
}

function MobileFiltersDrawer({
  open,
  onClose,
  filterProps,
}: MobileFiltersDrawerProps) {
  return (
    <Drawer
      anchor="bottom"
      open={open}
      slotProps={{
        paper: {
          'aria-labelledby': 'mobile-filters-title',
          'aria-modal': true,
          className: 'filters-drawer__paper',
          role: 'dialog',
        },
      }}
      onClose={onClose}
    >
      <div className="filters-drawer__handle" aria-hidden="true" />
      <div className="filters-drawer__content">
        <ActivityFilters titleId="mobile-filters-title" {...filterProps} />
      </div>
      <div className="filters-drawer__actions">
        <Button fullWidth size="large" variant="contained" onClick={onClose}>
          Pokaż wyniki
        </Button>
      </div>
    </Drawer>
  )
}

export default MobileFiltersDrawer
