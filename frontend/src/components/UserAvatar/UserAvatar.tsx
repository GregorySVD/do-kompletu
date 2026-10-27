import { Avatar, type AvatarProps } from '@mui/material'
import './UserAvatar.css'

interface UserAvatarProps extends Omit<
  AvatarProps,
  'alt' | 'children' | 'src'
> {
  avatarUrl?: string | null
  displayName: string
}

/**
 * Displays a user's configured avatar and falls back to the application avatar
 * whenever the URL is empty or the image cannot be loaded.
 */
function UserAvatar({
  avatarUrl,
  displayName,
  ...avatarProps
}: UserAvatarProps) {
  const normalizedAvatarUrl = avatarUrl?.trim() || undefined

  return (
    <Avatar {...avatarProps} src={normalizedAvatarUrl} alt={displayName}>
      <img
        className="user-avatar__fallback"
        src="/icons/icons8-avatar-64.png"
        alt=""
        width="64"
        height="64"
        aria-hidden="true"
      />
    </Avatar>
  )
}

export default UserAvatar
