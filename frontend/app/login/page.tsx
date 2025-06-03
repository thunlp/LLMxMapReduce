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
import { sendVerificationCode, login } from "@/lib/api"
import { toast } from "sonner"

export default function LoginPage() {
  const [phoneNumber, setPhoneNumber] = useState("")
  const [verificationCode, setVerificationCode] = useState("")
  const [isCodeSent, setIsCodeSent] = useState(false)
  const [countdown, setCountdown] = useState(60)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoginLoading, setIsLoginLoading] = useState(false)
  const router = useRouter()

  const handleSendCode = async () => {
    if (!phoneNumber || phoneNumber.length !== 11) {
      toast.error("请输入正确的手机号码")
      return
    }

    setIsLoading(true)
    try {
      const response = await sendVerificationCode(phoneNumber)
      
      if (response.success) {
        toast.success(response.message)
        setIsCodeSent(true)
        
        // 开发环境下显示验证码
        if (response.data?.code) {
          toast.info(`开发环境验证码: ${response.data.code}`)
        }

        // 开始倒计时
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
      } else {
        toast.error(response.message || "发送验证码失败")
      }
    } catch (error) {
      toast.error("发送验证码失败，请稍后重试")
      console.error('发送验证码错误:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!phoneNumber || !verificationCode) {
      toast.error("请填写完整信息")
      return
    }

    setIsLoginLoading(true)
    try {
      const response = await login(phoneNumber, verificationCode)
      
      if (response.success && response.data) {
        toast.success(response.message || "登录成功")
        
        // 保存token到localStorage
        localStorage.setItem('token', response.data.token)
        localStorage.setItem('user', JSON.stringify(response.data.user))
        
        // 跳转到dashboard
        router.push("/dashboard")
      } else {
        toast.error(response.message || "登录/注册失败")
      }
    } catch (error) {
      toast.error("登录/注册失败，请检查验证码是否正确")
      console.error('登录/注册错误:', error)
    } finally {
      setIsLoginLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header showUserNav={false} />
      <div className="flex-1 flex items-center justify-center py-12 px-4">
        <div className="mx-auto w-full max-w-md">
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">登录 / 注册</h1>
            <p className="text-sm text-muted-foreground">输入您的手机号码接收验证码，新用户将自动创建账户</p>
          </div>
          <div className="grid gap-6 mt-6">
            <form onSubmit={handleSubmit}>
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
                      disabled={isCodeSent || !phoneNumber || phoneNumber.length !== 11 || isLoading}
                    >
                      {isLoading ? "发送中..." : isCodeSent ? `${countdown}秒` : "发送验证码"}
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
                <Button type="submit" className="w-full" disabled={isLoginLoading}>
                  {isLoginLoading ? "处理中..." : "登录 / 注册"}
                </Button>
              </div>
            </form>
            <div className="text-center text-sm text-muted-foreground">
              点击"登录 / 注册"即表示您同意我们的{" "}
              <Link href="#" className="underline underline-offset-4 hover:text-primary">
                服务条款
              </Link>{" "}
              和{" "}
              <Link href="#" className="underline underline-offset-4 hover:text-primary">
                隐私政策
              </Link>
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  )
}
