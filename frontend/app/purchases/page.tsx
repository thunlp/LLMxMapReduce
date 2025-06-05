"use client"

import { useState, useEffect } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Gift, ShoppingBag, Loader2 } from "lucide-react"
import Link from "next/link"
import { redeemCode, getRedemptionHistory, getUserInfo } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

interface RedemptionRecord {
  id: number;
  code: string;
  uses_granted: number;
  redeemed_at: string;
}

export default function PurchasesPage() {
  const [currentCredits, setCurrentCredits] = useState(0)
  const [redemptionHistory, setRedemptionHistory] = useState<RedemptionRecord[]>([])
  const [redemptionCode, setRedemptionCode] = useState("")
  const [isRedeeming, setIsRedeeming] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const { toast } = useToast()

  // 获取用户信息和兑换历史
  useEffect(() => {
    async function fetchData() {
      try {
        const token = localStorage.getItem('token')
        if (!token) {
          return
        }

        // 并行获取用户信息和兑换历史
        const [userInfoResponse, historyResponse] = await Promise.all([
          getUserInfo(token),
          getRedemptionHistory(token)
        ])

        if (userInfoResponse.success) {
          setCurrentCredits(userInfoResponse.data.remaining_uses)
        }

        if (historyResponse.success) {
          setRedemptionHistory(historyResponse.data.history)
        }
      } catch (error) {
        console.error('获取数据失败:', error)
        toast({
          title: "获取数据失败",
          description: error instanceof Error ? error.message : "请刷新页面重试",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [toast])

  // 处理兑换码提交
  const handleRedeemCode = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!redemptionCode.trim()) {
      toast({
        title: "请输入兑换码",
        variant: "destructive",
      })
      return
    }

    const token = localStorage.getItem('token')
    if (!token) {
      toast({
        title: "请先登录",
        variant: "destructive",
      })
      return
    }

    setIsRedeeming(true)
    
    try {
      const response = await redeemCode(token, redemptionCode.trim())
      
      if (response.success) {
        toast({
          title: "兑换成功",
          description: `获得 ${response.data.added_uses} 次使用次数`,
        })
        
        // 更新当前次数
        setCurrentCredits(response.data.remaining_uses)
        
        // 刷新兑换历史
        const historyResponse = await getRedemptionHistory(token)
        if (historyResponse.success) {
          setRedemptionHistory(historyResponse.data.history)
        }
        
        // 清空输入框
        setRedemptionCode("")
      } else {
        toast({
          title: "兑换失败",
          description: response.message,
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "兑换失败",
        description: error instanceof Error ? error.message : "请稍后重试",
        variant: "destructive",
      })
    } finally {
      setIsRedeeming(false)
    }
  }

  // 格式化日期
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN')
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 py-8">
          <div className="container max-w-4xl mx-auto px-4">
            <div className="flex items-center justify-center min-h-[400px]">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 py-8">
        <div className="container max-w-4xl mx-auto px-4">
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">使用次数管理</h1>
              <p className="text-muted-foreground">管理您的使用次数和查看兑换历史</p>
            </div>
            <Separator />

            <Card>
              <CardHeader>
                <CardTitle>当前可用次数</CardTitle>
              </CardHeader>
              <CardContent className="flex items-center justify-between">
                <div className="text-4xl font-bold">{currentCredits} 次</div>
                <Link href="/settings?tab=subscription">
                  <Button>获取更多次数</Button>
                </Link>
              </CardContent>
            </Card>

            {/* 兑换码输入区域 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gift className="h-5 w-5" />
                  兑换码
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleRedeemCode} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="redemption-code">输入兑换码</Label>
                    <div className="flex gap-2">
                      <Input
                        id="redemption-code"
                        type="text"
                        placeholder="请输入兑换码"
                        value={redemptionCode}
                        onChange={(e) => setRedemptionCode(e.target.value)}
                        disabled={isRedeeming}
                        className="flex-1"
                      />
                      <Button type="submit" disabled={isRedeeming}>
                        {isRedeeming && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                        兑换
                      </Button>
                    </div>
                  </div>
                </form>
              </CardContent>
            </Card>

            <div className="mt-8">
              <h2 className="text-xl font-semibold mb-4">兑换历史</h2>
              {redemptionHistory.length > 0 ? (
                <div className="space-y-4">
                  {redemptionHistory.map((record) => (
                    <Card key={record.id}>
                      <CardContent className="p-6">
                        <div className="flex flex-col md:flex-row justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-1">
                              <Gift className="h-5 w-5 text-primary" />
                              <p className="font-medium text-lg">兑换码使用</p>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              兑换码: {record.code}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              日期: {formatDate(record.redeemed_at)}
                            </p>
                          </div>
                          <div className="flex flex-col md:items-end gap-2">
                            <p className="font-semibold text-lg text-green-600 dark:text-green-500">
                              +{record.uses_granted} 次
                            </p>
                            <Badge variant="default">
                              已兑换
                            </Badge>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <Card>
                  <CardContent className="p-6 text-center text-muted-foreground">
                    <Gift className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>暂无兑换记录</p>
                    <p className="text-sm mt-1">使用兑换码获取更多使用次数</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
