import { Box, Container, Typography } from '@mui/material'
import './App.css'

function App() {
  return (
    <Box component="main" className="app">
      <Container maxWidth="sm">
        <Typography component="h1" variant="h3" gutterBottom>
          Aktywności lokalne
        </Typography>
        <Typography color="text.secondary">
          Środowisko frontendowe zostało skonfigurowane
        </Typography>
      </Container>
    </Box>
  )
}

export default App
