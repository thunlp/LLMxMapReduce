import Link from "next/link"

export function Footer() {
  return (
    <footer className="border-t py-6">
      <div className="container flex flex-col items-center justify-between gap-4 md:h-16 md:flex-row max-w-6xl mx-auto px-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">© 2024 ResearchSynth. 保留所有权利。</p>
        <div className="flex gap-4">
          <Link href="#" className="text-sm text-gray-500 dark:text-gray-400 hover:underline">
            隐私政策
          </Link>
          <Link href="#" className="text-sm text-gray-500 dark:text-gray-400 hover:underline">
            服务条款
          </Link>
        </div>
      </div>
    </footer>
  )
}
