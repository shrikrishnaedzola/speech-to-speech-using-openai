// Shared column wrapper. On desktop each column scrolls on its own.
export default function Panel({ title, children, actions }) {
  return (
    <section className="flex flex-col rounded-lg bg-white shadow-sm lg:h-[calc(100vh-4.5rem)]">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="font-semibold text-slate-800">{title}</h2>
        {actions}
      </header>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">{children}</div>
    </section>
  )
}
