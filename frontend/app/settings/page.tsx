"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { useTheme } from "next-themes"
import { Badge } from "@/components/ui/badge"

export default function SettingsPage() {
  const [phoneNumber, setPhoneNumber] = useState("138****1234")
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [redeemCode, setRedeemCode] = useState("")
  const [notifications, setNotifications] = useState({
    email: false,
    sms: true,
    browser: true,
  })
  const { theme, setTheme } = useTheme()

  const handleSaveProfile = () => {
    // Here you would implement the profile update logic
    alert("个人资料已更新")
  }

  const handleSaveNotifications = () => {
    // Here you would implement the notification settings update logic
    alert("通知设置已更新")
  }

  const handleRedeem = () => {
    // Here you would implement the redemption logic
    setRedeemCode("")
    alert("兑换码已使用")
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 py-8">
        <div className="container max-w-4xl mx-auto px-4">
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">个人设置</h1>
              <p className="text-muted-foreground">管理您的账户设置和偏好</p>
            </div>
            <Separator />
            <Tabs defaultValue="profile" className="space-y-6">
              <TabsList>
                <TabsTrigger value="profile">个人资料</TabsTrigger>
                <TabsTrigger value="appearance">外观</TabsTrigger>
                <TabsTrigger value="notifications">通知</TabsTrigger>
                <TabsTrigger value="subscription">订阅与兑换</TabsTrigger>
              </TabsList>
              <TabsContent value="profile" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>个人资料</CardTitle>
                    <CardDescription>更新您的个人信息</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">姓名</Label>
                      <Input
                        id="name"
                        placeholder="请输入您的姓名"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="phone">手机号码</Label>
                      <Input id="phone" type="tel" value={phoneNumber} disabled />
                      <p className="text-sm text-muted-foreground">手机号码为登录凭证，无法修改</p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">电子邮箱</Label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="请输入您的电子邮箱"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                      />
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button onClick={handleSaveProfile}>保存更改</Button>
                  </CardFooter>
                </Card>
              </TabsContent>
              <TabsContent value="appearance" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>外观</CardTitle>
                    <CardDescription>自定义界面外观</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>主题</Label>
                      <RadioGroup value={theme} onValueChange={setTheme}>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="light" id="light" />
                          <Label htmlFor="light">浅色</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="dark" id="dark" />
                          <Label htmlFor="dark">深色</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="system" id="system" />
                          <Label htmlFor="system">跟随系统</Label>
                        </div>
                      </RadioGroup>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="notifications" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>通知设置</CardTitle>
                    <CardDescription>配置如何接收通知</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="email-notifications">电子邮件通知</Label>
                        <p className="text-sm text-muted-foreground">接收有关您的账户的电子邮件通知</p>
                      </div>
                      <Switch
                        id="email-notifications"
                        checked={notifications.email}
                        onCheckedChange={(checked) => setNotifications({ ...notifications, email: checked })}
                      />
                    </div>
                    <Separator />
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="sms-notifications">短信通知</Label>
                        <p className="text-sm text-muted-foreground">接收有关您的账户的短信通知</p>
                      </div>
                      <Switch
                        id="sms-notifications"
                        checked={notifications.sms}
                        onCheckedChange={(checked) => setNotifications({ ...notifications, sms: checked })}
                      />
                    </div>
                    <Separator />
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="browser-notifications">浏览器通知</Label>
                        <p className="text-sm text-muted-foreground">接收浏览器推送通知</p>
                      </div>
                      <Switch
                        id="browser-notifications"
                        checked={notifications.browser}
                        onCheckedChange={(checked) => setNotifications({ ...notifications, browser: checked })}
                      />
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button onClick={handleSaveNotifications}>保存设置</Button>
                  </CardFooter>
                </Card>
              </TabsContent>
              <TabsContent value="subscription" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>订阅信息</CardTitle>
                    <CardDescription>查看您的订阅状态和剩余使用次数</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex justify-between items-center p-4 border rounded-lg">
                      <div>
                        <h3 className="font-medium">当前计划</h3>
                        <p className="text-sm text-muted-foreground">标准版</p>
                      </div>
                      <div className="text-right">
                        <h3 className="font-medium">剩余次数</h3>
                        <Badge className="ml-2">12</Badge>
                      </div>
                    </div>

                    <div className="space-y-2 mt-6">
                      <Label htmlFor="redeem-code">兑换码</Label>
                      <div className="flex gap-2">
                        <Input
                          id="redeem-code"
                          placeholder="请输入兑换码"
                          value={redeemCode}
                          onChange={(e) => setRedeemCode(e.target.value)}
                        />
                        <Button onClick={handleRedeem} disabled={!redeemCode}>
                          兑换
                        </Button>
                      </div>
                      <p className="text-sm text-muted-foreground">输入兑换码获取更多使用次数</p>
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button variant="outline">升级到高级版</Button>
                  </CardFooter>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
