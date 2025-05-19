"use client"

import type React from "react"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"

export default function LoginPage() {
  const [phoneNumber, setPhoneNumber] = useState("")
  const [verificationCode, setVerificationCode] = useState("")
  const [isCodeSent, setIsCodeSent] = useState(false)
  const [countdown, setCountdown] = useState(60)
  const router = useRouter()

  const handleSendCode = () => {
    // Here you would implement the actual code sending logic
    setIsCodeSent(true)

    // Start countdown
    let timer = countdown
    const interval = setInterval(() => {
      timer -= 1
      setCountdown(timer)

      if (timer <= 0) {
        clearInterval(interval)
        setIsCodeSent(false)
        setCountdown(60)
      }
    }, 1000)
  }

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    // Here you would implement the actual login logic
    router.push("/dashboard")
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header showUserNav={false} />
      <div className="flex-1 flex items-center justify-center py-12 px-4">
        <div className="mx-auto w-full max-w-md">
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">登录账户</h1>
            <p className="text-sm text-muted-foreground">输入您的手机号码接收验证码登录</p>
          </div>
          <div className="grid gap-6 mt-6">
            <form onSubmit={handleLogin}>
              <div className="grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="phone">手机号码</Label>
                  <div className="flex gap-2">
                    <Input
                      id="phone"
                      type="tel"
                      placeholder="请输入手机号码"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      required
                    />
                    <Button
                      type="button"
                      onClick={handleSendCode}
                      disabled={isCodeSent || !phoneNumber || phoneNumber.length !== 11}
                    >
                      {isCodeSent ? `${countdown}秒` : "发送验证码"}
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="code">验证码</Label>
                  <Input
                    id="code"
                    type="text"
                    placeholder="请输入验证码"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full">
                  登录
                </Button>
              </div>
            </form>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">或者</span>
              </div>
            </div>
            <div className="text-center text-sm">
              还没有账户?{" "}
              <Link href="/register" className="underline underline-offset-4 hover:text-primary">
                立即注册
              </Link>
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  )
}
