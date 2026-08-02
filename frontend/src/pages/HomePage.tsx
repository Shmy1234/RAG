// Loaded only on the landing route, so the workspace bundle never pays for the
// display face or the scroll animation runtime.
import '@fontsource-variable/geist-mono/index.css'

import { EvidenceCanvas } from '@/components/home/EvidenceCanvas'
import { Faq } from '@/components/home/Faq'
import { Hero } from '@/components/home/Hero'
import { QuietBand } from '@/components/home/QuietBand'
import { SiteFooter } from '@/components/home/SiteFooter'

export function HomePage() {
  return (
    <main className="min-h-svh bg-background">
      <Hero />
      <EvidenceCanvas />
      <QuietBand />
      <Faq />
      <SiteFooter />
    </main>
  )
}
