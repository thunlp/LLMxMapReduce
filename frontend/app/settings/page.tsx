"use client"

import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
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
import { Loader2, Gift, CreditCard, Sparkles } from "lucide-react"
import { getUserInfo, redeemCode } from "@/lib/api"
import { toast } from "sonner"

export default function SettingsPage() {
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState("profile")
  const [phoneNumber, setPhoneNumber] = useState("")
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [redeemCodeInput, setRedeemCodeInput] = useState("")
  const [currentCredits, setCurrentCredits] = useState(0)
  const [isRedeeming, setIsRedeeming] = useState(false)
  const [isLoadingUserInfo, setIsLoadingUserInfo] = useState(true)
  const [notifications, setNotifications] = useState({
    email: false,
    sms: true,
    browser: true,
  })
  const { theme, setTheme } = useTheme()


  // 兑换码套餐配置
  const codePackages = [
    {
      id: "basic",
      name: "基础包",
      credits: 10,
      price: 29.9,
      description: "适合偶尔使用的用户",
      popular: false,
    },
    {
      id: "standard",
      name: "标准包",
      credits: 30,
      price: 79.9,
      description: "最受欢迎的选择",
      popular: true,
      originalPrice: 89.7,
    },
    {
      id: "premium",
      name: "高级包",
      credits: 100,
      price: 199.9,
      description: "重度使用用户的最佳选择",
      popular: false,
      originalPrice: 299,
    },
  ]

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab && ['profile', 'appearance', 'notifications', 'subscription'].includes(tab)) {
      setActiveTab(tab)
    }
  }, [searchParams])

  // 获取用户信息
  useEffect(() => {
    async function fetchUserInfo() {
      try {
        const token = localStorage.getItem('token')
        if (!token) {
          return
        }

        const response = await getUserInfo(token)
        if (response.success) {
          setCurrentCredits(response.data.remaining_uses)
          setPhoneNumber(response.data.phone)
        }
      } catch (error) {
        console.error('获取用户信息失败:', error)
      } finally {
        setIsLoadingUserInfo(false)
      }
    }

    fetchUserInfo()
  }, [])

  const handleSaveProfile = () => {
    // Here you would implement the profile update logic
    toast.success("个人资料已更新")
  }

  const handleSaveNotifications = () => {
    // Here you would implement the notification settings update logic
    toast.success("通知设置已更新")
  }

  const handleRedeemCode = async () => {
    if (!redeemCodeInput.trim()) {
      toast.error("请输入兑换码")
      return
    }

    const token = localStorage.getItem('token')
    if (!token) {
      toast.error("请先登录")
      return
    }

    setIsRedeeming(true)
    
    try {
      const response = await redeemCode(token, redeemCodeInput.trim())
      
      if (response.success) {
        toast.success("兑换成功", {
          description: `获得 ${response.data.added_uses} 次使用次数`,
        })
        
        // 更新当前次数
        setCurrentCredits(response.data.remaining_uses)
        
        // 清空输入框
        setRedeemCodeInput("")
      } else {
        // 根据后端返回的错误信息给出具体提示
        const errorMessage = response.message || "兑换失败"
        toast.error("兑换失败", {
          description: errorMessage,
        })
      }
    } catch (error) {
      // 处理网络错误或其他异常
      let errorMessage = "网络错误，请稍后重试"
      
      if (error instanceof Error) {
        // 如果是后端返回的具体错误信息，直接显示
        errorMessage = error.message
        
        // 针对常见错误给出更友好的提示
        if (error.message.includes("已被使用") || error.message.includes("已使用")) {
          errorMessage = "该兑换码已被使用，请检查兑换码是否正确"
        } else if (error.message.includes("无效") || error.message.includes("不存在")) {
          errorMessage = "兑换码无效，请检查兑换码是否正确"
        } else if (error.message.includes("过期")) {
          errorMessage = "兑换码已过期，请联系客服获取新的兑换码"
        }
      }
      
      toast.error("兑换失败", {
        description: errorMessage,
      })
    } finally {
      setIsRedeeming(false)
    }
  }

  const handlePurchaseCode = (packageId: string) => {
    // 这里未来会实现购买兑换码的逻辑
    const selectedPackage = codePackages.find(pkg => pkg.id === packageId)
    toast.info("功能开发中", {
      description: `${selectedPackage?.name} 购买功能即将上线`,
    })
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
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
              <TabsList>
                <TabsTrigger value="profile">个人资料</TabsTrigger>
                <TabsTrigger value="appearance">外观</TabsTrigger>
                <TabsTrigger value="notifications">通知</TabsTrigger>
                <TabsTrigger value="subscription">购买与兑换</TabsTrigger>
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
                {/* 当前次数显示 */}
                <Card>
                  <CardHeader>
                    <CardTitle>当前账户状态</CardTitle>
                    <CardDescription>查看您的使用次数余额</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex justify-between items-center p-4 border rounded-lg">
                      <div>
                        <h3 className="font-medium">可用次数</h3>
                        <p className="text-sm text-muted-foreground">当前剩余使用次数</p>
                      </div>
                      <div className="text-right">
                        {isLoadingUserInfo ? (
                          <Loader2 className="h-6 w-6 animate-spin" />
                        ) : (
                          <Badge variant="secondary" className="text-lg px-3 py-1">
                            {currentCredits} 次
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* 购买兑换码套餐 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <CreditCard className="h-5 w-5" />
                      购买使用次数
                    </CardTitle>
                    <CardDescription>选择适合您的套餐，获得更多使用次数</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 md:grid-cols-3">
                      {codePackages.map((pkg) => (
                        <Card key={pkg.id} className={`relative ${pkg.popular ? 'border-primary shadow-md' : ''}`}>
                          {pkg.popular && (
                            <div className="absolute -top-2 left-1/2 transform -translate-x-1/2">
                              <Badge className="bg-primary text-primary-foreground flex items-center gap-1">
                                <Sparkles className="h-3 w-3" />
                                推荐
                              </Badge>
                            </div>
                          )}
                          <CardHeader className="text-center pb-4">
                            <CardTitle className="text-lg">{pkg.name}</CardTitle>
                            <div className="space-y-1">
                              <div className="text-3xl font-bold">¥{pkg.price}</div>
                              {pkg.originalPrice && (
                                <div className="text-sm text-muted-foreground line-through">
                                  原价 ¥{pkg.originalPrice}
                                </div>
                              )}
                            </div>
                          </CardHeader>
                          <CardContent className="text-center space-y-2">
                            <div className="text-2xl font-semibold text-primary">
                              {pkg.credits} 次
                            </div>
                            <p className="text-sm text-muted-foreground">{pkg.description}</p>
                            <div className="text-xs text-muted-foreground">
                              平均 ¥{(pkg.price / pkg.credits).toFixed(2)}/次
                            </div>
                          </CardContent>
                          <CardFooter>
                            <Button 
                              className="w-full" 
                              variant={pkg.popular ? "default" : "outline"}
                              onClick={() => handlePurchaseCode(pkg.id)}
                            >
                              立即购买
                            </Button>
                          </CardFooter>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* 兑换码输入 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Gift className="h-5 w-5" />
                      兑换码
                    </CardTitle>
                    <CardDescription>如果您有兑换码，可以在这里使用</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="redeem-code">输入兑换码</Label>
                      <div className="flex gap-2">
                        <Input
                          id="redeem-code"
                          placeholder="请输入兑换码"
                          value={redeemCodeInput}
                          onChange={(e) => setRedeemCodeInput(e.target.value)}
                          disabled={isRedeeming}
                        />
                        <Button onClick={handleRedeemCode} disabled={!redeemCodeInput || isRedeeming}>
                          {isRedeeming && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                          兑换
                        </Button>
                      </div>
                      <p className="text-sm text-muted-foreground">输入兑换码获取更多使用次数</p>
                    </div>
                  </CardContent>
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
