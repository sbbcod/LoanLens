import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { Spinner } from './ui'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

/** Shows one page at a time. `page` is controlled so clicking a field can jump here. */
export function PdfViewer({ url, page, onPageChange }: {
  url: string
  page: number
  onPageChange: (page: number) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  const [pages, setPages] = useState(0)

  useEffect(() => {
    if (!box.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    observer.observe(box.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-stone-100 px-3 py-2">
        <div className="flex items-center gap-1">
          <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}
                  className="rounded-md p-1.5 text-stone-500 hover:bg-stone-100 disabled:opacity-30" aria-label="Previous page">
            <ChevronLeft className="size-4" />
          </button>
          <span className="min-w-16 text-center text-xs tabular-nums text-stone-500">
            {pages ? `Page ${page} of ${pages}` : '…'}
          </span>
          <button disabled={!pages || page >= pages} onClick={() => onPageChange(page + 1)}
                  className="rounded-md p-1.5 text-stone-500 hover:bg-stone-100 disabled:opacity-30" aria-label="Next page">
            <ChevronRight className="size-4" />
          </button>
        </div>
        <a href={url} target="_blank" rel="noreferrer"
           className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-stone-500 hover:bg-stone-100 hover:text-stone-900">
          Original <ExternalLink className="size-3" />
        </a>
      </div>
      <div ref={box} className="min-h-0 flex-1 overflow-auto bg-stone-100/70 p-4">
        <Document file={url} onLoadSuccess={({ numPages }) => setPages(numPages)}
                  loading={<div className="flex justify-center py-24"><Spinner /></div>}
                  error={<p className="py-24 text-center text-sm text-stone-500">Couldn't load the PDF.</p>}>
          <Page pageNumber={Math.min(page, pages || 1)} width={Math.max(width - 32, 200)}
                renderTextLayer={false} renderAnnotationLayer={false}
                className="overflow-hidden rounded-sm shadow-sm ring-1 ring-stone-900/5" />
        </Document>
      </div>
    </div>
  )
}
