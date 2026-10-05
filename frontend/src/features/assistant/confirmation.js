// Only registration actions still expose a confirmation card.
export const isSupportedConfirmation = (confirmation) => (
  confirmation?.kind === 'registration_create' || confirmation?.kind === 'registration_cancel'
)
