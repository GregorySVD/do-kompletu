import {
  AutoStories,
  Casino,
  Category,
  Memory,
  MusicNote,
  Palette,
  School,
  SportsEsports,
  SportsSoccer,
} from '@mui/icons-material'

export type ActivityCategoryVisualVariant =
  | 'team-sport'
  | 'board-games'
  | 'rpg'
  | 'gaming'
  | 'study'
  | 'technology'
  | 'music'
  | 'creative'
  | 'fallback'

export interface ActivityCategoryPresentation {
  icon: typeof Category
  pixelHeroIconSrc?: string
  pixelIconSrc?: string
  variant: ActivityCategoryVisualVariant
}

const categoryPresentationBySlug: Record<string, ActivityCategoryPresentation> =
  {
    'sport-zespolowy': {
      icon: SportsSoccer,
      pixelHeroIconSrc: '/icons/icons8-sport-64.png',
      pixelIconSrc: '/icons/icons8-sport-32.png',
      variant: 'team-sport',
    },
    'gry-planszowe': {
      icon: Casino,
      pixelHeroIconSrc: '/icons/icons8-dice-64.png',
      pixelIconSrc: '/icons/icons8-dice-32.png',
      variant: 'board-games',
    },
    rpg: {
      icon: AutoStories,
      pixelHeroIconSrc: "/icons/icons8-witch's-hat-64.png",
      pixelIconSrc: "/icons/icons8-witch's-hat-32.png",
      variant: 'rpg',
    },
    gaming: {
      icon: SportsEsports,
      pixelHeroIconSrc: '/icons/icons8-games-64.png',
      pixelIconSrc: '/icons/icons8-games-32.png',
      variant: 'gaming',
    },
    'wspolna-nauka': {
      icon: School,
      pixelHeroIconSrc: '/icons/icons8-book-stack-64.png',
      pixelIconSrc: '/icons/icons8-book-stack-32.png',
      variant: 'study',
    },
    technologia: {
      icon: Memory,
      pixelHeroIconSrc: '/icons/icons8-technology-64.png',
      pixelIconSrc: '/icons/icons8-technology-32.png',
      variant: 'technology',
    },
    muzyka: {
      icon: MusicNote,
      pixelHeroIconSrc: '/icons/icons8-rock-music-64.png',
      pixelIconSrc: '/icons/icons8-rock-music-32.png',
      variant: 'music',
    },
    kreatywne: {
      icon: Palette,
      pixelHeroIconSrc: '/icons/icons8-painting-64.png',
      pixelIconSrc: '/icons/icons8-painting-32.png',
      variant: 'creative',
    },
  }

const fallbackCategoryPresentation: ActivityCategoryPresentation = {
  icon: Category,
  variant: 'fallback',
}

export function getActivityCategoryPresentation(
  slug: string,
): ActivityCategoryPresentation {
  return categoryPresentationBySlug[slug] ?? fallbackCategoryPresentation
}
