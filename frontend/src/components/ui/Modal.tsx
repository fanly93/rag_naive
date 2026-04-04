import type { PropsWithChildren } from 'react'

type ModalProps = PropsWithChildren<{
  open: boolean
  title: string
  description?: string
  onClose: () => void
}>

export function Modal({ open, title, description, onClose, children }: ModalProps) {
  if (!open) {
    return null
  }

  return (
    <div className="ui-modal-overlay" role="presentation" onClick={onClose}>
      <section
        className="ui-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="ui-modal__header">
          <h3 className="ui-modal__title">{title}</h3>
          {description ? <p className="ui-modal__description">{description}</p> : null}
        </header>
        <div className="ui-modal__body">{children}</div>
      </section>
    </div>
  )
}
