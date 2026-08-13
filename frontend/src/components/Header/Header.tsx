import { DarkMode, LightMode } from '@mui/icons-material'
import {
  AppBar,
  Button,
  IconButton,
  TextField,
  Toolbar,
  Typography,
} from '@mui/material'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import './Header.css'

interface HeaderProps {
  mode: 'light' | 'dark'
  onToggleTheme: () => void
  searchQuery: string
  onSearchChange: (query: string) => void
}

function Header({
  mode,
  onToggleTheme,
  searchQuery,
  onSearchChange,
}: HeaderProps) {
  const location = useLocation()
  const navigate = useNavigate()

  function handleSearchChange(query: string) {
    onSearchChange(query)

    if (location.pathname !== '/') {
      navigate('/')
    }
  }

  return (
    <AppBar component="header" position="static" color="inherit">
      <Toolbar className="header">
        <Typography
          className="header__logo"
          component={Link}
          to="/"
          variant="h5"
        >
          DoKompletu
        </Typography>

        <TextField
          className="header__search"
          label="Szukaj aktywności"
          value={searchQuery}
          onChange={(event) => handleSearchChange(event.target.value)}
          size="small"
        />

        <IconButton
          aria-label={
            mode === 'light' ? 'Włącz ciemny motyw' : 'Włącz jasny motyw'
          }
          onClick={onToggleTheme}
        >
          {mode === 'light' ? <DarkMode /> : <LightMode />}
        </IconButton>

        <Button component={Link} to="/login" variant="outlined">
          Zaloguj się
        </Button>

        <Button component={Link} to="/activities/new" variant="contained">
          Dodaj aktywność
        </Button>
      </Toolbar>
    </AppBar>
  )
}

export default Header
