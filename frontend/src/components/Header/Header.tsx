import { DarkMode, LightMode } from '@mui/icons-material'
import {
  AppBar,
  Button,
  IconButton,
  TextField,
  Toolbar,
  Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'
import './Header.css'

interface HeaderProps {
  mode: 'light' | 'dark'
  onToggleTheme: () => void
}

function Header({ mode, onToggleTheme }: HeaderProps) {
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

        <Button component={Link} to="/activities/new" variant="contained">
          Dodaj aktywność
        </Button>
      </Toolbar>
    </AppBar>
  )
}

export default Header
