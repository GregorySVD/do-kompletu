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
  variant: ActivityCategoryVisualVariant
}

const categoryPresentationBySlug: Record<string, ActivityCategoryPresentation> =
  {
    'sport-zespolowy': {
      icon: SportsSoccer,
      variant: 'team-sport',
    },
    'gry-planszowe': {
      icon: Casino,
      variant: 'board-games',
    },
    rpg: {
      icon: AutoStories,
      variant: 'rpg',
    },
    gaming: {
      icon: SportsEsports,
      variant: 'gaming',
    },
    'wspolna-nauka': {
      icon: School,
      variant: 'study',
    },
    technologia: {
      icon: Memory,
      variant: 'technology',
    },
    muzyka: {
      icon: MusicNote,
      variant: 'music',
    },
    kreatywne: {
      icon: Palette,
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
