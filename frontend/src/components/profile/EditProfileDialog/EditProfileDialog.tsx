import { useRef, type FormEvent } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import axios from 'axios'
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from '@mui/material'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { useUpdateProfileMutation } from '../../../hooks/mutations/useUpdateProfileMutation'
import type { UpdateUserProfilePayload, UserProfile } from '../../../types/auth'
import './EditProfileDialog.css'

const editProfileSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(1, 'Nazwa użytkownika jest wymagana.')
    .max(80, 'Nazwa użytkownika może mieć maksymalnie 80 znaków.'),
  avatar_url: z
    .string()
    .trim()
    .max(2048, 'URL avatara może mieć maksymalnie 2048 znaków.'),
})

type EditProfileFormValues = z.infer<typeof editProfileSchema>

interface EditProfileDialogProps {
  user: UserProfile
  onClose: () => void
  onUpdated: () => void
}

interface UpdateProfileErrorResponse {
  detail?: unknown
}

function getUpdateProfileErrorMessage(error: unknown) {
  if (!axios.isAxiosError<UpdateProfileErrorResponse>(error)) {
    return 'Nie udało się zapisać zmian. Spróbuj ponownie.'
  }

  if (!error.response) {
    return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
  }

  if (error.response.status === 401) {
    return 'Sesja wygasła lub jest nieprawidłowa.'
  }

  if (
    error.response.status === 409 &&
    error.response.data.detail === 'Username is already taken'
  ) {
    return 'Ta nazwa użytkownika jest już zajęta.'
  }

  if (error.response.status === 422) {
    return 'Nie udało się zapisać profilu. Sprawdź poprawność danych.'
  }

  return 'Nie udało się zapisać zmian. Spróbuj ponownie.'
}

function EditProfileDialog({
  user,
  onClose,
  onUpdated,
}: EditProfileDialogProps) {
  const updateMutation = useUpdateProfileMutation()
  const isSavingRef = useRef(false)
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<EditProfileFormValues>({
    resolver: zodResolver(editProfileSchema),
    defaultValues: {
      display_name: user.display_name,
      avatar_url: user.avatar_url ?? '',
    },
  })
  const isPending = updateMutation.isPending || isSubmitting

  function handleDialogClose() {
    if (!isPending) {
      onClose()
    }
  }

  async function handleUpdate(values: EditProfileFormValues) {
    if (isSavingRef.current) {
      return
    }

    const avatarUrl = values.avatar_url.trim()
    const payload: UpdateUserProfilePayload = {
      display_name: values.display_name.trim(),
      avatar_url: avatarUrl === '' ? null : avatarUrl,
    }

    isSavingRef.current = true

    try {
      await updateMutation.mutateAsync(payload)
      onUpdated()
    } catch {
      return
    } finally {
      isSavingRef.current = false
    }
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    void handleSubmit(handleUpdate)(event)
  }

  return (
    <Dialog
      fullWidth
      maxWidth="sm"
      open
      aria-labelledby="edit-profile-dialog-title"
      onClose={handleDialogClose}
    >
      <DialogTitle id="edit-profile-dialog-title">Edytuj profil</DialogTitle>
      <DialogContent>
        <form
          id="edit-profile-form"
          className="edit-profile-dialog__form"
          onSubmit={handleFormSubmit}
          noValidate
        >
          {updateMutation.isError && (
            <Alert severity="error">
              {getUpdateProfileErrorMessage(updateMutation.error)}
            </Alert>
          )}

          <TextField
            autoFocus
            fullWidth
            label="Nazwa użytkownika"
            disabled={isPending}
            error={Boolean(errors.display_name)}
            helperText={errors.display_name?.message}
            {...register('display_name')}
          />

          <TextField
            fullWidth
            label="URL avatara"
            disabled={isPending}
            error={Boolean(errors.avatar_url)}
            helperText={errors.avatar_url?.message}
            {...register('avatar_url')}
          />
        </form>
      </DialogContent>
      <DialogActions className="edit-profile-dialog__actions">
        <Button disabled={isPending} onClick={handleDialogClose}>
          Anuluj
        </Button>
        <Button
          form="edit-profile-form"
          type="submit"
          variant="contained"
          disabled={isPending}
        >
          {isPending ? 'Zapisywanie...' : 'Zapisz zmiany'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default EditProfileDialog
