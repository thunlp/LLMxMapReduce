import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"
import { UserNav } from "@/components/user-nav"

interface HeaderProps {
  showUserNav?: boolean
}

export function Header({ showUserNav = true }: HeaderProps) {
  return (
    <header className="border-b">
      <div className="container flex h-16 items-center justify-between max-w-6xl mx-auto px-4">
        <Link href={showUserNav ? "/dashboard" : "/"} className="text-2xl font-bold">
          ResearchSynth
        </Link>
        <div className="flex items-center gap-4">
          <ThemeToggle />
          {showUserNav ? (
            <UserNav />
          ) : (
            <nav className="flex items-center gap-6">
              <Link href="/login" className="text-sm font-medium hover:underline">
                登录
              </Link>
              <Link href="/register" className="text-sm font-medium hover:underline">
                注册
              </Link>
            </nav>
          )}
        </div>
      </div>
    </header>
  )
}
