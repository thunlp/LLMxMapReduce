"use client"

import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Download, FileText } from "lucide-react"

export default function PurchasesPage() {
  // Mock purchase data
  const purchases = [
    {
      id: "INV-001",
      date: "2024-05-15",
      amount: "¥99.00",
      status: "已完成",
      description: "高级会员月度订阅",
      type: "subscription",
    },
    {
      id: "INV-002",
      date: "2024-04-15",
      amount: "¥99.00",
      status: "已完成",
      description: "高级会员月度订阅",
      type: "subscription",
    },
    {
      id: "INV-003",
      date: "2024-03-15",
      amount: "¥99.00",
      status: "已完成",
      description: "高级会员月度订阅",
      type: "subscription",
    },
    {
      id: "INV-004",
      date: "2024-05-10",
      amount: "¥50.00",
      status: "已完成",
      description: "10次使用次数充值包",
      type: "one-time",
    },
    {
      id: "INV-005",
      date: "2024-04-05",
      amount: "¥20.00",
      status: "已完成",
      description: "3次使用次数充值包",
      type: "one-time",
    },
  ]

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 py-8">
        <div className="container max-w-4xl mx-auto px-4">
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">购买记录</h1>
              <p className="text-muted-foreground">查看您的所有交易记录</p>
            </div>
            <Separator />

            <div className="grid gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">当前订阅</h2>
                  <p className="text-sm text-muted-foreground">您当前的订阅计划</p>
                </div>
                <Button>管理订阅</Button>
              </div>

              <Card>
                <CardContent className="p-6">
                  <div className="flex flex-col md:flex-row justify-between gap-4">
                    <div>
                      <h3 className="font-semibold text-lg">高级会员</h3>
                      <p className="text-muted-foreground">每月 ¥99.00</p>
                      <Badge className="mt-2">活跃</Badge>
                    </div>
                    <div className="text-right">
                      <p className="text-sm">下次扣款日期</p>
                      <p className="font-medium">2024年6月15日</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="mt-8">
                <h2 className="text-xl font-semibold mb-4">交易历史</h2>
                <div className="space-y-4">
                  {purchases.map((purchase) => (
                    <Card key={purchase.id}>
                      <CardContent className="p-6">
                        <div className="flex flex-col md:flex-row justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                              <p className="font-medium">{purchase.description}</p>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">订单号: {purchase.id}</p>
                            <p className="text-sm text-muted-foreground">{purchase.date}</p>
                          </div>
                          <div className="flex flex-col md:items-end gap-2">
                            <p className="font-semibold">{purchase.amount}</p>
                            <Badge variant="outline">{purchase.status}</Badge>
                            <Button variant="outline" size="sm" className="mt-2">
                              <Download className="h-4 w-4 mr-2" />
                              下载发票
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
