import type { PropsWithChildren } from 'react'

type CardProps = PropsWithChildren<{
  title: string
  subtitle?: string
}>

export function Card({ title, subtitle, children }: CardProps) {
  return (
    <section className="ui-card">
      <header className="ui-card__header">
        <h2 className="ui-card__title">{title}</h2>
        {subtitle ? <p className="ui-card__subtitle">{subtitle}</p> : null}
      </header>
      <div className="ui-card__body">{children}</div>
    </section>
  )
}
