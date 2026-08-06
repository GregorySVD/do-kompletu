import { Chip, Typography } from '@mui/material'
import ActivityCard from '../../components/ActivityCard/ActivityCard'
import { mockActivities } from '../../data/mockActivities'
import './HomePage.css'

const categories = [
  'Sport zespołowy',
  'Gry planszowe',
  'RPG',
  'Gaming',
  'Wspólna nauka',
  'Technologia',
  'Muzyka',
  'Kreatywne',
]

function HomePage() {
  return (
    <main className="home-page">
      <section className="categories" aria-labelledby="categories-title">
        <Typography id="categories-title" component="h2" variant="h6">
          Kategorie
        </Typography>

        <div className="categories__list">
          {categories.map((category) => (
            <Chip key={category} label={category} variant="outlined" />
          ))}
        </div>
      </section>

      <div className="home-layout">
        <section className="activities" aria-labelledby="activities-title">
          <div className="activities__heading">
            <div>
              <Typography id="activities-title" component="h1" variant="h5">
                Aktywności w Twojej okolicy
              </Typography>
              <Typography color="text.secondary">
                Znajdź aktywność i dołącz do innych
              </Typography>
            </div>

            <Typography color="text.secondary">
              {mockActivities.length} aktywności
            </Typography>
          </div>

          <div className="activities__list">
            {mockActivities.map((activity) => (
              <ActivityCard key={activity.id} activity={activity} />
            ))}
          </div>
        </section>

        <aside className="map-placeholder">
          <div>
            <Typography component="h2" variant="h5">
              Mapa aktywności
            </Typography>
            <Typography color="text.secondary">
              W tym miejscu pojawi się mapa.
            </Typography>
          </div>
        </aside>
      </div>
    </main>
  )
}

export default HomePage
