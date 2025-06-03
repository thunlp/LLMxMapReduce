"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Search, Send, Upload, Globe, ThumbsUp, MessageSquare, Clock, ChevronDown } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/contexts/auth-context"
import { submitTask } from "@/lib/api"
import { toast } from "sonner"

export default function DashboardPage() {
  const [topic, setTopic] = useState("")
  const [keywords, setKeywords] = useState("")
  const [language, setLanguage] = useState("zh")
  const [isGenerating, setIsGenerating] = useState(false)
  const { token, user } = useAuth()

  const handleGenerate = async () => {
    if (!token) {
      toast.error("请先登录", {
        description: "您需要登录后才能提交任务",
      })
      return
    }

    if (!topic) {
      toast.error("请输入文章标题", {
        description: "文章标题不能为空",
      })
      return
    }

    setIsGenerating(true)
    
    try {
      const response = await submitTask(token, topic, keywords || undefined)
      // 根据后端返回的success字段判断是否成功
      if (response.success) {
        toast.success("提交成功", {
          description: response.message || `任务ID: ${response.data.task_id}\n标题: ${response.data.unique_survey_title}`,
        })
      } else {
        toast.error("提交失败", {
          description: response.message || "任务提交失败",
        })
      }
      
      // 这里可以添加刷新历史记录的逻辑
      
    } catch (error: any) {
      toast.error("提交失败", {
        description: error.message || "网络错误或服务器异常",
      })
    } finally {
      setIsGenerating(false)
    }
  }

  // Mock history data
  const historyItems = [
    {
      id: "1",
      topic: "人工智能在医疗领域的应用",
      language: "zh",
      date: "2024-05-18",
      status: "completed",
      isPublic: true,
    },
    {
      id: "2",
      topic: "Blockchain Technology in Supply Chain Management",
      language: "en",
      date: "2024-05-15",
      status: "completed",
      isPublic: false,
    },
    {
      id: "3",
      topic: "可持续发展与环境保护",
      language: "zh",
      date: "2024-05-10",
      status: "completed",
      isPublic: true,
    },
  ]

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 py-8">
        <div className="container max-w-5xl mx-auto px-4">
          {/* Main Input Card */}
          <Card className="border border-gray-200 dark:border-gray-800 shadow-sm mb-8">
            <CardContent className="p-6">
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-medium">文章标题：</h3>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-muted-foreground">剩余次数：</span>
                      <Badge variant="outline">12</Badge>
                    </div>
                  </div>
                  <Input
                    id="topic"
                    placeholder="请输入论文主题，10-100个字符"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="text-base py-6"
                  />
                </div>

                <div className="space-y-2">
                  <h3 className="text-lg font-medium">检索关键词：</h3>
                  <Input
                    id="keywords"
                    placeholder="选填，明确标题意图用来辅助搜索"
                    value={keywords}
                    onChange={(e) => setKeywords(e.target.value)}
                    className="text-base py-5"
                  />
                </div>

                <div className="flex flex-wrap gap-3 mt-4">
                  <Button variant="outline" className="flex items-center gap-2">
                    <Upload className="h-4 w-4" />
                    上传文件
                  </Button>

                  <Button variant="outline" className="flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    Web检索
                  </Button>

                  <div className="ml-auto flex items-center gap-3">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" className="flex items-center gap-2">
                          {language === "zh" ? "简体中文" : "English"}
                          <ChevronDown className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setLanguage("zh")}>简体中文</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setLanguage("en")}>English</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>

                    <Button onClick={handleGenerate} disabled={!topic || isGenerating} className="px-8">
                      {isGenerating ? (
                        "生成中..."
                      ) : (
                        <div className="flex items-center gap-2">
                          <Send className="h-4 w-4" />
                          生成
                        </div>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* History Tabs */}
          <Tabs defaultValue="my-documents" className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <TabsList>
                <TabsTrigger value="public-documents" className="px-6">
                  公开文章
                </TabsTrigger>
                <TabsTrigger value="my-documents" className="px-6">
                  我的文章
                </TabsTrigger>
              </TabsList>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input placeholder="搜索文章标题或用户名" className="pl-10 w-[300px]" />
              </div>
            </div>

            <TabsContent value="public-documents">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {historyItems
                  .filter((item) => item.isPublic)
                  .map((item) => (
                    <HistoryCard key={item.id} item={item} />
                  ))}
              </div>
            </TabsContent>

            <TabsContent value="my-documents">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {historyItems.map((item) => (
                  <HistoryCard key={item.id} item={item} />
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>
      <Footer />
    </div>
  )
}

interface HistoryItemProps {
  item: {
    id: string
    topic: string
    language: string
    date: string
    status: string
    isPublic: boolean
  }
}

function HistoryCard({ item }: HistoryItemProps) {
  return (
    <Card className="overflow-hidden hover:shadow-md transition-shadow">
      <CardContent className="p-0">
        <div className="p-5 space-y-3">
          <div className="border-l-4 border-pink-400 pl-3 italic">
            <span className="text-xs text-pink-500">引用</span>
          </div>
          <h3 className="font-medium line-clamp-2">{item.topic}</h3>
          <p className="text-sm text-muted-foreground">
            {item.language === "zh" ? "NLP transformer deeplearning" : "NLP transformer deeplearning"}
          </p>

          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Button variant="ghost" size="sm" className="h-8 px-2">
              <Globe className="h-4 w-4 mr-1" />
              {item.language === "zh" ? "Arxiv检索" : "Arxiv Search"}
            </Button>

            <Button variant="ghost" size="sm" className="h-8 px-2">
              {item.language === "zh" ? "快速版" : "Quick Version"}
            </Button>
          </div>
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ThumbsUp className="h-4 w-4" />
            </Button>
            <span className="text-sm">0</span>

            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MessageSquare className="h-4 w-4" />
            </Button>
            <span className="text-sm">0</span>
          </div>

          <div className="flex items-center">
            <Clock className="h-4 w-4 mr-1 text-muted-foreground" />
            <Badge variant="outline">{item.isPublic ? "已公开" : "私有"}</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
