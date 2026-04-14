import { ReactNode } from 'react'
import Sidebar from '@/components/layout/sidebar'
import Navbar from '@/components/layout/navbar'
import AuthGuard from '@/components/auth/auth-guard'

export default function DashboardLayout({
  children,
}: {
  children: ReactNode
}) {
  return (
    <AuthGuard>
      <div className="flex h-screen bg-background">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Navbar />
          <main className="flex-1 overflow-auto">
            {children}
          </main>
        </div>
      </div>
    </AuthGuard>
  )
}
